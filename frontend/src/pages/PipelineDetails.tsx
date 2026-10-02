import React from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getPipelineRun } from '../api/pipelines';
import { getSystemStatus } from '../api/system';

function statusClass(status: string) {
  if (status === 'succeeded') return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
  if (status === 'failed') return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
  return 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40';
}

export default function PipelineDetails() {
  const { runId } = useParams<{ runId: string }>();

  const { data: run } = useQuery({
    queryKey: ['pipelineRun', runId],
    queryFn: () => getPipelineRun(runId!),
    enabled: !!runId,
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 2000 : false)
  });

  const { data: system } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: getSystemStatus,
    refetchInterval: 5000
  });

  if (!run) return <div className="text-slate-400">Loading pipeline run...</div>;

  const config = run.configuration;
  const operations = config?.processing?.operations?.map((operation) => operation.type).join(', ') || 'No transformations recorded';
  const services = [
    ['Kafka', system?.kafka?.connected],
    ['Spark', system?.spark?.connected],
    ['HDFS', system?.hdfs?.connected],
    ['Database', system?.database?.connected]
  ] as const;

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold">Pipeline Run: {run.name}</h2>
          <p className="mt-1 text-sm text-slate-400">Started {run.startedAt ? new Date(run.startedAt).toLocaleString() : 'not recorded'}</p>
        </div>
        <span className={`shrink-0 rounded-full border px-3 py-1 text-sm ${statusClass(run.status)}`}>Status: {run.status}</span>
      </div>

      <div className="bg-slate-800 p-6 rounded-lg border border-slate-700">
        <h3 className="text-lg mb-4">Execution Summary</h3>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
          <div>
            <span className="block text-slate-400 text-sm">Records Processed</span>
            <span className="text-2xl font-mono">{run.recordsProcessed}</span>
          </div>
          <div>
            <span className="block text-slate-400 text-sm">Spark Duration</span>
            <span className="text-2xl font-mono">{run.metrics?.duration_ms ? `${Math.round(run.metrics.duration_ms)} ms` : 'Not available'}</span>
          </div>
          <div><span className="block text-slate-400 text-sm">Completed</span><span className="text-sm">{run.completedAt ? new Date(run.completedAt).toLocaleString() : 'In progress'}</span></div>
        </div>
      </div>

      <div className="bg-slate-800 p-6 rounded-lg border border-slate-700">
        <h3 className="text-lg mb-4">Data Flow</h3>
        <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
          <div><p className="text-slate-400">Input</p><p className="mt-1 break-all font-mono">{config?.source?.path || 'Not recorded'}</p></div>
          <div><p className="text-slate-400">Output</p><p className="mt-1 break-all font-mono">{config?.storage?.path || 'Not recorded'}</p></div>
          <div className="sm:col-span-2"><p className="text-slate-400">Transformations</p><p className="mt-1">{operations}</p></div>
        </div>
      </div>

      {run.error_message && <div className="bg-rose-500/10 border border-rose-500/40 p-6 rounded-lg"><h3 className="font-medium text-rose-200">Failure Details</h3><pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs text-rose-100">{run.error_message}</pre></div>}

      <div className="bg-slate-800 p-6 rounded-lg border border-slate-700">
        <h3 className="text-lg mb-4">Live Services</h3>
        <div className="flex flex-wrap gap-3">
          {services.map(([name, connected]) => <span key={name} className={`rounded-full px-3 py-1 text-sm ${connected ? 'bg-emerald-500/15 text-emerald-300' : 'bg-rose-500/15 text-rose-300'}`}>{name}: {connected ? 'connected' : 'unavailable'}</span>)}
        </div>
      </div>
    </div>
  );
}
