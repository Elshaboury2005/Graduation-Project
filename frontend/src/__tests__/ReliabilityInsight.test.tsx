import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ReliabilityInsight from '../components/reports/ReliabilityInsight';

describe('ReliabilityInsight', () => {
  it('shows an explainable risk summary', () => {
    render(
      <ReliabilityInsight
        analysis={{
          method: 'robust_z_score',
          observation_count: 2,
          risk_score: 36,
          risk_level: 'medium',
          anomalies: [],
          likely_contributors: ['Kafka consumer lag'],
          recommendations: ['Review consumer instances.'],
          limitations: 'This is an indicator.'
        }}
      />
    );

    expect(screen.getByText(/MEDIUM RISK/)).toBeInTheDocument();
    expect(screen.getByText(/Kafka consumer lag/)).toBeInTheDocument();
    expect(screen.getByText(/Review consumer instances/)).toBeInTheDocument();
  });
});
