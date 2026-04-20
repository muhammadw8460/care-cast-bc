from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


REQUIRED_FILES = {
    "analytical": "data/processed/analytical_dataset.csv",
    "quality": "outputs/reports/data_quality_report.json",
    "forecast": "outputs/reports/workforce_forecast.csv",
    "regression": "outputs/reports/regression_predictions.csv",
}


REQUIRED_COLUMNS = {
    "analytical": ["year", "region", "profession", "workforce_supply"],
    "forecast": [
        "region",
        "profession",
        "year",
        "predicted_supply",
        "lower",
        "upper",
        "selected_model",
        "uncertainty_width",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate pipeline output artifacts.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Project root path.",
    )
    return parser.parse_args()


def ensure_files(root: Path) -> list[str]:
    errors: list[str] = []
    for label, rel_path in REQUIRED_FILES.items():
        full = root / rel_path
        if not full.exists():
            errors.append(f"Missing required file: {rel_path}")
            continue
        if full.is_file() and full.stat().st_size == 0:
            errors.append(f"Empty file: {rel_path}")
    return errors


def ensure_columns(df: pd.DataFrame, required: list[str], label: str) -> list[str]:
    missing = [col for col in required if col not in df.columns]
    if missing:
        return [f"{label} missing columns: {', '.join(missing)}"]
    return []


def validate_analytical(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if df.empty:
        errors.append("Analytical dataset is empty")
        return errors

    if df["year"].isna().any():
        errors.append("Analytical dataset has null year values")

    if (pd.to_numeric(df["workforce_supply"], errors="coerce") < 0).any():
        errors.append("Analytical dataset has negative workforce_supply")

    return errors


def validate_forecast(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if df.empty:
        errors.append("Forecast dataset is empty")
        return errors

    for col in ["predicted_supply", "lower", "upper", "uncertainty_width"]:
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.isna().any():
            errors.append(f"Forecast column '{col}' has non-numeric values")

    numeric_lower = pd.to_numeric(df["lower"], errors="coerce")
    numeric_upper = pd.to_numeric(df["upper"], errors="coerce")
    numeric_pred = pd.to_numeric(df["predicted_supply"], errors="coerce")
    numeric_width = pd.to_numeric(df["uncertainty_width"], errors="coerce")

    if (numeric_upper < numeric_lower).any():
        errors.append("Forecast has rows where upper < lower")

    if ((numeric_pred < numeric_lower) | (numeric_pred > numeric_upper)).any():
        errors.append("Forecast has rows where prediction is outside uncertainty bounds")

    if (numeric_width < 0).any():
        errors.append("Forecast has negative uncertainty_width")

    if df["selected_model"].isna().any():
        errors.append("Forecast has missing selected_model values")

    return errors


def main() -> int:
    args = parse_args()
    root = args.root.resolve()

    errors = ensure_files(root)
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        return 1

    analytical = pd.read_csv(root / REQUIRED_FILES["analytical"])
    forecast = pd.read_csv(root / REQUIRED_FILES["forecast"])

    errors.extend(ensure_columns(analytical, REQUIRED_COLUMNS["analytical"], "analytical"))
    errors.extend(ensure_columns(forecast, REQUIRED_COLUMNS["forecast"], "forecast"))

    if not errors:
        errors.extend(validate_analytical(analytical))
        errors.extend(validate_forecast(forecast))

    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        return 1

    print("Validation passed.")
    print(f"Analytical rows: {len(analytical)}")
    print(f"Forecast rows: {len(forecast)}")
    print(f"Forecast years: {int(forecast['year'].min())} to {int(forecast['year'].max())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
