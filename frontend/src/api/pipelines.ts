import { apiClient } from './client';
import { PipelineExecutionResult, PipelineRun, ValidationResult } from '../types/pipeline';

export async function validatePipeline(yamlContent: string): Promise<ValidationResult> {
  const res = await apiClient.post<ValidationResult>('/api/pipelines/validate', {
    yaml_content: yamlContent
  });
  return res.data;
}

export async function runPipeline(yamlContent: string): Promise<PipelineExecutionResult> {
  const res = await apiClient.post<PipelineExecutionResult>('/api/pipelines/run', {
    yaml_content: yamlContent
  });
  return res.data;
}

export async function getPipelineRuns(): Promise<PipelineRun[]> {
  const res = await apiClient.get<PipelineRun[]>('/api/pipeline-runs');
  return res.data;
}

export async function getPipelineRun(runId: string): Promise<PipelineRun> {
  const res = await apiClient.get<PipelineRun>(`/api/pipeline-runs/${runId}`);
  return res.data;
}
