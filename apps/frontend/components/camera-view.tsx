'use client';

import { RefObject } from 'react';

interface CameraViewProps {
  videoRef: RefObject<HTMLVideoElement | null>;
  isEnabled: boolean;
}

export function CameraView({ videoRef, isEnabled }: CameraViewProps) {
  return (
    <div className="relative w-full aspect-video max-w-4xl mx-auto rounded-2xl overflow-hidden bg-zinc-900">
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className="w-full h-full object-cover"
      />
      {!isEnabled && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-zinc-500 text-sm">Camera not enabled</p>
        </div>
      )}
    </div>
  );
}
