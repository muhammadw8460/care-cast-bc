# Allied Health Workforce Forecasting Model (Care Cast BC)

A reproducible forecasting pipeline for allied health workforce planning across BC health authorities. The project ingests public data, standardizes and integrates datasets, and produces regression and trend-based workforce projections with chart and report outputs.

## Project Status

Working baseline complete and validated locally.

## What This Project Does

- Ingests workforce, population, and demand-proxy datasets
- Cleans and standardizes schema (year, region, profession, metrics)
- Integrates cleaned tables into one analytical dataset
- Runs statistical modeling in R for baseline forecasting
- Exports chart and report artifacts for technical and non-technical review

## Validated Run Snapshot

Latest successful run in this repository produced:

- Integrated dataset: 540 rows, 6 columns
- Forecast dataset: 75 rows
- Forecast years: 2047 to 2051

## Pipeline Architecture

Data Sources -> Data Cleaning -> Data Integration -> Modeling -> Visualization -> Reporting

## Repository Layout

- data/raw: original and normalized input datasets
- data/processed: cleaned and integrated outputs
- scripts/prepare_bc_sources.py: prepares normalized inputs from raw BC sources
- scripts/data_cleaning.py: cleaning and standardization pipeline
- scripts/data_integration.sql: integration SQL logic
- scripts/run_integration.py: executes integration SQL via DuckDB and exports analytical dataset
- scripts/modeling.R: regression and trend forecasting + chart/report generation
- outputs/charts: generated visualizations
- outputs/reports: generated reports and forecast tables
- config/datasets.example.json: data source and column mapping manifest

## Prerequisites

- Python 3.10+
- R 4.2+
- PowerShell (for Windows commands below)

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

Install required R packages once:

```r
install.packages(c("dplyr", "ggplot2", "readr", "tidyr"))
```

## End-to-End Run

From project root, run in this order:

```powershell
python scripts/prepare_bc_sources.py
python scripts/data_cleaning.py --manifest config/datasets.example.json
python scripts/run_integration.py
Rscript scripts/modeling.R data/processed/analytical_dataset.csv outputs 5
```

## Dashboard Delivery Layer

An interactive Streamlit dashboard is included for communicating trends to technical and non-technical audiences.

Dashboard features:

- Region, profession, and year-range filtering
- Historical workforce trend visualization
- Supply vs demand-proxy trend chart
- Region/profession forecast view with uncertainty band
- Data quality summary table
- Download of filtered analytical data

Run the dashboard:

```powershell
pwsh scripts/start_dashboard.ps1
```

Then open:

- http://localhost:8501

## Expected Outputs

After a successful run, you should see:

- data/processed/workforce_clean.csv
- data/processed/population_clean.csv
- data/processed/demand_clean.csv
- data/processed/analytical_dataset.csv
- outputs/reports/data_quality_report.json
- outputs/reports/regression_summary.txt
- outputs/reports/regression_predictions.csv
- outputs/reports/workforce_forecast.csv
- outputs/reports/run_status.txt
- outputs/charts/supply_trends_by_region.png
- outputs/charts/supply_vs_demand_proxy.png
- interactive dashboard at dashboard/app.py

## Data Notes

- Input files are expected under data/raw.
- Source normalization and mapping are controlled through scripts/prepare_bc_sources.py and config/datasets.example.json.
- The integration workflow uses DuckDB for local reproducibility.

## Assumptions and Limitations

- This is a baseline statistical model for planning support, not a production clinical decision system.
- Workforce time trend is derived from available public source structure and proxy scaling.
- Results should be interpreted with policy and domain context.

## Troubleshooting

- If Python imports fail:

```powershell
python -m pip install -r requirements.txt
```

- If Rscript is not found on Windows, use full executable path:

```powershell
& "C:\Program Files\R\R-4.3.1\bin\Rscript.exe" scripts/modeling.R data/processed/analytical_dataset.csv outputs 5
```

- R package build-version warnings are often non-fatal if output files are still generated.

## Future Enhancements

- Add dashboard delivery layer
- Add richer forecasting models and uncertainty treatment
- Automate periodic data refresh and validation
