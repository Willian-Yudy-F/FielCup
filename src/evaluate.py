"""
FielCup — Passo 5: Validação por backtesting (Copa 2022)
========================================================

A pergunta honesta de qualquer modelo preditivo é: "ele acerta em dados
que NUNCA viu?". Aqui treinamos o Dixon-Coles SÓ com jogos anteriores a
novembro/2022 e pedimos que ele preveja a Copa de 2022 (que ele não viu).

Medimos a qualidade com:
  - Brier score (quanto menor, melhor): erro quadrático médio das
    probabilidades previstas para vitória/empate/derrota.
  - Acurácia: fração de jogos em que o resultado mais provável aconteceu.

Comparamos contra um BASELINE ingênuo (sempre prevê a frequência média
histórica de mandante/empate/visitante). Se o modelo não bate o baseline,
ele não está aprendendo nada útil.

Uso:
    python src/evaluate.py
"""

import numpy as np
import pandas as pd

import database as db
from dixon_coles import treinar, probabilidades, filtrar_times_raros

CORTE = "2022-11-01"   # treina só com o que veio antes da Copa 2022
XI = 0.0019


def _peso(df, ref):
    dias = (ref - df["date"]).dt.days
    return np.exp(-XI * dias)


def carregar_treino_ate(corte: str) -> pd.DataFrame:
    sql = """
        SELECT date, home_team, away_team,
               CAST(home_score AS INTEGER) AS home_score,
               CAST(away_score AS INTEGER) AS away_score,
               neutral
        FROM matches
        WHERE home_score IS NOT NULL AND away_score IS NOT NULL
          AND date >= '2014-01-01' AND date < ?
        ORDER BY date
    """
    df = db.query(sql, (corte,))
    df["date"] = pd.to_datetime(df["date"])
    df["neutral"] = df["neutral"].astype(str).str.lower().isin(["1", "true"])
    df["peso"] = _peso(df, df["date"].max())
    return df


def carregar_copa2022() -> pd.DataFrame:
    sql = """
        SELECT date, home_team, away_team,
               CAST(home_score AS INTEGER) AS home_score,
               CAST(away_score AS INTEGER) AS away_score
        FROM matches
        WHERE tournament = 'FIFA World Cup'
          AND substr(date,1,4) = '2022'
          AND home_score IS NOT NULL
    """
    df = db.query(sql)
    df["date"] = pd.to_datetime(df["date"])
    return df


def resultado_real(gc, gf):
    """0 = vitória mandante, 1 = empate, 2 = vitória visitante."""
    return 0 if gc > gf else (1 if gc == gf else 2)


def brier(probs, alvo_idx):
    """Brier multiclasse: média do erro quadrático vs vetor one-hot."""
    one_hot = np.zeros(3)
    one_hot[alvo_idx] = 1.0
    return float(np.sum((np.array(probs) - one_hot) ** 2))


def main():
    treino = carregar_treino_ate(CORTE)
    copa22 = carregar_copa2022()

    # mantém só seleções com amostra suficiente + as que jogaram a Copa 22
    times_copa = set(copa22["home_team"]) | set(copa22["away_team"])
    treino = filtrar_times_raros(treino, min_jogos=15, manter=times_copa)

    print(f"Treino até {CORTE}: {len(treino):,} jogos")
    modelo = treinar(treino)
    presentes = set(modelo["times"])

    # baseline: frequência média de mandante/empate/visitante no treino
    res_tr = treino.apply(lambda r: resultado_real(r["home_score"], r["away_score"]), axis=1)
    base = np.array([(res_tr == k).mean() for k in (0, 1, 2)])
    print(f"Baseline (freq. média M/E/V): {base.round(3)}")

    b_modelo, b_base, acertos, n = 0.0, 0.0, 0, 0
    for _, j in copa22.iterrows():
        if j["home_team"] not in presentes or j["away_team"] not in presentes:
            continue
        pc, pe, pf = probabilidades(modelo, j["home_team"], j["away_team"], neutro=True)
        probs = [pc, pe, pf]
        real = resultado_real(j["home_score"], j["away_score"])
        b_modelo += brier(probs, real)
        b_base += brier(base, real)
        acertos += int(np.argmax(probs) == real)
        n += 1

    b_modelo /= n
    b_base /= n
    melhora = (b_base - b_modelo) / b_base * 100

    print("\n--- Validação na Copa 2022 (dados não vistos) ---")
    print(f"Jogos avaliados:      {n}")
    print(f"Brier do modelo:      {b_modelo:.4f}")
    print(f"Brier do baseline:    {b_base:.4f}")
    print(f"Melhora vs baseline:  +{melhora:.1f}%")
    print(f"Acurácia do modelo:   {acertos/n*100:.1f}%")
    print("-------------------------------------------------")


if __name__ == "__main__":
    main()
