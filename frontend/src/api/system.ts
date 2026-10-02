import { apiClient } from './client';
import { setApiToken } from './client';

export interface SystemStatus {
  database: { connected: boolean };
  kafka: { connected: boolean };
  spark: { connected: boolean };
  hdfs: { connected: boolean };
}

export async function getSystemStatus(): Promise<SystemStatus> {
  const res = await apiClient.get<SystemStatus>('/api/system/status');
  return res.data;
}

export async function login(username: string, password: string): Promise<{ access_token: string; token_type: string }> {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const res = await apiClient.post<{ access_token: string; token_type: string }>('/api/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
  
  setApiToken(res.data.access_token);
  return res.data;
}

export async function getMe(): Promise<{ username: string }> {
  const res = await apiClient.get<{ username: string }>('/api/auth/me');
  return res.data;
}
