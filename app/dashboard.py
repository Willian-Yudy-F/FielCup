"""FielCup - Dashboard (Swiss poster edition, mono palette).

Agora com:
  - botao ALPHA (resultado <-> talento) que re-ranqueia a Copa localmente;
  - painel MODELO vs MERCADO (casas de aposta, junho/2026);
  - painel de jogos do dia com previsao vs resultado real;
  - exportacao HTML leve para enviar e abrir no celular;
  - grafico de probabilidade de titulo (Top 12);
  - motor de confrontos usando os ratings blendados.
"""
import sys
from pathlib import Path
import html as html_lib
import streamlit as st

# set_page_config TEM de ser o primeiro comando Streamlit.
st.set_page_config(page_title="FielCup Local Forecast", page_icon="*", layout="centered")

# "Sinal de vida": garante que SEMPRE aparece algo na tela, mesmo que os
# imports/dados falhem (evita a temida página em branco e mostra o erro real).
_boot = st.empty()
_boot.info("⏳ Carregando o FielCup… a primeira carga pode levar alguns segundos.")

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

try:
    from dixon_coles import probabilidades, matriz_placares, analisar_jogo
    from talento import ratings_blendados, indice_talento, detalhe_blend
    from simulate import simular
    import database as db
except Exception as _imp_err:
    _boot.empty()
    st.error("⚠️ Erro ao importar os módulos do projeto (src/). Detalhes:")
    st.exception(_imp_err)
    st.stop()

# Probabilidade implícita das odds das casas (junho/2026, com margem).
# Coletado de agregadores de odds; usado só para comparar com o modelo.
MERCADO = {
    "Spain": 18.2, "France": 18.2, "England": 12.5,
    "Portugal": 11.1, "Brazil": 10.0, "Argentina": 9.5,
}

TEAM = {
    "Argentina": ("Argentina", "AR", "holder"), "Spain": ("Spain", "ES", "euro champ"),
    "England": ("England", "EN", ""), "Morocco": ("Morocco", "MA", "2022 SF"),
    "Brazil": ("Brazil", "BR", "5x champ"), "Portugal": ("Portugal", "PT", ""),
    "Japan": ("Japan", "JP", ""), "France": ("France", "FR", "#1 FIFA"),
    "Germany": ("Germany", "DE", ""), "Netherlands": ("Netherlands", "NL", ""),
    "Colombia": ("Colombia", "CO", ""), "Ecuador": ("Ecuador", "EC", ""),
    "Norway": ("Norway", "NO", ""), "Belgium": ("Belgium", "BE", ""),
    "Switzerland": ("Switzerland", "CH", ""), "Uruguay": ("Uruguay", "UY", ""),
    "Croatia": ("Croatia", "HR", ""), "United States": ("USA", "US", "host"),
    "Mexico": ("Mexico", "MX", "host"), "South Korea": ("South Korea", "KR", ""),
    "Senegal": ("Senegal", "SN", ""), "Iran": ("Iran", "IR", ""),
    "Austria": ("Austria", "AT", ""), "Australia": ("Australia", "AU", ""),
    "Egypt": ("Egypt", "EG", ""), "Ivory Coast": ("Ivory Coast", "CI", ""),
    "Sweden": ("Sweden", "SE", ""), "Paraguay": ("Paraguay", "PY", ""),
    "Tunisia": ("Tunisia", "TN", ""), "Ghana": ("Ghana", "GH", ""),
    "Algeria": ("Algeria", "DZ", ""), "Scotland": ("Scotland", "SC", ""),
    "Qatar": ("Qatar", "QA", ""), "Saudi Arabia": ("Saudi Arabia", "SA", ""),
    "Turkey": ("Turkey", "TR", ""), "Czech Republic": ("Czechia", "CZ", ""),
    "South Africa": ("South Africa", "ZA", ""), "DR Congo": ("DR Congo", "CD", ""),
    "Cape Verde": ("Cape Verde", "CV", ""), "Panama": ("Panama", "PA", ""),
    "Jordan": ("Jordan", "JO", ""), "Uzbekistan": ("Uzbekistan", "UZ", ""),
    "New Zealand": ("New Zealand", "NZ", ""), "Curacao": ("Curacao", "CW", ""),
    "Curaçao": ("Curacao", "CW", ""), "Haiti": ("Haiti", "HT", ""),
    "Iraq": ("Iraq", "IQ", ""), "Bosnia and Herzegovina": ("Bosnia", "BA", ""),
    "Canada": ("Canada", "CA", "host"),
}


def nm(t): return TEAM.get(t, (t, "--", ""))[0]
def cd(t): return TEAM.get(t, (t, "--", ""))[1]
def tag(t): return TEAM.get(t, (t, "--", ""))[2]


@st.cache_data(show_spinner=False)
def carregar_estaticos():
    grupos = db.tabela("groups")
    talento = indice_talento().set_index("selecao")
    fixtures = db.tabela("fixtures_2026")[["date", "home_team", "away_team", "neutral"]]
    fixtures = fixtures.copy()
    fixtures["date"] = pd.to_datetime(fixtures["date"]).dt.strftime("%Y-%m-%d")
    return grupos, talento, fixtures


def ler_resultados_locais() -> dict:
    """Lê os placares reais digitados localmente no SQLite."""
    try:
        df = db.tabela("live_results")
    except Exception:
        return {}
    out = {}
    for _, r in df.iterrows():
        if pd.notna(r["home_score"]) and pd.notna(r["away_score"]):
            out[(r["home_team"], r["away_team"])] = (int(r["home_score"]), int(r["away_score"]))
    return out


def salvar_resultados_locais(df: pd.DataFrame) -> None:
    """Grava no banco só as linhas com os dois placares preenchidos."""
    val = df.dropna(subset=["Gols casa", "Gols fora"])
    out = pd.DataFrame({
        "home_team": val["Casa"],
        "away_team": val["Fora"],
        "home_score": val["Gols casa"].astype(int),
        "away_score": val["Gols fora"].astype(int),
    })
    db.salvar_df(out, "live_results")


def upsert_resultado(casa: str, fora: str, gc: int, gf: int) -> None:
    """Insere/atualiza o placar de UM jogo na tabela local de resultados."""
    atuais = ler_resultados_locais()
    atuais[(casa, fora)] = (int(gc), int(gf))
    out = pd.DataFrame(
        [{"home_team": h, "away_team": a, "home_score": s[0], "away_score": s[1]}
         for (h, a), s in atuais.items()])
    db.salvar_df(out, "live_results")


def resultado_real(resultados: dict, casa: str, fora: str):
    """Retorna placar registrado localmente para um jogo, se existir."""
    return resultados.get((casa, fora))


def outcome(gc: int, gf: int, casa: str, fora: str) -> str:
    if gc > gf:
        return casa
    if gf > gc:
        return fora
    return "Draw"


def pick_do_modelo(an: dict, casa: str, fora: str) -> tuple[str, float]:
    opcoes = [(casa, an["p_casa"]), ("Draw", an["p_empate"]), (fora, an["p_fora"])]
    return max(opcoes, key=lambda item: item[1])


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


@st.cache_data(show_spinner="Simulando a Copa...")
def simular_cache(alpha: float, res_key: tuple, sims: int = 8000):
    """Roda a simulacao. Cacheado por (alpha, resultados, sims).

    res_key é uma tupla hashável dos placares reais já conhecidos.
    """
    resultados = {(h, a): (gh, ga) for (h, a, gh, ga) in res_key}
    return simular(alpha=alpha, sims=sims, seed=42, resultados=resultados)


@st.cache_data(show_spinner=False)
def modelo_cache(alpha: float):
    return ratings_blendados(alpha)


@st.cache_data(show_spinner=False)
def detalhe_cache(alpha: float):
    return detalhe_blend(alpha)


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900&family=Archivo+Narrow:wght@400;500;700&display=swap');
:root{--papel:#F2EFE6;--tinta:#141414;--grafite:#1E1E1E;--vermelho:#C0392B;--linha:#CDC9BC;--nevoa:#8A867A;--prata:#9A968C;}
.stApp{background:#D8D4C8;}
.block-container{max-width:880px;padding-top:1.2rem;}
#MainMenu, header, footer{visibility:hidden;}
.poster{background:var(--papel);border:1px solid #B8B4A6;padding:40px 44px 0;}
.barras{display:flex;gap:6px;margin-bottom:26px;}
.barras span{display:block;width:46px;height:7px;}
.b1{background:var(--tinta);} .b2{background:var(--vermelho);} .b3{background:var(--prata);}
.titulo{font-family:'Archivo';font-weight:800;font-size:64px;line-height:0.92;letter-spacing:-3px;color:var(--tinta);margin-bottom:4px;}
.titulo .cup{color:var(--vermelho);}
.faixa-meta{font-family:'Archivo Narrow';font-size:13px;letter-spacing:1px;text-transform:uppercase;color:var(--nevoa);margin:4px 0 0;}
.palco{background:var(--grafite);margin:26px -44px 0;padding:32px 44px 36px;}
.palco-label{font-family:'Archivo Narrow';font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--papel);opacity:0.7;margin-bottom:14px;}
.rank{display:grid;grid-template-columns:32px 1fr auto;align-items:center;gap:14px;padding:11px 0;border-bottom:1px solid rgba(242,239,230,0.14);}
.rank-n{font-family:'Archivo';font-weight:800;font-size:22px;color:var(--papel);opacity:0.4;}
.rank-nome{font-family:'Archivo';font-weight:700;font-size:19px;color:var(--papel);letter-spacing:-0.5px;}
.rank-nome .tg{font-family:'Archivo Narrow';font-weight:400;font-size:11px;letter-spacing:1px;text-transform:uppercase;opacity:0.55;margin-left:8px;}
.rank-pct{font-family:'Archivo';font-weight:800;font-size:22px;color:var(--papel);font-variant-numeric:tabular-nums;}
.rank.br{background:rgba(192,57,43,0.16);margin:0 -16px;padding-left:16px;padding-right:16px;border-left:3px solid var(--vermelho);}
.rank.br .rank-nome{color:#fff;} .rank.br .rank-pct{color:var(--vermelho);}
.mini-label{font-family:'Archivo Narrow';font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--vermelho);font-weight:700;margin:26px 0 4px;}
.scorebox{display:flex;align-items:center;justify-content:space-between;padding:6px 0 2px;}
.sb-team{text-align:center;flex:1;}
.sb-cd{font-family:'Archivo';font-weight:800;font-size:22px;color:var(--nevoa);letter-spacing:1px;}
.sb-nm{font-family:'Archivo';font-weight:700;font-size:15px;margin-top:2px;color:var(--tinta);}
.sb-sc{font-family:'Archivo';font-weight:800;font-size:46px;letter-spacing:1px;color:var(--tinta);}
.sb-sc .o{color:var(--vermelho);}
.sb-x{font-family:'Archivo Narrow';font-size:15px;color:var(--nevoa);padding:0 6px;}
.cap{font-family:'Archivo Narrow';font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--nevoa);text-align:center;}
.nota{font-family:'Archivo Narrow';font-size:13px;line-height:1.55;color:var(--tinta);border-left:3px solid var(--vermelho);padding-left:14px;margin-top:18px;}
.mvm{display:grid;grid-template-columns:120px 1fr 1fr;gap:6px 12px;align-items:center;margin-top:6px;}
.mvm-h{font-family:'Archivo Narrow';font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--nevoa);}
.mvm-t{font-family:'Archivo';font-weight:700;font-size:14px;color:var(--tinta);}
.bar{height:16px;background:var(--linha);position:relative;}
.bar > i{position:absolute;left:0;top:0;height:100%;display:block;}
.bar.mod > i{background:var(--vermelho);}
.bar.mkt > i{background:var(--grafite);}
.bar span{position:absolute;right:4px;top:0;font-family:'Archivo';font-weight:700;font-size:11px;color:#fff;line-height:16px;}
.rodape{display:flex;justify-content:space-between;align-items:flex-end;padding:20px 0 26px;border-top:2px solid var(--tinta);margin-top:26px;}
.rodape-cred{font-family:'Archivo Narrow';font-size:11px;line-height:1.6;color:var(--nevoa);text-transform:uppercase;letter-spacing:0.5px;}
.edicao{font-family:'Archivo';font-weight:800;font-size:42px;letter-spacing:-2px;color:var(--tinta);}
.stSelectbox label, .stSlider label{font-family:'Archivo Narrow';text-transform:uppercase;letter-spacing:1px;font-size:12px;color:var(--nevoa);}
div[data-testid="stMetric"]{background:transparent;border-top:2px solid var(--tinta);padding-top:8px;}
div[data-testid="stMetricLabel"]{font-family:'Archivo Narrow';text-transform:uppercase;}
div[data-testid="stMetricValue"]{font-family:'Archivo';font-weight:800;}
.resumo{background:var(--papel);border:1px solid #B8B4A6;border-left:4px solid var(--vermelho);padding:16px 18px;margin-bottom:14px;}
.resumo h4{font-family:'Archivo';font-weight:800;font-size:15px;letter-spacing:1px;text-transform:uppercase;color:var(--vermelho);margin:0 0 8px;}
.resumo p{font-family:'Archivo Narrow';font-size:15px;line-height:1.5;color:var(--tinta);margin:0 0 6px;}
.resumo b{font-family:'Archivo';font-weight:700;}
.podio{display:flex;gap:8px;margin-top:10px;}
.podio div{flex:1;text-align:center;background:var(--grafite);padding:10px 4px;}
.podio .pp{font-family:'Archivo';font-weight:800;font-size:20px;color:var(--papel);}
.podio .pn{font-family:'Archivo Narrow';font-size:12px;color:var(--papel);opacity:0.85;text-transform:uppercase;letter-spacing:0.5px;}
@media (max-width: 640px){
  .block-container{padding-left:0.5rem;padding-right:0.5rem;}
  .poster{padding:22px 16px 0;border-left:none;border-right:none;}
  .titulo{font-size:38px;letter-spacing:-1.5px;}
  .faixa-meta{font-size:11px;}
  .palco{margin:18px -16px 0;padding:22px 16px 22px;}
  .rank{grid-template-columns:24px 1fr auto;gap:8px;padding:9px 0;}
  .rank-nome{font-size:15px;} .rank-nome .tg{display:none;}
  .rank-pct,.rank-n{font-size:17px;}
  .mvm{grid-template-columns:62px 1fr 1fr;gap:4px 6px;}
  .mvm-t{font-size:12px;} .bar span{font-size:10px;}
  .sb-sc{font-size:34px;} .sb-cd{font-size:18px;} .sb-nm{font-size:13px;}
  .resumo p{font-size:14px;} .podio .pp{font-size:17px;}
}
</style>
"""


def rank_row(pos, team, val, is_br=False):
    cls = "rank br" if is_br else "rank"
    t = tag(team)
    tg = f'<span class="tg">{t}</span>' if t else ""
    return (f'<div class="{cls}"><div class="rank-n">{pos}</div>'
            f'<div class="rank-nome">{nm(team)}{tg}</div>'
            f'<div class="rank-pct">{val*100:.1f}%</div></div>')


def painel_modelo_vs_mercado(probs):
    """Barras lado a lado: probabilidade do modelo vs implícita do mercado."""
    mod = dict(zip(probs["selecao"], probs["prob_titulo"] * 100))
    times = list(MERCADO.keys())
    vmax = max(max(MERCADO.values()), max(mod.get(t, 0) for t in times)) * 1.1

    h_mod = tr("Modelo", "Model")
    h_mkt = tr("Mercado (odds)", "Market (odds)")
    linhas = f'<div class="mvm"><div class="mvm-h"></div><div class="mvm-h">{h_mod}</div><div class="mvm-h">{h_mkt}</div>'
    for t in sorted(times, key=lambda x: -MERCADO[x]):
        pm = mod.get(t, 0.0)
        pk = MERCADO[t]
        linhas += (
            f'<div class="mvm-t">{nm(t)}</div>'
            f'<div class="bar mod"><i style="width:{pm/vmax*100:.1f}%"></i><span>{pm:.1f}%</span></div>'
            f'<div class="bar mkt"><i style="width:{pk/vmax*100:.1f}%"></i><span>{pk:.1f}%</span></div>'
        )
    linhas += "</div>"
    return linhas


def analise_fixture(modelo: dict, resultados: dict, jogo: pd.Series) -> dict:
    casa, fora = jogo["home_team"], jogo["away_team"]
    neutro = bool(int(jogo.get("neutral", 1)))
    an = analisar_jogo(modelo, casa, fora, neutro=neutro)
    pick, pick_p = pick_do_modelo(an, casa, fora)
    i, j = an["placar_provavel"]
    real = resultado_real(resultados, casa, fora)
    real_txt = "Pendente"
    status_txt = "Aguardando resultado"
    if real is not None:
        gc, gf = real
        real_txt = f"{nm(casa)} {gc} x {gf} {nm(fora)}"
        status_txt = "Modelo acertou o desfecho" if outcome(gc, gf, casa, fora) == pick else "Modelo errou o desfecho"
    return {
        "date": str(jogo["date"])[:10],
        "home_team": casa,
        "away_team": fora,
        "p_home": an["p_casa"],
        "p_draw": an["p_empate"],
        "p_away": an["p_fora"],
        "xg_home": an["xg_casa"],
        "xg_away": an["xg_fora"],
        "scoreline": f"{nm(casa)} {i} x {j} {nm(fora)}",
        "pick": pick,
        "pick_probability": pick_p,
        "actual": real_txt,
        "status": status_txt,
    }


def mobile_report_html(jogos: pd.DataFrame, modelo: dict, resultados: dict,
                       titulo: str, alpha: float) -> str:
    cards = []
    for _, jogo in jogos.iterrows():
        info = analise_fixture(modelo, resultados, jogo)
        home = html_lib.escape(nm(info["home_team"]))
        away = html_lib.escape(nm(info["away_team"]))
        pick = html_lib.escape(nm(info["pick"]) if info["pick"] != "Draw" else "Empate")
        status_class = "done" if info["actual"] != "Pendente" else "pending"
        cards.append(f"""
        <article class="match">
          <div class="date">{html_lib.escape(info['date'])}</div>
          <h2>{home} <span>vs</span> {away}</h2>
          <div class="score">{html_lib.escape(info['scoreline'])}</div>
          <div class="grid">
            <div><b>{home}</b><strong>{pct(info['p_home'])}</strong></div>
            <div><b>Empate</b><strong>{pct(info['p_draw'])}</strong></div>
            <div><b>{away}</b><strong>{pct(info['p_away'])}</strong></div>
          </div>
          <p><b>Pick do modelo:</b> {pick} ({pct(info['pick_probability'])})</p>
          <p><b>xG:</b> {home} {info['xg_home']:.2f} x {info['xg_away']:.2f} {away}</p>
          <p><b>Resultado final:</b> {html_lib.escape(info['actual'])}</p>
          <div class="status {status_class}">{html_lib.escape(info['status'])}</div>
        </article>
        """)

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_lib.escape(titulo)} - FielCup</title>
  <style>
    :root {{ --paper:#f4f1e8; --ink:#161616; --red:#c0392b; --muted:#777164; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#d8d4c8; color:var(--ink);
      font-family:Arial, Helvetica, sans-serif; }}
    header {{ background:#161616; color:#f4f1e8; padding:24px 18px 20px; }}
    header h1 {{ margin:0; font-size:34px; line-height:.95; letter-spacing:-1px; }}
    header p {{ margin:8px 0 0; color:#c9c3b4; font-size:13px; text-transform:uppercase; }}
    main {{ max-width:720px; margin:0 auto; padding:14px; }}
    .match {{ background:var(--paper); border:1px solid #b8b4a6; border-left:5px solid var(--red);
      margin:0 0 14px; padding:16px; }}
    .date {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:1px; }}
    h2 {{ margin:6px 0 10px; font-size:22px; line-height:1.05; }}
    h2 span {{ color:var(--muted); font-size:14px; }}
    .score {{ font-size:18px; font-weight:800; margin:8px 0 12px; }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin:12px 0; }}
    .grid div {{ background:#1e1e1e; color:#f4f1e8; padding:10px 8px; text-align:center; }}
    .grid b {{ display:block; font-size:11px; color:#c9c3b4; font-weight:400; }}
    .grid strong {{ display:block; font-size:20px; margin-top:4px; }}
    p {{ margin:8px 0; font-size:14px; }}
    .status {{ margin-top:12px; padding:9px 10px; font-weight:700; font-size:13px; }}
    .status.pending {{ background:#e6dfcf; }}
    .status.done {{ background:#161616; color:#f4f1e8; }}
  </style>
</head>
<body>
  <header>
    <h1>Fiel<span style="color:var(--red)">Cup</span></h1>
    <p>{html_lib.escape(titulo)} · alpha={alpha:.1f} · relatorio local</p>
  </header>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>"""


LANG = "PT"


def tr(pt, en):
    """Bilíngue: devolve o texto em PT ou EN conforme o idioma escolhido."""
    return pt if LANG == "PT" else en


def main():
    global LANG
    _boot.empty()  # remove o "sinal de vida" — chegamos a renderizar de verdade
    st.markdown(CSS, unsafe_allow_html=True)

    # ---- seletor de idioma / language switch ----
    cabec = st.columns([2, 1])
    with cabec[1]:
        idioma = st.radio("lang", ["🇧🇷 PT", "🇬🇧 EN"], horizontal=True,
                          label_visibility="collapsed")
    LANG = "PT" if "PT" in idioma else "EN"

    grupos, talento, fixtures = carregar_estaticos()
    live = ler_resultados_locais()
    res_key = tuple(sorted((h, a, gh, ga) for (h, a), (gh, ga) in live.items()))

    # ---- controle: botao alpha ----
    st.markdown(f'<div class="mini-label">{tr("Modelo: resultado &harr; talento", "Model: results &harr; talent")}</div>',
                unsafe_allow_html=True)
    alpha = st.slider(
        tr("ALPHA — peso dos resultados (1.0) vs talento FIFA+elenco (0.0)",
           "ALPHA — weight of results (1.0) vs FIFA+squad talent (0.0)"),
        min_value=0.0, max_value=1.0, value=0.6, step=0.1,
    )
    if live:
        st.caption(tr(
            f"📅 Análise condicionada a {len(live)} resultado(s) local(is) já registrado(s).",
            f"📅 Forecast conditioned on {len(live)} local result(s) already entered."))

    probs = simular_cache(alpha, res_key)
    modelo = modelo_cache(alpha)

    rows = ""
    for i, r in probs.head(8).iterrows():
        rows += rank_row(i + 1, r["selecao"], r["prob_titulo"],
                         is_br=(r["selecao"] == "Brazil"))

    # ---- RESUMO em linguagem simples (o que importa num relance no celular) ----
    t3 = probs.head(3).reset_index(drop=True)
    n1, n2, n3 = nm(t3.loc[0, "selecao"]), nm(t3.loc[1, "selecao"]), nm(t3.loc[2, "selecao"])
    p1 = t3.loc[0, "prob_titulo"] * 100
    cond = tr(
        f" Isso já considera <b>{len(live)} jogo(s) real(is)</b> da Copa que você registrou." if live else "",
        f" This already accounts for <b>{len(live)} real match(es)</b> you entered." if live else "")
    podio = "".join(
        f'<div><div class="pp">{r["prob_titulo"]*100:.0f}%</div>'
        f'<div class="pn">{nm(r["selecao"])}</div></div>'
        for _, r in t3.iterrows())
    resumo_html = tr(
        f"""<h4>📊 O que está acontecendo</h4>
      <p>Hoje o modelo aponta <b>{n1}</b> como o favorito ao título ({p1:.0f}% de chance),
      seguido de <b>{n2}</b> e <b>{n3}</b>.{cond}</p>
      <p>👉 Quanto <b>maior a %</b>, maior a chance de ser campeão — número obtido
      <b>simulando a Copa inteira 8 mil vezes</b>. Role para baixo para ver a análise
      de cada jogo e registrar os resultados.</p>""",
        f"""<h4>📊 What's going on</h4>
      <p>The model currently sees <b>{n1}</b> as the title favorite ({p1:.0f}% chance),
      followed by <b>{n2}</b> and <b>{n3}</b>.{cond}</p>
      <p>👉 The <b>higher the %</b>, the higher the chance of winning — obtained by
      <b>simulating the whole World Cup 8,000 times</b>. Scroll down for the per-match
      analysis and to enter results.</p>""")
    st.markdown(f'<div class="resumo">{resumo_html}<div class="podio">{podio}</div></div>',
                unsafe_allow_html=True)

    meta = tr(f"Copa 2026 · 8k Monte Carlo · blend resultado+talento (α={alpha:.1f})",
              f"World Cup 2026 · 8k Monte Carlo · results+talent blend (α={alpha:.1f})")
    palco_lbl = tr("Probabilidade de Título · Top 8", "Title Probability · Top 8")
    mvm_lbl = tr("Modelo vs Mercado · favoritos das casas", "Model vs Market · bookmaker favorites")
    st.markdown(f"""
    <div class="poster">
      <div class="barras"><span class="b1"></span><span class="b2"></span><span class="b3"></span></div>
      <div class="titulo">Fiel<span class="cup">Cup</span> Forecast</div>
      <div class="faixa-meta">{meta}</div>
      <div class="palco">
        <div class="palco-label">{palco_lbl}</div>
        {rows}
      </div>
      <div class="mini-label">{mvm_lbl}</div>
      {painel_modelo_vs_mercado(probs)}
    </div>
    """, unsafe_allow_html=True)

    # ---- grafico de barras top 12 ----
    st.markdown(f'<div class="mini-label">{tr("Probabilidade de título · Top 12", "Title probability · Top 12")}</div>',
                unsafe_allow_html=True)
    top12 = probs.head(12).copy()
    top12["seleção"] = top12["selecao"].map(nm)
    chart = top12.set_index("seleção")["prob_titulo"] * 100
    st.bar_chart(chart, color="#C0392B", height=280)

    # ---- etapas da copa ----
    st.markdown(f'<div class="mini-label">{tr("Etapas da Copa · caminho até o título", "World Cup stages · path to the title")}</div>',
                unsafe_allow_html=True)
    fases = probs.head(16)[
        ["selecao", "prob_grupo", "prob_r16", "prob_quartas",
         "prob_semi", "prob_final", "prob_titulo"]
    ].copy()
    fases["selecao"] = fases["selecao"].map(nm)
    fases.columns = tr(
        ["Seleção", "Sai dos grupos", "Oitavas", "Quartas", "Semi", "Final", "Título"],
        ["Team", "From groups", "Round of 16", "Quarters", "Semi", "Final", "Title"],
    )
    for col in fases.columns[1:]:
        fases[col] = (fases[col] * 100).map(lambda x: f"{x:.1f}%")
    st.dataframe(fases, hide_index=True, width="stretch")

    # ---- jogos do dia: modelo vs resultado real ----
    st.markdown(f'<div class="mini-label">{tr("Jogos do dia · previsão x resultado", "Daily matches · forecast vs result")}</div>',
                unsafe_allow_html=True)
    datas = sorted(fixtures["date"].unique())
    hoje = pd.Timestamp.today().strftime("%Y-%m-%d")
    idx_data = datas.index(hoje) if hoje in datas else 0
    data_sel = st.selectbox(tr("Data", "Date"), datas, index=idx_data)
    jogos_dia = fixtures[fixtures["date"] == data_sel].reset_index(drop=True)
    linhas_dia = []
    for _, jogo in jogos_dia.iterrows():
        info = analise_fixture(modelo, live, jogo)
        pick_nome = nm(info["pick"]) if info["pick"] != "Draw" else tr("Empate", "Draw")
        linhas_dia.append({
            tr("Jogo", "Match"): f"{nm(info['home_team'])} x {nm(info['away_team'])}",
            tr("Pick modelo", "Model pick"): f"{pick_nome} ({pct(info['pick_probability'])})",
            tr("Placar provável", "Likely score"): info["scoreline"],
            tr("1", "1"): pct(info["p_home"]),
            tr("X", "X"): pct(info["p_draw"]),
            tr("2", "2"): pct(info["p_away"]),
            tr("Resultado final", "Final result"): info["actual"],
            tr("Status", "Status"): info["status"],
        })
    st.dataframe(pd.DataFrame(linhas_dia), hide_index=True, width="stretch")

    # ---- relatório mobile ----
    st.markdown(f'<div class="mini-label">{tr("Relatório mobile · baixar HTML", "Mobile report · download HTML")}</div>',
                unsafe_allow_html=True)
    st.caption(tr(
        "Gere um arquivo HTML leve para abrir no celular ou enviar por mensagem. "
        "Ele usa os resultados locais que você já digitou.",
        "Generate a light HTML file to open on a phone or send by message. "
        "It uses the local results you already entered."))
    tipo_rel = st.radio(
        tr("Escopo do relatório", "Report scope"),
        [tr("Jogos do dia", "Daily matches"), tr("Um jogo", "Single match")],
        horizontal=True,
    )
    if tipo_rel == tr("Jogos do dia", "Daily matches"):
        jogos_rel = jogos_dia
        nome_rel = f"fielcup_{data_sel}.html"
        titulo_rel = f"Jogos de {data_sel}"
    else:
        labels_jogos = [
            f"{r['date']} · {nm(r['home_team'])} x {nm(r['away_team'])}"
            for _, r in fixtures.iterrows()
        ]
        escolha_rel = st.selectbox(tr("Jogo para exportar", "Match to export"), labels_jogos)
        jogo_idx = labels_jogos.index(escolha_rel)
        jogos_rel = fixtures.iloc[[jogo_idx]]
        row_rel = jogos_rel.iloc[0]
        nome_rel = f"fielcup_{row_rel['date']}_{row_rel['home_team']}_vs_{row_rel['away_team']}.html"
        nome_rel = nome_rel.replace(" ", "_").replace("/", "-")
        titulo_rel = f"{nm(row_rel['home_team'])} x {nm(row_rel['away_team'])}"
    html_rel = mobile_report_html(jogos_rel, modelo, live, titulo_rel, alpha)
    st.download_button(
        tr("Baixar relatório HTML", "Download HTML report"),
        html_rel,
        file_name=nome_rel,
        mime="text/html",
        width="stretch",
    )

    # ---- COMO O MODELO PENSA (explicação + cálculo local) ----
    st.markdown(f'<div class="mini-label">{tr("Como o modelo chega nesses números", "How the model gets these numbers")}</div>',
                unsafe_allow_html=True)
    with st.expander(tr("Entenda o raciocínio em 4 passos (linguagem simples)",
                        "Understand the reasoning in 4 steps (plain language)"), expanded=False):
        st.markdown(tr("""
**A ideia central:** um time é forte por dois motivos que o modelo mistura.

1. **O que ele faz em campo (resultados).** Olhamos ~8.000 jogos de seleções
   e medimos uma **força de ataque** (gols que costuma fazer) e uma **força de
   defesa** (gols que costuma evitar). Jogos recentes pesam mais. É o modelo
   *Dixon-Coles*. Ataque + defesa = **"força só pelos resultados"**.

2. **O talento que ele tem (mesmo que os resultados não mostrem).** Resultados
   de seleção escondem o talento individual — por isso a França aparecia mal.
   Somamos dois sinais externos: o **ranking FIFA** e o **valor de mercado do
   elenco** (Transfermarkt). Juntos formam o **"índice de talento"**.

3. **A mistura (o botão α).** Força final = `α × resultados + (1−α) × talento`.
   Com **α=1** vale só o que aconteceu em campo (Argentina dispara); diminuindo
   α, o talento entra e **França, Espanha e Inglaterra sobem**.

4. **Jogar a Copa milhares de vezes.** No dashboard, a Copa é simulada 8 mil
   vezes para manter a interação rápida. No pipeline offline, o mesmo motor pode
   rodar 50 mil simulações. A **probabilidade de título** é *em quantas dessas
   Copas o time foi campeão*.

> Para comparar réguas diferentes (gols, pontos FIFA, euros), tudo vira
> **z-score**: quantos desvios-padrão acima (+) ou abaixo (−) da média.
        """, """
**Core idea:** a team is strong for two reasons the model blends together.

1. **What it does on the pitch (results).** We look at ~8,000 national-team
   matches and measure an **attack strength** (goals it tends to score) and a
   **defense strength** (goals it tends to prevent). Recent games weigh more.
   That's the *Dixon-Coles* model. Attack + defense = **"results-only strength"**.

2. **The talent it has (even if results don't show it yet).** National-team
   results hide individual talent — that's why France looked weak. We add two
   external signals: the **FIFA ranking** and the **squad market value**
   (Transfermarkt). Together they form the **"talent index"**.

3. **The blend (the α knob).** Final strength = `α × results + (1−α) × talent`.
   At **α=1** only on-pitch results count (Argentina runs away); lowering α
   brings talent in and **France, Spain and England rise**.

4. **Playing the World Cup thousands of times.** In the dashboard, the World Cup
   is simulated 8,000 times to keep the interaction fast. In the offline
   pipeline, the same engine can run 50,000 simulations. The **title
   probability** is *in how many of those Cups the team won it*.

> To compare different scales (goals, FIFA points, euros), everything becomes a
> **z-score**: how many standard deviations above (+) or below (−) the mean.
        """))

    det = detalhe_cache(alpha)
    nomes_ord = det["selecao"].tolist()
    escolha = st.selectbox(tr("Veja a conta de um time específico:",
                              "See the math for a specific team:"), nomes_ord,
                           index=nomes_ord.index("France") if "France" in nomes_ord else 0,
                           format_func=nm)
    d = det[det["selecao"] == escolha].iloc[0]
    pos_final = nomes_ord.index(escolha) + 1
    prob_t = probs[probs["selecao"] == escolha]["prob_titulo"]
    prob_t = float(prob_t.iloc[0]) * 100 if not prob_t.empty else 0.0

    h = tr(["Passo", "Ingrediente", "Valor", "Em z-score"],
           ["Step", "Ingredient", "Value", "As z-score"])
    L = tr(["Ataque (Dixon-Coles)", "Defesa (Dixon-Coles)", "Força só pelos resultados",
            "Ranking FIFA", "Valor do elenco", "Índice de talento", "Força final → posição"],
           ["Attack (Dixon-Coles)", "Defense (Dixon-Coles)", "Results-only strength",
            "FIFA ranking", "Squad value", "Talent index", "Final strength → rank"])
    pts = tr("pts", "pts")
    st.markdown(f"""
| {h[0]} | {h[1]} | {h[2]} | {h[3]} |
|---|---|---:|---:|
| 1 | {L[0]} | {d['ataque']:+.2f} | — |
| 1 | {L[1]} | {d['defesa']:+.2f} | — |
| 1 | **{L[2]}** | **{d['forca_dc']:+.2f}** | **{d['z_resultado']:+.2f}** |
| 2 | {L[3]} | {d['fifa_points']:.0f} {pts} | {d['z_fifa']:+.2f} |
| 2 | {L[4]} | €{d['valor_mi']:.0f} mi | {d['z_valor']:+.2f} |
| 2 | **{L[5]}** | — | **{d['indice_talento']:+.2f}** |
| 3 | **Blend** = {alpha:.1f}×({d['z_resultado']:+.2f}) + {1-alpha:.1f}×({d['indice_talento']:+.2f}) | — | **{d['blend']:+.2f}** |
| 4 | **{L[6]}** | **{pos_final}º** | **{d['forca_final']:+.2f}** |

{tr(f'''**Em palavras:** com α={alpha:.1f}, {nm(escolha)} tem força de resultados
{d['z_resultado']:+.2f} e talento {d['indice_talento']:+.2f}. A mistura dá
{d['blend']:+.2f}, colocando o time em **{pos_final}º** na força, o que resulta em
**{prob_t:.1f}% de chance de título** nas 8 mil simulações.''',
f'''**In words:** at α={alpha:.1f}, {nm(escolha)} has results strength
{d['z_resultado']:+.2f} and talent {d['indice_talento']:+.2f}. The blend gives
{d['blend']:+.2f}, ranking the team **#{pos_final}** in strength, which yields a
**{prob_t:.1f}% title chance** across the 8,000 simulations.''')}
    """)

    # ---- ANÁLISE DE JOGO (leitura estatística completa) ----
    st.markdown(f'<div class="mini-label">{tr("Análise de Jogo · a leitura estatística", "Match Analysis · the statistical read")}</div>',
                unsafe_allow_html=True)
    teams = sorted(grupos["selecao"], key=nm)
    labels = {f"{nm(t)}": t for t in teams}
    keys = list(labels)
    c1, c2 = st.columns(2)
    with c1:
        la = st.selectbox(tr("Time A", "Team A"), keys, index=keys.index("Brazil") if "Brazil" in keys else 0)
    with c2:
        lb = st.selectbox(tr("Time B", "Team B"), keys, index=keys.index("France") if "France" in keys else 1)
    a, b = labels[la], labels[lb]

    if a == b:
        st.warning(tr("Escolha dois times diferentes.", "Pick two different teams."))
    else:
        an = analisar_jogo(modelo, a, b, neutro=True)
        i, j = an["placar_provavel"]

        # placar mais provável
        st.markdown(f"""
        <div class="scorebox">
          <div class="sb-team"><div class="sb-cd">{cd(a)}</div><div class="sb-nm">{nm(a)}</div></div>
          <div class="sb-sc">{i}<span class="sb-x">v</span><span class="o">{j}</span></div>
          <div class="sb-team"><div class="sb-cd">{cd(b)}</div><div class="sb-nm">{nm(b)}</div></div>
        </div>
        <div class="cap">{tr("placar mais provável", "most likely scoreline")} · α={alpha:.1f}</div>
        """, unsafe_allow_html=True)

        # 1X2
        d1, d2, d3 = st.columns(3)
        d1.metric(tr(f"{nm(a)} vence", f"{nm(a)} win"), f"{an['p_casa']*100:.0f}%")
        d2.metric(tr("Empate", "Draw"), f"{an['p_empate']*100:.0f}%")
        d3.metric(tr(f"{nm(b)} vence", f"{nm(b)} win"), f"{an['p_fora']*100:.0f}%")

        # quadro de indicadores principais
        ind = tr(["Indicador estatístico", "Gols esperados (xG)", "Probabilidade de vencer",
                  "Não sofrer gol (clean sheet)", "Mercado de gols", "Probabilidade",
                  "Mais de 2,5 gols (Over 2.5)", "Menos de 2,5 gols (Under 2.5)",
                  "Ambos marcam (BTTS)", "Jogo sem gols (0×0)"],
                 ["Statistical indicator", "Expected goals (xG)", "Win probability",
                  "Clean sheet", "Goals market", "Probability",
                  "Over 2.5 goals", "Under 2.5 goals",
                  "Both teams to score (BTTS)", "No goals (0×0)"])
        st.markdown(f"""
| {ind[0]} | {nm(a)} | {nm(b)} |
|---|:--:|:--:|
| **{ind[1]}** | **{an['xg_casa']:.2f}** | **{an['xg_fora']:.2f}** |
| {ind[2]} | {an['p_casa']*100:.0f}% | {an['p_fora']*100:.0f}% |
| {ind[3]} | {an['cs_casa']*100:.0f}% | {an['cs_fora']*100:.0f}% |

| {ind[4]} | {ind[5]} |
|---|:--:|
| {ind[6]} | {an['p_over25']*100:.0f}% |
| {ind[7]} | {an['p_under25']*100:.0f}% |
| {ind[8]} | {an['p_btts']*100:.0f}% |
| {ind[9]} | {an['p_sem_gols']*100:.0f}% |
        """)

        # top-5 placares + distribuição do total de gols
        cc1, cc2 = st.columns(2)
        with cc1:
            st.caption(tr("Placares mais prováveis", "Most likely scorelines"))
            linhas = ""
            pmax = an["top_placares"][0][1]
            for (gi, gj), p in an["top_placares"]:
                linhas += (
                    f'<div class="mvm-t" style="display:flex;justify-content:space-between;'
                    f'align-items:center;margin:3px 0;">'
                    f'<span>{nm(a)} {gi}×{gj} {nm(b)}</span>'
                    f'<span style="font-family:Archivo;">{p*100:.0f}%</span></div>'
                    f'<div class="bar mod"><i style="width:{p/pmax*100:.0f}%"></i></div>'
                )
            st.markdown(linhas, unsafe_allow_html=True)
        with cc2:
            st.caption(tr("Distribuição do total de gols", "Total goals distribution"))
            dist = an["dist_total_gols"]
            serie = pd.Series({str(k): v * 100 for k, v in dist.items()})
            st.bar_chart(serie, color="#1E1E1E", height=200)

        # leitura automática (narrativa)
        fav, pfav = (nm(a), an["p_casa"]) if an["p_casa"] >= an["p_fora"] else (nm(b), an["p_fora"])
        equilibrio_pt = "equilibrado" if abs(an["p_casa"] - an["p_fora"]) < 0.12 else "inclinado para um lado"
        equilibrio_en = "balanced" if abs(an["p_casa"] - an["p_fora"]) < 0.12 else "leaning to one side"
        tend_pt = "muitos gols" if an["p_over25"] >= 0.5 else "poucos gols"
        tend_en = "many goals" if an["p_over25"] >= 0.5 else "few goals"
        nota_html = tr(
            f"""<b>Leitura do modelo:</b> {fav} é o favorito ({pfav*100:.0f}% de vitória),
          mas com {an['p_empate']*100:.0f}% de chance de empate o jogo é {equilibrio_pt}.
          O ataque esperado é {an['xg_casa']:.2f} × {an['xg_fora']:.2f} gols, apontando para
          um jogo de <b>{tend_pt}</b> (Over 2,5 = {an['p_over25']*100:.0f}%) e
          {an['p_btts']*100:.0f}% de chance de ambos marcarem.""",
            f"""<b>Model read:</b> {fav} is the favorite ({pfav*100:.0f}% to win),
          but with a {an['p_empate']*100:.0f}% draw chance the game is {equilibrio_en}.
          Expected attack is {an['xg_casa']:.2f} × {an['xg_fora']:.2f} goals, pointing to a
          <b>{tend_en}</b> game (Over 2.5 = {an['p_over25']*100:.0f}%) and a
          {an['p_btts']*100:.0f}% chance both teams score.""")
        st.markdown(f'<div class="nota">{nota_html}</div>', unsafe_allow_html=True)

        # registrar o placar real (só se for um jogo de grupo da Copa)
        fx_pares = set(zip(fixtures["home_team"], fixtures["away_team"]))
        if (a, b) in fx_pares:
            casa_r, fora_r = a, b
        elif (b, a) in fx_pares:
            casa_r, fora_r = b, a
        else:
            casa_r = None

        if casa_r is not None:
            with st.expander(tr("📝 Registrar o placar REAL deste jogo (atualiza a previsão)",
                                "📝 Enter the REAL score of this match (updates the forecast)")):
                atual = live.get((casa_r, fora_r))
                st.caption(tr(f"Jogo da fase de grupos: {nm(casa_r)} (mandante) × {nm(fora_r)}.",
                              f"Group-stage match: {nm(casa_r)} (home) × {nm(fora_r)}."))
                rc1, rc2, rc3 = st.columns([1, 1, 2])
                with rc1:
                    gca = st.number_input(tr(f"Gols {nm(casa_r)}", f"{nm(casa_r)} goals"),
                                          min_value=0, max_value=20,
                                          value=int(atual[0]) if atual else 0, key="rg_casa")
                with rc2:
                    gfo = st.number_input(tr(f"Gols {nm(fora_r)}", f"{nm(fora_r)} goals"),
                                          min_value=0, max_value=20,
                                          value=int(atual[1]) if atual else 0, key="rg_fora")
                with rc3:
                    st.write("")
                    st.write("")
                    if st.button(tr("💾 Salvar placar e recalcular", "💾 Save score and recalculate"),
                                 type="primary"):
                        upsert_resultado(casa_r, fora_r, gca, gfo)
                        st.cache_data.clear()
                        st.rerun()
                if atual:
                    st.success(tr(
                        f"Resultado registrado: {nm(casa_r)} {atual[0]}×{atual[1]} {nm(fora_r)}. "
                        "Todo o ranking já está condicionado a ele.",
                        f"Result saved: {nm(casa_r)} {atual[0]}×{atual[1]} {nm(fora_r)}. "
                        "The whole ranking is now conditioned on it."))

    # ---- explorador de grupos ----
    st.markdown(f'<div class="mini-label">{tr("Explorador de Grupos · chance de avançar", "Group Explorer · chance to advance")}</div>',
                unsafe_allow_html=True)
    letra = st.selectbox(tr("Grupo", "Group"), sorted(grupos["grupo"].unique()))
    times_g = grupos[grupos["grupo"] == letra]["selecao"].tolist()
    tab = probs[probs["selecao"].isin(times_g)][
        ["selecao", "prob_grupo", "prob_quartas", "prob_titulo"]
    ].copy()
    tab["selecao"] = tab["selecao"].map(nm)
    tab.columns = tr(["Seleção", "Avança", "Quartas", "Título"],
                     ["Team", "Advance", "Quarters", "Title"])
    for c in tab.columns[1:]:
        tab[c] = (tab[c] * 100).map(lambda x: f"{x:.1f}%")
    st.dataframe(tab, hide_index=True, width="stretch")

    # ---- ATUALIZAR DURANTE A COPA ----
    st.markdown(f'<div class="mini-label">{tr("Resultados locais · atualize conforme os jogos terminam", "Local results · update as matches finish")}</div>',
                unsafe_allow_html=True)
    st.caption(tr(
        "Use este painel localmente no seu computador. Quando receber um placar, "
        "preencha os gols e salve. A previsão deixa de sortear aquele jogo e passa "
        "a tratá-lo como fato; todo o ranking recalcula condicionado aos resultados "
        "já digitados.",
        "Use this panel locally on your computer. When you receive a score, enter "
        "the goals and save. The forecast stops simulating that match and treats it "
        "as a fact; the whole ranking recomputes conditioned on entered results."))

    grp_de = dict(zip(grupos["selecao"], grupos["grupo"]))
    editor_df = fixtures[["date", "home_team", "away_team"]].copy()
    editor_df["Grupo"] = editor_df["home_team"].map(grp_de)
    editor_df = editor_df.rename(columns={"date": "Data", "home_team": "Casa", "away_team": "Fora"})
    editor_df["Gols casa"] = [live.get((c, f), (None, None))[0]
                              for c, f in zip(editor_df["Casa"], editor_df["Fora"])]
    editor_df["Gols fora"] = [live.get((c, f), (None, None))[1]
                              for c, f in zip(editor_df["Casa"], editor_df["Fora"])]
    editor_df = editor_df[["Data", "Grupo", "Casa", "Fora", "Gols casa", "Gols fora"]] \
        .sort_values(["Data", "Grupo", "Casa"]).reset_index(drop=True)

    edit = st.data_editor(
        editor_df,
        hide_index=True,
        width="stretch",
        height=320,
        column_config={
            "Data": st.column_config.TextColumn(tr("Data", "Date"), disabled=True, width="small"),
            "Grupo": st.column_config.TextColumn(tr("Grupo", "Group"), disabled=True, width="small"),
            "Casa": st.column_config.TextColumn(tr("Casa", "Home"), disabled=True),
            "Fora": st.column_config.TextColumn(tr("Fora", "Away"), disabled=True),
            "Gols casa": st.column_config.NumberColumn(tr("Gols casa", "Home goals"),
                                                       min_value=0, max_value=20, step=1),
            "Gols fora": st.column_config.NumberColumn(tr("Gols fora", "Away goals"),
                                                       min_value=0, max_value=20, step=1),
        },
        key="editor_resultados",
    )

    cb1, cb2 = st.columns([1, 1])
    with cb1:
        if st.button(tr("💾 Salvar e recalcular", "💾 Save and recalculate"),
                     width="stretch", type="primary"):
            salvar_resultados_locais(edit)
            st.cache_data.clear()
            st.rerun()
    with cb2:
        if st.button(tr("↺ Limpar resultados", "↺ Clear results"), width="stretch"):
            db.salvar_df(pd.DataFrame(
                columns=["home_team", "away_team", "home_score", "away_score"]),
                "live_results")
            st.cache_data.clear()
            st.rerun()

    # ---- nota metodologica + rodape ----
    top = probs.iloc[0]["selecao"]
    fr = probs[probs["selecao"] == "France"]
    fr_pos = (probs["selecao"] == "France").idxmax() + 1 if not fr.empty else "-"
    nota_final = tr(
        f"""Com α={alpha:.1f}, o modelo favorece {nm(top)} e coloca a França em {fr_pos}º.
      O botão α mistura o que o Dixon-Coles mede nos resultados com o talento a que
      ele é cego (ranking FIFA + valor de elenco). α=1 reproduz o modelo antigo
      (Argentina disparada); reduzir α aproxima do consenso das casas (Espanha,
      França e Inglaterra sobem).""",
        f"""At α={alpha:.1f}, the model favors {nm(top)} and ranks France {fr_pos}th.
      The α knob blends what Dixon-Coles measures in results with the talent it's
      blind to (FIFA ranking + squad value). α=1 reproduces the old model
      (Argentina running away); lowering α moves toward the bookmaker consensus
      (Spain, France and England rise).""")
    cred = tr(
        "Modelo · Dixon-Coles + blend de talento (α)<br>"
        "Método · Monte Carlo · dados em SQLite<br>"
        "Validação · backtest Copa 2022 · bracket simplificado",
        "Model · Dixon-Coles + talent blend (α)<br>"
        "Method · Monte Carlo · data in SQLite<br>"
        "Validation · 2022 World Cup backtest · simplified bracket")
    st.markdown(f"""
    <div class="nota">{nota_final}</div>
    <div class="rodape">
      <div class="rodape-cred">{cred}</div>
      <div class="edicao">/26</div>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as _e:
        # Em vez de tela em branco, mostra o erro real (essencial p/ debug na nuvem).
        try:
            st.error("⚠️ O dashboard encontrou um erro ao carregar. Detalhes abaixo:")
            st.exception(_e)
        except Exception:
            raise
