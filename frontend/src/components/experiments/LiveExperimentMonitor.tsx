import React, { useState, useCallback } from 'react';
import { usePolling } from '../../hooks/usePolling';
import { getExperiment, cancelExperiment } from '../../api/experiments';
import { ExperimentDetail } from '../../types/experiment';

interface Props {
  experimentId: string;
  onComplete: () => void;
}

export default function LiveExperimentMonitor({ experimentId, onComplete }: Props) {
  const [data, setData] = useState<ExperimentDetail | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const isFinished = data?.status === 'succeeded' || data?.status === 'failed' || data?.status === 'cancelled';

  const fetchStatus = useCallback(async () => {
    try {
      const exp = await getExperiment(experimentId);
      setData(exp);
      if (exp.status === 'succeeded' || exp.status === 'failed' || exp.status === 'cancelled') {
        onComplete();
      }
    } catch (e) {
      console.error(e);
    }
  }, [experimentId, onComplete]);

  usePolling(fetchStatus, 2000, !isFinished);
  usePolling(() => setElapsed(e => e + 1), 1000, !isFinished);

  const stages = [
    'pending', 'validating', 'preparing', 'baseline', 'injecting', 'monitoring',
    'rolling_back', 'waiting_for_recovery', 'validating_data', 'collecting_metrics',
    'analyzing', 'generating_report'
  ];
  const resultEntries = Object.entries(data?.results || {}).filter(([, value]) =>
    typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
  );

  if (!data) return <div className="p-4 text-slate-400">Loading monitor...</div>;

  return (
    <div className="bg-slate-800 p-6 rounded-lg border border-slate-700 mt-4 space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium">Monitoring: {data.name}</h3>
        <span className="font-mono text-indigo-400">{elapsed}s elapsed</span>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div><p className="text-slate-400">Target</p><p className="mt-1 font-mono">{data.target}</p></div>
        <div><p className="text-slate-400">Injected Fault</p><p className="mt-1 font-mono">{data.faultType}</p></div>
      </div>

      {/* Stepper */}
      <div className="flex items-center space-x-2 text-xs overflow-x-auto pb-2">
        {stages.map((stage, idx) => {
          const isActive = data.lifecycleStage === stage;
          const isPast = stages.indexOf(data.lifecycleStage) > idx || isFinished;
          return (
            <React.Fragment key={stage}>
              <div className={`px-3 py-1 rounded-full whitespace-nowrap ${
                isActive ? 'bg-indigo-600 text-white' : 
                isPast ? 'bg-slate-600 text-slate-300' : 'bg-slate-700 text-slate-500'
              }`}>
                {stage}
              </div>
              {idx < stages.length - 1 && <div className="w-4 h-px bg-slate-600" />}
            </React.Fragment>
          );
        })}
      </div>

      {data.status === 'succeeded' && <div className="text-emerald-400">Experiment SUCCEEDED</div>}
      {data.status === 'failed' && <div className="text-rose-400">Experiment FAILED</div>}

      {resultEntries.length > 0 && (
        <div className="border-t border-slate-700 pt-4 text-sm">
          <p className="mb-2 text-slate-400">Measured Results</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {resultEntries.map(([key, value]) => <p key={key}><span className="text-slate-400">{key}: </span>{String(value)}</p>)}
          </div>
        </div>
      )}

      {!isFinished && (
        <button 
          onClick={() => cancelExperiment(experimentId)}
          className="px-4 py-2 bg-rose-600/20 text-rose-400 hover:bg-rose-600/30 rounded"
        >
          Cancel
        </button>
      )}
    </div>
  );
}
