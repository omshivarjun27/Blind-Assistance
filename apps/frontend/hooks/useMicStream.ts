'use client';

import { useRef, useState } from 'react';

/**
 * Ally Vision v2 — Microphone capture hook.
 * Uses AudioWorklet to produce raw Int16 PCM chunks.
 * DashScope expects: 16kHz 16-bit mono PCM.
 */
export function useMicStream() {
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  async function startListening(
    onChunk: (pcm: ArrayBuffer) => void
  ): Promise<void> {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      // Create AudioContext at 16kHz
      // UNCONFIRMED: browser may not honor 16kHz exactly
      const ctx = new AudioContext({ sampleRate: 16000 });
      audioCtxRef.current = ctx;

      // Fail fast if browser ignores requested sampleRate
      if (Math.abs(ctx.sampleRate - 16000) > 1000) {
        await ctx.close();
        stream.getTracks().forEach((t) => t.stop());
        const msg = `Browser AudioContext sampleRate is ${ctx.sampleRate}Hz, not 16000Hz. Cannot send correct PCM to DashScope.`;
        setError(msg);
        throw new Error(msg);
      }

      await ctx.audioWorklet.addModule('/worklets/mic-processor.js');
      const workletNode = new AudioWorkletNode(ctx, 'mic-processor');
      workletNodeRef.current = workletNode;

      workletNode.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
        onChunk(e.data);
      };

      const source = ctx.createMediaStreamSource(stream);
      sourceRef.current = source;
      source.connect(workletNode);
      // Do NOT connect workletNode to destination
      // (we only want PCM data, not speaker output of mic)

      setIsListening(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Microphone error';
      setError(msg);
      setIsListening(false);
      throw new Error(msg);
    }
  }

  function stopListening(): void {
    workletNodeRef.current?.disconnect();
    sourceRef.current?.disconnect();
    void audioCtxRef.current?.close();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    workletNodeRef.current = null;
    sourceRef.current = null;
    audioCtxRef.current = null;
    streamRef.current = null;
    setIsListening(false);
  }

  return { isListening, error, startListening, stopListening };
}
