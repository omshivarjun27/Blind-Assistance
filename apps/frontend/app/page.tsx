'use client';

import { useEffect, useState } from 'react';

import { CameraView } from '@/components/camera-view';
import { ControlBar } from '@/components/control-bar';
import { StatusPill } from '@/components/status-pill';
import { useCameraCapture } from '@/hooks/useCameraCapture';
import { useRealtimeSession } from '@/hooks/useRealtimeSession';

export default function Home() {
  const camera = useCameraCapture();
  const session = useRealtimeSession(camera.captureFrame);
  const [showTranscript, setShowTranscript] = useState(false);

  // Enable camera on mount
  useEffect(() => {
    void camera.enableCamera().catch(() => {});
    return () => camera.disableCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-show transcript when messages arrive
  useEffect(() => {
    if (session.transcript.length > 0) {
      setShowTranscript(true);
    }
  }, [session.transcript.length]);

  return (
    <main className="min-h-screen bg-black flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 pt-5 pb-2">
        <span className="text-zinc-500 text-xs tracking-widest uppercase">
          Ally Vision
        </span>
        <StatusPill status={session.status} />
        <span className="text-zinc-500 text-xs w-20 text-right">
          {/* placeholder for timer if needed */}
        </span>
      </div>

      {/* Camera — takes most of screen */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 gap-0">
        <CameraView
          videoRef={camera.videoRef}
          isEnabled={camera.isEnabled}
        />

        {/* Dots animation when thinking/speaking */}
        {(session.status === 'thinking' || session.status === 'speaking') && (
          <div className="flex gap-1.5 mt-4">
            {[0, 1, 2, 3, 4].map((i) => (
              <span
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce"
                style={{ animationDelay: `${i * 0.1}s` }}
              />
            ))}
          </div>
        )}

        {/* Status text below camera */}
        {session.status === 'listening' && (
          <p className="mt-3 text-zinc-400 text-sm">
            I&apos;m listening
          </p>
        )}
      </div>

      {/* Error banner */}
      {session.error && (
        <div className="mx-4 mb-2 p-3 bg-red-950 border border-red-800 rounded-xl text-red-300 text-xs text-center">
          {session.error}
        </div>
      )}

      {/* Transcript — collapsible, shows last 3 messages */}
      {showTranscript && session.transcript.length > 0 && (
        <div className="mx-4 mb-2 max-h-32 overflow-y-auto space-y-1">
          {session.transcript.slice(-3).map((entry, i) => (
            <div
              key={i}
              className={`px-3 py-2 rounded-xl text-xs ${
                entry.role === 'user'
                  ? 'bg-zinc-800 text-zinc-300 text-right'
                  : 'bg-zinc-900 text-zinc-200'
              }`}
            >
              <span className="opacity-50 mr-1">
                {entry.role === 'user' ? 'You' : 'Ally'}
              </span>
              {entry.text}
            </div>
          ))}
        </div>
      )}

      {/* Controls — bottom centered */}
      <div className="pb-6">
        <ControlBar
          onStart={session.startSession}
          onStop={session.stopSession}
          onCapture={session.captureAndSend}
          status={session.status}
        />
      </div>
    </main>
  );
}
