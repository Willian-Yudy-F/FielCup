"""Build static mobile reports for GitHub Pages.

This generates docs/index.html with all fixture probabilities embedded as JSON.
The page runs without Streamlit, Python, or a live server.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import database as db
from dixon_coles import analisar_jogo
from talento import ALPHA_PADRAO, ratings_blendados

OUT = ROOT / "docs" / "index.html"

DISPLAY = {
    "Czech Republic": "Czechia",
    "United States": "USA",
    "Bosnia and Herzegovina": "Bosnia",
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


def build_matches() -> list[dict[str, object]]:
    fixtures = db.tabela("fixtures_2026")[
        ["date", "home_team", "away_team", "neutral"]
    ].copy()
    fixtures["date"] = pd.to_datetime(fixtures["date"]).dt.strftime("%Y-%m-%d")

    model = ratings_blendados(ALPHA_PADRAO)
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
        verdict = "A jogar"
        if final is not None:
            home_goals, away_goals = final
            final_text = f"{home_goals}-{away_goals}"
            verdict = (
                "Modelo acertou"
                if outcome(home_goals, away_goals, home, away) == pick
                else "Modelo errou"
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
                "pick": "Empate" if pick == "Draw" else nm(pick),
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


def render_html(matches: list[dict[str, object]]) -> str:
    generated_at = datetime.now(ZoneInfo("Australia/Sydney")).strftime(
        "%d/%m/%Y %H:%M Sydney"
    )
    results_count = sum(1 for match in matches if match["final"])
    payload = json.dumps(matches, ensure_ascii=False)
    generated_at_js = json.dumps(generated_at, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FielCup Hoje</title>
  <style>
    :root {{
      --paper:#f4f1e8; --ink:#151515; --red:#c0392b; --muted:#756f62;
      --line:#c9c2b1; --dark:#202020; --ok:#1f6f43;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#d8d4c8; color:var(--ink);
      font-family:Arial, Helvetica, sans-serif; }}
    header {{ background:var(--dark); color:var(--paper); padding:24px 16px 18px; }}
    h1 {{ margin:0; font-size:34px; line-height:.95; letter-spacing:-1px; }}
    h1 span {{ color:var(--red); }}
    header p {{ margin:8px 0 0; color:#cfc8b8; font-size:13px; line-height:1.35; }}
    main {{ max-width:760px; margin:0 auto; padding:14px; }}
    .toolbar {{ position:sticky; top:0; z-index:5; background:#d8d4c8;
      padding:10px 0 12px; border-bottom:1px solid #bbb4a5; }}
    label {{ display:block; color:var(--muted); text-transform:uppercase;
      letter-spacing:.08em; font-size:11px; margin-bottom:6px; }}
    select, button {{ width:100%; border:1px solid var(--dark); background:var(--paper);
      color:var(--ink); padding:12px; font-size:16px; font-weight:700; }}
    button {{ margin-top:8px; background:var(--dark); color:var(--paper); }}
    .summary {{ background:var(--paper); border:1px solid var(--line);
      border-left:5px solid var(--red); padding:14px; margin:12px 0; }}
    .summary h2 {{ margin:0 0 6px; font-size:18px; }}
    .summary p {{ margin:4px 0; color:var(--muted); font-size:14px; }}
    .match {{ background:var(--paper); border:1px solid var(--line); margin:12px 0;
      padding:15px; border-left:5px solid var(--red); }}
    .match.done {{ border-left-color:var(--ok); }}
    .date {{ color:var(--muted); font-size:11px; letter-spacing:.08em;
      text-transform:uppercase; }}
    .teams {{ margin:6px 0 10px; font-size:24px; line-height:1.05; font-weight:900; }}
    .teams span {{ color:var(--muted); font-size:14px; font-weight:700; }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin:12px 0; }}
    .grid div {{ background:var(--dark); color:var(--paper); padding:10px 6px; text-align:center; }}
    .grid small {{ display:block; color:#cfc8b8; font-size:11px; }}
    .grid b {{ display:block; font-size:20px; margin-top:4px; }}
    .facts {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }}
    .facts div {{ background:#e8e1d2; padding:9px; }}
    .facts small {{ display:block; color:var(--muted); font-size:11px; text-transform:uppercase; }}
    .facts b {{ font-size:16px; }}
    .status {{ margin-top:11px; padding:9px; font-size:13px; font-weight:800;
      background:#e8e1d2; }}
    .status.done {{ background:var(--dark); color:var(--paper); }}
    footer {{ padding:20px 14px 30px; color:var(--muted); font-size:12px; text-align:center; }}
    @media (max-width:420px) {{
      header {{ padding-top:20px; }}
      h1 {{ font-size:31px; }}
      .teams {{ font-size:22px; }}
      .grid b {{ font-size:18px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Fiel<span>Cup</span> Hoje</h1>
    <p>Probabilidades dos jogos do dia, direto no celular. Sem Streamlit. Sem servidor.</p>
    <p>Atualizado: <b id="generatedAt"></b></p>
  </header>
  <main>
    <section class="toolbar">
      <label for="dateSelect">Data dos jogos</label>
      <select id="dateSelect"></select>
      <button id="todayButton" type="button">Ver jogos de hoje</button>
      <button id="brazilButton" type="button">Ver próximo dia do Brasil</button>
    </section>
    <section id="summary" class="summary"></section>
    <section id="matches"></section>
  </main>
  <footer>
    FielCup · Dixon-Coles + talento · {results_count} resultados reais no banco
  </footer>
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
      const [year, month, day] = date.split("-");
      return `${{day}}/${{month}}/${{year}}`;
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
      summaryEl.innerHTML = `
        <h2>${{games.length}} jogo(s) em ${{labelDate(date)}}</h2>
        <p>${{finished}} terminado(s), ${{games.length - finished}} a jogar.</p>
        ${{brazilGame ? `<p>Brasil: <b>${{brazilGame.homeLabel}} x ${{brazilGame.awayLabel}}</b></p>` : ""}}
      `;
      matchesEl.innerHTML = games.map(match => `
        <article class="match ${{match.final ? "done" : ""}}">
          <div class="date">${{labelDate(match.date)}}</div>
          <div class="teams">${{match.homeLabel}} <span>vs</span> ${{match.awayLabel}}</div>
          <div class="grid">
            <div><small>${{match.homeLabel}}</small><b>${{match.pHome}}</b></div>
            <div><small>Empate</small><b>${{match.pDraw}}</b></div>
            <div><small>${{match.awayLabel}}</small><b>${{match.pAway}}</b></div>
          </div>
          <div class="facts">
            <div><small>Pick</small><b>${{match.pick}} (${{match.pickProbability}})</b></div>
            <div><small>Placar provável</small><b>${{match.likelyScore}}</b></div>
            <div><small>xG</small><b>${{match.xg}}</b></div>
            <div><small>Over 2.5 / BTTS</small><b>${{match.over25}} / ${{match.btts}}</b></div>
          </div>
          <div class="status ${{match.final ? "done" : ""}}">
            ${{match.final ? `Final: ${{match.final}} · ${{match.verdict}}` : "Aguardando o jogo"}}
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


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(build_matches())
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
