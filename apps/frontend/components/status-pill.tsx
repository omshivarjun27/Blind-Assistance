'use client';

const STATUS_CONFIG: Record<string, { label: string; dot: string }> = {
  idle:       { label: 'Ready',      dot: 'bg-zinc-400' },
  connecting: { label: 'Connecting', dot: 'bg-yellow-400 animate-pulse' },
  listening:  { label: 'Listening',  dot: 'bg-green-400 animate-pulse' },
  thinking:   { label: 'Thinking',   dot: 'bg-blue-400 animate-pulse' },
  speaking:   { label: 'Speaking',   dot: 'bg-purple-400 animate-pulse' },
  error:      { label: 'Error',      dot: 'bg-red-400' },
};

export function StatusPill({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.idle;
  return (
    <div className="flex items-center justify-center gap-2 py-2">
      <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
      <span className="text-sm text-zinc-300 tracking-wide">
        {cfg.label}
      </span>
    </div>
  );
}
