from pathlib import Path

import duckdb


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    con = duckdb.connect()
    con.execute(
        "CREATE OR REPLACE TABLE workforce_clean AS SELECT * FROM read_csv_auto('data/processed/workforce_clean.csv')"
    )
    con.execute(
        "CREATE OR REPLACE TABLE population_clean AS SELECT * FROM read_csv_auto('data/processed/population_clean.csv')"
    )
    con.execute(
        "CREATE OR REPLACE TABLE demand_clean AS SELECT * FROM read_csv_auto('data/processed/demand_clean.csv')"
    )

    sql = (root / "scripts" / "data_integration.sql").read_text(encoding="utf-8")
    integrated = con.execute(sql).df()

    output_path = root / "data" / "processed" / "analytical_dataset.csv"
    integrated.to_csv(output_path, index=False)

    print(f"Saved: {output_path}")
    print(f"Rows: {len(integrated)}")
    print(f"Columns: {len(integrated.columns)}")


if __name__ == "__main__":
    main()
