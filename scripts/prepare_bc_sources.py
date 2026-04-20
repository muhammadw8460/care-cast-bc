from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

MSP_FILE = RAW_DIR / "bc_msp_population_practitioners_services_lha.csv"
INDIGENOUS_FILE = RAW_DIR / "bc_indigenous_population_health_geographies.csv"
COVID_FILE = RAW_DIR / "bccdc_covid_case_details.csv"

OUT_WORKFORCE = RAW_DIR / "workforce_supply.csv"
OUT_POPULATION = RAW_DIR / "population_indicators.csv"
OUT_DEMAND = RAW_DIR / "demand_indicators.csv"

HA_NAMES = ["Fraser", "Interior", "Northern", "Vancouver Coastal", "Vancouver Island"]


def normalize_region(value: str) -> str:
    text = str(value).strip()
    if "-" in text and text.split("-", 1)[0].strip().isdigit():
        text = text.split("-", 1)[1].strip()
    text = text.replace("Health Authority", "").strip()
    return text


def build_population() -> pd.DataFrame:
    df = pd.read_csv(INDIGENOUS_FILE)
    pop = df[
        (df["Region.Type"] == "Health Authority") & (df["Gender"] == "Total")
    ][["Year", "Region.Name", "Total - Indigenous"]].copy()

    pop = (
        pop.rename(
            columns={
                "Year": "year",
                "Region.Name": "health_authority",
                "Total - Indigenous": "population_total",
            }
        )
        .groupby(["year", "health_authority"], as_index=False)["population_total"]
        .sum()
    )

    pop["health_authority"] = pop["health_authority"].apply(normalize_region)
    pop = pop[pop["health_authority"].isin(HA_NAMES)]

    pop["year"] = pd.to_numeric(pop["year"], errors="coerce").astype("Int64")
    pop["population_total"] = pd.to_numeric(pop["population_total"], errors="coerce")
    pop = pop.dropna(subset=["year", "population_total"])
    pop = pop.sort_values(["year", "health_authority"]).reset_index(drop=True)
    return pop


def build_workforce(pop: pd.DataFrame) -> pd.DataFrame:
    msp = pd.read_csv(MSP_FILE)
    msp = msp[msp["HA"].notna()].copy()
    msp["health_authority"] = msp["HA"].apply(normalize_region)
    msp = msp[msp["health_authority"].isin(HA_NAMES)]

    profession_cols = {
        "GP_DOCTORS": "General Practitioners",
        "SPEC_DOCTORS": "Medical Specialists",
        "SUPP_DOCTORS": "Other Practitioners",
    }

    for col in profession_cols:
        msp[col] = pd.to_numeric(msp[col], errors="coerce").fillna(0)

    base_counts = (
        msp.groupby("health_authority", as_index=False)[list(profession_cols.keys())]
        .sum()
        .copy()
    )

    pop_2011 = (
        pop[pop["year"] == 2011][["health_authority", "population_total"]]
        .set_index("health_authority")
        .to_dict()["population_total"]
    )

    ratio_rows = []
    for _, row in base_counts.iterrows():
        region = row["health_authority"]
        denom = pop_2011.get(region)
        if not denom or denom == 0:
            continue
        ratio_rows.append(
            {
                "health_authority": region,
                "gp_ratio": float(row["GP_DOCTORS"]) / float(denom),
                "spec_ratio": float(row["SPEC_DOCTORS"]) / float(denom),
                "supp_ratio": float(row["SUPP_DOCTORS"]) / float(denom),
            }
        )

    ratio_df = pd.DataFrame(ratio_rows)
    if ratio_df.empty:
        raise ValueError("Could not build workforce ratios from source files.")

    merged = pop.merge(ratio_df, on="health_authority", how="inner")
    records = []
    for _, row in merged.iterrows():
        estimates = {
            "General Practitioners": row["population_total"] * row["gp_ratio"],
            "Medical Specialists": row["population_total"] * row["spec_ratio"],
            "Other Practitioners": row["population_total"] * row["supp_ratio"],
        }
        for profession, count in estimates.items():
            records.append(
                {
                    "health_authority": row["health_authority"],
                    "profession_name": profession,
                    "year": int(row["year"]),
                    "count": float(round(count, 2)),
                }
            )

    workforce = pd.DataFrame(records)
    workforce = workforce.sort_values(["year", "health_authority", "profession_name"]).reset_index(
        drop=True
    )
    return workforce


def build_demand() -> pd.DataFrame:
    covid = pd.read_csv(COVID_FILE)
    covid["health_authority"] = covid["HA"].apply(normalize_region)
    covid = covid[covid["health_authority"].isin(HA_NAMES)].copy()

    covid["reported_date"] = pd.to_datetime(covid["Reported_Date"], errors="coerce")
    covid["year"] = covid["reported_date"].dt.year

    demand = (
        covid.dropna(subset=["year", "health_authority"])
        .groupby(["year", "health_authority"], as_index=False)
        .size()
        .rename(columns={"size": "demand_index"})
    )

    demand["year"] = demand["year"].astype(int)
    demand = demand.sort_values(["year", "health_authority"]).reset_index(drop=True)
    return demand


def main() -> None:
    missing = [p for p in [MSP_FILE, INDIGENOUS_FILE, COVID_FILE] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required source files: {missing}")

    population = build_population()
    workforce = build_workforce(population)
    demand = build_demand()

    population.to_csv(OUT_POPULATION, index=False)
    workforce.to_csv(OUT_WORKFORCE, index=False)
    demand.to_csv(OUT_DEMAND, index=False)

    print(f"Saved: {OUT_POPULATION}")
    print(f"Saved: {OUT_WORKFORCE}")
    print(f"Saved: {OUT_DEMAND}")


if __name__ == "__main__":
    main()
