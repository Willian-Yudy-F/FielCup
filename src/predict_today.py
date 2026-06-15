"""FielCup - quick command-line match predictor."""

from pathlib import Path
import argparse
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dixon_coles import matriz_placares, probabilidades
from talento import ALPHA_PADRAO, ratings_blendados


def load_model(alpha: float = ALPHA_PADRAO) -> dict:
    """Load the default FielCup blended model."""
    return ratings_blendados(alpha=alpha)


def bar(pct: float, width: int = 24) -> str:
    filled = int(round(max(0.0, min(100.0, pct)) / 100 * width))
    return "#" * filled + "." * (width - filled)


def render_card(model: dict, home: str, away: str, neutral: bool = True) -> int:
    teams = set(model["ataque"].keys())
    missing = [team for team in (home, away) if team not in teams]
    if missing:
        print(f"\n  Team not found in model: '{missing[0]}'")
        print("  Use the exact English name (e.g. 'Brazil', 'United States').\n")
        return 1

    p_home, p_draw, p_away = probabilidades(model, home, away, neutro=neutral)
    matrix = matriz_placares(model, home, away, neutro=neutral)
    home_goals, away_goals = np.unravel_index(matrix.argmax(), matrix.shape)

    options = [(home, p_home), ("Draw", p_draw), (away, p_away)]
    pick, pick_probability = max(options, key=lambda item: item[1])
    venue = "neutral venue" if neutral else f"{home} at home"
    alpha = model.get("alpha")
    model_label = (
        f"Dixon-Coles + talent blend (alpha={alpha:.1f})"
        if alpha is not None
        else "Dixon-Coles"
    )

    width = 58
    print()
    print("=" * width)
    print(f"  {home}  vs  {away}".center(width))
    print(f"FielCup forecast - {venue}".center(width))
    print(model_label.center(width))
    print("=" * width)
    print(f"  {home:<22} win   {p_home*100:5.1f}%  {bar(p_home*100)}")
    print(f"  {'Draw':<22}       {p_draw*100:5.1f}%  {bar(p_draw*100)}")
    print(f"  {away:<22} win   {p_away*100:5.1f}%  {bar(p_away*100)}")
    print("-" * width)
    print(f"  Most likely scoreline:   {home} {home_goals} x {away_goals} {away}")
    print(f"  PICK: {pick} ({pick_probability*100:.1f}%)")
    print("=" * width)
    print("  FielCup model output - not betting advice")
    print()
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FielCup quick match predictor")
    parser.add_argument("home", help="First team (exact English name)")
    parser.add_argument("away", help="Second team (exact English name)")
    parser.add_argument("--venue", choices=["neutral", "home"], default="neutral")
    parser.add_argument(
        "--alpha",
        type=float,
        default=ALPHA_PADRAO,
        help=(
            "Weight for results vs talent blend. "
            "Use 1.0 for results-only Dixon-Coles, 0.6 for the default model."
        ),
    )
    args = parser.parse_args()
    if not 0.0 <= args.alpha <= 1.0:
        parser.error("--alpha must be between 0.0 and 1.0")
    return args


def main() -> int:
    args = parse_args()
    model = load_model(alpha=args.alpha)
    return render_card(model, args.home, args.away, neutral=(args.venue == "neutral"))


if __name__ == "__main__":
    raise SystemExit(main())
