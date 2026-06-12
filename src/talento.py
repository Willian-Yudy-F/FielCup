"""
FielCup — Passo 3.5: Blend "resultado + talento"
================================================

PROBLEMA QUE ESTE MÓDULO RESOLVE
--------------------------------
O Dixon-Coles enxerga só os PLACARES das seleções. Isso o faz:
  - superestimar a Argentina (melhor defesa medida, mas elenco veterano);
  - subestimar a França (talento individual que não aparece nos resultados
    recentes da seleção).

A correção é dar ao modelo o sinal que falta: TALENTO, medido por dois
indicadores externos e objetivos coletados de fontes oficiais —
  (1) pontos do ranking FIFA  e
  (2) valor de mercado do elenco (Transfermarkt).

COMO FUNCIONA (transparente e ajustável)
----------------------------------------
Para as 48 seleções da Copa:
  r_dc   = ataque + defesa            (força "medida por resultados")
  s_tal  = w_fifa·z(pontos_fifa) + w_val·z(log valor_elenco)   (talento)
  s_blend = alpha·z(r_dc) + (1-alpha)·z(s_tal)

O parâmetro `alpha` é o BOTÃO do modelo:
  alpha = 1.0  -> só resultados (reproduz o modelo antigo: Argentina 1º)
  alpha = 0.0  -> só talento     (vira basicamente ranking FIFA + elenco)
  alpha ≈ 0.6  -> mistura equilibrada (recomendado)

A força blendada é reconvertida para a escala do Dixon-Coles e aplicada
como um ajuste por seleção, metade no ataque e metade na defesa. O
resultado é um "modelo" no mesmo formato do dixon_coles, que a simulação
e o dashboard consomem sem mudar mais nada.

Uso:
    python src/talento.py                 # mostra o efeito do blend
    from talento import ratings_blendados  # usado por simulate/dashboard
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd

import database as db

RAIZ = Path(__file__).resolve().parents[1]
MODELO_JSON = RAIZ / "data" / "processed" / "modelo_dc.json"

# Pesos padrão do índice de talento e da mistura.
ALPHA_PADRAO = 0.6     # peso dos resultados (Dixon-Coles)
W_FIFA = 0.5           # peso do ranking FIFA dentro do talento
W_VALOR = 0.5          # peso do valor de elenco dentro do talento


def _z(serie: pd.Series) -> pd.Series:
    """Padroniza (z-score). Protege contra desvio padrão zero."""
    dp = serie.std(ddof=0)
    if dp == 0 or np.isnan(dp):
        return serie * 0.0
    return (serie - serie.mean()) / dp


def carregar_modelo() -> dict:
    """Lê o modelo Dixon-Coles treinado (JSON)."""
    with open(MODELO_JSON) as f:
        return json.load(f)


def indice_talento(w_fifa: float = W_FIFA, w_valor: float = W_VALOR) -> pd.DataFrame:
    """Constrói o índice de talento por seleção a partir do banco.

    Retorna um DataFrame com colunas: selecao, s_talento (padronizado).
    """
    ref = db.tabela("teams_reference")
    ref = ref.copy()
    # log do valor amortece o efeito de outliers (Inglaterra/França bilionárias)
    ref["log_valor"] = np.log(ref["market_value_eur_mn"].clip(lower=1.0))
    ref["z_fifa"] = _z(ref["fifa_points"])
    ref["z_valor"] = _z(ref["log_valor"])
    ref["s_talento"] = _z(w_fifa * ref["z_fifa"] + w_valor * ref["z_valor"])
    return ref[["selecao", "fifa_points", "market_value_eur_mn",
                "z_fifa", "z_valor", "s_talento"]]


def ratings_blendados(alpha: float = ALPHA_PADRAO,
                      w_fifa: float = W_FIFA,
                      w_valor: float = W_VALOR,
                      modelo: dict | None = None) -> dict:
    """Devolve um modelo (formato dixon_coles) com ratings ajustados.

    Apenas as 48 seleções da Copa têm ataque/defesa recalibrados; as demais
    mantêm o valor original (não jogam a Copa, então não importam).
    """
    modelo = modelo or carregar_modelo()
    ataque = dict(modelo["ataque"])
    defesa = dict(modelo["defesa"])

    tal = indice_talento(w_fifa, w_valor).set_index("selecao")
    copa = [t for t in tal.index if t in ataque]  # 48 seleções presentes

    # força "medida por resultados" das 48 seleções
    r_dc = pd.Series({t: ataque[t] + defesa[t] for t in copa})
    z_dc = _z(r_dc)

    s_tal = tal.loc[copa, "s_talento"]
    s_blend = alpha * z_dc + (1.0 - alpha) * s_tal

    # reconverte para a escala original de r_dc (mesma média e desvio)
    r_blend = r_dc.mean() + r_dc.std(ddof=0) * s_blend
    delta = r_blend - r_dc  # ajuste por seleção

    # aplica metade no ataque, metade na defesa
    for t in copa:
        ataque[t] += delta[t] / 2.0
        defesa[t] += delta[t] / 2.0

    return {
        "times": modelo["times"],
        "ataque": ataque,
        "defesa": defesa,
        "mando": modelo["mando"],
        "rho": modelo["rho"],
        "alpha": alpha,
    }


def detalhe_blend(alpha: float = ALPHA_PADRAO,
                  w_fifa: float = W_FIFA,
                  w_valor: float = W_VALOR,
                  modelo: dict | None = None) -> pd.DataFrame:
    """Abre a 'caixa-preta': mostra cada número que entra no blend.

    Devolve, por seleção, todos os ingredientes do cálculo —
    ataque/defesa (Dixon-Coles), força bruta, z-scores, índice de talento,
    o blend e a força final. É o que o dashboard usa para EXPLICAR de onde
    vem o número de cada time.
    """
    modelo = modelo or carregar_modelo()
    tal = indice_talento(w_fifa, w_valor).set_index("selecao")
    copa = [t for t in tal.index if t in modelo["ataque"]]

    ataque = pd.Series({t: modelo["ataque"][t] for t in copa})
    defesa = pd.Series({t: modelo["defesa"][t] for t in copa})
    r_dc = ataque + defesa
    z_dc = _z(r_dc)
    s_tal = tal.loc[copa, "s_talento"]
    s_blend = alpha * z_dc + (1.0 - alpha) * s_tal
    r_blend = r_dc.mean() + r_dc.std(ddof=0) * s_blend

    df = pd.DataFrame({
        "selecao": copa,
        "ataque": ataque.values,
        "defesa": defesa.values,
        "forca_dc": r_dc.values,           # força "só resultado"
        "z_resultado": z_dc.values,        # padronizada
        "fifa_points": tal.loc[copa, "fifa_points"].values,
        "z_fifa": tal.loc[copa, "z_fifa"].values,
        "valor_mi": tal.loc[copa, "market_value_eur_mn"].values,
        "z_valor": tal.loc[copa, "z_valor"].values,
        "indice_talento": s_tal.values,    # FIFA + elenco combinados
        "blend": s_blend.values,           # α·resultado + (1-α)·talento
        "forca_final": r_blend.values,
    })
    return df.sort_values("forca_final", ascending=False).reset_index(drop=True)


def forca_ranking(modelo: dict) -> pd.Series:
    """Força (ataque+defesa) das 48 seleções da Copa, ordenada."""
    grupos = db.tabela("groups")
    copa = set(grupos["selecao"])
    r = pd.Series({t: modelo["ataque"][t] + modelo["defesa"][t]
                   for t in modelo["times"] if t in copa})
    return r.sort_values(ascending=False)


def main():
    base = carregar_modelo()
    antes = forca_ranking(base)
    depois = forca_ranking(ratings_blendados(ALPHA_PADRAO))

    ra = {t: i + 1 for i, t in enumerate(antes.index)}
    rd = {t: i + 1 for i, t in enumerate(depois.index)}

    print(f"Efeito do blend (alpha={ALPHA_PADRAO}, talento=FIFA+elenco)\n")
    print(f"{'Selecao':22s} {'so resultado':>12s} {'+ talento':>10s} {'mov':>6s}")
    print("-" * 54)
    for t in depois.head(12).index:
        mov = ra[t] - rd[t]
        seta = "▲" if mov > 0 else ("▼" if mov < 0 else "=")
        print(f"{t:22s} {ra[t]:>12d} {rd[t]:>10d}   {seta}{abs(mov):>3d}")

    print("\nMaiores SUBIDAS (talento que o modelo ignorava):")
    movs = pd.Series({t: ra[t] - rd[t] for t in antes.index}).sort_values(ascending=False)
    for t in movs.head(5).index:
        print(f"  {t:22s} {ra[t]:>2d} -> {rd[t]:<2d}  (+{movs[t]})")
    print("\nMaiores QUEDAS (resultado recente acima do talento):")
    for t in movs.tail(5).index:
        print(f"  {t:22s} {ra[t]:>2d} -> {rd[t]:<2d}  ({movs[t]})")


if __name__ == "__main__":
    main()
