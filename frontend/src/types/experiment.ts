export type FaultType =
  | 'container_stop'
  | 'container_restart'
  | 'network_disruption'
  | 'cpu_stress'
  | 'memory_stress'
  | 'disk_pressure'
  | 'service_delay';
export type AllowedService =
  | 'kafka'
  | 'spark-master'
  | 'spark-worker'
  | 'namenode'
  | 'datanode'
  | 'postgres'
  | 'backend';

export interface Experiment {
  id: string;
  name: string;
  target: AllowedService;
  faultType: FaultType;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  createdAt: string;
}

export interface ExperimentDetail extends Experiment {
  lifecycleStage: string;
  logs: string[];
  results?: {
    recoveryTimeSeconds: number;
    availabilityPercentage: number;
  };
}

export interface ExperimentRun {
  experimentId: string;
  durationSeconds: number;
}
