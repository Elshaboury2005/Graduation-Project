import { apiClient } from './client';
import { AllowedService, Experiment, ExperimentDetail } from '../types/experiment';
import { Report } from '../types/report';

export interface ReliabilityAnalysis {
  method: string;
  observation_count: number;
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high';
  anomalies: Array<Record<string, unknown>>;
  likely_contributors: string[];
  recommendations: string[];
  limitations: string;
}

export async function getAllowedTargets(): Promise<AllowedService[]> {
  const res = await apiClient.get<{ allowed_services: AllowedService[] }>('/api/experiments/allowed-targets');
  return res.data.allowed_services;
}

export async function createExperiment(yamlContent: string): Promise<{ experiment_id: string }> {
  const res = await apiClient.post<{ experiment_id: string }>('/api/experiments', {
    yaml_content: yamlContent
  });
  return res.data;
}

export async function runExperiment(experimentId: string, yamlContent: string): Promise<void> {
  await apiClient.post(`/api/experiments/${experimentId}/run`, { yaml_content: yamlContent });
}

export async function getExperiment(experimentId: string): Promise<ExperimentDetail> {
  const res = await apiClient.get<ExperimentDetail>(`/api/experiments/${experimentId}`);
  return res.data;
}

export async function listExperiments(): Promise<Experiment[]> {
  const res = await apiClient.get<Experiment[]>('/api/experiments');
  return res.data;
}

export async function cancelExperiment(experimentId: string): Promise<void> {
  await apiClient.post(`/api/experiments/${experimentId}/cancel`);
}

export async function getReports(): Promise<Report[]> {
  const res = await apiClient.get<Report[]>('/api/reports');
  return res.data;
}

export async function getReport(reportId: string): Promise<Report> {
  const res = await apiClient.get<Report>(`/api/reports/${reportId}`);
  return res.data;
}

export async function analyzeReliability(
  observations: Array<Record<string, number>>
): Promise<ReliabilityAnalysis> {
  const res = await apiClient.post<ReliabilityAnalysis>('/api/ai/reliability-analysis', {
    observations
  });
  return res.data;
}
