import React from 'react';
import { Report } from '../../types/report';

interface Props {
  report: Report;
}

export default function ReportCard({ report }: Props) {
  const isPass = report.result === 'PASS';
  
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex flex-col space-y-4">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="font-semibold text-slate-100">{report.experiment_name}</h3>
          <p className="text-sm text-slate-400">Target: {report.target} | Fault: {report.failure_type}</p>
        </div>
        <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${isPass ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
          {report.result}
        </span>
      </div>
      
      <div className="grid grid-cols-3 gap-4 text-sm bg-slate-900/50 p-3 rounded">
        <div>
          <span className="block text-slate-500">Recovery Time</span>
          <span className="font-mono text-slate-200">{report.recovery_time_seconds.toFixed(2)}s</span>
        </div>
        <div>
          <span className="block text-slate-500">Availability</span>
          <span className="font-mono text-slate-200">{report.availability_percentage.toFixed(1)}%</span>
        </div>
        <div>
          <span className="block text-slate-500">Data Loss</span>
          <span className="font-mono text-slate-200">{report.data_loss} records</span>
        </div>
      </div>
    </div>
  );
}
