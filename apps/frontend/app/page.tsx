'use client';

import { useEffect, useRef, useState } from 'react';

import { CameraView } from '@/components/camera-view';
import { ControlBar } from '@/components/control-bar';
import { StatusPill } from '@/components/status-pill';
import { useCameraCapture } from '@/hooks/useCameraCapture';
import { useRealtimeSession } from '@/hooks/useRealtimeSession';

export default function Home() {
  const camera = useCameraCapture();
  const session = useRealtimeSession(camera.captureFrame);
  const [showChat, setShowChat] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Enable camera on mount
  useEffect(() => {
    void camera.enableCamera().catch(() => {});
    return () => camera.disableCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session.transcript.length]);

  return (
    <main className="flex flex-col h-screen w-screen bg-black overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/10 shrink-0">
        <span className="text-sm font-semibold text-white">Ally Vision</span>
        <StatusPill status={session.status} />
        <span className="text-zinc-500 text-xs w-20 text-right">&nbsp;</span>
      </div>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <div className="relative flex flex-col w-full md:w-1/2 lg:w-1/2 bg-zinc-950 border-r border-white/10 shrink-0">
          <div className="flex-1 min-h-0">
            <CameraView videoRef={camera.videoRef} isEnabled={camera.isEnabled} />
          </div>

          {(session.status === 'thinking' || session.status === 'speaking') && (
            <div className="absolute bottom-16 left-0 right-0 flex justify-center gap-2 pb-2">
              {[0, 1, 2, 3, 4].map((i) => (
                <span
                  key={i}
                  className="w-2 h-2 rounded-full bg-white animate-bounce"
                  style={{ animationDelay: `${i * 0.1}s` }}
                />
              ))}
            </div>
          )}

          {session.error && (
            <div className="absolute bottom-0 left-0 right-0 bg-red-600/80 text-white text-xs px-3 py-1 text-center">
              {session.error}
            </div>
          )}

          <div className="shrink-0 px-4 py-3 border-t border-white/10 bg-zinc-950">
            <ControlBar
              onStart={session.startSession}
              onStop={session.stopSession}
              onCapture={session.captureAndSend}
              status={session.status}
            />
          </div>
        </div>

        <div className="hidden md:flex flex-col w-1/2 bg-zinc-900">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 shrink-0">
            <span className="text-sm font-semibold text-white">Chat</span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full border ${
                session.status === 'listening'
                  ? 'border-green-500 text-green-400 bg-green-500/10'
                  : session.status === 'thinking'
                    ? 'border-yellow-500 text-yellow-400 bg-yellow-500/10'
                    : session.status === 'speaking'
                      ? 'border-blue-500 text-blue-400 bg-blue-500/10'
                      : 'border-zinc-600 text-zinc-400 bg-zinc-800'
              }`}
            >
              {session.status === 'listening'
                ? 'Listening'
                : session.status === 'thinking'
                  ? 'Thinking'
                  : session.status === 'speaking'
                    ? 'Speaking'
                    : 'Idle'}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
            {session.transcript.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  className="text-zinc-600"
                >
                  <path
                    d="M12 3a3 3 0 0 0-3 3v6a3 3 0 1 0 6 0V6a3 3 0 0 0-3-3Zm5 9a1 1 0 1 1 2 0 7 7 0 1 1-14 0 1 1 0 1 1 2 0 5 5 0 1 0 10 0Zm-4 8.93V23a1 1 0 1 1-2 0v-2.07A8.002 8.002 0 0 1 4 13a1 1 0 1 1 2 0 6 6 0 0 0 12 0 1 1 0 1 1 2 0 8.002 8.002 0 0 1-7 7.93Z"
                    fill="currentColor"
                  />
                </svg>
                <p className="text-sm text-zinc-500 mt-2">No messages yet</p>
                <p className="text-xs text-zinc-600 mt-1">Start speaking to begin</p>
              </div>
            ) : (
              <>
                {session.transcript.map((entry, i) => (
                  entry.role === 'user' ? (
                    <div key={i} className="flex justify-end">
                      <div
                        data-transcript
                        className="max-w-[80%] rounded-2xl rounded-tr-sm px-3 py-2 bg-zinc-700 text-white text-sm"
                      >
                        {entry.text}
                      </div>
                    </div>
                  ) : (
                    <div key={i} className="flex justify-start gap-2">
                      <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                        <span className="text-[10px] text-zinc-400">A</span>
                      </div>
                      <div
                        data-transcript
                        className="max-w-[80%] rounded-2xl rounded-tl-sm px-3 py-2 bg-zinc-800 text-white text-sm"
                      >
                        {entry.text}
                      </div>
                    </div>
                  )
                ))}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          <div className="shrink-0 px-4 py-2 border-t border-white/10 bg-zinc-950">
            {session.status === 'thinking' ? (
              <div className="text-xs text-yellow-400">Ally is thinking...</div>
            ) : session.status === 'speaking' ? (
              <div className="text-xs text-blue-400">Ally is speaking...</div>
            ) : session.status === 'listening' ? (
              <div className="text-xs text-green-400">Listening...</div>
            ) : (
              <div className="h-4" />
            )}
          </div>
        </div>
      </div>

      {showChat && (
        <div className="md:hidden fixed inset-0 z-40 flex flex-col bg-zinc-900">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 shrink-0">
            <span className="text-sm font-semibold text-white">Chat</span>
            <button
              onClick={() => setShowChat(false)}
              className="text-zinc-400 hover:text-white text-sm"
              aria-label="Close chat"
            >
              X
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
            {session.transcript.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  className="text-zinc-600"
                >
                  <path
                    d="M12 3a3 3 0 0 0-3 3v6a3 3 0 1 0 6 0V6a3 3 0 0 0-3-3Zm5 9a1 1 0 1 1 2 0 7 7 0 1 1-14 0 1 1 0 1 1 2 0 5 5 0 1 0 10 0Zm-4 8.93V23a1 1 0 1 1-2 0v-2.07A8.002 8.002 0 0 1 4 13a1 1 0 1 1 2 0 6 6 0 0 0 12 0 1 1 0 1 1 2 0 8.002 8.002 0 0 1-7 7.93Z"
                    fill="currentColor"
                  />
                </svg>
                <p className="text-sm text-zinc-500 mt-2">No messages yet</p>
                <p className="text-xs text-zinc-600 mt-1">Start speaking to begin</p>
              </div>
            ) : (
              <>
                {session.transcript.map((entry, i) => (
                  entry.role === 'user' ? (
                    <div key={i} className="flex justify-end">
                      <div
                        data-transcript
                        className="max-w-[80%] rounded-2xl rounded-tr-sm px-3 py-2 bg-zinc-700 text-white text-sm"
                      >
                        {entry.text}
                      </div>
                    </div>
                  ) : (
                    <div key={i} className="flex justify-start gap-2">
                      <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                        <span className="text-[10px] text-zinc-400">A</span>
                      </div>
                      <div
                        data-transcript
                        className="max-w-[80%] rounded-2xl rounded-tl-sm px-3 py-2 bg-zinc-800 text-white text-sm"
                      >
                        {entry.text}
                      </div>
                    </div>
                  )
                ))}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>
        </div>
      )}

      <button
        onClick={() => setShowChat(true)}
        className="md:hidden fixed bottom-20 right-4 z-50 w-10 h-10 rounded-full bg-zinc-800 border border-white/10 flex items-center justify-center text-zinc-300"
        aria-label="Open chat"
      >
        Chat
      </button>
    </main>
  );
}
