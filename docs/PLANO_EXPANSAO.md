# FielCup v2 — Plano de Expansão: Dados, APIs e Automação

> Como evoluir o FielCup de um modelo treinado só com placares para um
> sistema que se atualiza sozinho durante a Copa e enxerga o que hoje é
> cego: a força real dos elencos.

---

## 1. Por que expandir (o diagnóstico)

O modelo atual tem uma cegueira conhecida e importante: **ele só vê
resultados de jogos de seleção**. Não sabe que a França tem Mbappé e a
defesa mais profunda do torneio, nem que a Espanha tem Yamal e Pedri. Por
isso superestima a Argentina (que venceu muito como seleção recentemente)
e subestima França e Espanha (cuja força mora no valor individual dos
jogadores, invisível nos placares).

Os especialistas e as casas de aposta acertam mais porque combinam
estatística **com** conhecimento de elenco, lesões, forma individual e
contexto. A expansão busca dar ao modelo parte dessa visão — e, de quebra,
automatizar a coleta para você não precisar acompanhar 104 jogos na mão.

---

## 2. Que dados realmente importam (em ordem de impacto)

Nem todo dado vale o esforço de coletar. Esta é a priorização honesta,
do que mais move a agulha para o que é "bom ter":

### Nível 1 — Alto impacto, essencial
- **Resultados das partidas** (placar, data, fase). Já temos. É a espinha
  dorsal e continua sendo o sinal mais forte.
- **Valor de mercado do elenco** (Transfermarkt). Proxy poderoso da força
  individual que falta ao modelo. Um elenco que vale €1,2 bi (França) vs.
  um que vale €400 mi diz muito que o placar não diz.
- **Ranking FIFA / Elo** das seleções. Sintetiza força relativa e é
  atualizado oficialmente. Ótimo como feature de ajuste.

### Nível 2 — Médio impacto, melhora o modelo
- **xG (expected goals) por jogo.** Mede a *qualidade* das chances, não só
  os gols. Um time pode vencer 1x0 com xG de 0,3 (sorte) ou de 2,5
  (domínio). xG separa sorte de mérito e dá um sinal muito mais estável que
  o placar bruto.
- **Disponibilidade de jogadores** (lesões, suspensões). Argentina sem
  Messi é outra Argentina. Coletar quem está fora antes de cada jogo
  permite ajustar a força na hora.
- **Estatísticas por jogo:** posse, finalizações, finalizações no gol,
  escanteios. Alimentam modelos mais ricos que só placar.

### Nível 3 — Baixo impacto, "bom ter" (cuidado com o custo/benefício)
- **Clima e estádio.** Você mencionou, e faz sentido pensar nisso — calor
  extremo, altitude (Cidade do México!), chuva afetam o jogo. MAS: o efeito
  é pequeno e difícil de estimar com poucos dados, e some no ruído de uma
  única partida. Recomendação honesta: colete o dado (é fácil via API de
  clima), mas **não espere que mova muito o modelo**. É mais um diferencial
  de "olha que completo" no portfólio do que um ganho preditivo real.
- **Dados de tracking/posicionamento.** Heatmaps, distância percorrida.
  Lindos, mas exigem APIs caras e raramente melhoram previsão de resultado.

> **Regra de ouro:** comece pelo Nível 1. Cada nível adicional dá retorno
> decrescente e custa mais trabalho. Um modelo com placar + valor de elenco
> + ranking FIFA já seria uma evolução enorme sobre o atual.

---

## 3. As APIs (o que existe e qual escolher)

Pesquisa de mercado (junho/2026), com o trade-off de cada uma:

| API | Cobre seleções/Copa? | Dados de jogador? | Grátis? | Veredito |
|-----|----------------------|-------------------|---------|----------|
| **API-Football** | Sim | Sim (lesões, stats, lineups) | 100 req/dia grátis | **Melhor escolha.** Cobre tudo que precisamos no tier grátis. |
| football-data.org | Ligas principais | Limitado | 10 req/min, grátis | Bom para resultados, fraco em jogador. |
| TheSportsDB | Sim | Básico | Grátis | Bom para logos/imagens, dados crowdsourced. |
| Transfermarkt | — (scraping) | Valor de mercado | Grátis (scraping) | Única fonte boa de valor de elenco. |
| Open-Meteo | Clima | — | Grátis, sem chave | Para o dado de clima do Nível 3. |

**Decisão:** API-Football como fonte principal (resultados, stats, lesões,
elencos) + Transfermarkt para valor de mercado + Open-Meteo para clima.
Todas têm opção gratuita.

### Como obter a chave da API-Football
1. Crie conta em https://dashboard.api-football.com
2. Copie sua API key do painel.
3. No terminal, antes de rodar o coletor:
   ```bash
   export API_FOOTBALL_KEY="sua_chave_aqui"
   ```
   (Nunca escreva a chave dentro do código nem suba para o GitHub.)

---

## 4. O coletor automático (já implementado)

O arquivo `src/api_collector.py` já faz a parte essencial:
- `--update-results`: baixa os jogos finalizados da Copa e os incorpora ao
  `results.csv`, sem duplicar.
- `--stats`: coleta estatísticas detalhadas por jogo.

Fluxo de uso durante a Copa:
```bash
export API_FOOTBALL_KEY="sua_chave"
python src/api_collector.py --update-results
# depois, reprocessa o pipeline com os dados novos:
python src/features.py
python src/dixon_coles.py
python src/simulate.py
```

---

## 5. Automação: rodar sozinho (o que você pediu)

São 104 jogos; ninguém acompanha na mão. Há três níveis de automação,
do mais simples ao mais robusto:

### Opção A — cron no seu Mac (simples, grátis)
O `cron` é o agendador do macOS/Linux. Você cria um script que roda o
pipeline inteiro e agenda para rodar, por exemplo, todo dia às 8h.

Crie um arquivo `atualizar.sh` na raiz do projeto:
```bash
#!/bin/bash
cd /Users/SEU_USUARIO/fielcup
source venv/bin/activate
export API_FOOTBALL_KEY="sua_chave"
python src/api_collector.py --update-results
python src/features.py
python src/dixon_coles.py
python src/simulate.py
echo "Atualizado em $(date)" >> log_atualizacao.txt
```

Torne-o executável e agende:
```bash
chmod +x atualizar.sh
crontab -e
# adicione a linha (roda todo dia às 8h):
0 8 * * * /Users/SEU_USUARIO/fielcup/atualizar.sh
```
Limitação: só roda com o Mac ligado.

### Opção B — GitHub Actions (roda na nuvem, grátis)
Melhor opção: roda sozinho num servidor do GitHub, mesmo com seu PC
desligado, e ainda versiona os resultados. Crie
`.github/workflows/atualizar.yml`:
```yaml
name: Atualizar FielCup
on:
  schedule:
    - cron: '0 8 * * *'   # todo dia às 8h UTC
  workflow_dispatch:        # permite rodar manualmente também
jobs:
  atualizar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: |
          python src/api_collector.py --update-results
          python src/features.py
          python src/dixon_coles.py
          python src/simulate.py
        env:
          API_FOOTBALL_KEY: ${{ secrets.API_FOOTBALL_KEY }}
      - run: |
          git config user.name "fielcup-bot"
          git config user.email "bot@fielcup"
          git add data/
          git commit -m "Atualização automática dos dados" || echo "sem mudanças"
          git push
```
A chave fica guardada com segurança em Settings → Secrets do seu repo
(nunca no código). Esta é a forma profissional e é o que eu recomendo.

### Opção C — Streamlit Cloud (dashboard sempre no ar)
Publique o dashboard de graça no Streamlit Community Cloud
(https://share.streamlit.io). Ele lê os dados que o GitHub Actions
atualiza, então o site fica sempre com os números mais recentes, sozinho.

---

## 6. Roadmap sugerido (ordem de implementação)

1. **Agora:** ligar o `api_collector.py` com sua chave e testar o
   `--update-results`. (Pré-Copa, ele não traz nada, mas valida a conexão.)
2. **Quando a Copa começar:** automatizar com GitHub Actions (Opção B).
3. **v2 do modelo:** adicionar valor de elenco (Transfermarkt) e ranking
   FIFA como features. É o que vai corrigir a cegueira de não ver os elencos.
4. **v3 (avançado):** migrar de "placar" para "xG" como variável-alvo,
   usando as estatísticas coletadas. Modelo mais sofisticado.
5. **Opcional:** clima via Open-Meteo, mais como vitrine de completude do
   que por ganho preditivo.

---

## 7. Uma nota honesta sobre expectativas

Adicionar dados de elenco vai aproximar o modelo dos especialistas, mas
**não vai torná-lo um oráculo** — futebol é irredutivelmente imprevisível
(foi por isso que Marrocos foi semifinalista e a Arábia bateu a Argentina
em 2022). O objetivo da expansão não é "acertar o campeão", é construir um
sistema de dados mais rico, automatizado e defensável. Esse é o valor real
para o portfólio: mostrar que você sabe desenhar um pipeline que evolui,
se atualiza sozinho e incorpora novas fontes — competências de engenharia
de dados que valem tanto quanto a estatística.
