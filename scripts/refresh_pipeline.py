from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_step(name: str, command: list[str], cwd: Path) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{timestamp}] START: {name}")
    print("Command:", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{timestamp}] DONE: {name}\n")


def resolve_rscript() -> str:
    env_value = os.environ.get("RSCRIPT_BIN")
    if env_value:
        return env_value

    which_value = shutil.which("Rscript")
    if which_value:
        return which_value

    common_windows_paths = [
        Path("C:/Program Files/R/R-4.3.1/bin/Rscript.exe"),
        Path("C:/Program Files/R/R-4.3.1/bin/x64/Rscript.exe"),
        Path("C:/Program Files/R/R-4.4.0/bin/Rscript.exe"),
        Path("C:/Program Files/R/R-4.4.0/bin/x64/Rscript.exe"),
    ]
    for p in common_windows_paths:
        if p.exists():
            return str(p)

    return "Rscript"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run periodic refresh: fetch, prepare, clean, integrate, model, validate."
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=5,
        help="Forecast horizon in years for modeling.R",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip fetching BC source files before refresh.",
    )
    parser.add_argument(
        "--skip-model",
        action="store_true",
        help="Skip R modeling step.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]

    python_exe = sys.executable
    rscript_exe = resolve_rscript()

    try:
        if not args.skip_fetch:
            run_step(
                "Fetch BC source datasets",
                [python_exe, "scripts/fetch_bc_sources.py", "--force"],
                root,
            )

        run_step(
            "Prepare normalized source files",
            [python_exe, "scripts/prepare_bc_sources.py"],
            root,
        )

        run_step(
            "Clean and standardize datasets",
            [python_exe, "scripts/data_cleaning.py", "--manifest", "config/datasets.example.json"],
            root,
        )

        run_step(
            "Integrate analytical dataset",
            [python_exe, "scripts/run_integration.py"],
            root,
        )

        if not args.skip_model:
            run_step(
                "Run forecasting and reporting model",
                [
                    rscript_exe,
                    "scripts/modeling.R",
                    "data/processed/analytical_dataset.csv",
                    "outputs",
                    str(args.horizon),
                ],
                root,
            )

        run_step(
            "Validate generated outputs",
            [python_exe, "scripts/validate_outputs.py"],
            root,
        )

    except subprocess.CalledProcessError as exc:
        print(f"Pipeline failed at command: {' '.join(exc.cmd)}")
        return exc.returncode

    print("Refresh pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
