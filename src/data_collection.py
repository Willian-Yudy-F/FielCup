"""FielCup - Passo 1: Coleta de dados."""
from pathlib import Path
import sys
import pandas as pd

URL_RESULTS = (
    "https://raw.githubusercontent.com/"
    "martj42/international_results/master/results.csv"
)
RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "data" / "raw" / "results.csv"


def baixar_resultados(url=URL_RESULTS):
    print(f"Baixando dados de:\n  {url}")
    try:
        df = pd.read_csv(url, parse_dates=["date"])
    except Exception as erro:
        print(f"ERRO ao baixar os dados: {erro}", file=sys.stderr)
        raise
    return df


def resumir(df):
    jogados = df.dropna(subset=["home_score", "away_score"])
    wc26 = df[(df["tournament"] == "FIFA World Cup") & (df["date"].dt.year == 2026)]
    print("\n--- Resumo dos dados baixados ---")
    print(f"Total de partidas:        {len(df):,}")
    print(f"Partidas ja disputadas:   {len(jogados):,}")
    print(f"Periodo coberto:          {df['date'].min().date()} a {df['date'].max().date()}")
    print(f"Confrontos da Copa 2026:  {len(wc26)}")
    print("---------------------------------")


def main():
    df = baixar_resultados()
    resumir(df)
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DESTINO, index=False)
    print(f"\nArquivo salvo em: {DESTINO}")


if __name__ == "__main__":
    main()
