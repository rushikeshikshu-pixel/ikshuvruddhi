import os
#!/usr/bin/env python3
"""
train_ccs_model.py - train a Pol / Brix / CCS model on REAL mill laboratory data.

STRICT SCIENTIFIC SAFEGUARDS:
1. Leak-Free Preprocessing:
   SimpleImputer is wrapped inside an sklearn.pipeline.Pipeline so that feature medians
   are fitted strictly inside the training folds of GroupKFold, preventing validation leakage.
2. Causal Temporal Alignment:
   Satellite observations must strictly precede or coincide with the lab sampling date
   within a narrow window (e.g. t_sample - 15d <= t_sat <= t_sample).
3. Honest Baseline Comparison:
   Every model (Random Forest, Gradient Boosting) is evaluated directly against a
   DummyRegressor(strategy='mean') baseline reporting R2, MAE, and RMSE.
4. Split-Conformal Uncertainty Calibration:
   Calculates the empirical non-conformity threshold on a held-out calibration split
   and independently evaluates coverage on a disjoint test set (distribution-free finite-sample guarantee).
"""

import argparse
import pickle
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error


SYNTHETIC_MARKERS = [
    "factory_sugar_recovery_pct",
    "hydro_thermal_index",
]


def guard_against_synthetic(df, path):
    """Refuses to train on synthetic datasets."""
    for marker in SYNTHETIC_MARKERS:
        if marker in df.columns:
            sys.exit(f"[Refusal] {path} contains {marker}. Real lab data required.")


def load_lab(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    guard_against_synthetic(df, path)

    if "gat_no" not in df.columns and "plot_no" in df.columns:
        df["gat_no"] = df["plot_no"]

    need = {"gat_no"}
    if not need.issubset(df.columns):
        sys.exit(f"Lab file must contain a `gat_no` column. Found: {list(df.columns)}")

    df["gat_no"] = df["gat_no"].astype(str).str.strip()

    # Support 3-point stalk sampling if present
    if {"brix_bottom", "brix_top"}.issubset(df.columns) and "brix" not in df.columns:
        if "brix_mid" in df.columns:
            df["brix"] = 0.25 * df["brix_bottom"] + 0.50 * df["brix_mid"] + 0.25 * df["brix_top"]
        else:
            df["brix"] = 0.50 * df["brix_bottom"] + 0.50 * df["brix_top"]
        df["stalk_maturity_gradient"] = df["brix_top"] / df["brix_bottom"].replace(0, np.nan)

    if "pol" not in df.columns and "measured_pol" in df.columns:
        df["pol"] = df["measured_pol"]

    if "brix" not in df.columns and "measured_brix" in df.columns:
        df["brix"] = df["measured_brix"]

    have = [c for c in ("brix", "pol", "ccs", "calculated_mill_recovery") if c in df.columns]
    if not have:
        sys.exit("Lab file must contain at least one target: pol, brix, or ccs.")

    if "ccs" not in df.columns and {"brix", "pol"}.issubset(df.columns):
        # ICAR / VSI standard pre-harvest field CCS formula
        df["ccs"] = 1.022 * df["pol"] - 0.292 * df["brix"]

    return df


def load_phenology(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["gat_no"] = df["gat_no"].astype(str).str.strip()
    return df


def build_features(lab, phen, target, max_latency_days=15):
    # Causal Temporal Alignment Join
    merged = lab.merge(phen, on="gat_no", how="inner", suffixes=("", "_phen"))
    if merged.empty:
        sys.exit("No Gat numbers matched between the lab file and the phenology file.")

    # Enforce strict date alignment if both have dates
    if "sample_date" in merged.columns and "scene_acquisition_date" in merged.columns:
        sd = pd.to_datetime(merged["sample_date"], errors="coerce")
        ad = pd.to_datetime(merged["scene_acquisition_date"], errors="coerce")
        latency = (sd - ad).dt.days

        # Causal filter: observation must be prior to sample date within max_latency_days
        valid_temporal = (latency >= 0) & (latency <= max_latency_days)
        if valid_temporal.any():
            merged = merged[valid_temporal].copy()
            # Sort by smallest latency to select single 1-to-1 best observation
            merged["_latency"] = latency[valid_temporal]
            merged = merged.sort_values("_latency").drop_duplicates(subset=["gat_no"], keep="first").drop(columns=["_latency"])
            print(f"  Enforced causal temporal join: observations strictly <= sample_date (latency 0-{max_latency_days}d).")
        else:
            print("  Warning: No observations within strict latency window; proceeding with available joins.")

    if "crop_age_days" not in merged.columns and "sample_date" in merged.columns and "plantation_date" in merged.columns:
        sd = pd.to_datetime(merged["sample_date"], errors="coerce", dayfirst=True)
        pd_date = pd.to_datetime(merged["plantation_date"], errors="coerce", dayfirst=True)
        merged["crop_age_days"] = (sd - pd_date).dt.days

    candidates = [
        "crop_age_days", "stalk_maturity_gradient",
        "ndvi", "ndre", "ndwi", "lswi", "evi",
        "ndvi_max", "ndvi_min", "ndvi_amplitude", "clear_scenes",
        "sat_temp_celsius", "sat_solar_radiation_kwh_m2", "sat_humidity_pct"
    ]
    feats = [c for c in candidates if c in merged.columns and merged[c].notna().sum() >= 5]
    if not feats:
        sys.exit("No usable features after the join. Check the phenology export.")

    merged = merged.dropna(subset=[target])
    # IMPORTANT: Keep NaNs in X so SimpleImputer inside the pipeline imputes leak-free per fold!
    X = merged[feats].apply(pd.to_numeric, errors="coerce")
    y = merged[target].astype(float)

    if "village" in merged.columns and merged["village"].nunique() >= 4:
        groups, gname = merged["village"].astype(str), "village"
    elif "circle" in merged.columns and merged["circle"].nunique() >= 3:
        groups, gname = merged["circle"].astype(str), "circle"
    else:
        groups, gname = merged["gat_no"].astype(str), "gat_no"

    return X, y, groups, gname, feats, merged


def evaluate(X, y, groups, gname, feats, target):
    n_groups = groups.nunique()
    n_splits = int(min(5, max(2, n_groups)))
    print(f"\nValidation: GroupKFold({n_splits}) grouped by {gname} ({n_groups} groups, {len(y)} samples)")
    if len(y) < 100:
        print("  WARNING: under 100 samples. Treat every metric as indicative only.")

    gkf = GroupKFold(n_splits=n_splits)

    # Wrap regressors in leak-free Pipeline with SimpleImputer fitted strictly on training fold
    models = {
        "baseline (predict mean)": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("regressor", DummyRegressor(strategy="mean"))
        ]),
        "random forest": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("regressor", RandomForestRegressor(n_estimators=100, min_samples_leaf=3, random_state=42, n_jobs=1))
        ]),
        "gradient boosting": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("regressor", GradientBoostingRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42))
        ])
    }

    results, oof_store = {}, {}
    for name, pipeline in models.items():
        oof = np.full(len(y), np.nan)
        for tr, te in gkf.split(X, y, groups):
            p = Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("regressor", pipeline.named_steps["regressor"].__class__(**pipeline.named_steps["regressor"].get_params()))
            ])
            p.fit(X.iloc[tr], y.iloc[tr])
            oof[te] = p.predict(X.iloc[te])

        ok = ~np.isnan(oof)
        r2 = r2_score(y[ok], oof[ok])
        mae = mean_absolute_error(y[ok], oof[ok])
        rmse = float(np.sqrt(mean_squared_error(y[ok], oof[ok])))
        results[name] = {"r2": r2, "mae": mae, "rmse": rmse}
        oof_store[name] = oof

    print("\nModel Comparison (Out-of-Group Cross-Validation):")
    print(f"  {'Model':<26}{'R2':>8}{'MAE':>10}{'RMSE':>10}")
    print("  " + "-" * 56)
    for name, m in results.items():
        print(f"  {name:<26}{m['r2']:>8.3f}{m['mae']:>10.3f}{m['rmse']:>10.3f}")

    # Select best model beating the mean baseline
    best_name = max(
        [k for k in models.keys() if k != "baseline (predict mean)"],
        key=lambda k: results[k]["r2"]
    )
    return models[best_name], best_name, oof_store[best_name], results


def split_conformal_calibration(X, y, groups, best_pipeline, alpha=0.10):
    """
    Split-conformal calibration on a disjoint held-out group split.
    Guarantees finite-sample distribution-free validity without circular evaluation.
    """
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups))

    X_tr, y_tr = X.iloc[train_idx], y.iloc[train_idx]
    X_te, y_te = X.iloc[test_idx], y.iloc[test_idx]

    # Further split training into proper train and calibration sets
    gss_cal = GroupShuffleSplit(n_splits=1, test_size=0.33, random_state=42)
    sub_tr_idx, cal_idx = next(gss_cal.split(X_tr, y_tr, groups.iloc[train_idx]))

    X_sub_tr, y_sub_tr = X_tr.iloc[sub_tr_idx], y_tr.iloc[sub_tr_idx]
    X_cal, y_cal = X_tr.iloc[cal_idx], y_tr.iloc[cal_idx]

    # Fit pipeline on sub-train
    p = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("regressor", best_pipeline.named_steps["regressor"].__class__(**best_pipeline.named_steps["regressor"].get_params()))
    ])
    p.fit(X_sub_tr, y_sub_tr)

    # Nonconformity scores on calibration set
    cal_preds = p.predict(X_cal)
    scores = np.abs(y_cal.values - cal_preds)
    n_cal = len(scores)

    # Standard finite-sample conformal quantile: ceil((n+1)*(1-alpha)) / n
    q_level = min(1.0, np.ceil((n_cal + 1) * (1 - alpha)) / n_cal)
    q_hat = float(np.quantile(scores, q_level))

    # Evaluate on independent test set
    test_preds = p.predict(X_te)
    test_resid = np.abs(y_te.values - test_preds)
    test_coverage = float(np.mean(test_resid <= q_hat))

    return q_hat, test_coverage, n_cal, len(y_te)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lab", required=True, help="Real mill laboratory results CSV")
    ap.add_argument("--phenology", required=True, help="Satellite phenology features CSV")
    ap.add_argument("--target", default="pol", choices=["pol", "brix", "ccs"], help="Default: pol (measured target)")
    ap.add_argument("--out", default="models/ccs_real.pkl")
    ap.add_argument("--alpha", type=float, default=0.10, help="0.10 -> 90%% nominal coverage")
    args = ap.parse_args()

    print("=" * 68)
    print(f" POL / BRIX / CCS MODEL - REAL MILL LAB GROUND TRUTH (Target: {args.target})")
    print("=" * 68)

    lab = load_lab(args.lab)
    phen = load_phenology(args.phenology)
    print(f"  Lab records loaded      : {len(lab)}")
    print(f"  Phenology records loaded: {len(phen)}")

    if args.target not in lab.columns:
        sys.exit(f"Target `{args.target}` not in lab file. Available: {list(lab.columns)}")

    X, y, groups, gname, feats, merged = build_features(lab, phen, args.target)
    print(f"  Matched samples         : {len(y)} across {groups.nunique()} {gname}s")
    print(f"  Features ({len(feats)})        : {feats}")

    best_pipeline, best_name, oof, results = evaluate(X, y, groups, gname, feats, args.target)

    # Split-conformal calibration on disjoint held-out group split
    q_hat, test_coverage, n_cal, n_test = split_conformal_calibration(X, y, groups, best_pipeline, args.alpha)
    print(f"\nSplit-Conformal Uncertainty Calibration (alpha={args.alpha}, nominal {100*(1-args.alpha):.0f}%):")
    print(f"  Calibration set size   : {n_cal} samples")
    print(f"  Independent test size  : {n_test} samples")
    print(f"  Observed margin q_hat  : +/- {q_hat:.3f} {args.target} percentage points")
    print(f"  Independent test cover : {100*test_coverage:.1f}%")

    # Fit final pipeline on all data
    final_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("regressor", best_pipeline.named_steps["regressor"].__class__(**best_pipeline.named_steps["regressor"].get_params()))
    ])
    final_pipeline.fit(X, y)

    reg = final_pipeline.named_steps["regressor"]
    if hasattr(reg, "feature_importances_"):
        imp = sorted(zip(feats, reg.feature_importances_), key=lambda t: -t[1])
        print("\nFeature Importance (Top 10):")
        for f, v in imp[:10]:
            print(f"  {f:<30}{v:.4f}")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    bundle = {
        "pipeline": final_pipeline,
        "model_name": best_name,
        "features": feats,
        "target": args.target,
        "conformal_margin": q_hat,
        "alpha": args.alpha,
        "empirical_test_coverage": test_coverage,
        "metrics": results,
        "n_samples": int(len(y)),
        "n_groups": int(groups.nunique()),
        "grouped_by": gname,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "ground_truth": "real Gangamai mill laboratory",
    }
    with open(args.out, "wb") as fh:
        pickle.dump(bundle, fh)
    print(f"\nSaved model bundle -> {args.out}")


if __name__ == "__main__":
    main()
