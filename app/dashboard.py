"""FielCup - Dashboard (Swiss poster edition, mono palette)."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from dixon_coles import probabilidades, matriz_placares

PROC = RAIZ / "data" / "processed"

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


def nm(t):
    return TEAM.get(t, (t, "--", ""))[0]


def cd(t):
    return TEAM.get(t, (t, "--", ""))[1]


def tag(t):
    return TEAM.get(t, (t, "--", ""))[2]


@st.cache_data
def load():
    with open(PROC / "modelo_dc.json") as f:
        modelo = json.load(f)
    probs = pd.read_csv(PROC / "prob_titulo.csv")
    grupos = pd.read_csv(PROC / "grupos.csv")
    return modelo, probs, grupos


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
.rodape{display:flex;justify-content:space-between;align-items:flex-end;padding:20px 0 26px;border-top:2px solid var(--tinta);margin-top:26px;}
.rodape-cred{font-family:'Archivo Narrow';font-size:11px;line-height:1.6;color:var(--nevoa);text-transform:uppercase;letter-spacing:0.5px;}
.edicao{font-family:'Archivo';font-weight:800;font-size:42px;letter-spacing:-2px;color:var(--tinta);}
.stSelectbox label{font-family:'Archivo Narrow';text-transform:uppercase;letter-spacing:1px;font-size:12px;color:var(--nevoa);}
div[data-testid="stMetric"]{background:transparent;border-top:2px solid var(--tinta);padding-top:8px;}
div[data-testid="stMetricLabel"]{font-family:'Archivo Narrow';text-transform:uppercase;}
div[data-testid="stMetricValue"]{font-family:'Archivo';font-weight:800;}
</style>
"""


def rank_row(pos, team, val, is_br=False):
    cls = "rank br" if is_br else "rank"
    t = tag(team)
    tg = f'<span class="tg">{t}</span>' if t else ""
    return (f'<div class="{cls}"><div class="rank-n">{pos}</div>'
            f'<div class="rank-nome">{nm(team)}{tg}</div>'
            f'<div class="rank-pct">{val*100:.1f}%</div></div>')


def main():
    st.set_page_config(page_title="FielCup Forecast", page_icon="*", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    modelo, probs, grupos = load()

    rows = ""
    for i, r in probs.head(8).iterrows():
        rows += rank_row(i + 1, r["selecao"], r["prob_titulo"],
                         is_br=(r["selecao"] == "Brazil"))

    st.markdown(f"""
    <div class="poster">
      <div class="barras"><span class="b1"></span><span class="b2"></span><span class="b3"></span></div>
      <div class="titulo">Fiel<span class="cup">Cup</span> Forecast</div>
      <div class="faixa-meta">World Cup 2026 - 50,000 Monte Carlo simulations - validated on WC2022</div>
      <div class="palco">
        <div class="palco-label">Title Probability - Top 8</div>
        {rows}
      </div>
      <div class="mini-label">Matchup Engine</div>
    </div>
    """, unsafe_allow_html=True)

    teams = sorted(grupos["selecao"], key=nm)
    labels = {f"{nm(t)}": t for t in teams}
    keys = list(labels)
    c1, c2 = st.columns(2)
    with c1:
        la = st.selectbox("Team A", keys, index=keys.index("Brazil") if "Brazil" in keys else 0)
    with c2:
        lb = st.selectbox("Team B", keys, index=keys.index("Argentina") if "Argentina" in keys else 1)
    a, b = labels[la], labels[lb]

    if a == b:
        st.warning("Pick two different teams.")
    else:
        pc, pe, pf = probabilidades(modelo, a, b, neutro=True)
        m = matriz_placares(modelo, a, b, neutro=True)
        i, j = np.unravel_index(m.argmax(), m.shape)
        st.markdown(f"""
        <div class="scorebox">
          <div class="sb-team"><div class="sb-cd">{cd(a)}</div><div class="sb-nm">{nm(a)}</div></div>
          <div class="sb-sc">{i}<span class="sb-x">v</span><span class="o">{j}</span></div>
          <div class="sb-team"><div class="sb-cd">{cd(b)}</div><div class="sb-nm">{nm(b)}</div></div>
        </div>
        <div class="cap">most likely scoreline</div>
        """, unsafe_allow_html=True)
        d1, d2, d3 = st.columns(3)
        d1.metric(f"{nm(a)} win", f"{pc*100:.0f}%")
        d2.metric("Draw", f"{pe*100:.0f}%")
        d3.metric(f"{nm(b)} win", f"{pf*100:.0f}%")

    top = probs.iloc[0]["selecao"]
    st.markdown(f"""
    <div class="nota">
      The model favors {nm(top)} on recent results - the strongest defensive
      rating in the field. Bookmakers disagree, fading an aging squad. Two
      valid reads of different evidence: the model weighs recent results,
      the market prices context the model can't see.
    </div>
    <div class="rodape">
      <div class="rodape-cred">
        Model - Dixon-Coles bivariate Poisson<br>
        Method - Monte Carlo x50,000<br>
        Validated - Brier +7.2% vs baseline - bracket simplified
      </div>
      <div class="edicao">/26</div>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
