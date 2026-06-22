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
MODEL_OUT = ROOT / "docs" / "modelo.html"

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
    .nav-link {{ display:block; margin-top:8px; border:1px solid var(--dark);
      background:var(--paper); color:var(--dark); padding:12px; font-size:16px;
      font-weight:800; text-align:center; text-decoration:none; }}
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
      <a class="nav-link" href="modelo.html">Entender o modelo</a>
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


def render_model_html(matches: list[dict[str, object]]) -> str:
    generated_at = datetime.now(ZoneInfo("Australia/Sydney")).strftime(
        "%d/%m/%Y %H:%M Sydney"
    )
    results_count = sum(1 for match in matches if match["final"])
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FielCup Modelo</title>
  <style>
    :root {{
      --paper:#f4f1e8; --ink:#151515; --red:#c0392b; --muted:#756f62;
      --line:#c9c2b1; --dark:#202020; --ok:#1f6f43;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#d8d4c8; color:var(--ink);
      font-family:Arial, Helvetica, sans-serif; }}
    header {{ background:var(--dark); color:var(--paper); padding:24px 16px 18px; }}
    h1 {{ margin:0; font-size:34px; line-height:.95; }}
    h1 span {{ color:var(--red); }}
    header p {{ margin:8px 0 0; color:#cfc8b8; font-size:13px; line-height:1.35; }}
    main {{ max-width:760px; margin:0 auto; padding:14px; }}
    .topbar {{ position:sticky; top:0; z-index:5; background:#d8d4c8;
      padding:10px 0 12px; border-bottom:1px solid #bbb4a5; }}
    .button {{ display:block; width:100%; border:1px solid var(--dark);
      background:var(--dark); color:var(--paper); padding:12px; font-size:16px;
      font-weight:800; text-align:center; text-decoration:none; }}
    .section {{ background:var(--paper); border:1px solid var(--line);
      border-left:5px solid var(--red); padding:15px; margin:12px 0; }}
    h2 {{ margin:0 0 8px; font-size:22px; line-height:1.1; }}
    h3 {{ margin:16px 0 6px; font-size:17px; }}
    p, li {{ color:#363227; font-size:15px; line-height:1.48; }}
    p {{ margin:8px 0; }}
    ul, ol {{ padding-left:21px; margin:8px 0; }}
    .formula {{ background:#202020; color:#f4f1e8; padding:12px;
      font-weight:800; overflow-wrap:anywhere; }}
    .note {{ background:#e8e1d2; border-left:4px solid var(--ok); padding:10px;
      color:#363227; }}
    .mini {{ color:var(--muted); font-size:12px; text-transform:uppercase;
      letter-spacing:.08em; font-weight:800; }}
    table {{ width:100%; border-collapse:collapse; margin-top:10px; font-size:13px; }}
    th, td {{ border:1px solid var(--line); padding:8px; text-align:left; }}
    th {{ background:#202020; color:#f4f1e8; }}
    footer {{ padding:20px 14px 30px; color:var(--muted); font-size:12px; text-align:center; }}
    @media (max-width:420px) {{
      h1 {{ font-size:31px; }}
      h2 {{ font-size:20px; }}
      th, td {{ padding:7px 5px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Fiel<span>Cup</span> Modelo</h1>
    <p>A página antiga de explicação, agora em HTML leve para abrir direto no celular.</p>
    <p>Atualizado: <b>{escape(generated_at)}</b></p>
  </header>
  <main>
    <nav class="topbar">
      <a class="button" href="index.html">Voltar para os jogos de hoje</a>
    </nav>

    <section class="section">
      <div class="mini">Resumo</div>
      <h2>Como o modelo chega nas probabilidades</h2>
      <p>O FielCup não tenta adivinhar o resultado. Ele estima a força de cada seleção,
      calcula uma distribuição de placares para cada jogo e transforma essa distribuição
      em probabilidade de vitória, empate e derrota.</p>
      <p class="note">A versão padrão mistura duas coisas: o que a seleção fez em campo
      e o talento do elenco. Isso evita que o modelo fique preso só ao histórico recente.</p>
    </section>

    <section class="section">
      <div class="mini">4 passos</div>
      <h2>O raciocínio em linguagem simples</h2>
      <ol>
        <li><b>Resultados em campo.</b> O modelo usa milhares de jogos de seleções e aprende
        uma força de ataque e uma força de defesa para cada time. Jogos recentes pesam mais.</li>
        <li><b>Dixon-Coles.</b> É uma versão da distribuição de Poisson ajustada para futebol.
        Ela melhora a estimativa de placares baixos, como 0-0, 1-0 e 1-1.</li>
        <li><b>Talento.</b> Ranking FIFA e valor de mercado do elenco entram como sinais externos.
        Isso ajuda em casos em que a seleção tem jogadores fortes, mas poucos jogos recentes.</li>
        <li><b>Simulação.</b> Para chances de título, a Copa é jogada milhares de vezes no computador.
        A probabilidade é a frequência com que cada seleção termina campeã.</li>
      </ol>
      <div class="formula">força final = alpha x resultados + (1 - alpha) x talento</div>
    </section>

    <section class="section">
      <div class="mini">Cada partida</div>
      <h2>Como sai Brasil x adversário, por exemplo</h2>
      <p>Para um confronto, o modelo calcula os gols esperados de cada lado. Depois monta
      uma matriz com muitos placares possíveis: 0-0, 1-0, 0-1, 2-1, 1-2 e assim por diante.</p>
      <p>Somando os placares em que o Brasil vence, sai a chance de vitória do Brasil.
      Somando os empates, sai a chance de empate. Somando os placares do adversário,
      sai a chance do outro time.</p>
      <p>Da mesma matriz também saem o placar mais provável, over 2.5 gols e BTTS
      (ambos marcam).</p>
    </section>

    <section class="section">
      <div class="mini">Transparência</div>
      <h2>O que o modelo vê e o que ele não vê</h2>
      <p>Ele vê placares recentes, força ofensiva, força defensiva, ranking FIFA e valor
      do elenco. Ele ainda não vê perfeitamente lesões, idade do elenco, desgaste físico,
      esquema tático, notícias de última hora ou motivação.</p>
      <p class="note">Por isso as probabilidades são uma régua estatística, não uma promessa.
      O valor do projeto está justamente em mostrar a régua e explicar seus limites.</p>
    </section>

    <section class="section">
      <div class="mini">Modelo vs mercado</div>
      <h2>Por que às vezes diverge das casas de aposta</h2>
      <p>Casas de aposta misturam estatística, informação contextual e dinheiro do mercado.
      O FielCup é mais explícito: ele mostra a conta. Quando diverge, isso ajuda a entender
      o que o modelo está valorizando.</p>
      <table>
        <thead>
          <tr><th>Seleção</th><th>Leitura do FielCup</th><th>Contexto</th></tr>
        </thead>
        <tbody>
          <tr><td>Argentina</td><td>Forte por resultados recentes</td><td>Mercado desconta idade e ciclo do elenco</td></tr>
          <tr><td>França</td><td>Sobe quando talento entra</td><td>Elenco muito valorizado e profundo</td></tr>
          <tr><td>Espanha</td><td>Forte no modelo e no mercado</td><td>Boa combinação de resultado e talento</td></tr>
          <tr><td>Brasil</td><td>Fica no bloco dos favoritos</td><td>Talento ajuda, resultados recentes pesam contra</td></tr>
        </tbody>
      </table>
    </section>

    <section class="section">
      <div class="mini">Glossário rápido</div>
      <h2>Termos importantes</h2>
      <ul>
        <li><b>Poisson:</b> distribuição usada para contar eventos raros, como gols.</li>
        <li><b>Dixon-Coles:</b> ajuste da Poisson para futebol, especialmente placares baixos.</li>
        <li><b>Monte Carlo:</b> repetir simulações muitas vezes para estimar probabilidade.</li>
        <li><b>Brier score:</b> métrica para medir se probabilidades previstas foram boas.</li>
        <li><b>Alpha:</b> botão que controla quanto pesa resultado e quanto pesa talento.</li>
      </ul>
    </section>
  </main>
  <footer>
    FielCup · Dixon-Coles + talento · {results_count} resultados reais no banco
  </footer>
</body>
</html>
"""


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    matches = build_matches()
    html = render_html(matches)
    model_html = render_model_html(matches)
    OUT.write_text(html, encoding="utf-8")
    MODEL_OUT.write_text(model_html, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"Wrote {MODEL_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
