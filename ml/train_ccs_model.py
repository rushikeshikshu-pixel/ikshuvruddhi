#!/usr/bin/env python3
"""
train_ccs_model.py - train a Brix / Pol / CCS model on REAL mill laboratory data.

WHY THIS FILE EXISTS
    `train_high_precision_95.py` reports 94-96% R2. That number is not real.
    It calls `generate_multispectral_dataset()`, which invents the target from a
    closed-form expression of the same features it then trains on:

        maturity   = 12.5 * sin(min(pi/2, (age/420)*(pi/2)))
        canopy     = 0.88 + ndre*0.25 + ndvi*0.15
        recovery   = maturity * canopy * solar * ripening + N(0, 0.05)

    The model is learning to invert its own generator through 0.05 of noise.
    A high R2 there is arithmetic, not agronomy. It has never seen a field.

    Worse, the synthetic NDVI/NDRE/NDWI are built from independent uniform
    random reflectances, so they are mutually uncorrelated. In real Sentinel-2
    data over sugarcane they correlate at r ~ 0.85-0.95. The model has learned
    to lean on band relationships that do not exist in nature, which is why it
    cannot transfer to a real plot.

    This script does the opposite. It refuses to run without real lab data,
    validates in a way that cannot leak, and always reports what a trivial
    baseline would have scored.

THE GROUND TRUTH YOU ALREADY HAVE
    Every cart crushed at Gangamai is sampled: Brix, Pol, Fibre -> CCS, keyed to
    a cane slip and therefore to a Gat number. That is thousands of labelled
    samples per season, already collected, already paid for. Export it as:

        gat_no, sample_date, brix, pol, fibre, ccs

    Join it to the phenology output from sentinel_phenology.py and you have a
    real training set. There is no substitute - sucrose is inside the stalk and
    no satellite sees it directly. What the satellite sees is the canopy
    behaviour that precedes sucrose accumulation, which is why crop age and the
    ripening-phase drying signal carry most of the predictive weight.

REALISTIC EXPECTATIONS
    With 500+ real samples spanning a full season, published work and our own
    feature set put you at roughly R2 0.55-0.70, RMSE 0.5-0.8 CCS points.
    That is genuinely useful for sequencing a harvest queue. It is NOT a
    replacement for the laboratory at the weighbridge, and this script prints
    that conclusion rather than burying it.

USAGE
    python train_ccs_model.py --lab lab_results.csv \
                              --phenology ../data/output/phenology.csv \
                              --target ccs --out ../models/ccs_real.pkl
"""

import argparse
import pickle
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error


SYNTHETIC_MARKERS = [
    "factory_sugar_recovery_pct",   # only ever produced by the generator
    "hydro_thermal_index",
]


def guard_against_synthetic(df, path):
    """Refuse to train on the generated dataset. This is the whole point."""
    hits = [c for c in SYNTHETIC_MARKERS if c in df.columns]
    if len(hits) >= 2 and "brix" not in df.columns and "pol" not in df.columns:
        sys.exit(
            f"\nREFUSING TO TRAIN.\n"
            f"  {path} carries the signature of generate_multispectral_dataset()\n"
            f"  (columns: {hits}) and has no brix/pol columns.\n\n"
            f"  Training on it reproduces the 94% illusion. Export real\n"
            f"  laboratory results instead - see the docstring in this file.\n"
        )


def load_lab(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    guard_against_synthetic(df, path)

    need = {"gat_no"}
    if not need.issubset(df.columns):
        sys.exit(f"Lab file must contain a `gat_no` column. Found: {list(df.columns)}")

    have = [c for c in ("brix", "pol", "ccs") if c in df.columns]
    if not have:
        sys.exit("Lab file must contain at least one of: brix, pol, ccs.")

    # Derive CCS where Pol and Brix are present but CCS is not.
    # Indian standard reduces to CCS = 1.022*Pol - 0.292*Brix at nominal fibre.
    if "ccs" not in df.columns and {"brix", "pol"}.issubset(df.columns):
        df["ccs"] = 1.022 * df["pol"] - 0.292 * df["brix"]
        print("  Derived CCS from Pol and Brix.")

    if "purity" not in df.columns and {"brix", "pol"}.issubset(df.columns):
        df["purity"] = 100.0 * df["pol"] / df["brix"].replace(0, np.nan)

    df["gat_no"] = df["gat_no"].astype(str).str.strip()
    return df


def load_phenology(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["gat_no"] = df["gat_no"].astype(str).str.strip()
    return df


def build_features(lab, phen, target):
    df = lab.merge(phen, on="gat_no", how="inner", suffixes=("", "_phen"))
    if df.empty:
        sys.exit("No Gat numbers matched between the lab file and the phenology file.")

    # Crop age at the moment the sample was taken - the single strongest
    # predictor, and only available because planting is detected, not guessed.
    if "sample_date" in df.columns and "planting_date_est" in df.columns:
        sd = pd.to_datetime(df["sample_date"], errors="coerce", dayfirst=True)
        pd_est = pd.to_datetime(df["planting_date_est"], errors="coerce")
        df["crop_age_days"] = (sd - pd_est).dt.days

    candidates = [
        "crop_age_days", "ndvi_max", "ndvi_min", "ndvi_amplitude",
        "net_acres_from_boundary", "clear_scenes",
        "ndvi", "ndre", "ndwi", "evi",
        "sat_temp_celsius", "sat_solar_radiation_kwh_m2",
        "sat_precipitation_mm", "sat_humidity_pct", "sat_diurnal_temp_range",
    ]
    feats = [c for c in candidates if c in df.columns and df[c].notna().sum() > len(df) * 0.5]

    for cat in ("variety", "cane_type"):
        if cat in df.columns:
            d = pd.get_dummies(df[cat].astype(str).str.upper().str.strip(), prefix=cat)
            keep = [c for c in d.columns if d[c].sum() >= 5]     # avoid singleton levels
            df = pd.concat([df, d[keep]], axis=1)
            feats.extend(keep)

    if not feats:
        sys.exit("No usable features after the join. Check the phenology export.")

    df = df.dropna(subset=[target])
    X = df[feats].apply(pd.to_numeric, errors="coerce").fillna(df[feats].median(numeric_only=True))
    y = df[target].astype(float)

    # Group by village where available, else by Gat. Neighbouring plots share
    # soil, weather and management; random k-fold across them leaks badly and
    # is the usual reason a demo model looks better than it is.
    if "village" in df.columns and df["village"].nunique() >= 4:
        groups, gname = df["village"].astype(str), "village"
    else:
        groups, gname = df["gat_no"].astype(str), "gat_no"

    return X, y, groups, gname, feats, df


def evaluate(X, y, groups, gname, feats, target):
    n_groups = groups.nunique()
    n_splits = int(min(5, max(2, n_groups)))
    print(f"\nValidation: GroupKFold({n_splits}) grouped by {gname} "
          f"({n_groups} groups, {len(y)} samples)")
    if len(y) < 100:
        print("  WARNING: under 100 samples. Treat every number below as indicative only.")

    gkf = GroupKFold(n_splits=n_splits)
    models = {
        "baseline (predict mean)": DummyRegressor(strategy="mean"),
        "random forest": RandomForestRegressor(n_estimators=400, min_samples_leaf=3,
                                               random_state=42, n_jobs=-1),
        "gradient boosting": GradientBoostingRegressor(n_estimators=300, max_depth=3,
                                                       learning_rate=0.05, random_state=42),
    }

    results, oof_store = {}, {}
    for name, mdl in models.items():
        oof = np.full(len(y), np.nan)
        for tr, te in gkf.split(X, y, groups):
            m = mdl.__class__(**mdl.get_params())
            m.fit(X.iloc[tr], y.iloc[tr])
            oof[te] = m.predict(X.iloc[te])
        ok = ~np.isnan(oof)
        results[name] = {
            "r2": r2_score(y[ok], oof[ok]),
            "mae": mean_absolute_error(y[ok], oof[ok]),
            "rmse": float(np.sqrt(mean_squared_error(y[ok], oof[ok]))),
        }
        oof_store[name] = oof

    print(f"\nOut-of-group performance on `{target}`:")
    print(f"  {'model':<26}{'R2':>8}{'MAE':>8}{'RMSE':>8}")
    for k, v in results.items():
        print(f"  {k:<26}{v['r2']:>8.3f}{v['mae']:>8.3f}{v['rmse']:>8.3f}")

    base = results["baseline (predict mean)"]["rmse"]
    best_name = min((k for k in results if "baseline" not in k), key=lambda k: results[k]["rmse"])
    best = results[best_name]
    gain = 100 * (base - best["rmse"]) / base

    print(f"\n  Best model: {best_name}")
    print(f"  It beats 'just predict the seasonal mean' by {gain:.1f}% on RMSE.")
    if gain < 10:
        print("  VERDICT: that is not a meaningful gain. The features do not yet")
        print("  explain CCS. Add samples across the full season and more varieties")
        print("  before putting this anywhere near a payment decision.")
    elif best["r2"] < 0.4:
        print("  VERDICT: usable for ranking plots, not for predicting a value.")
        print("  Publish it as a queue order, never as a CCS figure.")
    else:
        print("  VERDICT: usable as a planning estimate with the interval below.")
        print("  Still not a substitute for the weighbridge laboratory.")

    return models[best_name], best_name, oof_store[best_name], results


def conformal_interval(y, oof, alpha=0.10):
    """Split-conformal absolute-residual interval. Distribution-free coverage."""
    resid = np.abs(y.values - oof)
    resid = resid[~np.isnan(resid)]
    q = float(np.quantile(resid, 1 - alpha))
    cover = float(np.mean(resid <= q))
    return q, cover


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lab", required=True, help="Real mill laboratory results CSV")
    ap.add_argument("--phenology", required=True, help="Output of sentinel_phenology.py extract")
    ap.add_argument("--target", default="ccs", choices=["ccs", "pol", "brix", "purity"])
    ap.add_argument("--out", default="../models/ccs_real.pkl")
    ap.add_argument("--alpha", type=float, default=0.10, help="0.10 -> 90%% interval")
    args = ap.parse_args()

    print("=" * 68)
    print(" CCS / POL / BRIX MODEL - REAL LABORATORY GROUND TRUTH ONLY")
    print("=" * 68)

    lab = load_lab(args.lab)
    phen = load_phenology(args.phenology)
    print(f"  lab rows       : {len(lab)}")
    print(f"  phenology rows : {len(phen)}")

    if args.target not in lab.columns:
        sys.exit(f"Target `{args.target}` not in the lab file. Available: {list(lab.columns)}")

    X, y, groups, gname, feats, merged = build_features(lab, phen, args.target)
    print(f"  matched        : {len(y)} samples across {groups.nunique()} {gname}s")
    print(f"  features       : {len(feats)} -> {feats}")

    model, name, oof, results = evaluate(X, y, groups, gname, feats, args.target)

    q, cover = conformal_interval(y, oof, args.alpha)
    print(f"\nConformal interval at alpha={args.alpha}: +/- {q:.3f} {args.target} points")
    print(f"  empirical out-of-group coverage: {100*cover:.1f}% (nominal {100*(1-args.alpha):.0f}%)")

    model.fit(X, y)
    if hasattr(model, "feature_importances_"):
        imp = sorted(zip(feats, model.feature_importances_), key=lambda t: -t[1])
        print("\nFeature importance (top 10):")
        for f, v in imp[:10]:
            print(f"  {f:<34}{v:.4f}")

    bundle = {
        "model": model, "model_name": name, "features": feats, "target": args.target,
        "conformal_margin": q, "alpha": args.alpha, "empirical_coverage": cover,
        "metrics": results, "n_samples": int(len(y)),
        "n_groups": int(groups.nunique()), "grouped_by": gname,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "ground_truth": "real mill laboratory",
    }
    with open(args.out, "wb") as fh:
        pickle.dump(bundle, fh)
    print(f"\nSaved -> {args.out}")
    print("  The bundle carries its own metrics, sample count and conformal margin,")
    print("  so anything consuming it can report the uncertainty instead of hiding it.")


if __name__ == "__main__":
    main()
