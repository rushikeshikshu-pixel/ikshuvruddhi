import type { Plot, Sample } from '../app/types';

export type QualityGrade = 'A' | 'B' | 'C';

export type DataQualityReport = {
  score: number; // 0 to 100
  grade: QualityGrade;
  gradeLabel: string;
  chemicalHealth: {
    tested: boolean;
    valid: boolean;
    purityPct: number | null;
    flags: string[];
  };
  spatialHealth: {
    hasBoundary: boolean;
    valid: boolean;
    flags: string[];
  };
  satelliteHealth: {
    observed: boolean;
    freshnessDays: number | null;
    cloudPct: number | null;
    flags: string[];
  };
  flags: string[];
  eligibleForHarvest: boolean;
  eligibleForTraining: boolean;
};

/**
 * Evaluates the Data Quality Index (DQI) and Trust Score for a sugarcane plot.
 * Serves as the central data governance backbone for factory cutting orders and ML training.
 */
export function evaluatePlotQuality(
  plot: Plot,
  latestSample?: Sample | null,
  hasBoundary = true
): DataQualityReport {
  let score = 100;
  const flags: string[] = [];
  const chemicalFlags: string[] = [];
  const spatialFlags: string[] = [];
  const satelliteFlags: string[] = [];

  // --- 1. Agronomic & Profile Completeness ---
  if (!plot.variety || plot.variety.toLowerCase().includes('unknown')) {
    score -= 10;
    flags.push('Variety unverified');
  }

  if (!plot.plantingDate) {
    score -= 15;
    flags.push('Planting date missing');
  } else {
    const ageDays = Math.max(0, Math.floor((Date.now() - Date.parse(plot.plantingDate)) / 86400000));
    if (ageDays < 180) {
      flags.push(`Immature crop (${ageDays} days)`);
    }
  }

  if (plot.area <= 0 || !Number.isFinite(plot.area)) {
    score -= 20;
    flags.push('Invalid registered area');
    spatialFlags.push('Invalid area value');
  }

  // --- 2. Chemical Sanity & Laboratory Physics ---
  let purityPct: number | null = null;
  let chemicalValid = true;

  if (latestSample && latestSample.pol != null && latestSample.brix != null) {
    const pol = Number(latestSample.pol);
    const brix = Number(latestSample.brix);

    // Fatal physical law: Pol cannot exceed Brix (dissolved sucrose cannot exceed total dissolved solids)
    if (pol > brix) {
      score -= 50;
      chemicalValid = false;
      const msg = `FATAL: Pol (${pol}%) exceeds Brix (${brix}°Bx)`;
      flags.push(msg);
      chemicalFlags.push(msg);
    } else if (brix > 0) {
      purityPct = Number(((pol / brix) * 100).toFixed(1));
      // Mature fresh cane purity typically sits between 75% and 93%
      if (purityPct < 75.0) {
        score -= 15;
        const msg = `Low juice purity (${purityPct}%) - potential inversion`;
        flags.push(msg);
        chemicalFlags.push(msg);
      } else if (purityPct > 93.0) {
        score -= 15;
        const msg = `Suspicious high purity (${purityPct}%) - check refractometer`;
        flags.push(msg);
        chemicalFlags.push(msg);
      }
    }

    if (latestSample.sampleDate && plot.plantingDate && latestSample.sampleDate < plot.plantingDate) {
      score -= 25;
      chemicalValid = false;
      const msg = 'Sample date precedes planting date';
      flags.push(msg);
      chemicalFlags.push(msg);
    }
  } else {
    // No lab measurement recorded yet
    score -= 10;
    flags.push('Lab test pending');
    chemicalFlags.push('No laboratory measurement');
  }

  // --- 3. Satellite Observation Fidelity ---
  let freshnessDays: number | null = null;
  if (plot.acquisitionDate) {
    freshnessDays = Math.max(0, Math.floor((Date.now() - Date.parse(plot.acquisitionDate)) / 86400000));
    if (freshnessDays > 25) {
      score -= 10;
      const msg = `Satellite pass aged (${freshnessDays}d ago)`;
      flags.push(msg);
      satelliteFlags.push(msg);
    }

    if (plot.cloud != null) {
      const cloud = Number(plot.cloud);
      if (cloud > 40.0) {
        score -= 20;
        const msg = `Cloud contaminated (${cloud.toFixed(0)}% cloud)`;
        flags.push(msg);
        satelliteFlags.push(msg);
      } else if (cloud > 20.0) {
        score -= 10;
        const msg = `Moderate cloud review (${cloud.toFixed(0)}%)`;
        flags.push(msg);
        satelliteFlags.push(msg);
      }
    }

    if (plot.ndvi != null) {
      const ndvi = Number(plot.ndvi);
      if (ndvi < 0.20) {
        score -= 10;
        const msg = `Low vegetative signal (NDVI ${ndvi.toFixed(2)})`;
        flags.push(msg);
        satelliteFlags.push(msg);
      }
    }
  } else {
    score -= 15;
    flags.push('Satellite observation missing');
    satelliteFlags.push('No satellite pass linked');
  }

  // --- 4. Spatial Geometry Integrity ---
  if (!hasBoundary) {
    score -= 15;
    flags.push('Boundary polygon missing');
    spatialFlags.push('No polygon boundary registered');
  }

  // Ensure bounded score
  const finalScore = Math.max(0, Math.min(100, score));

  // Determine Grade
  const grade: QualityGrade = finalScore >= 85 ? 'A' : finalScore >= 70 ? 'B' : 'C';
  const gradeLabel =
    grade === 'A'
      ? 'Grade A · Verified Gold'
      : grade === 'B'
      ? 'Grade B · Usable'
      : 'Grade C · Review Required';

  const hasFatal = flags.some(f => f.includes('FATAL') || f.includes('precedes planting'));

  return {
    score: finalScore,
    grade,
    gradeLabel,
    chemicalHealth: {
      tested: Boolean(latestSample && latestSample.pol != null),
      valid: chemicalValid,
      purityPct,
      flags: chemicalFlags,
    },
    spatialHealth: {
      hasBoundary,
      valid: hasBoundary && !spatialFlags.some(f => f.includes('Invalid')),
      flags: spatialFlags,
    },
    satelliteHealth: {
      observed: Boolean(plot.acquisitionDate),
      freshnessDays,
      cloudPct: plot.cloud != null ? Number(plot.cloud) : null,
      flags: satelliteFlags,
    },
    flags,
    eligibleForHarvest: finalScore >= 70 && !hasFatal,
    eligibleForTraining: finalScore >= 85 && !hasFatal && chemicalValid && Boolean(latestSample),
  };
}
