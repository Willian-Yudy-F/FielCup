# FielCup — Explicação completa do projeto

Este documento explica, em português e em linguagem acessível, tudo o que
o projeto FielCup faz: desde a coleta dos dados até os modelos usados e
como mantê-lo atualizado durante a Copa de 2026. Serve como guia de estudo
e como memória do que foi construído.

---

## O que é o FielCup, em uma frase

Um sistema que prevê a probabilidade de cada seleção ser campeã da Copa do
Mundo de 2026, usando um modelo estatístico de futebol treinado com milhares
de jogos reais e uma simulação que "joga" o torneio inteiro milhares de vezes.
O forecast versionado no repositório usa 50.000 simulações; o dashboard usa
8.000 por padrão para continuar rápido quando o usuário mexe no botão `alpha`.

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
combinações de resultados. Então simulamos: jogamos a Copa inteira milhares
de vezes. Em cada simulação, sorteamos o placar de cada jogo (usando o modelo),
montamos as tabelas dos grupos com os critérios da FIFA, classificamos os 2
primeiros de cada grupo + os 8 melhores terceiros, e rodamos o mata-mata até
a final. A frequência com que cada seleção vence vira sua probabilidade.

### Etapa 5 — Validação (`src/evaluate.py`)
A parte que dá credibilidade. Treinamos o modelo SÓ com dados anteriores a
novembro de 2022, previmos a Copa de 2022 (que o modelo nunca viu) e medimos
o erro. O script `src/evaluate.py` calcula o Brier score do modelo e compara
com um baseline ingênuo. Isso prova, de forma honesta e reproduzível, se o
modelo tem poder preditivo.

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

Modelo padrão (`alpha=0.6`, resultado + talento): Argentina (18,5%),
Espanha (14,8%), Inglaterra (10,2%), França (9,8%), Brasil (7,6%) e
Portugal (6,4%).

IMPORTANTE — a honestidade do projeto: o modelo discorda das casas de aposta
(que põem Espanha e França no topo), mas a versão atual já reduz parte dessa
cegueira ao misturar resultados com ranking FIFA e valor de elenco. Ainda há
limitações: idade do elenco, lesões, tática e contexto de torneio continuam
fora do modelo. Entender essa limitação é o que dá maturidade ao projeto. O
documento `ANALISE_modelo_vs_especialistas.md` detalha isso.

---

## Como atualizar com os jogos que vão acontecer

Durante a Copa, novos resultados saem todo dia. O fluxo principal agora é
local e manual: você roda o dashboard no seu computador, digita os placares
que recebeu e salva. A previsão deixa de sortear esses jogos e passa a
tratá-los como fatos, recalculando o ranking condicionado aos resultados já
registrados.

1. No terminal:
   ```
   streamlit run app/dashboard.py
   ```
2. Abra a seção **Resultados locais**.
3. Preencha os gols dos jogos concluídos.
4. Clique em **Salvar e recalcular**.
5. Gere o relatório HTML mobile para os jogos do dia ou para uma partida.

O arquivo `src/api_collector.py` fica como experimento opcional para uma
automação futura, mas o dashboard principal não depende dele.

---

## Por que este projeto é bom para um portfólio

- Tem profundidade estatística real (não é só usar uma biblioteca pronta).
- Tem validação científica honesta (backtesting).
- Tem comunicação visual (dashboard).
- Tem pensamento crítico (a análise de por que diverge dos especialistas).
- Tem visão de engenharia (dashboard local, atualização manual controlada,
  testes e CI).

São exatamente as competências que separam um projeto de estudante de um
projeto profissional.
