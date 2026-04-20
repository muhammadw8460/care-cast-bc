from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve

SOURCE_URLS = {
    "bc_msp_population_practitioners_services_lha.csv": "https://catalogue.data.gov.bc.ca/dataset/4d069bae-6f10-4f74-ac98-f9ede8481600/resource/153f4ca5-6841-4850-aa02-9817af73f0fc/download/bchealthpopulationpractitionersservicesandexpendituresbylocalhealthauthority.csv",
    "bc_subprov_population_estimates_projections.csv": "https://catalogue.data.gov.bc.ca/dataset/86839277-986a-4a29-9f70-fa9b1166f6cb/resource/9e9679be-8f3d-42c0-b1ca-a4bb471d96f6/download/children-and-family-development-population.csv",
    "bc_indigenous_population_health_geographies.csv": "https://catalogue.data.gov.bc.ca/dataset/594ac924-967f-4a4d-8af2-91513ad8b903/resource/c4e30ab3-0239-4e26-b4b6-b32a35afe5b8/download/indigenous_population_estimates_projections_bc_subprov.csv",
    "bccdc_covid_case_details.csv": "http://www.bccdc.ca/Health-Info-Site/Documents/BCCDC_COVID19_Dashboard_Case_Details.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch BC public source files into data/raw.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even if they already exist.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    raw_dir = root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for filename, url in SOURCE_URLS.items():
        target = raw_dir / filename
        if target.exists() and not args.force:
            print(f"Skipped (exists): {target}")
            continue

        print(f"Downloading: {url}")
        urlretrieve(url, target)
        print(f"Saved: {target}")


if __name__ == "__main__":
    main()
