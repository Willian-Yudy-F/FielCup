"""
FielCup — Passo 2: Limpeza e engenharia de features (agora via SQL)
===================================================================

Transforma os dados brutos (tabela `matches` no SQLite) em conjuntos
limpos e prontos para o modelo. A grande mudança desta versão é que a
seleção, o filtro temporal e as agregações são feitos em **SQL**, e não
mais em pandas — o banco `db/fielcup.db` é a fonte da verdade.

O que este módulo faz:
  1. Separa TREINO (jogos com placar) e ALVO (os 72 confrontos da Copa
     2026) com duas queries SQL.
  2. Mantém só um recorte recente para o treino (WHERE date >= corte).
  3. Calcula o PESO DE DECAIMENTO TEMPORAL (jogos recentes pesam mais).
  4. Deriva os GRUPOS da Copa a partir dos confrontos.
  5. (Bônus SQL) calcula nº de jogos por seleção no período, útil para
     diagnosticar quem tem amostra pequena.

Uso:
    python src/database.py     # garanta que o banco existe
    python src/features.py
"""

from pathlib import Path
import numpy as np
import pandas as pd

import database as db

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "data" / "processed"

# --- Parâmetros de modelagem (decisões documentadas) ---

# Data de corte: só treinamos com jogos a partir daqui. ~8 anos de
# histórico capturam a era atual das seleções sem diluir com dados antigos.
DATA_CORTE_TREINO = "2018-01-01"

# xi (ξ): velocidade do decaimento temporal.
# 0.0019 dá meia-vida de ~1 ano (jogo de 1 ano atrás pesa metade).
XI = 0.0019


# ----------------------------------------------------------------------
# 1 e 2. Treino e alvo — direto em SQL
# ----------------------------------------------------------------------

def carregar_treino(data_corte: str = DATA_CORTE_TREINO) -> pd.DataFrame:
    """Jogos JÁ disputados (têm placar) a partir da data de corte.

    Toda a seleção e o filtro temporal acontecem no banco — o pandas só
    recebe o resultado já limpo.
    """
    sql = """
        SELECT date, home_team, away_team,
               CAST(home_score AS INTEGER) AS home_score,
               CAST(away_score AS INTEGER) AS away_score,
               tournament, neutral
        FROM matches
        WHERE home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND date >= ?
        ORDER BY date
    """
    df = db.query(sql, (data_corte,))
    df["date"] = pd.to_datetime(df["date"])
    # normaliza 'neutral' (pode vir como 0/1, 'True'/'False')
    df["neutral"] = df["neutral"].astype(str).str.lower().isin(["1", "true"])
    return df


def carregar_alvo() -> pd.DataFrame:
    """Os 72 confrontos da fase de grupos da Copa 2026 (sem placar)."""
    sql = """
        SELECT date, home_team, away_team, tournament, neutral
        FROM matches
        WHERE tournament = 'FIFA World Cup'
          AND substr(date, 1, 4) = '2026'
          AND home_score IS NULL
        ORDER BY date
    """
    df = db.query(sql)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ----------------------------------------------------------------------
# 3. Peso de decaimento temporal
# ----------------------------------------------------------------------

def adicionar_peso_temporal(treino: pd.DataFrame, xi: float = XI) -> pd.DataFrame:
    """peso = exp(-xi * dias_desde_o_jogo). Jogos recentes pesam mais."""
    treino = treino.copy()
    data_ref = treino["date"].max()
    dias = (data_ref - treino["date"]).dt.days
    treino["peso"] = np.exp(-xi * dias)
    return treino


# ----------------------------------------------------------------------
# 4. Grupos da Copa (componentes conexos dos confrontos)
# ----------------------------------------------------------------------

def extrair_grupos(alvo: pd.DataFrame) -> pd.DataFrame:
    """Descobre quem está em qual grupo a partir dos confrontos agendados."""
    from collections import defaultdict

    adjac = defaultdict(set)
    for _, j in alvo.iterrows():
        adjac[j["home_team"]].add(j["away_team"])
        adjac[j["away_team"]].add(j["home_team"])

    visitados, grupos = set(), []
    for time in sorted(adjac):
        if time in visitados:
            continue
        fila, componente = [time], set()
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


# ----------------------------------------------------------------------
# 5. (Bônus) diagnóstico de amostra por seleção — SQL de agregação
# ----------------------------------------------------------------------

def jogos_por_selecao(data_corte: str = DATA_CORTE_TREINO) -> pd.DataFrame:
    """Conta jogos por seleção no período (UNION + GROUP BY em SQL).

    Útil para identificar seleções com poucos jogos (estimativa frágil).
    """
    sql = """
        WITH part AS (
            SELECT home_team AS selecao FROM matches
            WHERE home_score IS NOT NULL AND date >= :corte
            UNION ALL
            SELECT away_team AS selecao FROM matches
            WHERE home_score IS NOT NULL AND date >= :corte
        )
        SELECT selecao, COUNT(*) AS jogos
        FROM part
        GROUP BY selecao
        ORDER BY jogos DESC
    """
    with db.conectar() as con:
        return pd.read_sql_query(sql, con, params={"corte": data_corte})


# ----------------------------------------------------------------------
# Execução
# ----------------------------------------------------------------------

def resumir(treino, alvo, grupos):
    print("\n--- Resumo do Passo 2 ---")
    print(f"Jogos de treino (recentes):  {len(treino):,}")
    print(f"  periodo: {treino['date'].min().date()} a "
          f"{treino['date'].max().date()}")
    print(f"  peso minimo/maximo: {treino['peso'].min():.3f} / "
          f"{treino['peso'].max():.3f}")
    print(f"Confrontos da Copa (alvo):   {len(alvo)}")
    print(f"Grupos identificados:        {grupos['grupo'].nunique()}")
    print(f"Selecoes por grupo:          "
          f"{grupos.groupby('grupo').size().unique()}")
    print("-------------------------")


def main():
    treino = carregar_treino()
    treino = adicionar_peso_temporal(treino)
    alvo = carregar_alvo()
    grupos = extrair_grupos(alvo)

    resumir(treino, alvo, grupos)

    # salva os CSVs processados (compatibilidade) ...
    SAIDA.mkdir(parents=True, exist_ok=True)
    treino.to_csv(SAIDA / "treino.csv", index=False)
    alvo.to_csv(SAIDA / "copa2026.csv", index=False)
    grupos.to_csv(SAIDA / "grupos.csv", index=False)

    # ... e atualiza as tabelas correspondentes no banco
    db.salvar_df(treino, "train_matches")
    db.salvar_df(alvo, "fixtures_2026")
    db.salvar_df(grupos, "groups")

    print(f"\nArquivos salvos em: {SAIDA}")
    print("Tabelas atualizadas no banco: train_matches, fixtures_2026, groups")


if __name__ == "__main__":
    main()
