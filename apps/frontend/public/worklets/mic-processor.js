/**
 * Ally Vision v2 — AudioWorklet microphone processor.
 * Runs off main thread. Accumulates 1600 mono Float32 samples
 * (= 100ms at 16kHz) then posts a 3200-byte Int16 PCM chunk.
 */
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = new Float32Array(1600);
    this._offset = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channel = input[0]; // Float32Array of 128 samples

    for (let i = 0; i < channel.length; i++) {
      this._buffer[this._offset++] = channel[i];

      if (this._offset === 1600) {
        // Convert Float32 → Int16 PCM
        const int16 = new Int16Array(1600);
        for (let j = 0; j < 1600; j++) {
          const s = Math.max(-1, Math.min(1, this._buffer[j]));
          int16[j] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        // Post 3200-byte buffer to main thread
        this.port.postMessage(int16.buffer, [int16.buffer]);
        this._offset = 0;
      }
    }
    return true; // keep processor alive
  }
}

registerProcessor('mic-processor', MicProcessor);
