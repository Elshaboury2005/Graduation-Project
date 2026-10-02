import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { analyzeReliability, getReports } from '../api/experiments';
import ReportChart from '../components/reports/ReportChart';
import ReportCard from '../components/reports/ReportCard';
import ReliabilityInsight from '../components/reports/ReliabilityInsight';

export default function Reports() {
  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: getReports
  });
  const { data: analysis } = useQuery({
    queryKey: ['reliability-analysis', reports?.map(report => report.id)],
    queryFn: () => analyzeReliability(
      (reports ?? []).map(report => ({
        recovery_time_seconds: report.recovery_time_seconds,
        throughput_rows_per_second: report.average_throughput,
        data_loss: report.data_loss,
        error_rate: 1 - report.availability_percentage / 100
      }))
    ),
    enabled: Boolean(reports?.length)
  });

  if (isLoading) return <div>Loading reports...</div>;

  return (
    <div className="max-w-5xl space-y-6">
      <h2 className="text-2xl font-bold">Resilience Reports</h2>
      
      {reports && reports.length > 0 ? (
        <>
          <ReportChart reports={reports} />
          {analysis && <ReliabilityInsight analysis={analysis} />}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {reports.map(report => (
              <ReportCard key={report.id} report={report} />
            ))}
          </div>
        </>
      ) : (
        <div className="text-slate-400">No reports generated yet. Run experiments to see data here.</div>
      )}
    </div>
  );
}
