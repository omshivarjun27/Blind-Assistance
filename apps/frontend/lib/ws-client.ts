/**
 * Ally Vision v2 — WebSocket client for /ws/realtime.
 * Binary messages = assistant PCM audio bytes.
 * Text messages   = JSON control: transcript / error / pong.
 */

export class RealtimeWSClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private manuallyClosed = false;
  private connectFactory: (() => void) | null = null;

  onAudio: ((pcm: ArrayBuffer) => void) | null = null;
  onTranscript: ((role: string, text: string, turnId?: string) => void) | null = null;
  onError: ((msg: string) => void) | null = null;
  onConnected: (() => void) | null = null;
  onDisconnected: (() => void) | null = null;
  onReconnecting: (() => void) | null = null;
  onTurnFailed: ((msg: string) => void) | null = null;

  constructor(url: string) {
    this.url = url;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      let settled = false;
      this.manuallyClosed = false;

      const openSocket = () => {
        const socket = new WebSocket(this.url);
        this.ws = socket;
        this.ws.binaryType = 'arraybuffer';

        socket.onopen = () => {
          this.clearReconnectTimer();
          this.onConnected?.();
          if (!settled) {
            settled = true;
            resolve();
          }
        };

        socket.onerror = () => {
          if (!settled) {
            settled = true;
            reject(new Error('WebSocket connection error'));
            return;
          }
          this.onError?.('WebSocket connection error');
        };

        socket.onclose = (event) => {
          this.ws = null;
          if (!settled) {
            settled = true;
            reject(new Error('WebSocket connection closed before opening'));
            return;
          }
          if (this.manuallyClosed || event.code === 1000) {
            this.onDisconnected?.();
            return;
          }
          this.onReconnecting?.();
          this.scheduleReconnect();
        };

        socket.onmessage = async (event) => {
          if (event.data instanceof Blob) {
            const buffer = await event.data.arrayBuffer();
            this.onAudio?.(buffer);
            return;
          }
          if (event.data instanceof ArrayBuffer) {
            this.onAudio?.(event.data);
            return;
          }
          try {
            const msg = JSON.parse(event.data as string);
            if (msg.type === 'ping' || msg.type === 'pong') {
              return;
            }
            if (msg.type === 'transcript') {
              this.onTranscript?.(msg.role ?? 'assistant', msg.text ?? '', msg.turn_id);
            } else if (msg.type === 'error') {
              this.onError?.(msg.message ?? 'Unknown error');
            } else if (msg.type === 'status' && msg.status === 'turn_failed') {
              this.onTurnFailed?.(msg.message ?? 'Voice turn failed — please try again');
            }
          } catch {
            console.warn('Unhandled WebSocket message:', event.data);
          }
        };
      };

      this.connectFactory = openSocket;
      openSocket();
    });
  }

  sendAudio(pcm: ArrayBuffer): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(pcm);
    }
  }

  sendImage(base64Jpeg: string): void {
    console.log('[WS] Sending image:', base64Jpeg.length, 'chars');
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'image', data: base64Jpeg }));
    }
  }

  sendInstructions(text: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'instructions', text }));
    }
  }

  sendPing(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'ping' }));
    }
  }

  sendInterrupt(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'interrupt' }));
    }
  }

  disconnect(): void {
    this.manuallyClosed = true;
    this.clearReconnectTimer();
    this.ws?.close();
    this.ws = null;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer || this.connectFactory === null) {
      return;
    }
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connectFactory?.();
    }, 2000);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
