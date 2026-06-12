# FielCup — Explicação completa do projeto

Este documento explica, em português e em linguagem acessível, tudo o que
o projeto FielCup faz: desde a coleta dos dados até os modelos usados e
como mantê-lo atualizado durante a Copa de 2026. Serve como guia de estudo
e como memória do que foi construído.

---

## O que é o FielCup, em uma frase

Um sistema que prevê a probabilidade de cada seleção ser campeã da Copa do
Mundo de 2026, usando um modelo estatístico de futebol treinado com milhares
de jogos reais e uma simulação que "joga" o torneio inteiro 50.000 vezes.

---

## A pergunta que o projeto responde

"Qual a chance real de cada seleção levantar a taça?" Em vez de chutar ou
repetir o senso comum, o FielCup constrói a resposta a partir de dados.

---

## As 6 etapas do projeto (o pipeline)

Um projeto de data science é uma esteira: cada etapa entrega algo para a
próxima. As nossas foram:

### Etapa 1 — Coleta de dados (`src/data_collection.py`)
Baixamos o histórico de ~49 mil partidas entre seleções (de 1872 até 2026)
de uma base pública e confiável (repositório martj42/international_results).
Esses dados ficam intocados em `data/raw/` — assim sempre podemos
reprocessar do zero. Surpresa boa: a base já trazia os 72 confrontos
agendados da fase de grupos de 2026, com as 48 seleções.

### Etapa 2 — Limpeza e preparação (`src/features.py`)
Transformamos dados brutos em dados prontos para o modelo:
- Separamos os jogos em TREINO (já têm placar, ~8 mil desde 2018) e ALVO
  (os 72 jogos da Copa, ainda sem placar).
- Demos mais "peso" aos jogos recentes (decaimento temporal): um jogo de 1
  ano atrás pesa metade de um jogo de hoje. Isso faz o modelo refletir a
  força ATUAL das seleções.
- Identificamos automaticamente os 12 grupos de 4 seleções.

### Etapa 3 — O modelo Dixon-Coles (`src/dixon_coles.py`)
O coração do projeto. O modelo aprende, a partir dos jogos, uma FORÇA DE
ATAQUE e uma FORÇA DE DEFESA para cada seleção. A ideia matemática:
- O número de gols de um time num jogo segue uma distribuição de Poisson
  (boa para contar eventos raros, como gols).
- O modelo combina o ataque de um time com a defesa do adversário para
  estimar quantos gols cada lado faz.
- A "correção de Dixon-Coles" ajusta placares baixos (0-0, 1-0, etc.), que
  o Poisson puro estima mal.
- Os números são encontrados por "máxima verossimilhança": o computador
  ajusta os valores até que os resultados reais fiquem os mais prováveis
  possíveis.
Com isso, conseguimos prever a distribuição de placares de QUALQUER
confronto (ex.: Brasil x Argentina).

### Etapa 4 — Simulação de Monte Carlo (`src/simulate.py`)
Não dá para calcular com uma fórmula a chance de título — são bilhões de
combinações de resultados. Então simulamos: jogamos a Copa inteira 50.000
vezes. Em cada simulação, sorteamos o placar de cada jogo (usando o modelo),
montamos as tabelas dos grupos com os critérios da FIFA, classificamos os 2
primeiros de cada grupo + os 8 melhores terceiros, e rodamos o mata-mata até
a final. A frequência com que cada seleção vence vira sua probabilidade.

### Etapa 5 — Validação (`src/evaluate.py`)
A parte que dá credibilidade. Treinamos o modelo SÓ com dados anteriores a
novembro de 2022, previmos a Copa de 2022 (que o modelo nunca viu) e medimos
o erro. Resultado: o modelo erra menos que um "chute ingênuo" em 7,2% (medido
pelo Brier score). Isso prova, de forma honesta, que ele tem poder preditivo.

### Etapa 6 — Dashboard e comunicação (`app/dashboard.py`)
Um painel visual interativo (em Streamlit) com o ranking de favoritos e um
simulador de confrontos. É a vitrine do projeto, com design de pôster
mid-century em preto/branco/vermelho.

---

## Os modelos e conceitos usados (glossário)

- **Distribuição de Poisson:** modelo estatístico para contar eventos
  (gols por jogo).
- **Modelo Dixon-Coles:** versão da Poisson feita sob medida para futebol,
  com correção de placares baixos e peso para jogos recentes.
- **Máxima verossimilhança:** método de "ensinar" o modelo ajustando seus
  parâmetros até os dados reais ficarem mais prováveis.
- **Simulação de Monte Carlo:** repetir um experimento aleatório milhares
  de vezes para estimar probabilidades.
- **Backtesting:** testar o modelo no passado para ver se ele teria
  acertado.
- **Brier score:** mede o quão boas são as probabilidades previstas (quanto
  menor, melhor).

---

## O resultado principal

Top 5 do modelo: Argentina (22,2%), Espanha (13,8%), Inglaterra (7,6%),
Marrocos (5,7%), Brasil (5,6%).

IMPORTANTE — a honestidade do projeto: o modelo discorda das casas de aposta
(que põem Espanha e França no topo). Isso acontece porque o modelo só vê
RESULTADOS de seleção, e não enxerga a força dos ELENCOS (Mbappé, Yamal...).
Por isso ele superestima a Argentina (que venceu muito recentemente) e
subestima França e Espanha (cuja força está no talento individual). Entender
essa limitação é o que dá maturidade ao projeto. O documento
`ANALISE_modelo_vs_especialistas.md` detalha isso.

---

## Como atualizar com os jogos que vão acontecer

Durante a Copa, novos resultados saem todo dia. O projeto tem um coletor
automático (`src/api_collector.py`) que puxa os jogos finalizados de uma API
(API-Football) e os incorpora aos dados. O fluxo:

1. Pegue uma chave gratuita em https://dashboard.api-football.com
2. No terminal:
   ```
   export API_FOOTBALL_KEY="sua_chave"
   python src/api_collector.py --update-results
   python src/features.py
   python src/dixon_coles.py
   python src/simulate.py
   ```
   Isso baixa os jogos novos e recalcula tudo com os dados atualizados.

Para não fazer isso na mão a cada jogo, dá para automatizar com GitHub
Actions (roda sozinho na nuvem, todo dia). O passo a passo está em
`PLANO_EXPANSAO.md`.

---

## Por que este projeto é bom para um portfólio

- Tem profundidade estatística real (não é só usar uma biblioteca pronta).
- Tem validação científica honesta (backtesting).
- Tem comunicação visual (dashboard).
- Tem pensamento crítico (a análise de por que diverge dos especialistas).
- Tem visão de engenharia (coletor automático e plano de automação).

São exatamente as competências que separam um projeto de estudante de um
projeto profissional.
