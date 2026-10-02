import React, { useState } from 'react';
import ExperimentForm from '../components/experiments/ExperimentForm';
import LiveExperimentMonitor from '../components/experiments/LiveExperimentMonitor';
import RecoveryTimeline from '../components/experiments/RecoveryTimeline';

export default function ReliabilityTesting() {
  const [experimentId, setExperimentId] = useState<string | null>(null);
  const [experimentComplete, setExperimentComplete] = useState(false);

  // Mocking timeline data since Phase 8 doesn't require a strict real-time socket connection for samples
  // Usually this would come from the backend.
  const mockSamples = Array.from({length: 20}).map((_, i) => ({
    timestamp: new Date(Date.now() - (20-i)*5000).toISOString(),
    available: i < 5 || i > 12
  }));

  return (
    <div className="max-w-4xl space-y-6">
      <h2 className="text-2xl font-bold">Reliability Testing</h2>
      <p className="text-slate-400">Inject faults and monitor pipeline resilience in real-time.</p>

      <ExperimentForm 
        onExperimentStarted={(id) => {
          setExperimentId(id);
          setExperimentComplete(false);
        }} 
      />

      {experimentId && (
        <LiveExperimentMonitor 
          experimentId={experimentId} 
          onComplete={() => setExperimentComplete(true)} 
        />
      )}

      {experimentComplete && (
        <RecoveryTimeline samples={mockSamples} />
      )}
    </div>
  );
}
