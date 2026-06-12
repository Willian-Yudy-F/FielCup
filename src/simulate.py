"""
FielCup — Passo 4: Simulação de Monte Carlo da Copa 2026
========================================================

Joga a Copa inteira N vezes (padrão 50.000) e conta com que frequência
cada seleção avança em cada fase e levanta a taça. Usa os ratings
BLENDADOS (resultado + talento) do módulo `talento.py`.

Como é rápido mesmo com 50.000 simulações?
  Tudo é vetorizado em numpy ao longo do eixo das simulações:
    - cada confronto de grupo: gols amostrados de uma Poisson de tamanho N;
    - classificação dos grupos: ordenação por (pontos, saldo, gols) em bloco;
    - mata-mata: cada rodada resolve as N simulações de uma vez via
      indexação avançada numa matriz de probabilidade de avanço.

Formato do mata-mata (simplificado, como documentado no README): os 32
classificados (2 por grupo + 8 melhores terceiros) entram num chaveamento
embaralhado de eliminatória simples; empate é decidido proporcionalmente
à força (pênaltis).

Uso:
    python src/simulate.py            # 50k simulações com alpha padrão
    python src/simulate.py --sims 20000 --alpha 0.5
"""

from pathlib import Path
import argparse
from itertools import combinations
import numpy as np
import pandas as pd

import database as db
from dixon_coles import matriz_placares
from talento import ratings_blendados, ALPHA_PADRAO

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"


# ----------------------------------------------------------------------
# Matrizes de confronto pré-calculadas (uma vez)
# ----------------------------------------------------------------------

def matrizes_confronto(modelo, times):
    """Pré-calcula, para todo par (i,j) entre as seleções da Copa:

      lamA[i,j] = gols esperados de i (mandante nominal) contra j (neutro)
      lamB[i,j] = gols esperados de j contra i
      adv[i,j]  = P(i elimina j num jogo de mata-mata)  (inclui pênaltis)
    """
    n = len(times)
    lamA = np.zeros((n, n))
    lamB = np.zeros((n, n))
    adv = np.zeros((n, n))
    a, d = modelo["ataque"], modelo["defesa"]

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            ti, tj = times[i], times[j]
            lamA[i, j] = np.exp(a[ti] - d[tj])
            lamB[i, j] = np.exp(a[tj] - d[ti])
            m = matriz_placares(modelo, ti, tj, neutro=True)
            p_i = np.tril(m, -1).sum()   # i vence
            p_e = np.trace(m)            # empate
            p_j = np.triu(m, 1).sum()    # j vence
            # empate vai para pênaltis, proporcional à força no tempo normal
            denom = p_i + p_j
            p_pen = p_i / denom if denom > 0 else 0.5
            adv[i, j] = p_i + p_e * p_pen
    return lamA, lamB, adv


# ----------------------------------------------------------------------
# Fase de grupos (vetorizada ao longo das N simulações)
# ----------------------------------------------------------------------

def _resultado_fixo(resultados, ta, tb):
    """Procura um placar real para o confronto ta x tb (em qualquer ordem).

    Devolve (gols_ta, gols_tb) se o jogo já aconteceu, senão None.
    """
    if not resultados:
        return None
    if (ta, tb) in resultados:
        return resultados[(ta, tb)]
    if (tb, ta) in resultados:
        gb, ga = resultados[(tb, ta)]
        return (ga, gb)
    return None


def simular_grupos(grupos, idx, lamA, lamB, N, rng, resultados=None):
    """Retorna, por grupo, os índices de times em 1º/2º/3º em cada sim,
    além do 'score' de classificação dos terceiros (para os 8 melhores).

    Se `resultados` traz o placar real de um confronto, ele é usado como
    fato (igual em todas as simulações) em vez de ser sorteado — é assim
    que a previsão se atualiza conforme a Copa acontece.
    """
    saida = []
    for letra, bloco in grupos.groupby("grupo"):
        times_g = list(bloco["selecao"])
        ig = [idx[t] for t in times_g]               # índices globais
        k = len(times_g)                              # 4

        pts = np.zeros((k, N))
        gd = np.zeros((k, N))
        gf = np.zeros((k, N))

        for a, b in combinations(range(k), 2):
            fixo = _resultado_fixo(resultados, times_g[a], times_g[b])
            if fixo is not None:
                ga = np.full(N, int(fixo[0]))
                gb = np.full(N, int(fixo[1]))
            else:
                ga = rng.poisson(lamA[ig[a], ig[b]], N)
                gb = rng.poisson(lamB[ig[a], ig[b]], N)
            pts[a] += np.where(ga > gb, 3, np.where(ga == gb, 1, 0))
            pts[b] += np.where(gb > ga, 3, np.where(ga == gb, 1, 0))
            gd[a] += ga - gb
            gd[b] += gb - ga
            gf[a] += ga
            gf[b] += gb

        # chave de classificação: pontos > saldo > gols > desempate aleatório
        rnd = rng.random((k, N))
        score = pts * 1e6 + (gd + 100) * 1e3 + gf * 1e1 + rnd
        ordem = np.argsort(-score, axis=0)            # ordem[0] = 1º colocado

        prim = np.array(ig)[ordem[0]]
        seg = np.array(ig)[ordem[1]]
        terc = np.array(ig)[ordem[2]]
        # score do 3º colocado (para comparar entre grupos)
        terc_score = np.take_along_axis(score, ordem[2:3], axis=0)[0]

        saida.append((prim, seg, terc, terc_score))
    return saida


def montar_classificados(grupos_out, N, rng):
    """Junta 1º+2º de cada grupo e os 8 melhores 3ºs -> matriz [N, 32]."""
    primeiros = np.stack([g[0] for g in grupos_out], axis=1)   # [N, 12]
    segundos = np.stack([g[1] for g in grupos_out], axis=1)    # [N, 12]
    terceiros = np.stack([g[2] for g in grupos_out], axis=1)   # [N, 12]
    terc_scores = np.stack([g[3] for g in grupos_out], axis=1)  # [N, 12]

    # os 8 melhores terceiros por simulação
    top8 = np.argsort(-terc_scores, axis=1)[:, :8]             # [N, 8]
    melhores_terc = np.take_along_axis(terceiros, top8, axis=1)  # [N, 8]

    classificados = np.concatenate([primeiros, segundos, melhores_terc], axis=1)  # [N,32]

    # embaralha o chaveamento por simulação (bracket simplificado)
    chaves = rng.random(classificados.shape)
    ordem = np.argsort(chaves, axis=1)
    return np.take_along_axis(classificados, ordem, axis=1)


# ----------------------------------------------------------------------
# Mata-mata (vetorizado: cada rodada resolve as N sims de uma vez)
# ----------------------------------------------------------------------

def jogar_mata_mata(bracket, adv, n_times, rng):
    """Recebe [N, 32] e devolve contagens por fase para cada seleção."""
    N = bracket.shape[0]
    fases = {}  # nome -> contagem por time (bincount)

    atual = bracket
    fases["r32"] = np.bincount(atual.ravel(), minlength=n_times)

    nomes = ["r16", "quartas", "semi", "final", "titulo"]
    for nome in nomes:
        a = atual[:, 0::2]
        b = atual[:, 1::2]
        p = adv[a, b]                       # P(a avança) por confronto [N, m]
        a_vence = rng.random(p.shape) < p
        vencedores = np.where(a_vence, a, b)
        fases[nome] = np.bincount(vencedores.ravel(), minlength=n_times)
        atual = vencedores
    return fases


# ----------------------------------------------------------------------
# Orquestração
# ----------------------------------------------------------------------

def simular(alpha=ALPHA_PADRAO, sims=50000, seed=42, resultados=None):
    """Simula a Copa. `resultados` é um dict {(casa, fora): (gc, gf)} com os
    placares de grupo já conhecidos (opcional) — a previsão se condiciona
    a eles."""
    rng = np.random.default_rng(seed)

    modelo = ratings_blendados(alpha)
    grupos = db.tabela("groups")
    copa = sorted(set(grupos["selecao"]))
    idx = {t: i for i, t in enumerate(copa)}

    # submatriz do modelo só com as seleções da Copa, reindexada 0..47
    sub = {
        "ataque": {t: modelo["ataque"][t] for t in copa},
        "defesa": {t: modelo["defesa"][t] for t in copa},
        "mando": modelo["mando"],
        "rho": modelo["rho"],
    }
    print(f"Simulando {sims:,} Copas (alpha={alpha})...")
    lamA, lamB, adv = matrizes_confronto(sub, copa)

    grupos_out = simular_grupos(grupos, idx, lamA, lamB, sims, rng, resultados)
    bracket = montar_classificados(grupos_out, sims, rng)
    fases = jogar_mata_mata(bracket, adv, len(copa), rng)

    res = pd.DataFrame({
        "selecao": copa,
        "prob_grupo": fases["r32"] / sims,     # avançou da fase de grupos
        "prob_r16": fases["r16"] / sims,       # venceu a 1ª eliminatória
        "prob_quartas": fases["quartas"] / sims,
        "prob_semi": fases["semi"] / sims,
        "prob_final": fases["final"] / sims,
        "prob_titulo": fases["titulo"] / sims,
    }).sort_values("prob_titulo", ascending=False).reset_index(drop=True)
    res["alpha"] = alpha
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=50000)
    ap.add_argument("--alpha", type=float, default=ALPHA_PADRAO)
    args = ap.parse_args()

    res = simular(alpha=args.alpha, sims=args.sims)

    PROC.mkdir(parents=True, exist_ok=True)
    res.to_csv(PROC / "prob_titulo.csv", index=False)
    db.salvar_df(res, "title_probabilities")

    print(f"\nResultado salvo em {PROC/'prob_titulo.csv'} e na tabela title_probabilities\n")
    print(f"{'#':>2} {'Selecao':22s} {'titulo':>7s} {'final':>7s} {'semi':>7s} {'grupo':>7s}")
    print("-" * 56)
    for i, r in res.head(12).iterrows():
        print(f"{i+1:>2} {r['selecao']:22s} "
              f"{r['prob_titulo']*100:>6.1f}% {r['prob_final']*100:>6.1f}% "
              f"{r['prob_semi']*100:>6.1f}% {r['prob_grupo']*100:>6.1f}%")


if __name__ == "__main__":
    main()
