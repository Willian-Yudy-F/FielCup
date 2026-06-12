"""
FielCup — Coletor automático via API (API-Football)
===================================================

Mantém os dados do projeto atualizados sozinho, puxando da API-Football
(https://www.api-sports.io/). Pensado para rodar periodicamente durante
a Copa — você não precisa acompanhar jogo a jogo na mão.

O que ele coleta:
  - Resultados de partidas finalizadas (atualiza o histórico de treino)
  - Estatísticas por jogo (posse, finalizações, xG quando disponível)
  - Elenco e dados de jogadores (para a evolução futura do modelo)

Por que API-Football:
  - Tier gratuito cobre seleções e Copa do Mundo (100 requisições/dia)
  - Mesmos endpoints do tier pago, só com limite diário
  - Cadastre-se em https://dashboard.api-football.com e pegue a chave

COMO USAR:
  1. export API_FOOTBALL_KEY="sua_chave_aqui"
  2. python src/api_collector.py --update-results
  3. (opcional) agende no cron para rodar sozinho — ver README

IMPORTANTE: este módulo NÃO grava sua chave em lugar nenhum. Ele lê da
variável de ambiente. Nunca coloque a chave dentro do código.
"""

from pathlib import Path
import argparse
import os
import sys
import time
import json
import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
PROC = RAIZ / "data" / "processed"

BASE = "https://v3.football.api-sports.io"
# ID da Copa do Mundo na API-Football (confira no painel; pode mudar por temporada)
LIGA_COPA = 1
TEMPORADA = 2026

# limite do tier gratuito; respeitamos com folga
PAUSA_ENTRE_CHAMADAS = 2.0  # segundos


def _headers():
    chave = os.environ.get("API_FOOTBALL_KEY")
    if not chave:
        print("ERRO: defina a variavel de ambiente API_FOOTBALL_KEY.\n"
              "  export API_FOOTBALL_KEY='sua_chave'", file=sys.stderr)
        sys.exit(1)
    return {"x-apisports-key": chave}


def _get(endpoint: str, params: dict) -> dict:
    """Faz uma requisição GET tratando erros e respeitando o rate limit."""
    url = f"{BASE}/{endpoint}"
    resp = requests.get(url, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    dados = resp.json()
    # a API devolve erros dentro do corpo, mesmo com status 200
    if dados.get("errors"):
        print(f"AVISO da API em {endpoint}: {dados['errors']}", file=sys.stderr)
    time.sleep(PAUSA_ENTRE_CHAMADAS)
    return dados


# ----------------------------------------------------------------------
# Coleta de resultados finalizados
# ----------------------------------------------------------------------

def baixar_resultados_copa() -> pd.DataFrame:
    """Baixa os jogos da Copa 2026 já finalizados e devolve no MESMO
    formato do results.csv (date, home_team, away_team, home_score,
    away_score, tournament, neutral) — assim o resto do pipeline não muda.
    """
    dados = _get("fixtures", {"league": LIGA_COPA, "season": TEMPORADA})
    linhas = []
    for item in dados.get("response", []):
        fx = item["fixture"]
        if fx["status"]["short"] != "FT":   # só jogos encerrados
            continue
        linhas.append({
            "date": fx["date"][:10],
            "home_team": item["teams"]["home"]["name"],
            "away_team": item["teams"]["away"]["name"],
            "home_score": item["goals"]["home"],
            "away_score": item["goals"]["away"],
            "tournament": "FIFA World Cup",
            "neutral": True,   # Copa é em campo neutro
            "fixture_id": fx["id"],
        })
    return pd.DataFrame(linhas)


def atualizar_results_csv():
    """Incorpora os novos resultados da Copa ao results.csv existente,
    sem duplicar jogos já registrados."""
    novos = baixar_resultados_copa()
    if novos.empty:
        print("Nenhum jogo finalizado da Copa ainda.")
        return

    caminho = RAW / "results.csv"
    base = pd.read_csv(caminho)

    # remove a coluna auxiliar antes de juntar
    novos_limpo = novos.drop(columns=["fixture_id"])

    # evita duplicatas: chave = data + mandante + visitante
    base["_k"] = base["date"] + base["home_team"] + base["away_team"]
    novos_limpo["_k"] = (novos_limpo["date"] + novos_limpo["home_team"]
                         + novos_limpo["away_team"])
    novos_unicos = novos_limpo[~novos_limpo["_k"].isin(base["_k"])]

    if novos_unicos.empty:
        print("Resultados já estavam atualizados.")
        return

    combinado = pd.concat(
        [base.drop(columns="_k"), novos_unicos.drop(columns="_k")],
        ignore_index=True)
    combinado.to_csv(caminho, index=False)
    print(f"Adicionados {len(novos_unicos)} novos jogos ao results.csv.")
    print("Rode features.py -> dixon_coles.py -> simulate.py para "
          "reprocessar com os dados novos.")


# ----------------------------------------------------------------------
# Coleta de estatísticas por jogo (para evolução do modelo)
# ----------------------------------------------------------------------

def baixar_estatisticas_jogo(fixture_id: int) -> pd.DataFrame:
    """Baixa estatísticas detalhadas de um jogo (posse, finalizações,
    chutes no gol, etc). Base para um modelo futuro baseado em xG."""
    dados = _get("fixtures/statistics", {"fixture": fixture_id})
    linhas = []
    for time_stats in dados.get("response", []):
        time_nome = time_stats["team"]["name"]
        registro = {"fixture_id": fixture_id, "team": time_nome}
        for s in time_stats["statistics"]:
            registro[s["type"]] = s["value"]
        linhas.append(registro)
    return pd.DataFrame(linhas)


def coletar_stats_da_copa():
    """Coleta as estatísticas de todos os jogos finalizados da Copa
    e salva em data/raw/estatisticas_copa.csv."""
    jogos = baixar_resultados_copa()
    if jogos.empty:
        print("Sem jogos finalizados para coletar estatisticas.")
        return
    todas = []
    for fid in jogos["fixture_id"]:
        todas.append(baixar_estatisticas_jogo(int(fid)))
    if todas:
        df = pd.concat(todas, ignore_index=True)
        df.to_csv(RAW / "estatisticas_copa.csv", index=False)
        print(f"Estatisticas de {len(jogos)} jogos salvas.")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Coletor FielCup via API-Football")
    p.add_argument("--update-results", action="store_true",
                   help="Atualiza results.csv com jogos finalizados da Copa")
    p.add_argument("--stats", action="store_true",
                   help="Coleta estatisticas detalhadas dos jogos")
    args = p.parse_args()

    if args.update_results:
        atualizar_results_csv()
    if args.stats:
        coletar_stats_da_copa()
    if not (args.update_results or args.stats):
        p.print_help()


if __name__ == "__main__":
    main()
