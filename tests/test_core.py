from pathlib import Path
import sqlite3
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DB = ROOT / "db" / "fielcup.db"

sys.path.insert(0, str(SRC))


def test_database_contains_expected_core_tables():
    assert DB.exists()

    expected_min_rows = {
        "matches": 1000,
        "fixtures_2026": 72,
        "groups": 48,
        "teams_reference": 48,
        "team_ratings": 48,
        "title_probabilities": 48,
    }

    with sqlite3.connect(DB) as con:
        for table, minimum in expected_min_rows.items():
            row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            assert row is not None
            assert row[0] >= minimum


def test_probability_matrix_is_normalized():
    from dixon_coles import matriz_placares, probabilidades
    from talento import ratings_blendados

    model = ratings_blendados(alpha=0.6)
    matrix = matriz_placares(model, "Brazil", "France", neutro=True)
    win, draw, loss = probabilidades(model, "Brazil", "France", neutro=True)

    assert matrix.shape == (11, 11)
    assert np.isclose(matrix.sum(), 1.0)
    assert np.all(matrix >= 0)
    assert np.isclose(win + draw + loss, 1.0)


def test_talent_blend_preserves_world_cup_teams():
    import database as db
    from talento import detalhe_blend, ratings_blendados

    groups = db.tabela("groups")
    cup_teams = set(groups["selecao"])
    model = ratings_blendados(alpha=0.6)
    detail = detalhe_blend(alpha=0.6)

    assert cup_teams.issubset(model["ataque"])
    assert cup_teams.issubset(model["defesa"])
    assert set(detail["selecao"]) == cup_teams
    assert detail["forca_final"].notna().all()


@pytest.mark.parametrize("alpha", [0.0, 0.6, 1.0])
def test_simulation_output_invariants(alpha):
    from simulate import simular

    result = simular(alpha=alpha, sims=250, seed=7)
    probability_columns = [
        "prob_grupo",
        "prob_r16",
        "prob_quartas",
        "prob_semi",
        "prob_final",
        "prob_titulo",
    ]

    assert len(result) == 48
    assert set(probability_columns).issubset(result.columns)
    assert (result[probability_columns] >= 0).all().all()
    assert (result[probability_columns] <= 1).all().all()
    assert np.isclose(result["prob_titulo"].sum(), 1.0)
    assert (result["prob_grupo"] >= result["prob_r16"]).all()
    assert (result["prob_r16"] >= result["prob_quartas"]).all()
    assert (result["prob_quartas"] >= result["prob_semi"]).all()
    assert (result["prob_semi"] >= result["prob_final"]).all()
    assert (result["prob_final"] >= result["prob_titulo"]).all()


def test_circular_bracket_svg_uses_fielcup_match_odds():
    from bracket_poster import build_round32, render_circular_bracket_svg
    from talento import ratings_blendados

    board = build_round32(ratings_blendados(alpha=0.6))
    brazil = next(game for game in board if game["match"] == "76")
    svg = render_circular_bracket_svg(board)

    assert brazil["home"] == "Brazil"
    assert brazil["away"] == "Japan"
    assert brazil["homeAdvanceValue"] > brazil["awayAdvanceValue"]
    assert "<svg" in svg
    assert "BRAZIL" in svg
    assert "JAPAN" in svg
    assert "M76" in svg


def test_committed_forecast_matches_documented_top_six():
    forecast = pd.read_csv(ROOT / "data" / "processed" / "prob_titulo.csv")
    top_six = forecast.head(6)

    assert top_six["selecao"].tolist() == [
        "Argentina",
        "Spain",
        "England",
        "France",
        "Brazil",
        "Portugal",
    ]
    assert np.allclose(
        top_six["prob_titulo"].to_numpy(),
        np.array([0.18502, 0.14844, 0.10200, 0.09836, 0.07576, 0.06434]),
    )


def test_predict_today_cli_runs():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "src" / "predict_today.py"),
            "Brazil",
            "France",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Brazil  vs  France" in result.stdout
    assert "Most likely scoreline" in result.stdout
    assert "PICK:" in result.stdout
