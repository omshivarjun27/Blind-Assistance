/**
 * Ally Vision v2 — WebSocket client for /ws/realtime.
 * Binary messages = assistant PCM audio bytes.
 * Text messages   = JSON control: transcript / error / pong.
 */

export class RealtimeWSClient {
  private ws: WebSocket | null = null;
  private url: string;

  onAudio: ((pcm: ArrayBuffer) => void) | null = null;
  onTranscript: ((role: string, text: string) => void) | null = null;
  onError: ((msg: string) => void) | null = null;
  onConnected: (() => void) | null = null;
  onDisconnected: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url);
      this.ws.binaryType = 'arraybuffer';

      this.ws.onopen = () => {
        this.onConnected?.();
        resolve();
      };

      this.ws.onerror = () => {
        this.onError?.('WebSocket connection error');
        reject(new Error('WebSocket connection error'));
      };

      this.ws.onclose = () => {
        this.onDisconnected?.();
      };

      this.ws.onmessage = async (event) => {
        // Binary = assistant PCM audio
        if (event.data instanceof Blob) {
          const buffer = await event.data.arrayBuffer();
          this.onAudio?.(buffer);
          return;
        }
        if (event.data instanceof ArrayBuffer) {
          this.onAudio?.(event.data);
          return;
        }
        // Text = JSON control message
        try {
          const msg = JSON.parse(event.data as string);
          if (msg.type === 'transcript') {
            this.onTranscript?.(msg.role ?? 'assistant', msg.text ?? '');
          } else if (msg.type === 'error') {
            this.onError?.(msg.message ?? 'Unknown error');
          }
          // pong — no action needed
        } catch {
          console.warn('Unhandled WebSocket message:', event.data);
        }
      };
    });
  }

  sendAudio(pcm: ArrayBuffer): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(pcm);
    }
  }

  sendImage(base64Jpeg: string): void {
    this.ws?.send(JSON.stringify({ type: 'image', data: base64Jpeg }));
  }

  sendInstructions(text: string): void {
    this.ws?.send(JSON.stringify({ type: 'instructions', text }));
  }

  sendPing(): void {
    this.ws?.send(JSON.stringify({ type: 'ping' }));
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }
}
