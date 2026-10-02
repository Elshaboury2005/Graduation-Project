import React from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

interface Sample {
  timestamp: string;
  available: boolean;
}

interface Props {
  samples: Sample[];
}

export default function RecoveryTimeline({ samples }: Props) {
  if (samples.length === 0) {
    return <div className="text-slate-400 text-sm">No timeline data available.</div>;
  }

  const chartData = samples.map(s => ({
    time: new Date(s.timestamp).toLocaleTimeString(),
    val: s.available ? 1 : 0
  }));

  return (
    <div className="h-64 w-full bg-slate-800 p-4 rounded-lg border border-slate-700 mt-4">
      <h4 className="text-sm text-slate-300 mb-4">Availability Timeline</h4>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData}>
          <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
          <YAxis domain={[0, 1]} ticks={[0, 1]} stroke="#94a3b8" fontSize={12} />
          <Tooltip 
            contentStyle={{ backgroundColor: '#1e293b', border: 'none', color: '#f8fafc' }}
          />
          <Area type="stepAfter" dataKey="val" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
