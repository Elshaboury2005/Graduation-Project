import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getSystemStatus } from '../api/system';
import { getPipelineRuns } from '../api/pipelines';
import { listExperiments } from '../api/experiments';
import ServiceStatusBadge from '../components/pipelines/ServiceStatusBadge';

export default function Dashboard() {
  const { data: status } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: getSystemStatus,
    refetchInterval: 5000
  });

  const { data: runs } = useQuery({
    queryKey: ['pipelineRuns'],
    queryFn: getPipelineRuns,
    refetchInterval: 5000
  });

  const { data: experiments } = useQuery({
    queryKey: ['experiments'],
    queryFn: listExperiments,
    refetchInterval: 5000
  });

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-xl font-semibold mb-4">System Status</h2>
        <div className="flex flex-wrap gap-4">
          {status ? (
            Object.entries(status).map(([service, connected]) => (
              <ServiceStatusBadge key={service} serviceName={service} connected={connected} />
            ))
          ) : (
            <div className="text-slate-400">Loading status...</div>
          )}
        </div>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section className="bg-slate-800 p-6 rounded-lg border border-slate-700">
          <h2 className="text-lg font-medium text-slate-300 mb-2">Pipelines Overview</h2>
          <div className="text-4xl font-bold text-indigo-400">{runs?.length || 0}</div>
          <p className="text-sm text-slate-400 mt-1">Total runs tracked</p>
        </section>

        <section className="bg-slate-800 p-6 rounded-lg border border-slate-700 overflow-hidden">
          <h2 className="text-lg font-medium text-slate-300 mb-4">Recent Experiments</h2>
          <div className="space-y-2">
            {experiments?.slice(0, 5).map(exp => (
              <div key={exp.id} className="flex justify-between items-center text-sm border-b border-slate-700 pb-2">
                <span className="font-mono">{exp.name}</span>
                <span className={`px-2 py-0.5 rounded text-xs ${exp.status === 'succeeded' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-700 text-slate-300'}`}>
                  {exp.status}
                </span>
              </div>
            ))}
            {!experiments?.length && <div className="text-slate-400 text-sm">No recent experiments.</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
