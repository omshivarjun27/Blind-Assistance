/**
 * Ally Vision v2 — PCM audio utilities.
 * Do NOT use decodeAudioData for raw PCM fragments.
 * Create AudioContext lazily — never at import time.
 */

/**
 * Play raw Int16 PCM bytes at the given sample rate.
 * DashScope returns 24kHz 16-bit mono PCM.
 */
export async function playPcmAudio(
  pcmBytes: ArrayBuffer,
  sampleRate = 24000
): Promise<void> {
  const int16 = new Int16Array(pcmBytes);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 32768;
  }

  // Create context with requested sample rate
  // UNCONFIRMED: browser may internally resample — acceptable for MVP
  const ctx = new AudioContext({ sampleRate });
  const buffer = ctx.createBuffer(1, float32.length, sampleRate);
  buffer.copyToChannel(float32, 0);

  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(ctx.destination);
  source.start();

  return new Promise((resolve) => {
    source.onended = () => {
      void ctx.close();
      resolve();
    };
  });
}

/**
 * Concatenate multiple ArrayBuffer chunks into one.
 */
export function concatArrayBuffers(buffers: ArrayBuffer[]): ArrayBuffer {
  const total = buffers.reduce((sum, b) => sum + b.byteLength, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const buf of buffers) {
    result.set(new Uint8Array(buf), offset);
    offset += buf.byteLength;
  }
  return result.buffer;
}

/**
 * Calculate RMS of Int16 PCM chunk.
 * Used for simple silence detection.
 */
export function calcRms(chunk: ArrayBuffer): number {
  const int16 = new Int16Array(chunk);
  if (int16.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < int16.length; i++) {
    const s = int16[i] / 32768;
    sum += s * s;
  }
  return Math.sqrt(sum / int16.length);
}
