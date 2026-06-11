"""FielCup - Passo 4: Engine de simulacao de Monte Carlo."""
from pathlib import Path
from collections import defaultdict
import json
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"


def precalcular_matrizes(modelo, confrontos, max_gols=10):
    a, d, rho = modelo["ataque"], modelo["defesa"], modelo["rho"]
    from scipy.stats import poisson
    cache = {}
    arange = np.arange(max_gols + 1)
    for casa, fora in confrontos:
        lam_c = np.exp(a[casa] - d[fora])
        lam_f = np.exp(a[fora] - d[casa])
        pc = poisson.pmf(arange, lam_c)
        pf = poisson.pmf(arange, lam_f)
        m = np.outer(pc, pf)
        m[0, 0] *= 1 - lam_c * lam_f * rho
        m[0, 1] *= 1 + lam_c * rho
        m[1, 0] *= 1 + lam_f * rho
        m[1, 1] *= 1 - rho
        m = m / m.sum()
        cache[(casa, fora)] = m.ravel()
    return cache, max_gols + 1


def sortear_placar(cache, dim, casa, fora, rng):
    if (casa, fora) in cache:
        probs = cache[(casa, fora)]
        idx = rng.choice(probs.size, p=probs)
        return idx // dim, idx % dim
    probs = cache[(fora, casa)]
    idx = rng.choice(probs.size, p=probs)
    return idx % dim, idx // dim


def simular_grupo(times, jogos, cache, dim, rng):
    tab = {t: {"pts": 0, "sg": 0, "gp": 0} for t in times}
    for casa, fora in jogos:
        gc, gf = sortear_placar(cache, dim, casa, fora, rng)
        tab[casa]["gp"] += gc
        tab[fora]["gp"] += gf
        tab[casa]["sg"] += gc - gf
        tab[fora]["sg"] += gf - gc
        if gc > gf:
            tab[casa]["pts"] += 3
        elif gf > gc:
            tab[fora]["pts"] += 3
        else:
            tab[casa]["pts"] += 1
            tab[fora]["pts"] += 1
    ordenado = sorted(times,
        key=lambda t: (tab[t]["pts"], tab[t]["sg"], tab[t]["gp"]),
        reverse=True)
    return ordenado, tab


def simular_mata_mata(bracket, cache, dim, rng, registrar):
    fases = {32: "R32", 16: "Oitavas", 8: "Quartas", 4: "Semi", 2: "Final"}
    atual = bracket
    while len(atual) > 1:
        fase = fases.get(len(atual), f"{len(atual)}")
        for t in atual:
            registrar(t, fase)
        proxima = []
        for i in range(0, len(atual), 2):
            a, b = atual[i], atual[i + 1]
            gc, gf = sortear_placar(cache, dim, a, b, rng)
            while gc == gf:
                gc, gf = sortear_placar(cache, dim, a, b, rng)
            vencedor = a if gc > gf else b
            proxima.append(vencedor)
        atual = proxima
    return atual[0]


def montar_jogos_por_grupo(copa, grupos):
    sel2grupo = dict(zip(grupos["selecao"], grupos["grupo"]))
    jogos = defaultdict(list)
    for _, j in copa.iterrows():
        g = sel2grupo[j["home_team"]]
        jogos[g].append((j["home_team"], j["away_team"]))
    times = {g: sorted(sub["selecao"]) for g, sub in grupos.groupby("grupo")}
    return times, jogos


def simular_torneio(times_grupo, jogos_grupo, cache, dim, rng, stats):
    primeiros, segundos, terceiros = [], [], []
    for g in sorted(times_grupo):
        classif, tab = simular_grupo(times_grupo[g], jogos_grupo[g], cache, dim, rng)
        primeiros.append(classif[0])
        segundos.append(classif[1])
        terceiros.append((classif[2], tab[classif[2]]))
        for t in classif[:2]:
            stats[t]["classificou"] += 1
    terceiros.sort(key=lambda x: (x[1]["pts"], x[1]["sg"], x[1]["gp"]), reverse=True)
    melhores3 = [t[0] for t in terceiros[:8]]
    for t in melhores3:
        stats[t]["classificou"] += 1
    bracket = primeiros + segundos + melhores3
    rng.shuffle(bracket)
    def registrar(t, fase):
        stats[t][fase] += 1
    campeao = simular_mata_mata(bracket, cache, dim, rng, registrar)
    stats[campeao]["campeao"] += 1


def main(n_sim=50000, seed=42):
    with open(PROC / "modelo_dc.json") as f:
        modelo = json.load(f)
    copa = pd.read_csv(PROC / "copa2026.csv", parse_dates=["date"])
    grupos = pd.read_csv(PROC / "grupos.csv")
    times_grupo, jogos_grupo = montar_jogos_por_grupo(copa, grupos)
    selecoes = sorted(grupos["selecao"])
    confrontos = [(a, b) for a in selecoes for b in selecoes if a != b]
    cache, dim = precalcular_matrizes(modelo, confrontos)
    chaves = ["classificou", "R32", "Oitavas", "Quartas", "Semi", "Final", "campeao"]
    stats = {t: {k: 0 for k in chaves} for t in selecoes}
    rng = np.random.default_rng(seed)
    print(f"Rodando {n_sim:,} simulacoes da Copa 2026...")
    for i in range(n_sim):
        simular_torneio(times_grupo, jogos_grupo, cache, dim, rng, stats)
        if (i + 1) % 10000 == 0:
            print(f"  {i+1:,} simulacoes concluidas")
    linhas = []
    for t in selecoes:
        linhas.append({
            "selecao": t,
            "prob_titulo": stats[t]["campeao"] / n_sim,
            "prob_final": stats[t]["Final"] / n_sim,
            "prob_semi": stats[t]["Semi"] / n_sim,
            "prob_classificar": stats[t]["classificou"] / n_sim,
        })
    res = pd.DataFrame(linhas).sort_values("prob_titulo", ascending=False)
    res.to_csv(PROC / "prob_titulo.csv", index=False)
    print("\n=== TOP 15 FAVORITAS AO TITULO ===")
    for _, r in res.head(15).iterrows():
        print(f"  {r['selecao']:18s} titulo {r['prob_titulo']:5.1%}  "
              f"final {r['prob_final']:5.1%}  "
              f"classifica {r['prob_classificar']:5.1%}")
    print(f"\nResultado salvo em: {PROC / 'prob_titulo.csv'}")


if __name__ == "__main__":
    main()
