"""
FielCup — Passo 1: Coleta de dados
==================================

Baixa o histórico de partidas entre seleções do repositório público
martj42/international_results (dados de 1872 até hoje, atualizado
continuamente) e salva uma cópia bruta em data/raw/.

Por que esta fonte?
- É um dataset consolidado e mantido: evita scraping frágil e chaves de API.
- Usa sempre o NOME ATUAL de cada seleção, o que já resolve boa parte
  da padronização de nomes.
- Inclui a coluna 'neutral' (campo neutro), essencial para modelar
  corretamente a vantagem de mando de campo.
- Já contém os confrontos agendados da Copa 2026 (com placar vazio).

Uso:
    python src/data_collection.py
"""

from pathlib import Path
import sys
import pandas as pd

# URL do arquivo bruto no GitHub (branch master)
URL_RESULTS = (
    "https://raw.githubusercontent.com/"
    "martj42/international_results/master/results.csv"
)

# Caminho de saída relativo à raiz do projeto
RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "data" / "raw" / "results.csv"


def baixar_resultados(url: str = URL_RESULTS) -> pd.DataFrame:
    """Baixa o CSV de resultados e devolve um DataFrame.

    Lança uma exceção clara se o download falhar, em vez de salvar
    um arquivo corrompido silenciosamente.
    """
    print(f"Baixando dados de:\n  {url}")
    try:
        df = pd.read_csv(url, parse_dates=["date"])
    except Exception as erro:
        print(f"ERRO ao baixar os dados: {erro}", file=sys.stderr)
        raise

    return df


def resumir(df: pd.DataFrame) -> None:
    """Imprime um resumo do que foi baixado (sanity check)."""
    jogados = df.dropna(subset=["home_score", "away_score"])
    wc26 = df[
        (df["tournament"] == "FIFA World Cup")
        & (df["date"].dt.year == 2026)
    ]

    print("\n--- Resumo dos dados baixados ---")
    print(f"Total de partidas:        {len(df):,}")
    print(f"Partidas já disputadas:   {len(jogados):,}")
    print(f"Período coberto:          "
          f"{df['date'].min().date()} a {df['date'].max().date()}")
    print(f"Confrontos da Copa 2026:  {len(wc26)}")
    print("---------------------------------")


def main() -> None:
    df = baixar_resultados()
    resumir(df)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DESTINO, index=False)
    print(f"\nArquivo salvo em: {DESTINO}")


if __name__ == "__main__":
    main()
