from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYTICAL_PATH = PROJECT_ROOT / "data" / "processed" / "analytical_dataset.csv"
FORECAST_PATH = PROJECT_ROOT / "outputs" / "reports" / "workforce_forecast.csv"
QUALITY_PATH = PROJECT_ROOT / "outputs" / "reports" / "data_quality_report.json"


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return pd.read_csv(path)


def load_quality(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(str(path))

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    entries = payload.get("quality_summary", [])
    if not entries:
        return pd.DataFrame()

    return pd.DataFrame(entries)


def apply_filters(df: pd.DataFrame, regions: list[str], professions: list[str], year_range: tuple[int, int]) -> pd.DataFrame:
    filtered = df.copy()
    if regions:
        filtered = filtered[filtered["region"].isin(regions)]
    if professions:
        filtered = filtered[filtered["profession"].isin(professions)]
    filtered = filtered[(filtered["year"] >= year_range[0]) & (filtered["year"] <= year_range[1])]
    return filtered


def main() -> None:
    st.set_page_config(page_title="Care Cast BC Dashboard", layout="wide")
    st.title("Care Cast BC Workforce Dashboard")
    st.caption("Historical workforce and demand trends with forecast visualization.")

    try:
        analytical = load_csv(ANALYTICAL_PATH)
        forecast = load_csv(FORECAST_PATH)
        quality = load_quality(QUALITY_PATH)
    except FileNotFoundError as exc:
        st.error("Missing required output files.")
        st.info("Run the pipeline before launching the dashboard:\n"
                "1) python scripts/prepare_bc_sources.py\n"
                "2) python scripts/data_cleaning.py --manifest config/datasets.example.json\n"
                "3) python scripts/run_integration.py\n"
                "4) Rscript scripts/modeling.R data/processed/analytical_dataset.csv outputs 5")
        st.code(str(exc), language="text")
        return

    analytical["year"] = analytical["year"].astype(int)

    all_regions = sorted(analytical["region"].dropna().unique().tolist())
    all_professions = sorted(analytical["profession"].dropna().unique().tolist())
    min_year = int(analytical["year"].min())
    max_year = int(analytical["year"].max())

    with st.sidebar:
        st.header("Filters")
        selected_regions = st.multiselect("Region", all_regions, default=all_regions)
        selected_professions = st.multiselect("Profession", all_professions, default=all_professions)
        selected_years = st.slider("Year range", min_year, max_year, (min_year, max_year))

    filtered = apply_filters(analytical, selected_regions, selected_professions, selected_years)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rows", f"{len(filtered):,}")
    col2.metric("Regions", f"{filtered['region'].nunique()}")
    col3.metric("Professions", f"{filtered['profession'].nunique()}")
    col4.metric("Years", f"{filtered['year'].min()}-{filtered['year'].max()}")

    st.subheader("Historical Workforce Supply")
    history = (
        filtered.groupby(["year", "region"], as_index=False)["workforce_supply"]
        .sum()
        .sort_values(["year", "region"])
    )
    fig_history = px.line(
        history,
        x="year",
        y="workforce_supply",
        color="region",
        markers=True,
        labels={"workforce_supply": "Workforce supply", "year": "Year"},
    )
    st.plotly_chart(fig_history, use_container_width=True)

    st.subheader("Supply vs Demand Proxy")
    demand = (
        filtered.groupby("year", as_index=False)
        .agg(supply=("workforce_supply", "sum"), demand=("demand_indicator", "sum"))
        .sort_values("year")
    )
    fig_demand = go.Figure()
    fig_demand.add_trace(go.Scatter(x=demand["year"], y=demand["supply"], mode="lines+markers", name="Supply"))
    fig_demand.add_trace(go.Scatter(x=demand["year"], y=demand["demand"], mode="lines+markers", name="Demand proxy"))
    fig_demand.update_layout(xaxis_title="Year", yaxis_title="Value")
    st.plotly_chart(fig_demand, use_container_width=True)

    st.subheader("Forecast by Region and Profession")
    f_region = st.selectbox("Forecast region", sorted(forecast["region"].unique().tolist()))
    f_profession = st.selectbox("Forecast profession", sorted(forecast["profession"].unique().tolist()))

    hist_series = (
        analytical[(analytical["region"] == f_region) & (analytical["profession"] == f_profession)]
        .groupby("year", as_index=False)["workforce_supply"]
        .sum()
        .sort_values("year")
    )
    forecast_series = forecast[(forecast["region"] == f_region) & (forecast["profession"] == f_profession)].sort_values("year")

    fig_forecast = go.Figure()
    fig_forecast.add_trace(
        go.Scatter(
            x=hist_series["year"],
            y=hist_series["workforce_supply"],
            mode="lines+markers",
            name="Historical supply",
        )
    )
    fig_forecast.add_trace(
        go.Scatter(
            x=forecast_series["year"],
            y=forecast_series["predicted_supply"],
            mode="lines+markers",
            name="Forecast",
        )
    )
    fig_forecast.add_trace(
        go.Scatter(
            x=forecast_series["year"],
            y=forecast_series["upper"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
        )
    )
    fig_forecast.add_trace(
        go.Scatter(
            x=forecast_series["year"],
            y=forecast_series["lower"],
            mode="lines",
            fill="tonexty",
            name="Prediction interval",
            line=dict(width=0),
            fillcolor="rgba(0, 120, 212, 0.2)",
        )
    )
    fig_forecast.update_layout(xaxis_title="Year", yaxis_title="Supply")
    st.plotly_chart(fig_forecast, use_container_width=True)

    st.subheader("Data Quality Summary")
    if quality.empty:
        st.info("No data quality summary found.")
    else:
        preview_cols = ["dataset", "rows_before", "rows_after", "dropped_rows"]
        present = [col for col in preview_cols if col in quality.columns]
        st.dataframe(quality[present], use_container_width=True)

    st.subheader("Download Current Data")
    st.download_button(
        label="Download filtered analytical data (CSV)",
        data=filtered.to_csv(index=False),
        file_name="filtered_analytical_dataset.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
