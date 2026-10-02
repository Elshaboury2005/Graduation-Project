import React from 'react';

interface Props {
  serviceName: string;
  connected: boolean;
}

export default function ServiceStatusBadge({ serviceName, connected }: Props) {
  return (
    <div className="flex items-center space-x-2 bg-slate-800 px-3 py-2 rounded border border-slate-700">
      <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-rose-500'}`} />
      <span className="text-sm font-medium">{serviceName}</span>
      <span className={`text-xs px-2 py-0.5 rounded ${connected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
        {connected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  );
}
