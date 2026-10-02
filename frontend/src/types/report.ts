export interface Report {
  id: string;
  experiment_name: string;
  target: string;
  failure_type: string;
  recovery_time_seconds: number;
  expected_records: number;
  processed_records: number;
  data_loss: number;
  average_throughput: number;
  availability_percentage: number;
  result: 'PASS' | 'FAIL';
}
