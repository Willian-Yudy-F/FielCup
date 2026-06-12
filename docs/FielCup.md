# FielCup 2026 Analytics — Guia Completo de Projeto de Data Science

> **O que é este documento?** Um guia de ponta a ponta para construir um projeto de portfólio que prevê resultados da Copa do Mundo de 2026 e simula o torneio inteiro. Foi escrito para servir **ao mesmo tempo** como material de estudo (cada termo de estatística e machine learning é explicado do zero) e como a documentação oficial do seu projeto no GitHub.
>
> **Pré-requisito real:** saber programar em Python. Todo o resto — Poisson, máxima verossimilhança, Monte Carlo, calibração — é explicado aqui.

---

## Sumário

1. [A grande ideia do projeto](#1-a-grande-ideia)
2. [Por que esse projeto impressiona num portfólio](#2-por-que-impressiona)
3. [Conceitos de estatística explicados do zero](#3-estatistica)
4. [Conceitos de machine learning explicados do zero](#4-machine-learning)
5. [O formato da Copa 2026 (e por que ele importa para o código)](#5-formato)
6. [Estrutura de pastas do projeto](#6-estrutura)
7. [Fase 1 — Coleta de dados](#7-coleta)
8. [Fase 2 — Limpeza e features](#8-limpeza)
9. [Fase 3 — O modelo Dixon-Coles (código comentado)](#9-modelo)
10. [Fase 4 — Engine de simulação Monte Carlo](#10-simulacao)
11. [Fase 5 — Validação honesta do modelo](#11-validacao)
12. [Fase 6 — Dashboard e comunicação](#12-dashboard)
13. [Cronograma de 4 semanas](#13-cronograma)
14. [Glossário rápido](#14-glossario)

---

<a name="1-a-grande-ideia"></a>
## 1. A grande ideia do projeto

A maioria dos projetos de "previsão de futebol" faz a coisa errada do ponto de vista estatístico: treina um classificador para prever direto "vitória / empate / derrota". Isso joga fora informação valiosa (a diferença entre ganhar de 1x0 e de 5x0) e não consegue simular um torneio.

A abordagem profissional é **modelar a quantidade de gols que cada time marca**. Se eu sei prever a distribuição de gols de qualquer confronto, eu consigo:

- Derivar a probabilidade de vitória, empate e derrota (somando as probabilidades dos placares).
- Simular uma partida sorteando um placar dessa distribuição.
- Simular o **torneio inteiro** repetindo isso milhares de vezes (Monte Carlo) e contar quantas vezes cada seleção foi campeã.

O resultado final do projeto é uma frase como: *"Segundo o modelo, a Espanha tem 18,4% de chance de ser campeã, a Argentina 15,1%..."* — acompanhada de toda a metodologia que justifica esse número.

---

<a name="2-por-que-impressiona"></a>
## 2. Por que esse projeto impressiona num portfólio

Um recrutador técnico vê dezenas de projetos de "treinei um random forest no dataset X". O que diferencia este:

- **Modelagem estatística de verdade**, não só `.fit()` numa biblioteca. Você implementa uma função de verossimilhança e a otimiza.
- **Simulação Monte Carlo**, que demonstra raciocínio probabilístico.
- **Validação honesta** (backtesting em Copas passadas, calibração, Brier score) em vez de só reportar acurácia.
- **Comunicação clara** dos resultados num dashboard.
- **Tema atual**, o que mostra iniciativa e gera conversa em entrevista.

---

<a name="3-estatistica"></a>
## 3. Conceitos de estatística explicados do zero

### 3.1. Variável aleatória

Uma **variável aleatória** é um número cujo valor depende do acaso. "Quantos gols a Argentina marca neste jogo?" é uma variável aleatória: pode ser 0, 1, 2, 3... e cada valor tem uma probabilidade.

### 3.2. Distribuição de probabilidade

A **distribuição** é a "tabela" que diz a probabilidade de cada valor possível. Por exemplo:

| Gols | Probabilidade |
|------|---------------|
| 0    | 0,20          |
| 1    | 0,34          |
| 2    | 0,28          |
| 3    | 0,12          |
| ...  | ...           |

As probabilidades somam 1 (100%). Modelar futebol é, no fundo, estimar essa tabela para cada confronto.

### 3.3. A distribuição de Poisson

A **Poisson** é a distribuição natural para contar "quantas vezes algo raro acontece num intervalo fixo" — número de e-mails por hora, número de gols por jogo. Ela tem **um único parâmetro**, geralmente chamado de **λ (lambda)**, que é a **média esperada** de ocorrências.

A fórmula da probabilidade de observar exatamente *k* gols é:

```
P(k gols) = (λ^k · e^(−λ)) / k!
```

onde `e ≈ 2,718` e `k!` é o fatorial de k. Você não precisa decorar isso — em Python é `scipy.stats.poisson.pmf(k, lam)`. O importante é a intuição: **se um time tem λ = 1,5, ele marca em média 1,5 gol por jogo**, e a Poisson te dá a probabilidade de cada placar específico em torno dessa média.

Por que Poisson funciona para futebol? Gols são eventos relativamente raros e independentes ao longo dos 90 minutos — exatamente o cenário que a Poisson descreve. Não é perfeito (gols não são 100% independentes), e é por isso que existe a correção de Dixon-Coles, explicada na seção 3.7.

### 3.4. Parâmetros de força: ataque e defesa

Cada seleção recebe dois números estimados a partir dos dados históricos:

- **Força de ataque** — quão acima ou abaixo da média o time marca.
- **Força de defesa** — quão acima ou abaixo da média o time sofre gols.

O λ esperado de gols de um time num jogo combina o ataque dele com a defesa do adversário, mais a média geral de gols e um bônus de mando de campo:

```
λ_casa = exp( média_geral + ataque_casa − defesa_visitante + vantagem_mando )
λ_fora = exp( média_geral + ataque_fora − defesa_casa )
```

O `exp()` (exponencial) garante que λ seja sempre positivo (não existe gol negativo). Esse uso de exponencial é o que se chama de **modelo log-linear**.

### 3.5. Vantagem de mando de campo

Times jogando em casa historicamente marcam mais. O parâmetro **vantagem de mando** captura isso. Na Copa 2026 quase ninguém joga "em casa" de verdade (só os anfitriões EUA, Canadá e México), então você pode zerar ou reduzir esse termo para jogos neutros — uma decisão de modelagem que vale documentar.

### 3.6. Máxima verossimilhança (Maximum Likelihood Estimation, MLE)

Esta é a ideia central de como o modelo "aprende". 

**Verossimilhança** (*likelihood*) é a probabilidade de os dados que você observou terem acontecido, assumindo um certo conjunto de parâmetros. A lógica do MLE é: *"quais valores de ataque/defesa de cada time tornam os resultados históricos reais os mais prováveis possíveis?"*

Na prática:
1. Você tem um histórico de jogos com placares reais.
2. Para um chute de parâmetros, calcula a probabilidade (segundo o modelo) de cada placar real ter ocorrido.
3. Multiplica todas essas probabilidades → essa é a verossimilhança total.
4. Um otimizador ajusta os parâmetros para **maximizar** esse número.

Por razões numéricas, sempre se trabalha com o **logaritmo** da verossimilhança (*log-likelihood*), e como otimizadores geralmente *minimizam*, minimiza-se a **log-verossimilhança negativa**. Guarde este nome: você vai escrever uma função chamada `negative_log_likelihood`.

### 3.7. A correção de Dixon-Coles

Em 1997, Mark Dixon e Stuart Coles publicaram um artigo mostrando que o modelo Poisson puro erra sistematicamente nos **placares baixos** (0-0, 1-0, 0-1, 1-1) — ele subestima empates 0-0 e 1-1, por exemplo. Eles adicionaram:

- **Um termo de correção (rho, ρ)** que ajusta as probabilidades exatamente desses quatro placares.
- **Decaimento temporal (time decay):** jogos mais antigos pesam menos na estimativa, porque a força de uma seleção muda com o tempo. Controlado por um parâmetro **xi (ξ)**.

Esse é o modelo que você vai implementar. Citá-lo pelo nome ("implementei um modelo Dixon-Coles") sinaliza que você conhece a literatura da área.

### 3.8. Simulação de Monte Carlo

**Monte Carlo** é o nome chique para "rodar o experimento aleatório muitas vezes e contar os resultados". Se eu quero saber a chance de a Espanha ser campeã, eu:

1. Simulo a Copa inteira uma vez (cada jogo tem o placar sorteado da sua distribuição).
2. Anoto quem foi campeão.
3. Repito 50.000 vezes.
4. A probabilidade estimada de cada time ser campeão é: (número de vezes que ele venceu) / 50.000.

Quanto mais simulações, mais estável a estimativa (lei dos grandes números).

---

<a name="4-machine-learning"></a>
## 4. Conceitos de machine learning explicados do zero

### 4.1. O que é "treinar um modelo"

É ajustar os parâmetros internos de uma fórmula usando dados, de modo que ela faça boas previsões. No Dixon-Coles, "treinar" é justamente a maximização da verossimilhança da seção 3.6.

### 4.2. Treino, teste e vazamento de dados

Você **nunca** avalia um modelo nos mesmos dados em que o treinou — senão ele parece bom só porque "decorou". Divide-se:

- **Conjunto de treino:** dados usados para estimar os parâmetros.
- **Conjunto de teste:** dados separados, usados só para medir desempenho.

Em séries temporais (como jogos ao longo dos anos), a divisão é **cronológica**: treine no passado, teste no futuro. Misturar isso é **data leakage** (vazamento de dados) — um erro grave que infla artificialmente os resultados.

### 4.3. Backtesting

**Backtesting** é testar o modelo em eventos passados como se você não soubesse o resultado. No nosso caso: treinar com dados até antes da Copa de 2022, prever 2022, e comparar com o que de fato aconteceu. É a forma mais honesta de validar.

### 4.4. Modelos de comparação: regressão logística e XGBoost

Para enriquecer o portfólio, você compara o Dixon-Coles com modelos de ML "de prateleira":

- **Regressão logística:** modelo simples e interpretável que estima a probabilidade de uma classe (ex: vitória do mandante) a partir de variáveis de entrada.
- **XGBoost:** um modelo de *gradient boosting* — ele combina centenas de árvores de decisão pequenas, cada uma corrigindo os erros da anterior. Costuma ter ótima performance, mas é menos interpretável ("caixa-preta"). É um dos modelos mais usados em competições de ML.

A discussão "interpretabilidade vs. performance" entre eles é exatamente o tipo de maturidade que entrevistadores procuram.

### 4.5. Métricas de avaliação (além da acurácia)

**Acurácia** (% de acertos) é uma métrica fraca para probabilidades. Use também:

- **Brier score:** mede o erro das probabilidades previstas. Se você disse "70% de vitória" e o time ganhou, o erro foi pequeno; se perdeu, foi grande. Quanto **menor** o Brier score, melhor.
- **Log loss:** parecido, penaliza fortemente previsões confiantes e erradas.
- **Calibração:** um modelo é *bem calibrado* se, entre todos os jogos onde ele disse "70% de chance", o time realmente venceu ~70% das vezes. Você visualiza isso num **reliability diagram** (curva de calibração).

---

<a name="5-formato"></a>
## 5. O formato da Copa 2026 (e por que ele importa para o código)

A Copa de 2026 tem **48 seleções em 12 grupos de 4 times**. Cada time joga **3 partidas** na fase de grupos. Avançam **32 times**: os **2 primeiros de cada grupo** (24 times) mais os **8 melhores terceiros colocados**.

Critérios de desempate, nesta ordem: **saldo de gols → gols marcados → confronto direto → fair play → sorteio**.

Detalhe importante para a engine: o chaveamento é **semi-determinístico**. A FIFA organizou os caminhos para que as duas seleções mais bem ranqueadas só possam se encontrar na final. Além disso, a posição dos 8 terceiros no mata-mata depende de **quais grupos** eles vieram, seguindo uma tabela oficial de combinações.

**Implicações para o código (as partes difíceis e valiosas):**

1. **Selecionar os 8 melhores terceiros:** rankeie os 12 terceiros por (pontos, saldo, gols) e pegue os 8 primeiros.
2. **Mapear terceiros para o bracket:** use a tabela oficial da FIFA de combinações de grupos.
3. **Respeitar a separação dos cabeças de chave** no chaveamento.

> **Dica:** quando chegar na engine, busque "FIFA 2026 third-place qualification bracket table" para a tabela oficial de mapeamento. É um detalhe que quase ninguém implementa certo.

---

<a name="6-estrutura"></a>
## 6. Estrutura de pastas do projeto

```
worldcup2026-analytics/
├── README.md                  # versão resumida deste guia (vitrine do projeto)
├── requirements.txt           # dependências
├── data/
│   ├── raw/                   # dados brutos baixados (não editar)
│   └── processed/             # dados limpos prontos para modelar
├── notebooks/
│   ├── 01_eda.ipynb           # análise exploratória
│   └── 02_model_report.ipynb  # relatório com gráficos e conclusões
├── src/
│   ├── data_collection.py     # coleta via API/scraping
│   ├── features.py            # limpeza e engenharia de features
│   ├── dixon_coles.py         # o modelo estatístico
│   ├── simulate.py            # engine de Monte Carlo do torneio
│   └── evaluate.py            # backtesting e métricas
├── app/
│   └── dashboard.py           # Streamlit
└── tests/
    └── test_simulate.py       # testes (impressiona muito ter testes!)
```

---

<a name="7-coleta"></a>
## 7. Fase 1 — Coleta de dados

Você precisa de um **histórico de jogos entre seleções** com placares e datas. Boas fontes:

- **football-data.org** — API gratuita com chave, cobre competições principais.
- **Kaggle** — datasets de "international football results" com décadas de jogos de seleções (ótimo ponto de partida, sem scraping).
- **FBref / Transfermarkt** — para dados mais ricos (xG, valor de elenco), via scraping respeitoso.

> **Ética e legalidade:** sempre leia os termos de uso e o `robots.txt` do site antes de fazer scraping, respeite limites de requisição (`time.sleep` entre chamadas) e prefira APIs oficiais quando existirem. Documente a fonte no README.

Exemplo mínimo de coleta via API (estrutura, adapte à API escolhida):

```python
# src/data_collection.py
import requests
import pandas as pd
import time

def baixar_jogos(api_key: str, competicao: str) -> pd.DataFrame:
    """Baixa jogos de uma competição da football-data.org.

    Retorna um DataFrame com colunas: data, mandante, visitante,
    gols_mandante, gols_visitante.
    """
    url = f"https://api.football-data.org/v4/competitions/{competicao}/matches"
    headers = {"X-Auth-Token": api_key}

    resposta = requests.get(url, headers=headers, timeout=30)
    resposta.raise_for_status()          # erro explícito se a requisição falhar
    dados = resposta.json()

    linhas = []
    for jogo in dados["matches"]:
        if jogo["status"] != "FINISHED":
            continue                      # só jogos já encerrados têm placar
        linhas.append({
            "data": jogo["utcDate"],
            "mandante": jogo["homeTeam"]["name"],
            "visitante": jogo["awayTeam"]["name"],
            "gols_mandante": jogo["score"]["fullTime"]["home"],
            "gols_visitante": jogo["score"]["fullTime"]["away"],
        })

    time.sleep(6)                         # respeita o limite da API gratuita
    return pd.DataFrame(linhas)
```

---

<a name="8-limpeza"></a>
## 8. Fase 2 — Limpeza e engenharia de features

Objetivos desta fase:

- **Padronizar nomes** de seleções ("USA", "United States", "EUA" → um só nome).
- **Tratar a data** como `datetime` para poder calcular o decaimento temporal.
- **Calcular o peso temporal** de cada jogo (jogos recentes pesam mais).

```python
# src/features.py
import pandas as pd
import numpy as np

def preparar(df: pd.DataFrame, xi: float = 0.0019) -> pd.DataFrame:
    """Limpa os dados e adiciona o peso de decaimento temporal.

    xi controla a velocidade do decaimento: quanto maior, mais rápido
    jogos antigos perdem importância. 0.0019 é um valor usado na
    literatura (meia-vida de ~1 ano).
    """
    df = df.dropna(subset=["gols_mandante", "gols_visitante"]).copy()
    df["data"] = pd.to_datetime(df["data"])

    # peso = e^(−xi · dias_desde_o_jogo)
    data_ref = df["data"].max()
    dias = (data_ref - df["data"]).dt.days
    df["peso"] = np.exp(-xi * dias)

    return df
```

**Feature engineering** é o nome do processo de criar variáveis úteis a partir dos dados brutos. Aqui, o "peso" é uma feature. Para os modelos de comparação (XGBoost), você criaria outras: média de gols nos últimos 5 jogos, diferença de ranking FIFA, etc.

---

<a name="9-modelo"></a>
## 9. Fase 3 — O modelo Dixon-Coles (código comentado)

Este é o coração do projeto. Vamos por partes.

### 9.1. A função de correção rho (placares baixos)

```python
# src/dixon_coles.py
import numpy as np
from scipy.stats import poisson
from scipy.optimize import minimize

def tau(gols_casa, gols_fora, lam_casa, lam_fora, rho):
    """Correção de Dixon-Coles para os 4 placares baixos.

    Ajusta as probabilidades de 0-0, 1-0, 0-1 e 1-1, que a
    Poisson pura estima mal. Para todos os outros placares
    retorna 1 (nenhuma correção).
    """
    if gols_casa == 0 and gols_fora == 0:
        return 1 - lam_casa * lam_fora * rho
    elif gols_casa == 0 and gols_fora == 1:
        return 1 + lam_casa * rho
    elif gols_casa == 1 and gols_fora == 0:
        return 1 + lam_fora * rho
    elif gols_casa == 1 and gols_fora == 1:
        return 1 - rho
    else:
        return 1.0
```

### 9.2. A log-verossimilhança negativa (o que o otimizador minimiza)

```python
def _desempacotar(params, times):
    """Separa o vetor de parâmetros em dicionários legíveis."""
    n = len(times)
    ataque = dict(zip(times, params[:n]))
    defesa = dict(zip(times, params[n:2*n]))
    mando = params[2*n]
    rho = params[2*n + 1]
    return ataque, defesa, mando, rho

def neg_log_verossimilhanca(params, df, times):
    """Calcula a log-verossimilhança negativa ponderada.

    Para cada jogo, calcula a probabilidade do placar real segundo
    o modelo, aplica a correção de Dixon-Coles, pondera pelo peso
    temporal e soma. O otimizador busca os parâmetros que minimizam
    o negativo disso (= maximizam a verossimilhança).
    """
    ataque, defesa, mando, rho = _desempacotar(params, times)
    total = 0.0

    for _, jogo in df.iterrows():
        casa, fora = jogo["mandante"], jogo["visitante"]
        gc, gf = int(jogo["gols_mandante"]), int(jogo["gols_visitante"])

        # gols esperados (lambda) de cada lado — modelo log-linear
        lam_casa = np.exp(ataque[casa] - defesa[fora] + mando)
        lam_fora = np.exp(ataque[fora] - defesa[casa])

        # probabilidade Poisson de cada placar individual
        p_casa = poisson.pmf(gc, lam_casa)
        p_fora = poisson.pmf(gf, lam_fora)

        # correção de placares baixos
        ajuste = tau(gc, gf, lam_casa, lam_fora, rho)

        prob = max(ajuste * p_casa * p_fora, 1e-10)  # evita log(0)
        total += jogo["peso"] * np.log(prob)

    return -total   # negativo porque o scipy minimiza

def treinar(df):
    """Estima os parâmetros via máxima verossimilhança."""
    times = sorted(set(df["mandante"]) | set(df["visitante"]))
    n = len(times)

    # chute inicial: ataque e defesa zerados, mando 0.25, rho 0
    chute = np.concatenate([
        np.zeros(n),        # ataques
        np.zeros(n),        # defesas
        [0.25],             # mando
        [0.0],              # rho
    ])

    # restrição: soma dos ataques = 0 (identificabilidade do modelo)
    restricoes = ({
        "type": "eq",
        "fun": lambda p: np.sum(p[:n]),
    },)

    resultado = minimize(
        neg_log_verossimilhanca,
        chute,
        args=(df, times),
        method="SLSQP",
        constraints=restricoes,
        options={"maxiter": 200, "disp": True},
    )

    ataque, defesa, mando, rho = _desempacotar(resultado.x, times)
    return {"ataque": ataque, "defesa": defesa, "mando": mando, "rho": rho}
```

> **Nota técnica:** a restrição "soma dos ataques = 0" existe porque, sem ela, você poderia somar uma constante a todos os ataques e subtrair da média geral sem mudar nada — o modelo ficaria "indeterminado". Fixar a soma resolve isso. Em entrevista, isso se chama **identificabilidade do modelo**.

### 9.3. Prever a matriz de placares de um confronto

```python
def matriz_placares(modelo, casa, fora, max_gols=8):
    """Retorna uma matriz (max_gols+1 x max_gols+1) onde a célula
    [i][j] é a probabilidade do placar i x j."""
    a, d, mando, rho = (modelo["ataque"], modelo["defesa"],
                        modelo["mando"], modelo["rho"])

    lam_casa = np.exp(a[casa] - d[fora] + mando)
    lam_fora = np.exp(a[fora] - d[casa])

    m = np.zeros((max_gols + 1, max_gols + 1))
    for i in range(max_gols + 1):
        for j in range(max_gols + 1):
            m[i, j] = (poisson.pmf(i, lam_casa)
                       * poisson.pmf(j, lam_fora)
                       * tau(i, j, lam_casa, lam_fora, rho))
    return m / m.sum()   # renormaliza para somar 1

def probabilidades_resultado(matriz):
    """Converte a matriz de placares em P(vitória casa), P(empate),
    P(vitória fora) — somando os triângulos da matriz."""
    p_casa = np.tril(matriz, -1).sum()   # abaixo da diagonal
    p_empate = np.trace(matriz)          # diagonal (placares iguais)
    p_fora = np.triu(matriz, 1).sum()    # acima da diagonal
    return p_casa, p_empate, p_fora
```

---

<a name="10-simulacao"></a>
## 10. Fase 4 — Engine de simulação Monte Carlo

Agora usamos o modelo para simular o torneio inteiro milhares de vezes.

```python
# src/simulate.py
import numpy as np
from collections import defaultdict
from dixon_coles import matriz_placares

def simular_jogo(modelo, casa, fora, rng):
    """Sorteia um placar da distribuição prevista pelo modelo."""
    m = matriz_placares(modelo, casa, fora)
    # achata a matriz e sorteia um índice proporcional à probabilidade
    idx = rng.choice(m.size, p=m.ravel())
    gc, gf = np.unravel_index(idx, m.shape)
    return int(gc), int(gf)

def simular_grupo(modelo, times_do_grupo, rng):
    """Joga todos contra todos e devolve a classificação ordenada
    pelos critérios de desempate da FIFA."""
    tabela = {t: {"pts": 0, "sg": 0, "gp": 0} for t in times_do_grupo}

    for i in range(len(times_do_grupo)):
        for j in range(i + 1, len(times_do_grupo)):
            a, b = times_do_grupo[i], times_do_grupo[j]
            ga, gb = simular_jogo(modelo, a, b, rng)

            tabela[a]["gp"] += ga; tabela[b]["gp"] += gb
            tabela[a]["sg"] += ga - gb; tabela[b]["sg"] += gb - ga
            if ga > gb:   tabela[a]["pts"] += 3
            elif gb > ga: tabela[b]["pts"] += 3
            else:         tabela[a]["pts"] += 1; tabela[b]["pts"] += 1

    # ordena por: pontos, saldo de gols, gols marcados (desempate FIFA)
    classificacao = sorted(
        times_do_grupo,
        key=lambda t: (tabela[t]["pts"], tabela[t]["sg"], tabela[t]["gp"]),
        reverse=True,
    )
    return classificacao, tabela

def simular_mata_mata(modelo, chave, rng):
    """Recebe a lista ordenada de times do bracket e elimina em pares
    até sobrar o campeão. Empates são decididos por nova simulação
    (proxy para prorrogação/pênaltis)."""
    while len(chave) > 1:
        proxima = []
        for i in range(0, len(chave), 2):
            a, b = chave[i], chave[i + 1]
            ga, gb = simular_jogo(modelo, a, b, rng)
            while ga == gb:                         # mata-mata não tem empate
                ga, gb = simular_jogo(modelo, a, b, rng)
            proxima.append(a if ga > gb else b)
        chave = proxima
    return chave[0]

def rodar_torneio(modelo, grupos, n_sim=50000, seed=42):
    """grupos: dict {'A': [t1,t2,t3,t4], 'B': [...], ...}

    Retorna a probabilidade de cada seleção ser campeã.
    """
    rng = np.random.default_rng(seed)
    titulos = defaultdict(int)

    for _ in range(n_sim):
        primeiros, segundos, terceiros = [], [], []

        for times_grupo in grupos.values():
            classif, tabela = simular_grupo(modelo, times_grupo, rng)
            primeiros.append(classif[0])
            segundos.append(classif[1])
            terceiros.append((classif[2], tabela[classif[2]]))

        # 8 melhores terceiros (ordena por pts, sg, gp)
        terceiros.sort(
            key=lambda x: (x[1]["pts"], x[1]["sg"], x[1]["gp"]),
            reverse=True,
        )
        melhores_terceiros = [t[0] for t in terceiros[:8]]

        # monta o bracket de 32 (simplificado — ver nota abaixo)
        bracket = primeiros + segundos + melhores_terceiros
        rng.shuffle(bracket)   # placeholder: troque pela tabela oficial FIFA

        campeao = simular_mata_mata(modelo, bracket, rng)
        titulos[campeao] += 1

    return {t: v / n_sim for t, v in
            sorted(titulos.items(), key=lambda x: -x[1])}
```

> **Onde melhorar (e ganhar pontos):** o `rng.shuffle(bracket)` acima é um atalho. A versão profissional usa a **tabela oficial da FIFA** que mapeia "1º do grupo A enfrenta 3º do grupo X" etc., respeitando a separação dos favoritos. Implementar isso corretamente é o detalhe que faz seu projeto se destacar — deixe um comentário no código admitindo a simplificação e, se tiver tempo, implemente a versão real. Honestidade técnica conta a favor.

---

<a name="11-validacao"></a>
## 11. Fase 5 — Validação honesta do modelo

Antes de confiar nas probabilidades, prove que o modelo presta.

```python
# src/evaluate.py
import numpy as np

def brier_score_multi(probs, resultado_real):
    """Brier score para 3 classes (vitória casa / empate / vitória fora).

    probs: array [p_casa, p_empate, p_fora]
    resultado_real: índice 0, 1 ou 2 do que de fato aconteceu.
    Quanto MENOR, melhor.
    """
    alvo = np.zeros(3)
    alvo[resultado_real] = 1
    return np.sum((np.array(probs) - alvo) ** 2)

def backtest(df_treino, df_teste, treinar_fn, modelo_probs_fn):
    """Treina no passado, prevê o futuro e mede o Brier score médio.

    É a prova honesta de que o modelo generaliza para dados que
    nunca viu. Use Copas anteriores (2018, 2022) como df_teste.
    """
    modelo = treinar_fn(df_treino)
    scores = []
    for _, jogo in df_teste.iterrows():
        probs = modelo_probs_fn(modelo, jogo["mandante"], jogo["visitante"])
        gc, gf = jogo["gols_mandante"], jogo["gols_visitante"]
        real = 0 if gc > gf else (1 if gc == gf else 2)
        scores.append(brier_score_multi(probs, real))
    return np.mean(scores)
```

**O que reportar no relatório:**

- Brier score do seu modelo vs. um **baseline ingênuo** (ex: sempre prever 33%/33%/33%, ou prever pelo ranking FIFA). Bater o baseline é o mínimo.
- **Curva de calibração** (reliability diagram): no eixo X a probabilidade prevista, no eixo Y a frequência real observada. Quanto mais perto da diagonal, melhor calibrado.
- Comparação Dixon-Coles vs. XGBoost no mesmo backtest, com uma discussão honesta dos trade-offs.

---

<a name="12-dashboard"></a>
## 12. Fase 6 — Dashboard e comunicação

Um **Streamlit** transforma o projeto numa experiência interativa. Esqueleto:

```python
# app/dashboard.py
import streamlit as st
import pandas as pd

st.title("World Cup 2026 — Simulador de Probabilidades")

st.markdown(
    "Probabilidades de título estimadas por um modelo Dixon-Coles "
    "e 50.000 simulações de Monte Carlo do torneio."
)

# carregue aqui os resultados pré-computados (não rode 50k sims no app!)
probs = pd.read_csv("data/processed/prob_titulo.csv")

st.subheader("Favoritos ao título")
st.bar_chart(probs.set_index("selecao")["prob_titulo"].head(10))

col1, col2 = st.columns(2)
with col1:
    casa = st.selectbox("Seleção A", probs["selecao"])
with col2:
    fora = st.selectbox("Seleção B", probs["selecao"])

if st.button("Simular confronto"):
    st.write("Carregue o modelo e mostre P(vitória), P(empate), P(derrota).")
```

> **Regra de ouro de performance:** nunca rode as 50.000 simulações dentro do app. Compute offline, salve os resultados em CSV e o dashboard só **lê** e exibe.

**No README**, conte a história: o problema, a abordagem (Dixon-Coles + Monte Carlo), os resultados de validação, e um print do dashboard. É a primeira coisa que um recrutador lê.

---

<a name="13-cronograma"></a>
## 13. Cronograma de 4 semanas

**Semana 1 — Dados.** Escolher fonte, coletar histórico de seleções, limpar, padronizar nomes, montar a EDA (gráficos de gols por seleção, desempenho histórico). Entregável: `01_eda.ipynb` e dados em `data/processed/`.

**Semana 2 — Modelo.** Implementar e treinar o Dixon-Coles. Validar com backtest na Copa de 2022. Comparar Brier score contra um baseline. Entregável: `dixon_coles.py` funcionando + primeiros números de validação.

**Semana 3 — Simulação.** Construir a engine de Monte Carlo com a regra dos 8 terceiros e (idealmente) o mapeamento oficial do bracket. Rodar as 50.000 simulações. Treinar o XGBoost de comparação. Entregável: `simulate.py` + tabela de probabilidades de título.

**Semana 4 — Comunicação.** Dashboard Streamlit, curva de calibração, README profissional, testes em `tests/`, e a escrita da metodologia. Entregável: projeto publicado no GitHub com README caprichado.

---

<a name="14-glossario"></a>
## 14. Glossário rápido

- **Variável aleatória:** número cujo valor depende do acaso.
- **Distribuição de Poisson:** distribuição para contar eventos raros; parâmetro λ = média esperada.
- **λ (lambda):** número esperado de gols de um time num jogo.
- **Força de ataque/defesa:** quanto um time marca/sofre acima ou abaixo da média.
- **Vantagem de mando:** bônus de gols por jogar em casa.
- **Verossimilhança (likelihood):** probabilidade dos dados observados dado um conjunto de parâmetros.
- **MLE:** método de estimar parâmetros maximizando a verossimilhança.
- **Dixon-Coles:** modelo Poisson refinado para futebol (corrige placares baixos + decaimento temporal).
- **rho (ρ):** parâmetro de correção dos placares baixos.
- **xi (ξ):** parâmetro de decaimento temporal.
- **Monte Carlo:** estimar probabilidades repetindo uma simulação aleatória muitas vezes.
- **Treino/teste:** dados para ajustar / para avaliar o modelo.
- **Data leakage:** vazamento de informação do teste para o treino; infla resultados falsamente.
- **Backtesting:** validar o modelo em eventos passados.
- **Regressão logística:** modelo simples para prever probabilidade de classes.
- **XGBoost:** modelo de boosting de árvores; alta performance, baixa interpretabilidade.
- **Acurácia:** % de previsões corretas.
- **Brier score:** erro das probabilidades previstas (menor = melhor).
- **Log loss:** erro de probabilidade que pune confiança errada.
- **Calibração:** quão fiéis são as probabilidades à realidade.
- **Feature engineering:** criar variáveis úteis a partir de dados brutos.
- **Identificabilidade:** garantir que os parâmetros do modelo têm solução única.

---

*Documento criado como material de estudo e documentação de portfólio. Adapte os nomes de seleções, a fonte de dados e os grupos reais do sorteio de 2026 conforme for construindo.*
