import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LiveExperimentMonitor from '../components/experiments/LiveExperimentMonitor';

vi.mock('../api/experiments', () => ({
  getExperiment: vi.fn(),
  cancelExperiment: vi.fn(),
}));

describe('LiveExperimentMonitor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Loading monitor... initially', () => {
    render(<LiveExperimentMonitor experimentId="123" onComplete={() => {}} />);
    expect(screen.getByText(/Loading monitor.../i)).toBeInTheDocument();
  });

  // Note: For fully testing async data fetch in vitest, we'd need waitFor or flushPromises,
  // but as per basic requirements, we only check the structure here.
});
