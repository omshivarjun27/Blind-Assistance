'use client';

import { RefObject } from 'react';

interface CameraViewProps {
  videoRef: RefObject<HTMLVideoElement | null>;
  isEnabled: boolean;
}

export function CameraView({ videoRef, isEnabled }: CameraViewProps) {
  return (
    <div className="relative w-[640px] h-[480px] bg-gray-900 rounded-lg overflow-hidden border border-gray-700">
      {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className="w-full h-full object-cover"
      />
      {!isEnabled && (
        <div className="absolute inset-0 flex items-center justify-center text-gray-400 text-sm">
          Camera not enabled
        </div>
      )}
    </div>
  );
}
