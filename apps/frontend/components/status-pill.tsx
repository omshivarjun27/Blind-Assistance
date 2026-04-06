'use client';

interface StatusPillProps {
  status: string;
}

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  idle:       { label: 'Ready',      color: 'bg-gray-500' },
  connecting: { label: 'Connecting', color: 'bg-yellow-500' },
  listening:  { label: 'Listening',  color: 'bg-green-500' },
  thinking:   { label: 'Thinking',   color: 'bg-blue-500' },
  speaking:   { label: 'Speaking',   color: 'bg-purple-500' },
  error:      { label: 'Error',      color: 'bg-red-500' },
};

export function StatusPill({ status }: StatusPillProps) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.idle;
  return (
    <span
      className={`inline-flex items-center px-3 py-1 rounded-full text-white text-sm font-medium ${cfg.color}`}
    >
      <span className="w-2 h-2 rounded-full bg-white mr-2 opacity-75" />
      {cfg.label}
    </span>
  );
}
