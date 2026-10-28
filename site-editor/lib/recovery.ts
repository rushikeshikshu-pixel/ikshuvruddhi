/**
 * Factory Commercial Sugar Recovery Realization Factor
 * Calibrated against actual Gangamai Sugar factory boiling house performance (7.30% - 7.45% recovery in early crushing).
 */
export const RECOVERY_FACTOR = 0.812;

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
