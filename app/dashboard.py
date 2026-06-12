"""FielCup - Dashboard (Swiss poster edition, mono palette).

Agora com:
  - botao ALPHA (resultado <-> talento) que re-ranqueia a Copa ao vivo;
  - painel MODELO vs MERCADO (casas de aposta, junho/2026);
  - grafico de probabilidade de titulo (Top 12);
  - motor de confrontos usando os ratings blendados.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from dixon_coles import probabilidades, matriz_placares, analisar_jogo
from talento import ratings_blendados, indice_talento, detalhe_blend
from simulate import simular
import database as db

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
    fixtures = db.tabela("fixtures_2026")[["home_team", "away_team"]]
    return grupos, talento, fixtures


def ler_resultados_live() -> dict:
    """Lê os placares reais já digitados (tabela live_results)."""
    try:
        df = db.tabela("live_results")
    except Exception:
        return {}
    out = {}
    for _, r in df.iterrows():
        if pd.notna(r["home_score"]) and pd.notna(r["away_score"]):
            out[(r["home_team"], r["away_team"])] = (int(r["home_score"]), int(r["away_score"]))
    return out


def salvar_resultados_live(df: pd.DataFrame) -> None:
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
    """Insere/atualiza o placar de UM jogo na tabela live_results."""
    atuais = ler_resultados_live()
    atuais[(casa, fora)] = (int(gc), int(gf))
    out = pd.DataFrame(
        [{"home_team": h, "away_team": a, "home_score": s[0], "away_score": s[1]}
         for (h, a), s in atuais.items()])
    db.salvar_df(out, "live_results")


def buscar_resultados_api(fixtures: pd.DataFrame):
    """(Opcional) Busca resultados finalizados da Copa na API-Football e
    grava os que casam com jogos de grupo em live_results.

    É totalmente defensivo: se faltar chave, biblioteca ou rede, devolve
    uma mensagem amigável em vez de quebrar o dashboard.

    Retorna (qtde_gravada, mensagem).
    """
    import os
    if not os.environ.get("API_FOOTBALL_KEY"):
        return 0, ("Defina a chave antes de abrir o dashboard:\n"
                   "`export API_FOOTBALL_KEY='sua_chave'` "
                   "(gratuita em dashboard.api-football.com).")
    try:
        from api_collector import baixar_resultados_copa
        jogos = baixar_resultados_copa()
    except ModuleNotFoundError:
        return 0, "Falta a biblioteca `requests`. Rode: `pip install requests`."
    except Exception as e:
        return 0, f"Não consegui consultar a API: {e}"

    if jogos is None or jogos.empty:
        return 0, "A API não retornou jogos finalizados ainda."

    fx_pares = set(zip(fixtures["home_team"], fixtures["away_team"]))
    gravados = 0
    for _, r in jogos.iterrows():
        h, a = r["home_team"], r["away_team"]
        if (h, a) in fx_pares:
            upsert_resultado(h, a, r["home_score"], r["away_score"]); gravados += 1
        elif (a, h) in fx_pares:
            upsert_resultado(a, h, r["away_score"], r["home_score"]); gravados += 1
    nota = "" if gravados else (" Nenhum bateu com os nomes do dataset — "
                                "os nomes da API podem diferir; use o registro manual.")
    return gravados, f"{gravados} resultado(s) importado(s) da API.{nota}"


@st.cache_data(show_spinner="Simulando a Copa...")
def simular_cache(alpha: float, res_key: tuple, sims: int = 20000):
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

    linhas = '<div class="mvm"><div class="mvm-h"></div><div class="mvm-h">Modelo</div><div class="mvm-h">Mercado (odds)</div>'
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


def main():
    st.set_page_config(page_title="FielCup Forecast", page_icon="*", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)

    grupos, talento, fixtures = carregar_estaticos()
    live = ler_resultados_live()
    res_key = tuple(sorted((h, a, gh, ga) for (h, a), (gh, ga) in live.items()))

    # ---- controle: botao alpha ----
    st.markdown('<div class="mini-label">Modelo: resultado &harr; talento</div>',
                unsafe_allow_html=True)
    alpha = st.slider(
        "ALPHA — peso dos resultados (1.0) vs talento FIFA+elenco (0.0)",
        min_value=0.0, max_value=1.0, value=0.6, step=0.1,
    )
    if live:
        st.caption(f"📅 Análise condicionada a {len(live)} resultado(s) real(is) da Copa já digitado(s).")

    probs = simular_cache(alpha, res_key)
    modelo = modelo_cache(alpha)

    rows = ""
    for i, r in probs.head(8).iterrows():
        rows += rank_row(i + 1, r["selecao"], r["prob_titulo"],
                         is_br=(r["selecao"] == "Brazil"))

    # ---- RESUMO em linguagem simples (o que importa num relance no celular) ----
    t3 = probs.head(3).reset_index(drop=True)
    cond = (f" Isso já considera <b>{len(live)} jogo(s) real(is)</b> da Copa que você registrou."
            if live else "")
    podio = "".join(
        f'<div><div class="pp">{r["prob_titulo"]*100:.0f}%</div>'
        f'<div class="pn">{nm(r["selecao"])}</div></div>'
        for _, r in t3.iterrows())
    st.markdown(f"""
    <div class="resumo">
      <h4>📊 O que está acontecendo</h4>
      <p>Hoje o modelo aponta <b>{nm(t3.loc[0,'selecao'])}</b> como o favorito ao título
      ({t3.loc[0,'prob_titulo']*100:.0f}% de chance), seguido de
      <b>{nm(t3.loc[1,'selecao'])}</b> e <b>{nm(t3.loc[2,'selecao'])}</b>.{cond}</p>
      <p>👉 Quanto <b>maior a %</b>, maior a chance de ser campeão — número obtido
      <b>simulando a Copa inteira 20 mil vezes</b>. Role para baixo para ver a análise
      de cada jogo e registrar os resultados.</p>
      <div class="podio">{podio}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="poster">
      <div class="barras"><span class="b1"></span><span class="b2"></span><span class="b3"></span></div>
      <div class="titulo">Fiel<span class="cup">Cup</span> Forecast</div>
      <div class="faixa-meta">World Cup 2026 · 20k Monte Carlo · blend resultado+talento (α={alpha:.1f})</div>
      <div class="palco">
        <div class="palco-label">Title Probability · Top 8</div>
        {rows}
      </div>
      <div class="mini-label">Modelo vs Mercado · favoritos das casas</div>
      {painel_modelo_vs_mercado(probs)}
    </div>
    """, unsafe_allow_html=True)

    # ---- grafico de barras top 12 ----
    st.markdown('<div class="mini-label">Probabilidade de título · Top 12</div>',
                unsafe_allow_html=True)
    top12 = probs.head(12).copy()
    top12["seleção"] = top12["selecao"].map(nm)
    chart = top12.set_index("seleção")["prob_titulo"] * 100
    st.bar_chart(chart, color="#C0392B", height=280)

    # ---- COMO O MODELO PENSA (explicação + cálculo ao vivo) ----
    st.markdown('<div class="mini-label">Como o modelo chega nesses números</div>',
                unsafe_allow_html=True)
    with st.expander("Entenda o raciocínio em 4 passos (linguagem simples)", expanded=False):
        st.markdown("""
**A ideia central:** um time é forte por dois motivos que o modelo mistura.

1. **O que ele faz em campo (resultados).** Olhamos ~8.000 jogos de seleções
   e medimos, para cada uma, uma **força de ataque** (quantos gols costuma
   fazer) e uma **força de defesa** (quantos costuma evitar). Jogos recentes
   pesam mais. Isso é o modelo *Dixon-Coles*. Somando ataque + defesa temos a
   **"força só pelos resultados"**.

2. **O talento que ele tem (mesmo que os resultados ainda não mostrem).**
   Resultados de seleção escondem o talento individual — por isso a França
   (cheia de craques) aparecia mal. Então somamos dois sinais externos:
   o **ranking FIFA** e o **valor de mercado do elenco** (Transfermarkt).
   Juntos formam o **"índice de talento"**.

3. **A mistura (o botão α).** A força final é uma média ponderada:
   `força = α × resultados + (1−α) × talento`. Com **α=1** vale só o que
   aconteceu em campo (a Argentina dispara); diminuindo α, o talento entra e
   **França, Espanha e Inglaterra sobem** — perto do que as casas de aposta dizem.

4. **Jogar a Copa 50 mil vezes.** Com a força final de cada time, sorteamos
   o placar de cada jogo milhares de vezes (grupos + mata-mata). A
   **probabilidade de título** é simplesmente *em quantas dessas 50 mil Copas
   o time levantou a taça*.

> Para comparar times de "réguas" diferentes (gols, pontos FIFA, euros),
> tudo é convertido para **z-score**: quantos desvios-padrão acima (+) ou
> abaixo (−) da média o time está. Por isso os números aparecem como +1,2 / −0,4.
        """)

    det = detalhe_cache(alpha)
    nomes_ord = det["selecao"].tolist()
    escolha = st.selectbox("Veja a conta de um time específico:", nomes_ord,
                           index=nomes_ord.index("France") if "France" in nomes_ord else 0,
                           format_func=nm)
    d = det[det["selecao"] == escolha].iloc[0]
    pos_final = nomes_ord.index(escolha) + 1
    prob_t = probs[probs["selecao"] == escolha]["prob_titulo"]
    prob_t = float(prob_t.iloc[0]) * 100 if not prob_t.empty else 0.0

    st.markdown(f"""
| Passo | Ingrediente | Valor | Em z-score |
|---|---|---:|---:|
| 1 | Ataque (Dixon-Coles) | {d['ataque']:+.2f} | — |
| 1 | Defesa (Dixon-Coles) | {d['defesa']:+.2f} | — |
| 1 | **Força só pelos resultados** | **{d['forca_dc']:+.2f}** | **{d['z_resultado']:+.2f}** |
| 2 | Ranking FIFA | {d['fifa_points']:.0f} pts | {d['z_fifa']:+.2f} |
| 2 | Valor do elenco | €{d['valor_mi']:.0f} mi | {d['z_valor']:+.2f} |
| 2 | **Índice de talento** | — | **{d['indice_talento']:+.2f}** |
| 3 | **Blend** = {alpha:.1f}×({d['z_resultado']:+.2f}) + {1-alpha:.1f}×({d['indice_talento']:+.2f}) | — | **{d['blend']:+.2f}** |
| 4 | **Força final → posição** | **{pos_final}º** | **{d['forca_final']:+.2f}** |

**Em palavras:** com α={alpha:.1f}, {nm(escolha)} tem força de resultados
{d['z_resultado']:+.2f} e talento {d['indice_talento']:+.2f}. A mistura dá
{d['blend']:+.2f}, o que coloca o time em **{pos_final}º** na força e resulta em
**{prob_t:.1f}% de chance de título** nas 20 mil simulações.
    """)

    # ---- ANÁLISE DE JOGO (leitura estatística completa) ----
    st.markdown('<div class="mini-label">Análise de Jogo · a leitura estatística</div>',
                unsafe_allow_html=True)
    teams = sorted(grupos["selecao"], key=nm)
    labels = {f"{nm(t)}": t for t in teams}
    keys = list(labels)
    c1, c2 = st.columns(2)
    with c1:
        la = st.selectbox("Time A", keys, index=keys.index("Brazil") if "Brazil" in keys else 0)
    with c2:
        lb = st.selectbox("Time B", keys, index=keys.index("France") if "France" in keys else 1)
    a, b = labels[la], labels[lb]

    if a == b:
        st.warning("Escolha dois times diferentes.")
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
        <div class="cap">placar mais provável · α={alpha:.1f}</div>
        """, unsafe_allow_html=True)

        # 1X2
        d1, d2, d3 = st.columns(3)
        d1.metric(f"{nm(a)} vence", f"{an['p_casa']*100:.0f}%")
        d2.metric("Empate", f"{an['p_empate']*100:.0f}%")
        d3.metric(f"{nm(b)} vence", f"{an['p_fora']*100:.0f}%")

        # quadro de indicadores principais
        st.markdown(f"""
| Indicador estatístico | {nm(a)} | {nm(b)} |
|---|:--:|:--:|
| **Gols esperados (xG)** | **{an['xg_casa']:.2f}** | **{an['xg_fora']:.2f}** |
| Probabilidade de vencer | {an['p_casa']*100:.0f}% | {an['p_fora']*100:.0f}% |
| Não sofrer gol (clean sheet) | {an['cs_casa']*100:.0f}% | {an['cs_fora']*100:.0f}% |

| Mercado de gols | Probabilidade |
|---|:--:|
| Mais de 2,5 gols (Over 2.5) | {an['p_over25']*100:.0f}% |
| Menos de 2,5 gols (Under 2.5) | {an['p_under25']*100:.0f}% |
| Ambos marcam (BTTS) | {an['p_btts']*100:.0f}% |
| Jogo sem gols (0×0) | {an['p_sem_gols']*100:.0f}% |
        """)

        # top-5 placares + distribuição do total de gols
        cc1, cc2 = st.columns(2)
        with cc1:
            st.caption("Placares mais prováveis")
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
            st.caption("Distribuição do total de gols")
            dist = an["dist_total_gols"]
            serie = pd.Series({k: v * 100 for k, v in dist.items()})
            st.bar_chart(serie, color="#1E1E1E", height=200)

        # leitura automática (narrativa)
        fav, pfav = (nm(a), an["p_casa"]) if an["p_casa"] >= an["p_fora"] else (nm(b), an["p_fora"])
        tendencia = "muitos gols" if an["p_over25"] >= 0.5 else "poucos gols"
        st.markdown(f"""
        <div class="nota">
          <b>Leitura do modelo:</b> {fav} é o favorito ({pfav*100:.0f}% de vitória),
          mas com {an['p_empate']*100:.0f}% de chance de empate o jogo é
          {'equilibrado' if abs(an['p_casa']-an['p_fora'])<0.12 else 'inclinado'}.
          O ataque esperado é de {an['xg_casa']:.2f} × {an['xg_fora']:.2f} gols, o que
          aponta para um jogo de <b>{tendencia}</b> (Over 2,5 = {an['p_over25']*100:.0f}%)
          e {an['p_btts']*100:.0f}% de chance de ambos marcarem.
        </div>
        """, unsafe_allow_html=True)

        # registrar o placar real (só se for um jogo de grupo da Copa)
        fx_pares = set(zip(fixtures["home_team"], fixtures["away_team"]))
        if (a, b) in fx_pares:
            casa_r, fora_r = a, b
        elif (b, a) in fx_pares:
            casa_r, fora_r = b, a
        else:
            casa_r = None

        if casa_r is not None:
            with st.expander("📝 Registrar o placar REAL deste jogo (atualiza a previsão)"):
                atual = live.get((casa_r, fora_r))
                st.caption(f"Jogo da fase de grupos: {nm(casa_r)} (mandante) × {nm(fora_r)}.")
                rc1, rc2, rc3 = st.columns([1, 1, 2])
                with rc1:
                    gca = st.number_input(f"Gols {nm(casa_r)}", min_value=0, max_value=20,
                                          value=int(atual[0]) if atual else 0, key="rg_casa")
                with rc2:
                    gfo = st.number_input(f"Gols {nm(fora_r)}", min_value=0, max_value=20,
                                          value=int(atual[1]) if atual else 0, key="rg_fora")
                with rc3:
                    st.write("")
                    st.write("")
                    if st.button("💾 Salvar placar e recalcular", type="primary"):
                        upsert_resultado(casa_r, fora_r, gca, gfo)
                        st.cache_data.clear()
                        st.rerun()
                if atual:
                    st.success(f"Resultado registrado: {nm(casa_r)} {atual[0]}×{atual[1]} {nm(fora_r)}. "
                               "Todo o ranking já está condicionado a ele.")

    # ---- explorador de grupos ----
    st.markdown('<div class="mini-label">Group Explorer · chance de avançar</div>',
                unsafe_allow_html=True)
    letra = st.selectbox("Grupo", sorted(grupos["grupo"].unique()))
    times_g = grupos[grupos["grupo"] == letra]["selecao"].tolist()
    tab = probs[probs["selecao"].isin(times_g)][
        ["selecao", "prob_grupo", "prob_quartas", "prob_titulo"]
    ].copy()
    tab["selecao"] = tab["selecao"].map(nm)
    tab.columns = ["Seleção", "Avança", "Quartas", "Título"]
    for c in ["Avança", "Quartas", "Título"]:
        tab[c] = (tab[c] * 100).map(lambda x: f"{x:.1f}%")
    st.dataframe(tab, hide_index=True, use_container_width=True)

    # ---- ATUALIZAR DURANTE A COPA ----
    st.markdown('<div class="mini-label">Durante a Copa · digite os resultados reais</div>',
                unsafe_allow_html=True)
    st.caption(
        "À medida que os jogos da fase de grupos acontecem, preencha o placar. "
        "A previsão deixa de *sortear* aquele jogo e passa a tratá-lo como fato — "
        "todo o ranking acima se recalcula condicionado ao que já rolou. "
        "Dica: dá para registrar um jogo por vez, com análise, na seção *Análise de Jogo* acima."
    )

    with st.expander("⚡ Opcional: importar resultados automaticamente (API-Football)"):
        st.caption("Precisa de uma chave gratuita em dashboard.api-football.com, "
                   "exportada antes de abrir o dashboard (`export API_FOOTBALL_KEY=...`).")
        if st.button("Buscar resultados finalizados da Copa"):
            n, msg = buscar_resultados_api(fixtures)
            (st.success if n else st.info)(msg)
            if n:
                st.cache_data.clear()
                st.rerun()

    grp_de = dict(zip(grupos["selecao"], grupos["grupo"]))
    editor_df = fixtures.copy()
    editor_df["Grupo"] = editor_df["home_team"].map(grp_de)
    editor_df = editor_df.rename(columns={"home_team": "Casa", "away_team": "Fora"})
    editor_df["Gols casa"] = [live.get((c, f), (None, None))[0]
                              for c, f in zip(editor_df["Casa"], editor_df["Fora"])]
    editor_df["Gols fora"] = [live.get((c, f), (None, None))[1]
                              for c, f in zip(editor_df["Casa"], editor_df["Fora"])]
    editor_df = editor_df[["Grupo", "Casa", "Fora", "Gols casa", "Gols fora"]] \
        .sort_values(["Grupo", "Casa"]).reset_index(drop=True)

    edit = st.data_editor(
        editor_df,
        hide_index=True,
        use_container_width=True,
        height=320,
        column_config={
            "Grupo": st.column_config.TextColumn(disabled=True, width="small"),
            "Casa": st.column_config.TextColumn(disabled=True),
            "Fora": st.column_config.TextColumn(disabled=True),
            "Gols casa": st.column_config.NumberColumn(min_value=0, max_value=20, step=1),
            "Gols fora": st.column_config.NumberColumn(min_value=0, max_value=20, step=1),
        },
        key="editor_resultados",
    )

    cb1, cb2 = st.columns([1, 1])
    with cb1:
        if st.button("💾 Salvar e recalcular", use_container_width=True, type="primary"):
            salvar_resultados_live(edit)
            st.cache_data.clear()
            st.rerun()
    with cb2:
        if st.button("↺ Limpar resultados", use_container_width=True):
            db.salvar_df(pd.DataFrame(
                columns=["home_team", "away_team", "home_score", "away_score"]),
                "live_results")
            st.cache_data.clear()
            st.rerun()

    # ---- nota metodologica + rodape ----
    top = probs.iloc[0]["selecao"]
    fr = probs[probs["selecao"] == "France"]
    fr_pos = (probs["selecao"] == "France").idxmax() + 1 if not fr.empty else "-"
    st.markdown(f"""
    <div class="nota">
      Com α={alpha:.1f}, o modelo favorece {nm(top)} e coloca a França em {fr_pos}º.
      O botão α mistura o que o Dixon-Coles mede nos resultados com o talento que
      ele é cego (ranking FIFA + valor de elenco). α=1 reproduz o modelo antigo
      (Argentina disparada); reduzir α aproxima do consenso das casas (Espanha,
      França e Inglaterra sobem).
    </div>
    <div class="rodape">
      <div class="rodape-cred">
        Model · Dixon-Coles + blend de talento (α)<br>
        Method · Monte Carlo · dados em SQLite<br>
        Validated · Brier +5.2% vs baseline · bracket simplificado
      </div>
      <div class="edicao">/26</div>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
