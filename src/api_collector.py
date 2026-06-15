"""FielCup API-Football collector.

Updates the project with finished 2026 World Cup matches from API-Football.

Usage:
    export API_FOOTBALL_KEY="your_key"
    python src/api_collector.py --update-results
    python src/api_collector.py --update-results --dry-run
    python src/api_collector.py --stats

The API key is read only from the environment. It is never written to disk.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import os
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

BASE_URL = "https://v3.football.api-sports.io"
DEFAULT_LEAGUE = 1
DEFAULT_SEASON = 2026
REQUEST_PAUSE_SECONDS = 2.0
FINISHED_STATUSES = {"FT", "AET", "PEN"}

API_NAME_MAP = {
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "Turkiye": "Turkey",
    "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Cabo Verde": "Cape Verde",
    "IR Iran": "Iran",
    "Korea Republic": "South Korea",
    "USA": "United States",
    "DR Congo": "DR Congo",
    "Congo DR": "DR Congo",
    "Curacao": "Curacao",
    "Curaçao": "Curacao",
}

HOST_CITY_COUNTRY = {
    "Atlanta": "United States",
    "Boston": "United States",
    "Dallas": "United States",
    "Houston": "United States",
    "Kansas City": "United States",
    "Los Angeles": "United States",
    "Miami": "United States",
    "New York": "United States",
    "New York/New Jersey": "United States",
    "New York New Jersey": "United States",
    "Philadelphia": "United States",
    "San Francisco": "United States",
    "Seattle": "United States",
    "Vancouver": "Canada",
    "Toronto": "Canada",
    "Guadalajara": "Mexico",
    "Mexico City": "Mexico",
    "Monterrey": "Mexico",
}


class ApiFootballError(RuntimeError):
    """Friendly API error for command-line and dashboard callers."""


def require_pandas():
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise ApiFootballError(
            "Missing Python package: pandas. Run:\n"
            "  pip install -r requirements.txt"
        ) from exc
    return pd


def normalise_team(name: str | None) -> str:
    """Map API-Football names to the dataset naming convention."""
    if not name:
        return ""
    return API_NAME_MAP.get(name.strip(), name.strip())


def country_for_city(city: str | None, fallback: str = "Unknown") -> str:
    if not city:
        return fallback
    city_clean = city.strip()
    return HOST_CITY_COUNTRY.get(city_clean, fallback)


def api_key() -> str:
    key = os.environ.get("API_FOOTBALL_KEY", "").strip()
    if not key:
        raise ApiFootballError(
            "Missing API_FOOTBALL_KEY. Run:\n"
            "  export API_FOOTBALL_KEY='your_real_key'\n"
            "Get a free key at https://dashboard.api-football.com/"
        )
    return key


def headers() -> dict[str, str]:
    return {"x-apisports-key": api_key()}


def get_json(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET wrapper with useful errors and free-tier friendly pacing."""
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    request_headers = headers()

    try:
        import requests
    except ModuleNotFoundError as exc:
        raise ApiFootballError(
            "Missing Python package: requests. Run:\n"
            "  pip install -r requirements.txt"
        ) from exc

    try:
        response = requests.get(url, headers=request_headers, params=params, timeout=30)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise ApiFootballError(
            f"API-Football HTTP error {status} for {endpoint}. "
            "Check your API key, daily limit and endpoint parameters."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise ApiFootballError(
            f"Could not reach API-Football ({endpoint}): {exc}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ApiFootballError("API-Football returned a non-JSON response.") from exc

    errors = payload.get("errors")
    if errors:
        raise ApiFootballError(f"API-Football returned errors: {errors}")

    time.sleep(REQUEST_PAUSE_SECONDS)
    return payload


def fixture_country(item: dict[str, Any]) -> str:
    venue = item.get("fixture", {}).get("venue") or {}
    city = venue.get("city")
    league_country = item.get("league", {}).get("country") or "Unknown"
    return country_for_city(city, fallback=league_country)


def score_from_fixture(item: dict[str, Any]) -> tuple[int | None, int | None]:
    goals = item.get("goals") or {}
    home = goals.get("home")
    away = goals.get("away")
    if home is None or away is None:
        return None, None
    return int(home), int(away)


def baixar_resultados_copa(
    season: int = DEFAULT_SEASON,
    league: int = DEFAULT_LEAGUE,
) -> pd.DataFrame:
    """Return finished World Cup matches in the same shape as results.csv."""
    payload = get_json("fixtures", {"league": league, "season": season})
    rows = []

    for item in payload.get("response", []):
        fixture = item.get("fixture", {})
        status = (fixture.get("status") or {}).get("short")
        if status not in FINISHED_STATUSES:
            continue

        home_score, away_score = score_from_fixture(item)
        if home_score is None or away_score is None:
            continue

        venue = fixture.get("venue") or {}
        rows.append(
            {
                "date": str(fixture.get("date", ""))[:10],
                "home_team": normalise_team(item.get("teams", {}).get("home", {}).get("name")),
                "away_team": normalise_team(item.get("teams", {}).get("away", {}).get("name")),
                "home_score": home_score,
                "away_score": away_score,
                "tournament": "FIFA World Cup",
                "city": venue.get("city") or "Unknown",
                "country": fixture_country(item),
                "neutral": True,
                "fixture_id": fixture.get("id"),
            }
        )

    return require_pandas().DataFrame(rows)


def key_columns(df: pd.DataFrame) -> pd.Series:
    required = ["date", "home_team", "away_team"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ApiFootballError(f"Missing required columns: {', '.join(missing)}")
    return (
        df["date"].astype(str)
        + "|"
        + df["home_team"].astype(str)
        + "|"
        + df["away_team"].astype(str)
    )


def align_to_base_columns(new_rows: pd.DataFrame, base_columns: list[str]) -> pd.DataFrame:
    pd = require_pandas()
    aligned = new_rows.copy()
    for column in base_columns:
        if column not in aligned.columns:
            aligned[column] = pd.NA
    return aligned[base_columns]


def atualizar_results_csv(
    dry_run: bool = False,
    season: int = DEFAULT_SEASON,
    league: int = DEFAULT_LEAGUE,
) -> pd.DataFrame:
    """Merge finished World Cup matches into data/raw/results.csv."""
    new_rows = baixar_resultados_copa(season=season, league=league)
    if new_rows.empty:
        print("No finished World Cup matches returned by the API.")
        return new_rows

    results_path = RAW / "results.csv"
    if not results_path.exists():
        raise ApiFootballError(f"Missing source file: {results_path}")

    pd = require_pandas()
    base = pd.read_csv(results_path)
    clean_new_rows = new_rows.drop(columns=["fixture_id"], errors="ignore")

    base_keys = set(key_columns(base))
    new_keys = key_columns(clean_new_rows)
    unique_rows = clean_new_rows[~new_keys.isin(base_keys)].copy()

    if unique_rows.empty:
        print("results.csv is already up to date.")
        return unique_rows

    print(f"Found {len(unique_rows)} new finished match(es):")
    for _, row in unique_rows.iterrows():
        print(
            "  "
            f"{row['date']} | {row['home_team']} {row['home_score']}-"
            f"{row['away_score']} {row['away_team']}"
        )

    if dry_run:
        print("Dry run only: results.csv was not changed.")
        return unique_rows

    aligned_rows = align_to_base_columns(unique_rows, list(base.columns))
    combined = pd.concat([base, aligned_rows], ignore_index=True)
    combined.to_csv(results_path, index=False)
    print(f"Added {len(unique_rows)} match(es) to {results_path}.")
    print("Next: python src/features.py && python src/dixon_coles.py && python src/simulate.py")
    return unique_rows


def baixar_estatisticas_jogo(fixture_id: int) -> pd.DataFrame:
    """Download detailed match statistics for one fixture."""
    payload = get_json("fixtures/statistics", {"fixture": fixture_id})
    rows = []
    for team_stats in payload.get("response", []):
        team_name = normalise_team((team_stats.get("team") or {}).get("name"))
        record = {"fixture_id": fixture_id, "team": team_name}
        for stat in team_stats.get("statistics", []):
            record[str(stat.get("type"))] = stat.get("value")
        rows.append(record)
    return require_pandas().DataFrame(rows)


def coletar_stats_da_copa(
    season: int = DEFAULT_SEASON,
    league: int = DEFAULT_LEAGUE,
    limit: int | None = None,
) -> pd.DataFrame:
    """Collect statistics for finished World Cup matches."""
    matches = baixar_resultados_copa(season=season, league=league)
    if matches.empty:
        print("No finished matches available for statistics.")
        return require_pandas().DataFrame()

    if limit is not None:
        matches = matches.head(limit)

    all_stats = []
    for fixture_id in matches["fixture_id"].dropna():
        all_stats.append(baixar_estatisticas_jogo(int(fixture_id)))

    if not all_stats:
        print("No statistics returned.")
        return require_pandas().DataFrame()

    pd = require_pandas()
    stats = pd.concat(all_stats, ignore_index=True)
    output = RAW / "estatisticas_copa.csv"
    stats.to_csv(output, index=False)
    print(f"Saved statistics for {len(matches)} match(es) to {output}.")
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FielCup API-Football collector")
    parser.add_argument(
        "--update-results",
        action="store_true",
        help="Update data/raw/results.csv with finished World Cup matches",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Collect detailed statistics for finished matches",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show new matches without writing to results.csv",
    )
    parser.add_argument("--season", type=int, default=DEFAULT_SEASON)
    parser.add_argument("--league", type=int, default=DEFAULT_LEAGUE)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of fixtures when collecting statistics",
    )
    return parser


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def main() -> int:
    args = parse_args()

    try:
        if args.update_results:
            atualizar_results_csv(
                dry_run=args.dry_run,
                season=args.season,
                league=args.league,
            )
        if args.stats:
            coletar_stats_da_copa(
                season=args.season,
                league=args.league,
                limit=args.limit,
            )
        if not (args.update_results or args.stats):
            print("Choose an action: --update-results or --stats\n")
            build_parser().print_help()
            return 2
    except ApiFootballError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
