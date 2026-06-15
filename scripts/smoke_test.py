"""Quick health check for the FielCup project.

This script is intentionally small: it verifies that the committed database and
core modelling modules are usable, then runs a tiny Monte Carlo simulation.
"""

from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DB = ROOT / "db" / "fielcup.db"

sys.path.insert(0, str(SRC))


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path.relative_to(ROOT)}")


def table_count(name: str) -> int:
    with sqlite3.connect(DB) as con:
        row = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()
    return int(row[0])


def main() -> None:
    required_files = [
        ROOT / "data" / "raw" / "results.csv",
        ROOT / "data" / "processed" / "copa2026.csv",
        ROOT / "data" / "processed" / "grupos.csv",
        ROOT / "data" / "reference" / "talento_2026.csv",
        DB,
    ]
    for path in required_files:
        require_file(path)

    required_tables = {
        "matches": 1000,
        "fixtures_2026": 1,
        "groups": 1,
        "teams_reference": 1,
        "team_ratings": 1,
    }
    for table, minimum in required_tables.items():
        count = table_count(table)
        if count < minimum:
            raise AssertionError(f"Table {table} has {count} rows; expected >= {minimum}")
        print(f"OK table {table}: {count:,} rows")

    from simulate import simular

    result = simular(alpha=0.6, sims=200, seed=7)
    if result.empty:
        raise AssertionError("Simulation returned no rows")

    title_sum = float(result["prob_titulo"].sum())
    if abs(title_sum - 1.0) > 1e-9:
        raise AssertionError(f"Title probabilities sum to {title_sum:.6f}, expected 1.0")

    top = result.iloc[0]
    print(
        "OK simulation: "
        f"{top['selecao']} leads with {top['prob_titulo'] * 100:.1f}% "
        "in a 200-run smoke test"
    )
    print("FielCup smoke test passed.")


if __name__ == "__main__":
    main()
