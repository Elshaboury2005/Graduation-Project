import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ValidationErrors from '../components/pipelines/ValidationErrors';

describe('ValidationErrors', () => {
  it('renders Valid! when errors is empty', () => {
    render(<ValidationErrors errors={[]} />);
    expect(screen.getByText(/Valid! No errors found/i)).toBeInTheDocument();
  });

  it('renders each error message when errors has items', () => {
    const errors = [
      { field: 'testField1', message: 'testMessage1' },
      { field: 'testField2', message: 'testMessage2' },
    ];
    render(<ValidationErrors errors={errors} />);
    expect(screen.getByText(/testMessage1/)).toBeInTheDocument();
    expect(screen.getByText(/testMessage2/)).toBeInTheDocument();
  });

  it('renders correct count of error items', () => {
    const errors = [
      { field: 'f1', message: 'm1' },
      { field: 'f2', message: 'm2' },
    ];
    render(<ValidationErrors errors={errors} />);
    expect(screen.getByText(/Validation Errors \(2\):/)).toBeInTheDocument();
  });
});
