'use client';

import { useEffect } from 'react';

import { CameraView } from '@/components/camera-view';
import { ControlBar } from '@/components/control-bar';
import { StatusPill } from '@/components/status-pill';
import { useCameraCapture } from '@/hooks/useCameraCapture';
import { useRealtimeSession } from '@/hooks/useRealtimeSession';

export default function Home() {
  const camera = useCameraCapture();
  const session = useRealtimeSession(camera.captureFrame);

  // Enable camera on mount
  useEffect(() => {
    void camera.enableCamera().catch(() => {});
    return () => camera.disableCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">Ally Vision</h1>
          <StatusPill status={session.status} />
        </div>

        {/* Camera */}
        <CameraView
          videoRef={camera.videoRef}
          isEnabled={camera.isEnabled}
        />

        {/* Controls */}
        <ControlBar
          onStart={session.startSession}
          onStop={session.stopSession}
          onCapture={session.captureAndSend}
          status={session.status}
        />

        {/* Error */}
        {session.error && (
          <div className="p-3 bg-red-900/50 border border-red-500 rounded-lg text-red-300 text-sm">
            {session.error}
          </div>
        )}

        {/* Transcript */}
        {session.transcript.length > 0 && (
          <div className="space-y-2">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wide">
              Transcript
            </h2>
            <div className="space-y-2">
              {session.transcript.slice(-10).map((entry, i) => (
                <div
                  key={i}
                  className={`p-3 rounded-lg text-sm ${
                    entry.role === 'user'
                      ? 'bg-gray-800 text-gray-200'
                      : 'bg-blue-900/50 text-blue-100'
                  }`}
                >
                  <span className="font-medium mr-2 text-xs uppercase opacity-60">
                    {entry.role === 'user' ? 'You' : 'Ally'}
                  </span>
                  {entry.text}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
