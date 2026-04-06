'use client';

import { Camera, Mic, X } from 'lucide-react';

interface ControlBarProps {
  onStart: () => void;
  onStop: () => void;
  onCapture: () => void;
  status: string;
}

export function ControlBar({ onStart, onStop, onCapture, status }: ControlBarProps) {
  const isActive = ['listening', 'thinking', 'speaking'].includes(status);
  const isDisabled = ['connecting', 'thinking'].includes(status);

  return (
    <div className="flex items-center justify-center gap-6 py-4">
      {isActive ? (
        <button
          onClick={onStop}
          className="w-12 h-12 rounded-full bg-zinc-800 hover:bg-zinc-700 flex items-center justify-center transition-colors"
          aria-label="Stop"
        >
          <X size={20} className="text-zinc-300" />
        </button>
      ) : (
        <div className="w-12 h-12" />
      )}

      <button
        onClick={isActive ? onStop : onStart}
        disabled={isDisabled}
        className="w-16 h-16 rounded-full bg-white hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors shadow-lg"
        aria-label={isActive ? 'Stop' : 'Start'}
      >
        <Mic size={24} className="text-black" />
      </button>

      <button
        onClick={onCapture}
        disabled={isDisabled}
        className="w-12 h-12 rounded-full bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
        aria-label="Capture frame"
      >
        <Camera size={18} className="text-zinc-300" />
      </button>
    </div>
  );
}
