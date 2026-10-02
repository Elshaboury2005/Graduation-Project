import React from 'react';
import { ReliabilityAnalysis } from '../../api/experiments';

interface Props {
  analysis: ReliabilityAnalysis;
}

const riskStyles = {
  low: 'bg-emerald-500/20 text-emerald-300',
  medium: 'bg-amber-500/20 text-amber-300',
  high: 'bg-rose-500/20 text-rose-300'
};

export default function ReliabilityInsight({ analysis }: Props) {
  return (
    <section className="border border-slate-700 bg-slate-800 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="font-semibold text-slate-100">Reliability Analysis</h3>
          <p className="text-sm text-slate-400">Based on {analysis.observation_count} experiment reports</p>
        </div>
        <span className={`rounded px-2.5 py-1 text-sm font-semibold ${riskStyles[analysis.risk_level]}`}>
          {analysis.risk_level.toUpperCase()} RISK ({analysis.risk_score})
        </span>
      </div>
      <div className="grid gap-4 md:grid-cols-2 text-sm">
        <div>
          <p className="mb-1 text-slate-500">Likely contributors</p>
          <p className="text-slate-200">{analysis.likely_contributors.join(', ') || 'No dominant signal'}</p>
        </div>
        <div>
          <p className="mb-1 text-slate-500">Recommendations</p>
          <p className="text-slate-200">{analysis.recommendations.join(' ')}</p>
        </div>
      </div>
      <p className="text-xs text-slate-500">{analysis.limitations}</p>
    </section>
  );
}
