"""FielCup - Passo 3: O modelo Dixon-Coles."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln

RAIZ = Path(__file__).resolve().parents[1]
TREINO = RAIZ / "data" / "processed" / "treino.csv"
MODELO_OUT = RAIZ / "data" / "processed" / "modelo_dc.json"


def _log_poisson(k, lam):
    return k * np.log(lam) - lam - gammaln(k + 1)


def _log_tau(gc, gf, lam_c, lam_f, rho):
    tau = np.ones_like(lam_c, dtype=float)
    m00 = (gc == 0) & (gf == 0)
    m01 = (gc == 0) & (gf == 1)
    m10 = (gc == 1) & (gf == 0)
    m11 = (gc == 1) & (gf == 1)
    tau[m00] = 1 - lam_c[m00] * lam_f[m00] * rho
    tau[m01] = 1 + lam_c[m01] * rho
    tau[m10] = 1 + lam_f[m10] * rho
    tau[m11] = 1 - rho
    tau = np.clip(tau, 1e-10, None)
    return np.log(tau)


def filtrar_times_raros(df, min_jogos=15, manter=None):
    manter = set(manter or [])
    contagem = pd.concat([df["home_team"], df["away_team"]]).value_counts()
    times_ok = set(contagem[contagem >= min_jogos].index) | manter
    mask = df["home_team"].isin(times_ok) & df["away_team"].isin(times_ok)
    return df[mask].copy()


def _neg_log_verossimilhanca(params, idx_casa, idx_fora, gc, gf, nao_neutro, pesos, n_times):
    ataque = params[:n_times]
    defesa = params[n_times:2 * n_times]
    mando = params[2 * n_times]
    rho = params[2 * n_times + 1]
    log_lam_c = ataque[idx_casa] - defesa[idx_fora] + mando * nao_neutro
    log_lam_f = ataque[idx_fora] - defesa[idx_casa]
    lam_c = np.exp(log_lam_c)
    lam_f = np.exp(log_lam_f)
    ll = (_log_poisson(gc, lam_c) + _log_poisson(gf, lam_f)
          + _log_tau(gc, gf, lam_c, lam_f, rho))
    return -np.sum(pesos * ll)


def treinar(df):
    times = sorted(set(df["home_team"]) | set(df["away_team"]))
    idx = {t: i for i, t in enumerate(times)}
    n = len(times)
    idx_casa = df["home_team"].map(idx).to_numpy()
    idx_fora = df["away_team"].map(idx).to_numpy()
    gc = df["home_score"].to_numpy()
    gf = df["away_score"].to_numpy()
    nao_neutro = (~df["neutral"]).to_numpy().astype(float)
    pesos = df["peso"].to_numpy()
    x0 = np.concatenate([np.zeros(n), np.zeros(n), [0.25], [0.0]])
    restricoes = ({"type": "eq", "fun": lambda p: np.sum(p[:n])},)
    print(f"Treinando com {len(df):,} jogos e {n} selecoes...")
    resultado = minimize(
        _neg_log_verossimilhanca, x0,
        args=(idx_casa, idx_fora, gc, gf, nao_neutro, pesos, n),
        method="SLSQP", constraints=restricoes,
        options={"maxiter": 300, "ftol": 1e-7, "disp": True})
    p = resultado.x
    return {
        "times": times,
        "ataque": dict(zip(times, p[:n].tolist())),
        "defesa": dict(zip(times, p[n:2 * n].tolist())),
        "mando": float(p[2 * n]),
        "rho": float(p[2 * n + 1]),
    }


def matriz_placares(modelo, casa, fora, neutro=True, max_gols=10):
    from scipy.stats import poisson
    a, d = modelo["ataque"], modelo["defesa"]
    mando = 0.0 if neutro else modelo["mando"]
    rho = modelo["rho"]
    lam_c = np.exp(a[casa] - d[fora] + mando)
    lam_f = np.exp(a[fora] - d[casa])
    pc = poisson.pmf(np.arange(max_gols + 1), lam_c)
    pf = poisson.pmf(np.arange(max_gols + 1), lam_f)
    m = np.outer(pc, pf)
    m[0, 0] *= 1 - lam_c * lam_f * rho
    m[0, 1] *= 1 + lam_c * rho
    m[1, 0] *= 1 + lam_f * rho
    m[1, 1] *= 1 - rho
    return m / m.sum()


def probabilidades(modelo, casa, fora, neutro=True):
    m = matriz_placares(modelo, casa, fora, neutro=neutro)
    p_casa = np.tril(m, -1).sum()
    p_empate = np.trace(m)
    p_fora = np.triu(m, 1).sum()
    return float(p_casa), float(p_empate), float(p_fora)


def main():
    df = pd.read_csv(TREINO, parse_dates=["date"])
    grupos = pd.read_csv(RAIZ / "data" / "processed" / "grupos.csv")
    selecoes_copa = set(grupos["selecao"])
    n_antes = len(df)
    df = filtrar_times_raros(df, min_jogos=15, manter=selecoes_copa)
    print(f"Filtro de times raros: {n_antes:,} -> {len(df):,} jogos")
    modelo = treinar(df)
    with open(MODELO_OUT, "w") as f:
        json.dump(modelo, f)
    print(f"\nModelo salvo em: {MODELO_OUT}")
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
