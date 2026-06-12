"""
FielCup — Camada de dados SQL (SQLite)
======================================

Este módulo é a "fonte da verdade" do projeto. Em vez de cada script ler
CSVs soltos, todos passam a conversar com um único banco SQLite
(`db/fielcup.db`). Isso deixa o projeto mais próximo de um pipeline real
e permite fazer a engenharia de dados em SQL puro.

Tabelas:
  matches              histórico completo de jogos (results.csv)
  fixtures_2026        os confrontos da Copa 2026 (sem placar)
  groups               seleção -> grupo
  teams_reference      ranking FIFA + valor de elenco (sinal de talento)
  team_ratings         ataque/defesa estimados pelo Dixon-Coles
  title_probabilities  saída da simulação de Monte Carlo

Uso:
    python src/database.py            # (re)constrói o banco a partir dos CSVs

API para os outros módulos:
    from database import query, tabela, conectar, salvar_df
    df = query("SELECT * FROM matches WHERE date >= '2018-01-01'")
    ref = tabela("teams_reference")
"""

from pathlib import Path
import sqlite3
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DB = RAIZ / "db" / "fielcup.db"

RAW = RAIZ / "data" / "raw"
PROC = RAIZ / "data" / "processed"
REF = RAIZ / "data" / "reference"


# ----------------------------------------------------------------------
# Conexão e helpers de leitura/escrita
# ----------------------------------------------------------------------

def conectar() -> sqlite3.Connection:
    """Abre conexão com o banco (cria a pasta db/ se preciso)."""
    DB.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB)


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Roda um SELECT e devolve um DataFrame. Atalho central de SQL."""
    with conectar() as con:
        return pd.read_sql_query(sql, con, params=params)


def tabela(nome: str) -> pd.DataFrame:
    """Lê uma tabela inteira como DataFrame."""
    return query(f"SELECT * FROM {nome}")


def salvar_df(df: pd.DataFrame, nome: str, if_exists: str = "replace") -> None:
    """Grava um DataFrame como tabela (usado pelo modelo e pela simulação)."""
    with conectar() as con:
        df.to_sql(nome, con, if_exists=if_exists, index=False)


# ----------------------------------------------------------------------
# Construção do banco a partir dos CSVs
# ----------------------------------------------------------------------

ESQUEMA_INDICES = [
    "CREATE INDEX IF NOT EXISTS ix_matches_date ON matches(date)",
    "CREATE INDEX IF NOT EXISTS ix_matches_home ON matches(home_team)",
    "CREATE INDEX IF NOT EXISTS ix_matches_away ON matches(away_team)",
]


def construir_db() -> None:
    """Carrega todos os CSVs de origem para dentro do SQLite.

    Roda de forma idempotente: pode ser chamado quantas vezes quiser que
    sempre reconstrói as tabelas de origem a partir dos arquivos.
    """
    print(f"Construindo banco em: {DB}")

    # 1. histórico de jogos (a base de tudo)
    matches = pd.read_csv(RAW / "results.csv")
    salvar_df(matches, "matches")
    print(f"  matches              {len(matches):>7,} linhas")

    # 2. confrontos da Copa 2026 (gerado pelo features.py; pode não existir
    #    ainda na primeira construção — então é opcional)
    if (PROC / "copa2026.csv").exists():
        fixtures = pd.read_csv(PROC / "copa2026.csv")
        salvar_df(fixtures, "fixtures_2026")
        print(f"  fixtures_2026        {len(fixtures):>7,} linhas")

    # 3. grupos
    if (PROC / "grupos.csv").exists():
        grupos = pd.read_csv(PROC / "grupos.csv")
        salvar_df(grupos, "groups")
        print(f"  groups               {len(grupos):>7,} linhas")

    # 4. tabela de talento (ranking FIFA + valor de elenco)
    ref = pd.read_csv(REF / "talento_2026.csv")
    salvar_df(ref, "teams_reference")
    print(f"  teams_reference      {len(ref):>7,} linhas")

    # índices para acelerar as queries de feature engineering
    with conectar() as con:
        for ddl in ESQUEMA_INDICES:
            con.execute(ddl)
        con.commit()

    print("Banco construído com sucesso.")


def resumo() -> None:
    """Imprime um pequeno panorama do que há no banco (sanidade)."""
    with conectar() as con:
        tabelas = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
            con,
        )
    print("\nTabelas no banco:")
    for t in tabelas["name"]:
        n = query(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
        print(f"  {t:22s} {n:>8,} linhas")


def main():
    construir_db()
    resumo()


if __name__ == "__main__":
    main()
