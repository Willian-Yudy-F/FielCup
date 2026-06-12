"""
FielCup — Passo 3: O modelo Dixon-Coles
=======================================

Estima, a partir dos jogos de treino, a FORÇA DE ATAQUE e a FORÇA DE
DEFESA de cada seleção, mais um parâmetro de vantagem de MANDO e a
correção RHO de Dixon-Coles para placares baixos.

Com o modelo treinado é possível prever a distribuição de placares de
qualquer confronto (ex.: P(Brasil 2 x 1 Espanha)) e dela derivar as
probabilidades de vitória, empate e derrota.

A matemática (resumo):
  - Gols de cada lado seguem uma Poisson com média lambda.
  - lambda_casa = exp(ataque_casa - defesa_fora + mando*(nao_neutro))
  - lambda_fora = exp(ataque_fora - defesa_casa)
  - A correção tau(rho) ajusta os 4 placares baixos (0-0,1-0,0-1,1-1).
  - Os parâmetros são achados por MÁXIMA VEROSSIMILHANÇA PONDERADA
    (jogos recentes pesam mais, via a coluna 'peso' do Passo 2).

Uso:
    python src/dixon_coles.py          # treina e salva o modelo
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln  # log(k!) = gammaln(k+1), estável

RAIZ = Path(__file__).resolve().parents[1]
TREINO = RAIZ / "data" / "processed" / "treino.csv"
MODELO_OUT = RAIZ / "data" / "processed" / "modelo_dc.json"


# ----------------------------------------------------------------------
# Funções de baixo nível
# ----------------------------------------------------------------------

def _log_poisson(k, lam):
    """log da probabilidade Poisson de observar k, dado lambda.

    Usar o logaritmo (em vez da probabilidade direta) evita problemas
    numéricos quando multiplicamos milhares de probabilidades.
    """
    return k * np.log(lam) - lam - gammaln(k + 1)


def _log_tau(gc, gf, lam_c, lam_f, rho):
    """log da correção de Dixon-Coles para os 4 placares baixos.

    Vetorizado: recebe arrays e devolve um array do mesmo tamanho.
    Para placares que não são 0-0,1-0,0-1,1-1, a correção é 1
    (log = 0), ou seja, nenhum ajuste.
    """
    tau = np.ones_like(lam_c, dtype=float)

    m00 = (gc == 0) & (gf == 0)
    m01 = (gc == 0) & (gf == 1)
    m10 = (gc == 1) & (gf == 0)
    m11 = (gc == 1) & (gf == 1)

    tau[m00] = 1 - lam_c[m00] * lam_f[m00] * rho
    tau[m01] = 1 + lam_c[m01] * rho
    tau[m10] = 1 + lam_f[m10] * rho
    tau[m11] = 1 - rho

    # tau pode ficar <= 0 para rho extremo; protege o log
    tau = np.clip(tau, 1e-10, None)
    return np.log(tau)


# ----------------------------------------------------------------------
# Treino
# ----------------------------------------------------------------------

def _neg_log_verossimilhanca(params, idx_casa, idx_fora, gc, gf,
                             nao_neutro, pesos, n_times):
    """Função objetivo que o otimizador minimiza.

    params empacota: [ataques (n_times), defesas (n_times), mando, rho].
    Retorna a log-verossimilhança negativa ponderada de todos os jogos.
    """
    ataque = params[:n_times]
    defesa = params[n_times:2 * n_times]
    mando = params[2 * n_times]
    rho = params[2 * n_times + 1]

    # lambdas vetorizados (um por jogo)
    log_lam_c = ataque[idx_casa] - defesa[idx_fora] + mando * nao_neutro
    log_lam_f = ataque[idx_fora] - defesa[idx_casa]
    lam_c = np.exp(log_lam_c)
    lam_f = np.exp(log_lam_f)

    # log-verossimilhança de cada jogo
    ll = (_log_poisson(gc, lam_c)
          + _log_poisson(gf, lam_f)
          + _log_tau(gc, gf, lam_c, lam_f, rho))

    # ponderada pelo decaimento temporal e negada (scipy minimiza)
    return -np.sum(pesos * ll)


def filtrar_times_raros(df, min_jogos=15, manter=None):
    """Remove seleções com poucos jogos (estimativa não confiável).

    Seleções com 2-3 jogos recebem parâmetros extremos e sem sentido
    do otimizador, além de atrapalhar a convergência. Removemos quem
    tem menos de `min_jogos`, exceto as seleções em `manter` (as da
    Copa, que nunca devem ser removidas).
    """
    manter = set(manter or [])
    contagem = pd.concat([df["home_team"], df["away_team"]]).value_counts()
    times_ok = set(contagem[contagem >= min_jogos].index) | manter
    mask = df["home_team"].isin(times_ok) & df["away_team"].isin(times_ok)
    return df[mask].copy()


def treinar(df: pd.DataFrame) -> dict:
    """Estima os parâmetros do modelo via máxima verossimilhança.

    Retorna um dicionário com ataque/defesa por seleção, mando e rho.
    """
    times = sorted(set(df["home_team"]) | set(df["away_team"]))
    idx = {t: i for i, t in enumerate(times)}
    n = len(times)

    # converte tudo para arrays numpy (treino vetorizado = rápido)
    idx_casa = df["home_team"].map(idx).to_numpy()
    idx_fora = df["away_team"].map(idx).to_numpy()
    gc = df["home_score"].to_numpy()
    gf = df["away_score"].to_numpy()
    nao_neutro = (~df["neutral"]).to_numpy().astype(float)
    pesos = df["peso"].to_numpy()

    # chute inicial: ataque/defesa 0, mando 0.25, rho 0
    x0 = np.concatenate([np.zeros(n), np.zeros(n), [0.25], [0.0]])

    # restrição de identificabilidade: soma dos ataques = 0
    restricoes = ({"type": "eq", "fun": lambda p: np.sum(p[:n])},)

    print(f"Treinando com {len(df):,} jogos e {n} selecoes...")
    resultado = minimize(
        _neg_log_verossimilhanca,
        x0,
        args=(idx_casa, idx_fora, gc, gf, nao_neutro, pesos, n),
        method="SLSQP",
        constraints=restricoes,
        options={"maxiter": 300, "ftol": 1e-7, "disp": True},
    )

    p = resultado.x
    return {
        "times": times,
        "ataque": dict(zip(times, p[:n].tolist())),
        "defesa": dict(zip(times, p[n:2 * n].tolist())),
        "mando": float(p[2 * n]),
        "rho": float(p[2 * n + 1]),
    }


# ----------------------------------------------------------------------
# Previsão
# ----------------------------------------------------------------------

def matriz_placares(modelo, casa, fora, neutro=True, max_gols=10):
    """Matriz (max_gols+1 x max_gols+1) com P(placar i x j)."""
    from scipy.stats import poisson

    a, d = modelo["ataque"], modelo["defesa"]
    mando = 0.0 if neutro else modelo["mando"]
    rho = modelo["rho"]

    lam_c = np.exp(a[casa] - d[fora] + mando)
    lam_f = np.exp(a[fora] - d[casa])

    pc = poisson.pmf(np.arange(max_gols + 1), lam_c)
    pf = poisson.pmf(np.arange(max_gols + 1), lam_f)
    m = np.outer(pc, pf)

    # correção de Dixon-Coles nos 4 cantos
    m[0, 0] *= 1 - lam_c * lam_f * rho
    m[0, 1] *= 1 + lam_c * rho
    m[1, 0] *= 1 + lam_f * rho
    m[1, 1] *= 1 - rho

    return m / m.sum()


def probabilidades(modelo, casa, fora, neutro=True):
    """Devolve (P_vitoria_casa, P_empate, P_vitoria_fora)."""
    m = matriz_placares(modelo, casa, fora, neutro=neutro)
    p_casa = np.tril(m, -1).sum()
    p_empate = np.trace(m)
    p_fora = np.triu(m, 1).sum()
    return float(p_casa), float(p_empate), float(p_fora)


def analisar_jogo(modelo, casa, fora, neutro=True):
    """Leitura estatística completa de um confronto.

    A partir da matriz de placares P(i x j) extrai os indicadores que mais
    importam para analisar um jogo de futebol:
      - 1X2: prob. de vitória / empate / derrota
      - xG: gols esperados de cada lado (a média da Poisson de cada time)
      - placar mais provável e o top-5 de placares
      - Over/Under 2.5 gols, Ambos Marcam (BTTS) e jogo sem gols
      - prob. de cada time não sofrer gol (clean sheet)
      - distribuição do total de gols (0,1,2,...)

    Devolve um dicionário pronto para o dashboard exibir.
    """
    m = matriz_placares(modelo, casa, fora, neutro=neutro)
    n = m.shape[0]
    i = np.arange(n)

    p_casa = float(np.tril(m, -1).sum())
    p_emp = float(np.trace(m))
    p_fora = float(np.triu(m, 1).sum())

    # gols esperados (média da matriz em cada eixo)
    xg_casa = float((i[:, None] * m).sum())
    xg_fora = float((i[None, :] * m).sum())

    total = i[:, None] + i[None, :]
    p_over25 = float(m[total >= 3].sum())
    p_under25 = 1.0 - p_over25
    p_sem_gols = float(m[0, 0])
    p_btts = float(1 - m[0, :].sum() - m[:, 0].sum() + m[0, 0])
    cs_casa = float(m[:, 0].sum())   # visitante não marca -> casa não sofre
    cs_fora = float(m[0, :].sum())   # mandante não marca -> visitante não sofre

    # top-5 placares mais prováveis
    pares = [((a, b), float(m[a, b])) for a in range(n) for b in range(n)]
    top = sorted(pares, key=lambda x: -x[1])[:5]
    placar_provavel = top[0][0]

    # distribuição do total de gols (0..6, e 7+)
    dist = {k: float(m[total == k].sum()) for k in range(7)}
    dist["7+"] = float(m[total >= 7].sum())

    return {
        "p_casa": p_casa, "p_empate": p_emp, "p_fora": p_fora,
        "xg_casa": xg_casa, "xg_fora": xg_fora,
        "p_over25": p_over25, "p_under25": p_under25,
        "p_btts": p_btts, "p_sem_gols": p_sem_gols,
        "cs_casa": cs_casa, "cs_fora": cs_fora,
        "placar_provavel": placar_provavel,
        "top_placares": top,
        "dist_total_gols": dist,
    }


# ----------------------------------------------------------------------
# Execução
# ----------------------------------------------------------------------

def main():
    df = pd.read_csv(TREINO, parse_dates=["date"])

    # mantém sempre as 48 seleções da Copa, filtra o resto
    grupos = pd.read_csv(RAIZ / "data" / "processed" / "grupos.csv")
    selecoes_copa = set(grupos["selecao"])
    n_antes = len(df)
    df = filtrar_times_raros(df, min_jogos=15, manter=selecoes_copa)
    print(f"Filtro de times raros: {n_antes:,} -> {len(df):,} jogos")

    modelo = treinar(df)

    with open(MODELO_OUT, "w") as f:
        json.dump(modelo, f)
    print(f"\nModelo salvo em: {MODELO_OUT}")

    # grava os ratings (ataque/defesa) no SQLite -> tabela team_ratings.
    # Mantém o JSON para compatibilidade, mas o banco passa a ser a fonte
    # consultável por SQL e pelos passos seguintes (talento/simulação).
    try:
        import database as db
        ratings = pd.DataFrame({
            "selecao": modelo["times"],
            "ataque": [modelo["ataque"][t] for t in modelo["times"]],
            "defesa": [modelo["defesa"][t] for t in modelo["times"]],
        })
        db.salvar_df(ratings, "team_ratings")
        # guarda os hiperparâmetros globais (mando, rho) numa tabelinha
        params = pd.DataFrame([
            {"parametro": "mando", "valor": modelo["mando"]},
            {"parametro": "rho", "valor": modelo["rho"]},
        ])
        db.salvar_df(params, "model_params")
        print(f"Ratings gravados no banco: team_ratings ({len(ratings)} selecoes)")
    except Exception as e:  # não quebra o treino se o banco não existir
        print(f"[aviso] nao foi possivel gravar no banco: {e}")

    # rankings rápidos para conferir sanidade
    ataque = pd.Series(modelo["ataque"]).sort_values(ascending=False)
    defesa = pd.Series(modelo["defesa"]).sort_values(ascending=False)
    print(f"\nmando = {modelo['mando']:.3f}  |  rho = {modelo['rho']:.3f}")
    print("\nTop 10 ataque:")
    for t, v in ataque.head(10).items():
        print(f"  {t:20s} {v:+.3f}")
    print("\nTop 10 defesa (maior = mais defende):")
    for t, v in defesa.head(10).items():
        print(f"  {t:20s} {v:+.3f}")


if __name__ == "__main__":
    main()
