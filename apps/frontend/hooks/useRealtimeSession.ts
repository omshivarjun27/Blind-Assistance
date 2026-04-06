'use client';

import { useCallback, useRef, useState } from 'react';

import { playPcmAudio, concatArrayBuffers, calcRms } from '@/lib/audio-utils';
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

export function useRealtimeSession(captureFrame: () => string | null) {
  const [status, setStatus] = useState<SessionStatus>('idle');
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<RealtimeWSClient | null>(null);
  const chunksRef = useRef<ArrayBuffer[]>([]);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isSpeakingRef = useRef(false);
  const mic = useMicStream();

  const appendTranscript = useCallback((entry: TranscriptEntry) => {
    setTranscript((prev) => [...prev.slice(-9), entry]);
  }, []);

  const flushTurn = useCallback(() => {
    if (chunksRef.current.length === 0) return;
    const pcm = concatArrayBuffers(chunksRef.current);
    chunksRef.current = [];
    setStatus('thinking');
    wsRef.current?.sendAudio(pcm);
  }, []);

  const onPcmChunk = useCallback(
    (chunk: ArrayBuffer) => {
      if (isSpeakingRef.current) return; // don't capture while assistant speaks

      chunksRef.current.push(chunk);

      // Silence detection
      const rms = calcRms(chunk);
      if (rms < SILENCE_THRESHOLD) {
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
        // Voice detected — cancel silence timer
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
      }
    },
    [flushTurn]
  );

  async function startSession(): Promise<void> {
    setError(null);
    setStatus('connecting');

    try {
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://127.0.0.1:8000/ws/realtime';

      const ws = new RealtimeWSClient(wsUrl);
      wsRef.current = ws;

      ws.onAudio = async (pcm) => {
        isSpeakingRef.current = true;
        setStatus('speaking');
        await playPcmAudio(pcm);
        isSpeakingRef.current = false;
        setStatus('listening');
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
    mic.stopListening();
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
