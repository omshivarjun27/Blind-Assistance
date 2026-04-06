'use client';

import { Camera, Mic, Square } from 'lucide-react';

interface ControlBarProps {
  onStart: () => void;
  onStop: () => void;
  onCapture: () => void;
  status: string;
}

export function ControlBar({ onStart, onStop, onCapture, status }: ControlBarProps) {
  const isActive = status === 'listening' || status === 'thinking' || status === 'speaking';
  const isDisabled = status === 'connecting' || status === 'thinking';

  return (
    <div className="flex items-center gap-4">
      {!isActive ? (
        <button
          onClick={onStart}
          disabled={status === 'connecting'}
          className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700
                     disabled:opacity-50 disabled:cursor-not-allowed
                     text-white rounded-lg font-medium transition-colors"
        >
          <Mic size={18} />
          Start
        </button>
      ) : (
        <button
          onClick={onStop}
          className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700
                     text-white rounded-lg font-medium transition-colors"
        >
          <Square size={18} />
          Stop
        </button>
      )}

      <button
        onClick={onCapture}
        disabled={isDisabled}
        className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600
                   disabled:opacity-50 disabled:cursor-not-allowed
                   text-white rounded-lg font-medium transition-colors"
      >
        <Camera size={18} />
        Capture
      </button>
    </div>
  );
}
