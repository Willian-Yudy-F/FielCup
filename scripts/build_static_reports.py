"""Build static mobile reports for GitHub Pages.

This generates docs/index.html with all fixture probabilities embedded as JSON.
The page runs without Streamlit, Python, or a live server.
"""

from __future__ import annotations

import json
import contextlib
import io
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import database as db
from bracket_poster import build_round32, render_circular_bracket_svg
from dixon_coles import analisar_jogo
from simulate import simular
from talento import ALPHA_PADRAO, ratings_blendados

OUT = ROOT / "docs" / "index.html"
MODEL_OUT = ROOT / "docs" / "modelo.html"

DISPLAY = {
    "Czech Republic": "Czechia",
    "United States": "USA",
    "Bosnia and Herzegovina": "Bosnia",
}

SIMS = 20_000

MARKET = {
    "Spain": 18.2,
    "France": 18.2,
    "England": 12.5,
    "Portugal": 11.1,
    "Brazil": 10.0,
    "Argentina": 9.5,
}

TAGS = {
    "Argentina": "holder",
    "Spain": "euro champ",
    "France": "#1 FIFA",
    "Brazil": "5x champ",
    "United States": "host",
    "Mexico": "host",
    "Canada": "host",
    "Morocco": "2022 SF",
}

def nm(team: str) -> str:
    return DISPLAY.get(team, team)


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def load_results() -> dict[tuple[str, str], tuple[int, int]]:
    try:
        results = db.tabela("live_results")
    except Exception:
        return {}

    out: dict[tuple[str, str], tuple[int, int]] = {}
    for _, row in results.iterrows():
        if pd.notna(row["home_score"]) and pd.notna(row["away_score"]):
            out[(row["home_team"], row["away_team"])] = (
                int(row["home_score"]),
                int(row["away_score"]),
            )
    return out


def outcome(home_goals: int, away_goals: int, home: str, away: str) -> str:
    if home_goals > away_goals:
        return home
    if away_goals > home_goals:
        return away
    return "Draw"


def build_matches(
    results: dict[tuple[str, str], tuple[int, int]] | None = None,
) -> list[dict[str, object]]:
    fixtures = db.tabela("fixtures_2026")[
        ["date", "home_team", "away_team", "neutral"]
    ].copy()
    fixtures["date"] = pd.to_datetime(fixtures["date"]).dt.strftime("%Y-%m-%d")

    model = ratings_blendados(ALPHA_PADRAO)
    if results is None:
        results = load_results()
    matches: list[dict[str, object]] = []

    for _, game in fixtures.iterrows():
        home = game["home_team"]
        away = game["away_team"]
        analysis = analisar_jogo(model, home, away, neutro=bool(game["neutral"]))
        likely_home, likely_away = analysis["placar_provavel"]
        options = [
            (home, analysis["p_casa"]),
            ("Draw", analysis["p_empate"]),
            (away, analysis["p_fora"]),
        ]
        pick, pick_probability = max(options, key=lambda item: item[1])

        final = results.get((home, away))
        final_text = None
        verdict = "Pending"
        if final is not None:
            home_goals, away_goals = final
            final_text = f"{home_goals}-{away_goals}"
            verdict = (
                "Model was right"
                if outcome(home_goals, away_goals, home, away) == pick
                else "Model missed"
            )

        matches.append(
            {
                "date": game["date"],
                "home": home,
                "away": away,
                "homeLabel": nm(home),
                "awayLabel": nm(away),
                "pHome": pct(analysis["p_casa"]),
                "pDraw": pct(analysis["p_empate"]),
                "pAway": pct(analysis["p_fora"]),
                "pick": "Draw" if pick == "Draw" else nm(pick),
                "pickProbability": pct(pick_probability),
                "likelyScore": f"{likely_home}-{likely_away}",
                "xg": f"{analysis['xg_casa']:.2f}-{analysis['xg_fora']:.2f}",
                "over25": pct(analysis["p_over25"]),
                "btts": pct(analysis["p_btts"]),
                "final": final_text,
                "verdict": verdict,
                "isBrazil": home == "Brazil" or away == "Brazil",
            }
        )
    return matches


def build_forecast(results: dict[tuple[str, str], tuple[int, int]]) -> pd.DataFrame:
    """Run the title forecast conditioned on recorded group-stage results."""
    with contextlib.redirect_stdout(io.StringIO()):
        return simular(
            alpha=ALPHA_PADRAO,
            sims=SIMS,
            seed=42,
            resultados=results,
        )


def title_rows(forecast: pd.DataFrame) -> str:
    rows = []
    for pos, (_, row) in enumerate(forecast.head(8).iterrows(), start=1):
        team = str(row["selecao"])
        tag = TAGS.get(team, "")
        tag_html = f'<span class="tag">{escape(tag)}</span>' if tag else ""
        br_class = " br" if team == "Brazil" else ""
        rows.append(
            f'<div class="rank-row{br_class}">'
            f'<div class="rank-n">{pos}</div>'
            f'<div class="rank-team">{escape(nm(team))}{tag_html}</div>'
            f'<div class="rank-pct">{float(row["prob_titulo"]) * 100:.1f}%</div>'
            f'</div>'
        )
    return "".join(rows)


def market_rows(forecast: pd.DataFrame) -> str:
    model = {
        str(row["selecao"]): float(row["prob_titulo"]) * 100
        for _, row in forecast.iterrows()
    }
    teams = sorted(MARKET, key=lambda team: -MARKET[team])
    vmax = max(max(MARKET.values()), max(model.get(team, 0.0) for team in teams)) * 1.1
    rows = [
        '<div class="mvm-grid">',
        '<div class="mvm-head"></div><div class="mvm-head">Model</div>'
        '<div class="mvm-head">Market (odds)</div>',
    ]
    for team in teams:
        model_pct = model.get(team, 0.0)
        market_pct = MARKET[team]
        model_width = model_pct / vmax * 100
        market_width = market_pct / vmax * 100
        rows.append(
            f'<div class="mvm-team">{escape(nm(team))}</div>'
            f'<div class="bar model"><i style="width:{model_width:.1f}%"></i>'
            f'<span>{model_pct:.1f}%</span></div>'
            f'<div class="bar market"><i style="width:{market_width:.1f}%"></i>'
            f'<span>{market_pct:.1f}%</span></div>'
        )
    rows.append("</div>")
    return "".join(rows)


def round32_cards(round32: list[dict[str, object]]) -> str:
    cards = []
    for game in round32:
        confirmed = game["status"] == "confirmed"
        status_class = " confirmed" if confirmed else " pending"
        if confirmed:
            cards.append(
                f'<article class="r32-card{status_class}">'
                f'<div class="r32-kicker">Match {escape(str(game["match"]))} · Round of 32</div>'
                f'<h3>{escape(str(game["homeLabel"]))} <span>v</span> {escape(str(game["awayLabel"]))}</h3>'
                f'<div class="r32-probs">'
                f'<div><small>{escape(str(game["homeLabel"]))}</small><b>{game["pHome"]}</b></div>'
                f'<div><small>Draw</small><b>{game["pDraw"]}</b></div>'
                f'<div><small>{escape(str(game["awayLabel"]))}</small><b>{game["pAway"]}</b></div>'
                f'</div>'
                f'<div class="r32-facts">'
                f'<div><small>Advance pick</small><b>{escape(str(game["advancePick"]))}</b></div>'
                f'<div><small>Advance odds</small><b>{game["homeAdvance"]} / {game["awayAdvance"]}</b></div>'
                f'<div><small>Likely score</small><b>{game["likelyScore"]}</b></div>'
                f'<div><small>xG</small><b>{game["xg"]}</b></div>'
                f'</div>'
                f'</article>'
            )
        else:
            cards.append(
                f'<article class="r32-card{status_class}">'
                f'<div class="r32-kicker">Match {escape(str(game["match"]))} · Round of 32</div>'
                f'<h3>{escape(str(game["homeLabel"]))} <span>v</span> {escape(str(game["awayLabel"]))}</h3>'
                f'<p>{escape(str(game["status"]))}</p>'
                f'</article>'
            )
    return "".join(cards)


def render_html(
    matches: list[dict[str, object]],
    forecast: pd.DataFrame,
    round32: list[dict[str, object]],
) -> str:
    generated_at = datetime.now(ZoneInfo("Australia/Sydney")).strftime(
        "%d/%m/%Y %H:%M Sydney"
    )
    results_count = sum(1 for match in matches if match["final"])
    top3 = forecast.head(3).reset_index(drop=True)
    leader = str(top3.loc[0, "selecao"])
    second = str(top3.loc[1, "selecao"])
    third = str(top3.loc[2, "selecao"])
    leader_pct = float(top3.loc[0, "prob_titulo"]) * 100
    podium_cards = "".join(
        f'<div><b>{float(row["prob_titulo"]) * 100:.0f}%</b>'
        f'<span>{escape(nm(str(row["selecao"]))).upper()}</span></div>'
        for _, row in top3.iterrows()
    )
    title_rows_html = title_rows(forecast)
    market_rows_html = market_rows(forecast)
    bracket_svg = render_circular_bracket_svg(
        round32,
        title="FIELCUP 2026",
        subtitle="advance probability by match",
    )
    round32_html = round32_cards(round32)
    payload = json.dumps(matches, ensure_ascii=False)
    generated_at_js = json.dumps(generated_at, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FielCup Matchday</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800;900&family=Archivo+Narrow:wght@500;700&display=swap');
    :root {{
      --paper:#f2efe6; --ink:#141414; --graphite:#1e1e1e;
      --red:#c0392b; --red-dark:#8e2a20; --line:#cdc9bc;
      --muted:#8a867a; --silver:#9a968c; --ok:#2c6b45;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#d8d4c8; color:var(--ink);
      font-family:'Archivo', Arial, Helvetica, sans-serif; padding:14px; }}
    .poster {{ max-width:840px; margin:0 auto; background:var(--paper);
      border:1px solid #b8b4a6; box-shadow:0 20px 54px rgba(0,0,0,.18); }}
    header {{ padding:28px 22px 22px; }}
    .topline {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }}
    .bars {{ display:flex; gap:6px; margin-bottom:24px; }}
    .bars span {{ display:block; width:42px; height:7px; }}
    .bars span:nth-child(1) {{ background:var(--ink); }}
    .bars span:nth-child(2) {{ background:var(--red); }}
    .bars span:nth-child(3) {{ background:var(--silver); }}
    .edition {{ font-weight:900; font-size:38px; letter-spacing:-1px; line-height:.9; }}
    .brand {{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; }}
    h1 {{ margin:0; font-size:54px; line-height:.92; letter-spacing:0; font-weight:900; }}
    h1 span {{ color:var(--red); }}
    .subtitle {{ font-family:'Archivo Narrow', Arial, sans-serif; text-align:right;
      color:var(--ink); font-size:15px; line-height:1.25; text-transform:uppercase; }}
    .meta {{ margin-top:10px; font-family:'Archivo Narrow', Arial, sans-serif;
      color:var(--muted); letter-spacing:1px; text-transform:uppercase; font-size:13px; }}
    .toolbar {{ position:sticky; top:0; z-index:5; background:var(--graphite);
      padding:14px; border-top:1px solid rgba(242,239,230,.16);
      border-bottom:1px solid rgba(242,239,230,.16); }}
    label {{ display:block; color:var(--paper); opacity:.7; text-transform:uppercase;
      letter-spacing:2px; font-family:'Archivo Narrow', Arial, sans-serif;
      font-size:12px; margin-bottom:7px; }}
    select, button, .nav-link {{ width:100%; min-height:46px; border:1px solid var(--line);
      background:var(--paper); color:var(--ink); padding:11px 12px;
      font:800 15px 'Archivo', Arial, sans-serif; border-radius:0; }}
    button {{ margin-top:8px; background:var(--red); color:#fff; border-color:var(--red); }}
    .nav-link {{ display:block; margin-top:8px; text-align:center; text-decoration:none;
      background:transparent; color:var(--paper); border-color:rgba(242,239,230,.4); }}
    main {{ padding:0; }}
    .summary {{ padding:18px 22px; background:var(--paper); border-bottom:1px solid var(--line); }}
    .summary h2 {{ margin:0 0 6px; font-size:24px; line-height:1.05; font-weight:900; }}
    .summary p {{ margin:4px 0; color:#4b463d; font-size:14px; line-height:1.35; }}
    .forecast-note {{ padding:18px 22px; background:var(--paper); border-top:1px solid var(--line);
      border-bottom:1px solid var(--line); border-left:5px solid var(--red); }}
    .forecast-note h2 {{ margin:0 0 10px; color:var(--red); font-size:18px; letter-spacing:2px;
      text-transform:uppercase; font-weight:900; }}
    .forecast-note p {{ margin:8px 0; color:#2f2b24; font-size:15px; line-height:1.45; }}
    .podium {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:14px; }}
    .podium div {{ background:var(--graphite); color:var(--paper); text-align:center;
      padding:14px 6px 13px; min-width:0; }}
    .podium b {{ display:block; font-size:25px; font-weight:900; }}
    .podium span {{ display:block; margin-top:8px; color:#c8c2b4; font-family:'Archivo Narrow', Arial, sans-serif;
      letter-spacing:1px; font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .forecast-board {{ background:var(--graphite); color:var(--paper); padding:28px 22px 30px; }}
    .board-label {{ font-family:'Archivo Narrow', Arial, sans-serif; font-size:13px; letter-spacing:5px;
      text-transform:uppercase; color:var(--paper); opacity:.72; margin-bottom:18px; }}
    .rank-row {{ display:grid; grid-template-columns:36px 1fr auto; align-items:center; gap:14px;
      padding:13px 0; border-bottom:1px solid rgba(242,239,230,.15); }}
    .rank-n {{ font-size:24px; font-weight:900; color:var(--paper); opacity:.42; }}
    .rank-team {{ font-size:21px; font-weight:900; color:var(--paper); min-width:0; overflow-wrap:anywhere; }}
    .rank-team .tag {{ margin-left:8px; color:var(--paper); opacity:.48; font-family:'Archivo Narrow', Arial, sans-serif;
      font-size:12px; letter-spacing:1px; text-transform:uppercase; font-weight:700; white-space:nowrap; }}
    .rank-pct {{ font-size:24px; font-weight:900; color:var(--paper); font-variant-numeric:tabular-nums; }}
    .rank-row.br {{ background:rgba(192,57,43,.18); margin:0 -12px; padding-left:12px; padding-right:12px;
      border-left:4px solid var(--red); }}
    .rank-row.br .rank-pct {{ color:var(--red); }}
    .market-box {{ padding:24px 22px 26px; background:var(--paper); border-bottom:1px solid var(--line); }}
    .market-title {{ margin:0 0 16px; color:var(--red); font-size:16px; letter-spacing:4px;
      text-transform:uppercase; font-weight:900; }}
    .mvm-grid {{ display:grid; grid-template-columns:92px 1fr 1fr; gap:7px 10px; align-items:center; }}
    .mvm-head {{ color:var(--muted); font-family:'Archivo Narrow', Arial, sans-serif; text-transform:uppercase;
      letter-spacing:1px; font-size:12px; font-weight:700; }}
    .mvm-team {{ font-size:14px; font-weight:900; min-width:0; overflow-wrap:anywhere; }}
    .bar {{ height:20px; background:var(--line); position:relative; overflow:hidden; }}
    .bar i {{ display:block; height:100%; }}
    .bar.model i {{ background:var(--red); }}
    .bar.market i {{ background:var(--graphite); }}
    .bar span {{ position:absolute; right:5px; top:0; color:#fff; font-size:12px; line-height:20px;
      font-weight:900; font-variant-numeric:tabular-nums; text-shadow:0 1px 1px rgba(0,0,0,.5); }}
    .round32-box {{ background:var(--graphite); color:var(--paper); padding:24px 22px 18px;
      border-bottom:1px solid rgba(242,239,230,.14); }}
    .round32-title {{ margin:0 0 8px; color:var(--paper); font-size:20px; letter-spacing:3px;
      text-transform:uppercase; font-weight:900; }}
    .round32-note {{ margin:0 0 16px; color:#c8c2b4; font-size:13px; line-height:1.45; }}
    .circle-bracket-wrap {{ background:#111; border:1px solid rgba(242,239,230,.12);
      margin:14px 0 18px; overflow:hidden; }}
    .circle-bracket-wrap svg {{ display:block; width:100%; height:auto; }}
    .r32-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    .r32-card {{ background:var(--paper); color:var(--ink); border:1px solid #b8b4a6;
      border-left:5px solid var(--red); padding:13px; min-width:0; }}
    .r32-card.pending {{ border-left-color:var(--muted); opacity:.82; }}
    .r32-kicker {{ color:var(--muted); font-family:'Archivo Narrow', Arial, sans-serif;
      font-size:11px; letter-spacing:2px; text-transform:uppercase; font-weight:700; }}
    .r32-card h3 {{ margin:5px 0 11px; font-size:21px; line-height:1.05; font-weight:900;
      overflow-wrap:anywhere; }}
    .r32-card h3 span {{ color:var(--red); font-family:'Archivo Narrow', Arial, sans-serif;
      font-size:15px; padding:0 2px; }}
    .r32-card p {{ margin:6px 0 0; color:#4b463d; font-size:13px; line-height:1.35; }}
    .r32-probs {{ display:grid; grid-template-columns:1fr 1fr 1fr; border-top:2px solid var(--ink);
      border-bottom:1px solid var(--line); }}
    .r32-probs div {{ padding:8px 4px; text-align:center; border-right:1px solid var(--line);
      min-width:0; }}
    .r32-probs div:last-child {{ border-right:0; }}
    .r32-probs small, .r32-facts small {{ display:block; color:var(--muted);
      font-family:'Archivo Narrow', Arial, sans-serif; font-size:10px; letter-spacing:1px;
      text-transform:uppercase; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .r32-probs b {{ display:block; margin-top:3px; font-size:17px; font-weight:900; }}
    .r32-facts {{ display:grid; grid-template-columns:1fr 1fr; border-top:1px solid var(--line); }}
    .r32-facts div {{ padding:8px 4px; border-right:1px solid var(--line);
      border-bottom:1px solid var(--line); min-width:0; }}
    .r32-facts div:nth-child(even) {{ border-right:0; }}
    .r32-facts b {{ display:block; margin-top:3px; font-size:13px; font-weight:900;
      overflow-wrap:anywhere; }}
    .stage {{ background:var(--graphite); padding:18px 22px 22px; }}
    .match {{ background:var(--paper); color:var(--ink); border:1px solid #b8b4a6;
      margin:0 0 14px; padding:16px; border-left:5px solid var(--red); }}
    .match.done {{ border-left-color:var(--ok); }}
    .match-kicker {{ font-family:'Archivo Narrow', Arial, sans-serif; color:var(--muted);
      font-size:12px; letter-spacing:2px; text-transform:uppercase; font-weight:700; }}
    .teams {{ margin:6px 0 12px; font-size:29px; line-height:1; letter-spacing:0;
      font-weight:900; overflow-wrap:anywhere; }}
    .teams span {{ color:var(--red); font-family:'Archivo Narrow', Arial, sans-serif;
      font-size:17px; font-weight:700; padding:0 2px; }}
    .prob-grid {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:0;
      border-top:2px solid var(--ink); border-bottom:1px solid var(--line); }}
    .prob-grid div {{ padding:12px 6px; text-align:center; border-right:1px solid var(--line);
      min-width:0; }}
    .prob-grid div:last-child {{ border-right:0; }}
    .prob-grid small {{ display:block; color:var(--muted); font-family:'Archivo Narrow', Arial, sans-serif;
      font-size:11px; letter-spacing:1px; text-transform:uppercase; white-space:nowrap;
      overflow:hidden; text-overflow:ellipsis; }}
    .prob-grid b {{ display:block; font-size:25px; margin-top:4px; font-weight:900; }}
    .facts {{ display:grid; grid-template-columns:1fr 1fr; border-top:1px solid var(--line); }}
    .fact {{ padding:11px 6px 8px; border-right:1px solid var(--line);
      border-bottom:1px solid var(--line); min-width:0; }}
    .fact:nth-child(even) {{ border-right:0; }}
    .fact small {{ display:block; color:var(--red); font-family:'Archivo Narrow', Arial, sans-serif;
      font-size:11px; letter-spacing:1px; text-transform:uppercase; font-weight:700; }}
    .fact b {{ display:block; font-size:16px; margin-top:3px; overflow-wrap:anywhere; }}
    .status {{ margin-top:11px; padding:9px 10px; font-size:13px; font-weight:900;
      background:#e5dfd1; border-left:3px solid var(--red); }}
    .status.done {{ background:var(--ink); color:var(--paper); border-left-color:var(--ok); }}
    footer {{ padding:18px 22px 28px; color:var(--muted); font-family:'Archivo Narrow', Arial, sans-serif;
      font-size:12px; text-transform:uppercase; letter-spacing:.8px; line-height:1.55; }}
    @media (max-width:420px) {{
      body {{ padding:0; }}
      .poster {{ border-left:0; border-right:0; box-shadow:none; }}
      header {{ padding:22px 16px 18px; }}
      .bars span {{ width:34px; }}
      .edition {{ font-size:32px; }}
      h1 {{ font-size:42px; }}
      .subtitle {{ font-size:13px; }}
      .toolbar {{ padding:12px; }}
      .summary {{ padding:16px; }}
      .forecast-note {{ padding:16px; }}
      .forecast-note h2 {{ font-size:16px; letter-spacing:2px; }}
      .podium {{ gap:6px; }}
      .podium b {{ font-size:20px; }}
      .forecast-board {{ padding:22px 16px 24px; }}
      .board-label {{ font-size:12px; letter-spacing:4px; }}
      .rank-row {{ grid-template-columns:26px 1fr auto; gap:8px; padding:10px 0; }}
      .rank-n, .rank-pct {{ font-size:18px; }}
      .rank-team {{ font-size:17px; }}
      .rank-team .tag {{ display:none; }}
      .market-box {{ padding:20px 16px 22px; }}
      .mvm-grid {{ grid-template-columns:68px 1fr 1fr; gap:6px; }}
      .mvm-team {{ font-size:12px; }}
      .bar span {{ font-size:10px; }}
      .round32-box {{ padding:20px 12px 14px; }}
      .round32-title {{ font-size:17px; letter-spacing:2px; }}
      .r32-grid {{ grid-template-columns:1fr; gap:10px; }}
      .r32-card {{ padding:12px; }}
      .r32-card h3 {{ font-size:20px; }}
      .stage {{ padding:14px 12px 18px; }}
      .match {{ padding:14px 12px; }}
      .teams {{ font-size:25px; }}
      .prob-grid b {{ font-size:21px; }}
      .fact b {{ font-size:15px; }}
    }}
  </style>
</head>
<body>
  <div class="poster">
    <header>
      <div class="topline">
        <div class="bars"><span></span><span></span><span></span></div>
        <div class="edition">/26</div>
      </div>
      <div class="brand">
        <h1>Fiel<span>Cup</span><br>Matchday</h1>
        <div class="subtitle">Dixon-Coles<br>plus talent<br>daily board</div>
      </div>
      <div class="meta">World Cup 2026 · {SIMS // 1000}K Monte Carlo · Results+Talent Blend (alpha={ALPHA_PADRAO:.1f})</div>
      <div class="meta">Updated <b id="generatedAt"></b></div>
    </header>
    <section class="toolbar">
      <label for="dateSelect">Match date</label>
      <select id="dateSelect"></select>
      <button id="todayButton" type="button">Today</button>
      <button id="brazilButton" type="button">Next Brazil matchday</button>
      <a class="nav-link" href="modelo.html">Understand the model</a>
    </section>
    <section class="forecast-note">
      <h2>What's going on</h2>
      <p>The model currently sees <b>{escape(nm(leader))}</b> as the title favorite
      ({leader_pct:.0f}% chance), followed by <b>{escape(nm(second))}</b> and
      <b>{escape(nm(third))}</b>.</p>
      <p>This forecast is conditioned on <b>{results_count} recorded World Cup results</b>
      and comes from <b>{SIMS:,} Monte Carlo simulations</b>.</p>
      <div class="podium">{podium_cards}</div>
    </section>
    <section class="forecast-board">
      <div class="board-label">Title probability · Top 8</div>
      {title_rows_html}
    </section>
    <section class="market-box">
      <h2 class="market-title">Model vs market · bookmaker favorites</h2>
      {market_rows_html}
    </section>
    <section class="round32-box">
      <h2 class="round32-title">Round of 32 · knockout board</h2>
      <p class="round32-note">
        Confirmed knockout fixtures are priced by the FielCup model. The circular
        board shows advancement probability for each side; TBD slots still depend
        on the final Group J, K and L matches.
      </p>
      <div class="circle-bracket-wrap">{bracket_svg}</div>
      <div class="r32-grid">{round32_html}</div>
    </section>
    <main>
      <section id="summary" class="summary"></section>
      <section id="matches" class="stage"></section>
    </main>
    <footer>
      FielCup · Dixon-Coles + talent · {results_count} real results in the database
    </footer>
  </div>
  <script>
    const MATCHES = {payload};
    const GENERATED_AT = {generated_at_js};
    const dateSelect = document.getElementById("dateSelect");
    const matchesEl = document.getElementById("matches");
    const summaryEl = document.getElementById("summary");
    document.getElementById("generatedAt").textContent = GENERATED_AT;

    const dates = [...new Set(MATCHES.map(match => match.date))].sort();
    const todaySydney = new Intl.DateTimeFormat("en-CA", {{
      timeZone: "Australia/Sydney",
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    }}).format(new Date());

    function labelDate(date) {{
      const parsed = new Date(`${{date}}T12:00:00Z`);
      return new Intl.DateTimeFormat("en", {{
        month: "short",
        day: "numeric",
        year: "numeric"
      }}).format(parsed);
    }}

    function defaultDate() {{
      if (dates.includes(todaySydney)) return todaySydney;
      const future = dates.find(date => date >= todaySydney && MATCHES.some(match => match.date === date && !match.final));
      return future || dates[dates.length - 1];
    }}

    function nextBrazilDate() {{
      const upcoming = MATCHES.find(match => match.isBrazil && match.date >= todaySydney && !match.final);
      if (upcoming) return upcoming.date;
      const brazil = MATCHES.filter(match => match.isBrazil);
      return brazil.length ? brazil[brazil.length - 1].date : defaultDate();
    }}

    function fillDates(selected) {{
      dateSelect.innerHTML = "";
      for (const date of dates) {{
        const option = document.createElement("option");
        option.value = date;
        option.textContent = labelDate(date);
        if (date === selected) option.selected = true;
        dateSelect.appendChild(option);
      }}
    }}

    function render(date) {{
      fillDates(date);
      const games = MATCHES.filter(match => match.date === date);
      const finished = games.filter(match => match.final).length;
      const brazilGame = games.find(match => match.isBrazil);
      const matchWord = games.length === 1 ? "match" : "matches";
      summaryEl.innerHTML = `
        <h2>${{games.length}} ${{matchWord}} on ${{labelDate(date)}}</h2>
        <p>${{finished}} final, ${{games.length - finished}} pending.</p>
        ${{brazilGame ? `<p>Brazil match: <b>${{brazilGame.homeLabel}} v ${{brazilGame.awayLabel}}</b></p>` : ""}}
      `;
      matchesEl.innerHTML = games.map(match => `
        <article class="match ${{match.final ? "done" : ""}}">
          <div class="match-kicker">${{labelDate(match.date)}}</div>
          <div class="teams">${{match.homeLabel}} <span>v</span> ${{match.awayLabel}}</div>
          <div class="prob-grid">
            <div><small>${{match.homeLabel}}</small><b>${{match.pHome}}</b></div>
            <div><small>Draw</small><b>${{match.pDraw}}</b></div>
            <div><small>${{match.awayLabel}}</small><b>${{match.pAway}}</b></div>
          </div>
          <div class="facts">
            <div class="fact"><small>Model pick</small><b>${{match.pick}} (${{match.pickProbability}})</b></div>
            <div class="fact"><small>Likely score</small><b>${{match.likelyScore}}</b></div>
            <div class="fact"><small>xG</small><b>${{match.xg}}</b></div>
            <div class="fact"><small>Over 2.5 / BTTS</small><b>${{match.over25}} / ${{match.btts}}</b></div>
          </div>
          <div class="status ${{match.final ? "done" : ""}}">
            ${{match.final ? `Final: ${{match.final}} - ${{match.verdict}}` : "Waiting for kickoff"}}
          </div>
        </article>
      `).join("");
      window.history.replaceState(null, "", `#${{date}}`);
    }}

    dateSelect.addEventListener("change", () => render(dateSelect.value));
    document.getElementById("todayButton").addEventListener("click", () => render(defaultDate()));
    document.getElementById("brazilButton").addEventListener("click", () => render(nextBrazilDate()));

    const initialDate = dates.includes(location.hash.slice(1)) ? location.hash.slice(1) : defaultDate();
    render(initialDate);
  </script>
</body>
</html>
"""


def render_model_html(matches: list[dict[str, object]]) -> str:
    generated_at = datetime.now(ZoneInfo("Australia/Sydney")).strftime(
        "%d/%m/%Y %H:%M Sydney"
    )
    results_count = sum(1 for match in matches if match["final"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FielCup Model Notes</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800;900&family=Archivo+Narrow:wght@500;700&display=swap');
    :root {{
      --paper:#f2efe6; --ink:#141414; --graphite:#1e1e1e;
      --red:#c0392b; --line:#cdc9bc; --muted:#8a867a;
      --silver:#9a968c; --ok:#2c6b45;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#d8d4c8; color:var(--ink);
      font-family:'Archivo', Arial, Helvetica, sans-serif; padding:14px; }}
    .poster {{ max-width:840px; margin:0 auto; background:var(--paper);
      border:1px solid #b8b4a6; box-shadow:0 20px 54px rgba(0,0,0,.18); }}
    header {{ padding:28px 22px 22px; }}
    .topline {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }}
    .bars {{ display:flex; gap:6px; margin-bottom:24px; }}
    .bars span {{ display:block; width:42px; height:7px; }}
    .bars span:nth-child(1) {{ background:var(--ink); }}
    .bars span:nth-child(2) {{ background:var(--red); }}
    .bars span:nth-child(3) {{ background:var(--silver); }}
    .edition {{ font-weight:900; font-size:38px; letter-spacing:-1px; line-height:.9; }}
    .brand {{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; }}
    h1 {{ margin:0; font-size:54px; line-height:.92; letter-spacing:0; font-weight:900; }}
    h1 span {{ color:var(--red); }}
    .subtitle {{ font-family:'Archivo Narrow', Arial, sans-serif; text-align:right;
      color:var(--ink); font-size:15px; line-height:1.25; text-transform:uppercase; }}
    .meta {{ margin-top:10px; font-family:'Archivo Narrow', Arial, sans-serif;
      color:var(--muted); letter-spacing:1px; text-transform:uppercase; font-size:13px; }}
    .topbar {{ position:sticky; top:0; z-index:5; background:var(--graphite);
      padding:14px; border-top:1px solid rgba(242,239,230,.16);
      border-bottom:1px solid rgba(242,239,230,.16); }}
    .button {{ display:block; width:100%; border:1px solid var(--red);
      background:var(--red); color:#fff; padding:12px; font-size:16px;
      font-weight:900; text-align:center; text-decoration:none; border-color:var(--red); }}
    main {{ background:var(--graphite); padding:18px 22px 22px; }}
    .section {{ background:var(--paper); border:1px solid #b8b4a6;
      border-left:5px solid var(--red); padding:16px; margin:0 0 14px; }}
    h2 {{ margin:0 0 8px; font-size:25px; line-height:1.05; font-weight:900; }}
    p, li {{ color:#363227; font-size:15px; line-height:1.48; }}
    p {{ margin:8px 0; }}
    ul, ol {{ padding-left:21px; margin:8px 0; }}
    .formula {{ background:var(--graphite); color:var(--paper); padding:12px;
      font-weight:900; overflow-wrap:anywhere; margin-top:10px; }}
    .note {{ background:#e5dfd1; border-left:4px solid var(--ok); padding:10px;
      color:#363227; }}
    .mini {{ color:var(--red); font-family:'Archivo Narrow', Arial, sans-serif;
      font-size:12px; text-transform:uppercase; letter-spacing:2px; font-weight:700;
      margin-bottom:8px; }}
    table {{ width:100%; border-collapse:collapse; margin-top:10px; font-size:13px; }}
    th, td {{ border:1px solid var(--line); padding:8px; text-align:left; vertical-align:top; }}
    th {{ background:var(--graphite); color:var(--paper); }}
    footer {{ padding:18px 22px 28px; color:var(--muted); font-family:'Archivo Narrow', Arial, sans-serif;
      font-size:12px; text-transform:uppercase; letter-spacing:.8px; line-height:1.55; }}
    @media (max-width:420px) {{
      body {{ padding:0; }}
      .poster {{ border-left:0; border-right:0; box-shadow:none; }}
      header {{ padding:22px 16px 18px; }}
      .bars span {{ width:34px; }}
      .edition {{ font-size:32px; }}
      h1 {{ font-size:42px; }}
      h2 {{ font-size:20px; }}
      main {{ padding:14px 12px 18px; }}
      th, td {{ padding:7px 5px; }}
    }}
  </style>
</head>
<body>
  <div class="poster">
    <header>
      <div class="topline">
        <div class="bars"><span></span><span></span><span></span></div>
        <div class="edition">/26</div>
      </div>
      <div class="brand">
        <h1>Fiel<span>Cup</span><br>Model</h1>
        <div class="subtitle">Plain-English<br>forecast notes<br>mobile page</div>
      </div>
      <div class="meta">World Cup 2026 · Updated <b>{escape(generated_at)}</b></div>
    </header>
    <nav class="topbar">
      <a class="button" href="index.html">Back to matchday</a>
    </nav>
    <main>
      <section class="section">
        <div class="mini">Summary</div>
        <h2>How the model gets the probabilities</h2>
        <p>FielCup does not try to guess a score. It estimates team strength,
        builds a scoreline distribution for each match, and turns that distribution
        into win, draw and loss probabilities.</p>
        <p class="note">The default version blends two signals: what the team has
        done on the pitch and the talent in the squad. That keeps the model from
        relying only on recent national-team results.</p>
      </section>

      <section class="section">
        <div class="mini">Four steps</div>
        <h2>The plain-English logic</h2>
        <ol>
          <li><b>Results on the pitch.</b> The model reads thousands of international
          matches and learns an attack rating and a defense rating for each team.
          Recent matches carry more weight.</li>
          <li><b>Dixon-Coles.</b> This is a football-specific Poisson model. It improves
          low-score estimates such as 0-0, 1-0 and 1-1.</li>
          <li><b>Talent prior.</b> FIFA ranking points and squad market value enter as
          outside signals. This helps when a national team has elite players but a
          noisy recent record.</li>
          <li><b>Simulation.</b> For title odds, the tournament is played thousands of
          times in the computer. A team's title probability is how often it wins.</li>
        </ol>
        <div class="formula">final strength = alpha x results + (1 - alpha) x talent</div>
      </section>

      <section class="section">
        <div class="mini">Each match</div>
        <h2>From scorelines to match odds</h2>
        <p>For a match, the model estimates expected goals for both teams. It then
        builds a matrix of possible scores: 0-0, 1-0, 0-1, 2-1, 1-2 and so on.</p>
        <p>All scorelines where the home team wins are added together to get the
        home-win probability. Draw scorelines become the draw probability. Away-win
        scorelines become the away-win probability.</p>
        <p>The same matrix also gives the likely score, xG, over 2.5 goals and BTTS.</p>
      </section>

      <section class="section">
        <div class="mini">Transparency</div>
        <h2>What the model sees and misses</h2>
        <p>It sees recent scorelines, attacking strength, defensive strength, FIFA
        ranking and squad value. It does not fully see injuries, age curves, fatigue,
        tactical changes, breaking news or tournament psychology.</p>
        <p class="note">The probabilities are a statistical lens, not a promise. The
        value is in showing the lens and being honest about its limits.</p>
      </section>

      <section class="section">
        <div class="mini">Model vs market</div>
        <h2>Why it can differ from betting markets</h2>
        <p>Betting markets mix statistics, context and money from thousands of bettors.
        FielCup is more explicit: it shows its assumptions. When it disagrees, the
        disagreement helps explain what evidence the model values.</p>
        <table>
          <thead>
            <tr><th>Team</th><th>FielCup read</th><th>Context</th></tr>
          </thead>
          <tbody>
            <tr><td>Argentina</td><td>Strong recent results profile</td><td>Market fades age and cycle risk</td></tr>
            <tr><td>France</td><td>Rises when talent enters</td><td>Deep, high-value squad</td></tr>
            <tr><td>Spain</td><td>Strong in model and market</td><td>Good blend of results and talent</td></tr>
            <tr><td>Brazil</td><td>Still in the favorite cluster</td><td>Talent helps; recent results hold it back</td></tr>
          </tbody>
        </table>
      </section>

      <section class="section">
        <div class="mini">Quick glossary</div>
        <h2>Key terms</h2>
        <ul>
          <li><b>Poisson:</b> a distribution used to count rare events, like goals.</li>
          <li><b>Dixon-Coles:</b> a Poisson adjustment for football, especially low scores.</li>
          <li><b>Monte Carlo:</b> repeated simulation used to estimate probabilities.</li>
          <li><b>Brier score:</b> a metric for judging forecast probability quality.</li>
          <li><b>Alpha:</b> the blend between results and talent.</li>
        </ul>
      </section>
    </main>
    <footer>
      FielCup · Dixon-Coles + talent · {results_count} real results in the database
    </footer>
  </div>
</body>
</html>
"""


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    results = load_results()
    matches = build_matches(results)
    forecast = build_forecast(results)
    round32 = build_round32()
    html = render_html(matches, forecast, round32)
    model_html = render_model_html(matches)
    OUT.write_text(html, encoding="utf-8")
    MODEL_OUT.write_text(model_html, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"Wrote {MODEL_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
