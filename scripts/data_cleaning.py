import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

CANONICAL_COLUMNS = {
    "year": ["year", "fiscal_year", "reporting_year"],
    "region": ["region", "health_authority", "ha", "authority"],
    "profession": ["profession", "occupation", "role", "discipline"],
    "workforce_supply": ["workforce_supply", "supply", "count", "fte"],
    "population": ["population", "population_total", "pop"],
    "demand_indicator": ["demand_indicator", "demand_index", "service_demand"],
}


def to_snake_case(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in text.strip().lower())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


def apply_canonical_mapping(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: Dict[str, str] = {}
    current_cols = set(df.columns)
    for canonical, aliases in CANONICAL_COLUMNS.items():
        for alias in aliases:
            alias_norm = to_snake_case(alias)
            if alias_norm in current_cols and alias_norm != canonical:
                rename_map[alias_norm] = canonical
                break
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def load_dataset(spec: Dict[str, Any], root: Path) -> pd.DataFrame:
    source = spec.get("source", "csv").lower()
    if source == "csv":
        csv_path = root / spec["path"]
        return pd.read_csv(csv_path)

    if source == "sqlite":
        db_path = root / spec["database_path"]
        query = spec.get("query")
        if not query:
            raise ValueError(f"Dataset '{spec.get('name', 'unknown')}' requires a SQL query.")
        with sqlite3.connect(db_path) as conn:
            return pd.read_sql_query(query, conn)

    raise ValueError(f"Unsupported source type: {source}")


def clean_dataframe(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [to_snake_case(c) for c in df.columns]
    df = apply_canonical_mapping(df)

    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    for text_col in ["region", "profession"]:
        if text_col in df.columns:
            df[text_col] = (
                df[text_col]
                .astype(str)
                .str.strip()
                .replace({"": np.nan, "nan": np.nan, "None": np.nan})
            )

    for num_col in ["workforce_supply", "population", "demand_indicator"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

    key_cols = [c for c in ["year", "region", "profession"] if c in df.columns]
    if key_cols:
        df = df.drop_duplicates(subset=key_cols)

    if "year" in df.columns:
        df = df[df["year"].notna()]

    # Fill numerical gaps with grouped medians first, then global median.
    group_cols = [c for c in ["region", "profession"] if c in df.columns]
    for num_col in ["workforce_supply", "population", "demand_indicator"]:
        if num_col not in df.columns:
            continue
        if group_cols:
            med = df.groupby(group_cols)[num_col].transform("median")
            df[num_col] = df[num_col].fillna(med)
        df[num_col] = df[num_col].fillna(df[num_col].median())

    if "region" in df.columns:
        df["region"] = df["region"].str.title()

    if "profession" in df.columns:
        df["profession"] = df["profession"].str.title()

    return df


def summarize_quality(raw_df: pd.DataFrame, clean_df: pd.DataFrame, name: str) -> Dict[str, Any]:
    missing_before = raw_df.isna().sum().to_dict()
    missing_after = clean_df.isna().sum().to_dict()

    return {
        "dataset": name,
        "rows_before": int(len(raw_df)),
        "rows_after": int(len(clean_df)),
        "dropped_rows": int(len(raw_df) - len(clean_df)),
        "columns_after": list(clean_df.columns),
        "missing_values_before": {k: int(v) for k, v in missing_before.items()},
        "missing_values_after": {k: int(v) for k, v in missing_after.items()},
    }


def run_pipeline(manifest_path: Path, output_dir: Path, quality_report_path: Path) -> None:
    root = manifest_path.parent.parent
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    datasets: List[Dict[str, Any]] = manifest.get("datasets", [])
    if not datasets:
        raise ValueError("No datasets found in manifest.")

    output_dir.mkdir(parents=True, exist_ok=True)
    quality_report_path.parent.mkdir(parents=True, exist_ok=True)

    quality_log: List[Dict[str, Any]] = []

    for spec in datasets:
        name = spec.get("name", "dataset")
        raw_df = load_dataset(spec, root)

        if "column_map" in spec and isinstance(spec["column_map"], dict):
            mapped = {to_snake_case(k): to_snake_case(v) for k, v in spec["column_map"].items()}
            raw_df = raw_df.rename(columns=mapped)

        clean_df = clean_dataframe(raw_df, name)
        clean_path = output_dir / f"{name}_clean.csv"
        clean_df.to_csv(clean_path, index=False)

        quality_log.append(summarize_quality(raw_df, clean_df, name))
        print(f"Saved: {clean_path}")

    with quality_report_path.open("w", encoding="utf-8") as f:
        json.dump({"quality_summary": quality_log}, f, indent=2)

    print(f"Saved: {quality_report_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load, clean, and standardize allied health workforce datasets."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("config/datasets.example.json"),
        help="Path to dataset manifest JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directory where cleaned datasets are written.",
    )
    parser.add_argument(
        "--quality-report",
        type=Path,
        default=Path("outputs/reports/data_quality_report.json"),
        help="Path to write data quality report JSON.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(args.manifest, args.output_dir, args.quality_report)
