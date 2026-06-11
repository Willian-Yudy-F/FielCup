"""FielCup - Passo 5: Validacao do modelo (backtesting)."""
from pathlib import Path
import numpy as np
import pandas as pd
from dixon_coles import treinar, filtrar_times_raros, probabilidades

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw" / "results.csv"
DATA_COPA_2022 = "2022-11-01"
XI = 0.0019


def preparar_treino_ate(df, data_limite, xi=XI):
    treino = df.dropna(subset=["home_score", "away_score"]).copy()
    treino = treino[treino["date"] < data_limite]
    treino = treino[treino["date"] >= "2018-01-01"].copy()
    treino["home_score"] = treino["home_score"].astype(int)
    treino["away_score"] = treino["away_score"].astype(int)
    dias = (pd.Timestamp(data_limite) - treino["date"]).dt.days
    treino["peso"] = np.exp(-xi * dias)
    return treino


def resultado_real(gc, gf):
    if gc > gf:
        return 0
    if gc == gf:
        return 1
    return 2


def brier(probs, real):
    alvo = np.zeros(3)
    alvo[real] = 1.0
    return float(np.sum((np.array(probs) - alvo) ** 2))


def avaliar():
    df = pd.read_csv(RAW, parse_dates=["date"])
    treino = preparar_treino_ate(df, DATA_COPA_2022)
    copa22 = df[(df["tournament"] == "FIFA World Cup")
                & (df["date"].dt.year == 2022)].dropna(
                    subset=["home_score", "away_score"]).copy()
    selecoes_copa = set(copa22["home_team"]) | set(copa22["away_team"])
    treino = filtrar_times_raros(treino, min_jogos=15, manter=selecoes_copa)
    print(f"Treinando com {len(treino):,} jogos (ate {DATA_COPA_2022})...")
    modelo = treinar(treino)
    times_modelo = set(modelo["ataque"].keys())
    brier_modelo, brier_base = [], []
    acertos_modelo, acertos_base = 0, 0
    n = 0
    for _, j in copa22.iterrows():
        casa, fora = j["home_team"], j["away_team"]
        if casa not in times_modelo or fora not in times_modelo:
            continue
        real = resultado_real(j["home_score"], j["away_score"])
        probs = probabilidades(modelo, casa, fora, neutro=True)
        base = [1/3, 1/3, 1/3]
        brier_modelo.append(brier(probs, real))
        brier_base.append(brier(base, real))
        if int(np.argmax(probs)) == real:
            acertos_modelo += 1
        if real == 1:
            acertos_base += 1
        n += 1
    bm, bb = np.mean(brier_modelo), np.mean(brier_base)
    print("\n=== VALIDACAO: Copa 2022 (backtesting) ===")
    print(f"Jogos avaliados:            {n}")
    print(f"Brier score do MODELO:      {bm:.4f}  (menor = melhor)")
    print(f"Brier score do BASELINE:    {bb:.4f}  (chute 1/3,1/3,1/3)")
    melhora = (bb - bm) / bb * 100
    print(f"Melhora sobre o baseline:   {melhora:+.1f}%")
    print(f"Acuracia top-1 do MODELO:   {acertos_modelo/n:.1%}")
    print("------------------------------------------")
    if bm < bb:
        print("OK: o modelo BATE o baseline -> tem poder preditivo.")
    else:
        print("ATENCAO: o modelo NAO bate o baseline.")


if __name__ == "__main__":
    avaliar()
