'use client';

import { useCallback, useRef, useState } from 'react';

import { concatArrayBuffers, calcRms } from '@/lib/audio-utils';
import { RealtimeWSClient } from '@/lib/ws-client';
import { useMicStream } from '@/hooks/useMicStream';

export type SessionStatus =
  | 'idle'
  | 'connecting'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'error';

export interface TranscriptEntry {
  role: 'user' | 'assistant';
  text: string;
}

/**
 * Ally Vision v2 — Main realtime session hook.
 *
 * Turn detection: simple RMS silence timeout.
 * If RMS < SILENCE_THRESHOLD for SILENCE_TIMEOUT_MS:
 *   flush accumulated PCM chunks as one binary turn.
 *
 * Backend contract: one binary WebSocket frame = one full user turn.
 * Do NOT send every 3200-byte worklet chunk directly.
 */

const SILENCE_THRESHOLD = 0.01;   // RMS below this = silent
const SILENCE_TIMEOUT_MS = 1500;  // ms of silence before flushing turn
const PLAYBACK_INTERRUPT_ARM_MS = 1500;
const PLAYBACK_BARGE_IN_CHUNKS = 3;
const PLAYBACK_COOLDOWN_MS = 500;

let _audioCtx: AudioContext | null = null;
let _nextPlayTime = 0;
let _currentSource: AudioBufferSourceNode | null = null;
let _scheduledSources: AudioBufferSourceNode[] = [];

function _getAudioCtx(): AudioContext {
  if (!_audioCtx || _audioCtx.state === 'closed') {
    _audioCtx = new AudioContext({ sampleRate: 24000 });
  }
  if (_audioCtx.state === 'suspended') {
    void _audioCtx.resume();
  }
  return _audioCtx;
}

function _playPCMChunk(buffer: ArrayBuffer): AudioBufferSourceNode {
  const ctx = _getAudioCtx();
  const int16 = new Int16Array(buffer);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 32768.0;
  }
  const audioBuffer = ctx.createBuffer(1, float32.length, 24000);
  audioBuffer.copyToChannel(float32, 0);
  const source = ctx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(ctx.destination);
  const startAt = Math.max(_nextPlayTime, ctx.currentTime + 0.005);
  source.start(startAt);
  _nextPlayTime = startAt + audioBuffer.duration;
  _currentSource = source;
  _scheduledSources.push(source);
  return source;
}

function _stopPlayback(): void {
  for (const source of _scheduledSources) {
    try {
      source.stop(0);
    } catch {}
    try {
      source.disconnect();
    } catch {}
  }
  _scheduledSources = [];
  _currentSource = null;
  _nextPlayTime = 0;
}

export function useRealtimeSession(captureFrame: () => string | null) {
  const [status, setStatus] = useState<SessionStatus>('idle');
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<RealtimeWSClient | null>(null);
  const captureFrameRef = useRef<(() => string | null) | null>(null);
  const chunksRef = useRef<ArrayBuffer[]>([]);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const playbackEndTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isSpeakingRef = useRef(false);
  const isPlayingRef = useRef(false);
  const isSendingRef = useRef(false);
  const hasSpeechRef = useRef(false);
  const interruptArmedAtRef = useRef(0);
  const micCooldownUntilRef = useRef(0);
  const playbackSpeechChunksRef = useRef(0);
  const responseCancelledRef = useRef(false);
  const mic = useMicStream();

  const appendTranscript = useCallback((entry: TranscriptEntry) => {
    setTranscript((prev) => [...prev, entry]);
  }, []);

  const flushTurn = useCallback(() => {
    if (isSendingRef.current) return;
    if (isPlayingRef.current) return;
    if (chunksRef.current.length === 0) return;
    isSendingRef.current = true;
    hasSpeechRef.current = false;
    responseCancelledRef.current = false;

    const frame = captureFrameRef.current?.();
    console.log('[Session] Frame captured:', frame ? frame.length : 'none');
    if (frame) {
      wsRef.current?.sendImage(frame);
    }

    const pcm = concatArrayBuffers(chunksRef.current);
    chunksRef.current = [];
    setStatus('thinking');
    wsRef.current?.sendAudio(pcm);
  }, []);

  function chunkHasSpeechEnergy(pcmInt16Buffer: ArrayBuffer): boolean {
    const pcmInt16 = new Int16Array(pcmInt16Buffer);
    let sum = 0;
    for (let i = 0; i < pcmInt16.length; i++) {
      sum += pcmInt16[i] * pcmInt16[i];
    }
    const rms = Math.sqrt(sum / pcmInt16.length);
    return rms > 500;
  }

  const stopAssistantPlayback = useCallback(() => {
    if (playbackEndTimerRef.current) {
      clearTimeout(playbackEndTimerRef.current);
      playbackEndTimerRef.current = null;
    }
    _stopPlayback();
    interruptArmedAtRef.current = 0;
    playbackSpeechChunksRef.current = 0;
    micCooldownUntilRef.current = 0;
    isPlayingRef.current = false;
    isSpeakingRef.current = false;
  }, []);

  const playPCMChunk = useCallback(
    (pcmBytes: ArrayBuffer): void => {
      if (responseCancelledRef.current) {
        return;
      }

      if (!isPlayingRef.current) {
        if (playbackEndTimerRef.current) {
          clearTimeout(playbackEndTimerRef.current);
          playbackEndTimerRef.current = null;
        }
        _nextPlayTime = 0;
        isPlayingRef.current = true;
        interruptArmedAtRef.current = performance.now() + PLAYBACK_INTERRUPT_ARM_MS;
        playbackSpeechChunksRef.current = 0;
        micCooldownUntilRef.current = 0;
      }

      const source = _playPCMChunk(pcmBytes);
      isSpeakingRef.current = true;
      setStatus('speaking');

      source.onended = () => {
        _scheduledSources = _scheduledSources.filter((item) => item !== source);
        if (_currentSource === source) {
          _currentSource = _scheduledSources[_scheduledSources.length - 1] ?? null;
        }
        if (_scheduledSources.length === 0) {
          micCooldownUntilRef.current = performance.now() + PLAYBACK_COOLDOWN_MS;
          playbackEndTimerRef.current = setTimeout(() => {
            playbackEndTimerRef.current = null;
            _nextPlayTime = 0;
            const newFrame = captureFrameRef.current?.();
            if (newFrame) {
              wsRef.current?.sendImage(newFrame);
            }
            isPlayingRef.current = false;
            isSpeakingRef.current = false;
            isSendingRef.current = false;
            playbackSpeechChunksRef.current = 0;
            setStatus('listening');
          }, PLAYBACK_COOLDOWN_MS);
        }
      };
    },
    []
  );

  const onPcmChunk = useCallback(
    (chunk: ArrayBuffer) => {
      const hasSpeechEnergy = chunkHasSpeechEnergy(chunk);
      const now = performance.now();

      if (isPlayingRef.current) {
        if (now < interruptArmedAtRef.current || now < micCooldownUntilRef.current) {
          playbackSpeechChunksRef.current = 0;
          return;
        }

        if (hasSpeechEnergy) {
          playbackSpeechChunksRef.current += 1;
          if (playbackSpeechChunksRef.current >= PLAYBACK_BARGE_IN_CHUNKS) {
            responseCancelledRef.current = true;
            wsRef.current?.sendInterrupt();
            stopAssistantPlayback();
            isSendingRef.current = false;
          }
        } else {
          playbackSpeechChunksRef.current = 0;
        }

        if (isPlayingRef.current) {
          return;
        }
      }

      if (now < micCooldownUntilRef.current) {
        return;
      }

      if (isSendingRef.current && hasSpeechEnergy) {
        responseCancelledRef.current = true;
        wsRef.current?.sendInterrupt();
        isSendingRef.current = false;
      }
      if (isSendingRef.current) return;

      // Silence detection
      const rms = calcRms(chunk);
      if (rms < SILENCE_THRESHOLD) {
        if (!hasSpeechRef.current) return;
        chunksRef.current.push(chunk);
        // Start or reset silence timer
        if (!silenceTimerRef.current) {
          silenceTimerRef.current = setTimeout(() => {
            silenceTimerRef.current = null;
            if (chunksRef.current.length > 0) {
              flushTurn();
            }
          }, SILENCE_TIMEOUT_MS);
        }
      } else {
        hasSpeechRef.current = true;
        chunksRef.current.push(chunk);
        // Voice detected — cancel silence timer
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
      }
    },
    [flushTurn, stopAssistantPlayback]
  );

  async function startSession(): Promise<void> {
    setError(null);
    setStatus('connecting');

    try {
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://127.0.0.1:8000/ws/realtime';
      captureFrameRef.current = captureFrame;

      const ws = new RealtimeWSClient(wsUrl);
      wsRef.current = ws;
      responseCancelledRef.current = false;

      ws.onAudio = (pcm) => {
        playPCMChunk(pcm);
      };

      ws.onTranscript = (role, text) => {
        appendTranscript({ role: role as 'user' | 'assistant', text });
      };

      ws.onError = (msg) => {
        setError(msg);
        setStatus('error');
      };

      ws.onDisconnected = () => {
        setStatus('idle');
      };

      await ws.connect();
      await mic.startListening(onPcmChunk);
      setStatus('listening');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Session failed';
      setError(msg);
      setStatus('error');
      mic.stopListening();
      stopAssistantPlayback();
      void _audioCtx?.close();
      _audioCtx = null;
      _nextPlayTime = 0;
      _currentSource = null;
      _scheduledSources = [];
      wsRef.current?.disconnect();
      wsRef.current = null;
    }
  }

  function captureAndSend(): void {
    const frame = captureFrame();
    if (frame) {
      wsRef.current?.sendImage(frame);
    }
  }

  function stopSession(): void {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
      chunksRef.current = [];
      hasSpeechRef.current = false;
      isSendingRef.current = false;
      isPlayingRef.current = false;
      interruptArmedAtRef.current = 0;
      micCooldownUntilRef.current = 0;
      playbackSpeechChunksRef.current = 0;
      responseCancelledRef.current = false;
      if (playbackEndTimerRef.current) {
        clearTimeout(playbackEndTimerRef.current);
        playbackEndTimerRef.current = null;
      }
      captureFrameRef.current = null;
      mic.stopListening();
      stopAssistantPlayback();
      void _audioCtx?.close();
      _audioCtx = null;
      _nextPlayTime = 0;
      _currentSource = null;
      _scheduledSources = [];
      wsRef.current?.disconnect();
      wsRef.current = null;
      setStatus('idle');
  }

  return {
    status,
    transcript,
    error: error ?? mic.error,
    startSession,
    stopSession,
    captureAndSend,
  };
}
