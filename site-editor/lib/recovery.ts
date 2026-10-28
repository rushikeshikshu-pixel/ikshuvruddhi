/**
 * Factory Commercial Sugar Recovery Realization Factor (Kf)
 * Standard Indian Sugar Technology (VSI / NSI / Meade-Chen SJM Formula):
 * Kf = Reduced Mill Extraction (0.9465) x Boiling House Retention (0.860) = 0.8140
 * Reconciles CCS on cane with actual commercial bagged sugar recovery (7.35% - 7.45% in late Oct).
 */
export const RECOVERY_FACTOR = 0.814;

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
