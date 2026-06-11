"""FielCup - Passo 2: Limpeza e engenharia de features."""
from pathlib import Path
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA = RAIZ / "data" / "raw" / "results.csv"
SAIDA = RAIZ / "data" / "processed"

DATA_CORTE_TREINO = "2018-01-01"
XI = 0.0019


def carregar(caminho=ENTRADA):
    return pd.read_csv(caminho, parse_dates=["date"])


def separar_treino_e_alvo(df):
    alvo = df[(df["tournament"] == "FIFA World Cup") & (df["date"].dt.year == 2026)].copy()
    treino = df.dropna(subset=["home_score", "away_score"]).copy()
    treino["home_score"] = treino["home_score"].astype(int)
    treino["away_score"] = treino["away_score"].astype(int)
    return treino, alvo


def filtrar_recente(treino, data_corte=DATA_CORTE_TREINO):
    return treino[treino["date"] >= data_corte].copy()


def adicionar_peso_temporal(treino, xi=XI):
    treino = treino.copy()
    data_ref = treino["date"].max()
    dias = (data_ref - treino["date"]).dt.days
    treino["peso"] = np.exp(-xi * dias)
    return treino


def extrair_grupos(alvo):
    from collections import defaultdict
    adjac = defaultdict(set)
    for _, j in alvo.iterrows():
        adjac[j["home_team"]].add(j["away_team"])
        adjac[j["away_team"]].add(j["home_team"])
    visitados = set()
    grupos = []
    for time in sorted(adjac):
        if time in visitados:
            continue
        fila = [time]
        componente = set()
        while fila:
            t = fila.pop()
            if t in componente:
                continue
            componente.add(t)
            fila.extend(adjac[t] - componente)
        visitados |= componente
        grupos.append(sorted(componente))
    linhas = []
    for i, times in enumerate(grupos):
        letra = chr(ord("A") + i)
        for t in times:
            linhas.append({"grupo": letra, "selecao": t})
    return pd.DataFrame(linhas)


def resumir(treino, alvo, grupos):
    print("\n--- Resumo do Passo 2 ---")
    print(f"Jogos de treino (recentes):  {len(treino):,}")
    print(f"  periodo: {treino['date'].min().date()} a {treino['date'].max().date()}")
    print(f"  peso minimo/maximo: {treino['peso'].min():.3f} / {treino['peso'].max():.3f}")
    print(f"Confrontos da Copa (alvo):   {len(alvo)}")
    print(f"Grupos identificados:        {grupos['grupo'].nunique()}")
    print(f"Selecoes por grupo:          {grupos.groupby('grupo').size().unique()}")
    print("-------------------------")


def main():
    df = carregar()
    treino, alvo = separar_treino_e_alvo(df)
    treino = filtrar_recente(treino)
    treino = adicionar_peso_temporal(treino)
    grupos = extrair_grupos(alvo)
    resumir(treino, alvo, grupos)
    SAIDA.mkdir(parents=True, exist_ok=True)
    treino.to_csv(SAIDA / "treino.csv", index=False)
    alvo.to_csv(SAIDA / "copa2026.csv", index=False)
    grupos.to_csv(SAIDA / "grupos.csv", index=False)
    print(f"\nArquivos salvos em: {SAIDA}")


if __name__ == "__main__":
    main()
