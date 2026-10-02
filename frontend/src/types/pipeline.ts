export interface ValidationError {
  field: string;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

export interface PipelineRunResult {
  recordsProcessed: number;
  durationMs: number;
}

export interface PipelineExecutionResult {
  run_id: string | null;
  pipeline_run_id: string;
  status: 'success' | 'failed' | 'invalid';
  metrics: Record<string, Record<string, number | string | null>>;
  logs: Array<{ level: string; step: string; message: string }>;
}

export interface PipelineRun {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  recordsProcessed: number;
  startedAt: string;
  completedAt?: string;
  result?: PipelineRunResult;
  error_message?: string | null;
  metrics?: Record<string, number>;
  configuration?: {
    source?: { path?: string; type?: string };
    storage?: { path?: string; type?: string };
    processing?: { operations?: Array<{ type: string }> };
  } | null;
}
