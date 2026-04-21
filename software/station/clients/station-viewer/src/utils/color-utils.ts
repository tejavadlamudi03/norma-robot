export function getConnectionStatusColor(status: string): string {
  switch (status) {
    case 'connected': return 'text-accent-success';
    case 'connecting': return 'text-accent-warning';
    case 'disconnected': return 'text-accent-critical';
    default: return 'text-text-label';
  }
}

export function getFPSColor(fps: number): string {
  if (fps >= 15) return 'text-accent-success';
  if (fps >= 10) return 'text-accent-warning';
  if (fps >= 5) return 'text-accent-danger';
  return 'text-accent-critical';
}

export function getLatencyTextColor(latency: number): string {
  if (latency < 100) return 'text-accent-success';
  if (latency < 500) return 'text-accent-warning';
  if (latency < 1000) return 'text-accent-danger';
  return 'text-accent-critical';
}

export function getLatencyBgColor(latency: number, hasError: boolean): string {
  if (hasError) return 'bg-accent-critical-deep';
  if (latency < 100) return 'bg-accent-success-deep';
  if (latency < 500) return 'bg-accent-warning-deep';
  if (latency < 1000) return 'bg-accent-danger-deep';
  return 'bg-accent-critical-deep';
}

export function getMotorStatusColor(latency: number, hasError: boolean): string {
  if (hasError) return 'text-accent-critical-deep';
  if (latency < 100) return 'text-accent-success-deep';
  if (latency < 500) return 'text-accent-warning-deep';
  if (latency < 1000) return 'text-accent-danger-deep';
  return 'text-accent-critical-deep';
}

export function getMotorStatusTextColor(latency: number, hasError: boolean): string {
  if (hasError) return 'text-accent-critical';
  if (latency > 500) return 'text-accent-warning';
  return 'text-accent-success';
}

export function getCurrentColor(current: number): string {
  if (current === 0) return 'text-text-muted';
  if (current < 100) return 'text-accent-success';
  if (current < 200) return 'text-accent-warning';
  if (current < 300) return 'text-accent-danger';
  return 'text-accent-critical';
}

export function getGradientClass(percentage: number): string {
  if (percentage < 33) return 'bg-gradient-to-r from-accent-info-bg to-accent-info';
  if (percentage < 66) return 'bg-gradient-to-r from-accent-success-bg to-accent-success';
  return 'bg-gradient-to-r from-accent-warning-deep to-accent-warning';
}

export function getTemperatureColor(temp: number): string {
  if (temp === 0) return 'text-text-muted';
  if (temp < 40) return 'text-accent-success';
  if (temp < 50) return 'text-accent-warning';
  if (temp < 60) return 'text-accent-danger';
  return 'text-accent-critical';
}
