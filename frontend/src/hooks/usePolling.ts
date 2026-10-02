import { useEffect } from 'react';

export function usePolling(callback: () => void, intervalMs: number, enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(callback, intervalMs);
    return () => clearInterval(id);
  }, [callback, intervalMs, enabled]);
}
