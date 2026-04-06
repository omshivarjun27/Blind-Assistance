'use client';

import { useRef, useState } from 'react';

/**
 * Ally Vision v2 — Camera capture hook.
 * Attaches getUserMedia video to a <video> element.
 * captureFrame() draws current video frame to canvas → JPEG base64.
 */
export function useCameraCapture() {
  const [isEnabled, setIsEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  async function enableCamera(): Promise<void> {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setIsEnabled(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Camera error';
      setError(msg);
    }
  }

  function captureFrame(): string | null {
    if (!isEnabled || !videoRef.current) return null;
    const video = videoRef.current;
    if (video.videoWidth === 0) return null;

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    // Use requestVideoFrameCallback if available for fresher frame
    // Feature detect — not all browsers support it
    ctx.drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
    // Strip the data URL prefix, return only base64
    return dataUrl.replace('data:image/jpeg;base64,', '');
  }

  function disableCamera(): void {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    streamRef.current = null;
    setIsEnabled(false);
  }

  return { isEnabled, error, videoRef, enableCamera, captureFrame, disableCamera };
}
