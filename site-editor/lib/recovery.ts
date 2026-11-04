/**
 * Factory Commercial Sugar Recovery Realization Factor (Kf)
 * Calibrated to Gangamai Sugar Mills 2026 ground-truth laboratory recovery:
 * Season average recovery: 7.74% | Nov 2: 8.31% | Nov 3: 8.44%
 * Mean Command CCS = 9.394% -> Kf = 7.74 / 9.394 = 0.8239
 */
export const RECOVERY_FACTOR = 0.824;

/** Calculated estimate requested by the mill; keep full precision until display. */
export function estimatedRecovery(ccs: unknown): number | null {
  if ((typeof ccs !== 'number' && typeof ccs !== 'string') || (typeof ccs === 'string' && !ccs.trim())) return null;
  const value = Number(ccs);
  return Number.isFinite(value) && value >= 0 ? value * RECOVERY_FACTOR : null;
}

export function recoveryForExport(ccs: unknown): number | null {
  const value = estimatedRecovery(ccs);
  return value == null ? null : Number(value.toFixed(2));
}
