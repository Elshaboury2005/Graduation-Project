import React from 'react';
import { ValidationError } from '../../types/pipeline';

interface Props {
  errors: ValidationError[];
}

export default function ValidationErrors({ errors }: Props) {
  if (errors.length === 0) {
    return (
      <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-md text-emerald-400 text-sm">
        Valid! No errors found.
      </div>
    );
  }

  return (
    <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-md">
      <h3 className="text-sm font-semibold text-rose-400 mb-2">Validation Errors ({errors.length}):</h3>
      <ul className="list-disc list-inside space-y-1">
        {errors.map((err, idx) => (
          <li key={idx} className="text-sm text-rose-300">
            <span className="font-mono bg-rose-500/20 px-1 rounded">{err.field}</span>: {err.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
