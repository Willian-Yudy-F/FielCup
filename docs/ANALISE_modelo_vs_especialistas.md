# FielCup: o modelo vs. os especialistas

Uma das partes mais interessantes de um projeto preditivo é confrontar o
que o modelo diz com o consenso dos profissionais da área. Quando os dois
discordam, ou o modelo achou algo que o mercado ignora, ou o modelo tem um
viés que precisa ser entendido. Aqui acontecem as duas coisas — e entender
qual é qual é exatamente o tipo de raciocínio que dá valor ao projeto.

## O placar: modelo vs. casas de aposta (junho/2026)

Modelo padrão: resultados + talento, com `alpha=0.6`.

| Posição | Modelo FielCup | Casas de aposta / mercados |
|---------|----------------|----------------------------|
| 1º | 🇦🇷 Argentina (18,5%) | 🇪🇸 Espanha (~18%) |
| 2º | 🇪🇸 Espanha (14,8%) | 🇫🇷 França (~18%) |
| 3º | 🏴 Inglaterra (10,2%) | 🏴 Inglaterra (~12%) |
| 4º | 🇫🇷 França (9,8%) | 🇵🇹 Portugal (~11%) |
| 5º | 🇧🇷 Brasil (7,6%) | 🇧🇷 Brasil (~10%) |
| 6º | 🇵🇹 Portugal (6,4%) | 🇦🇷 Argentina (~9,5%) |

As casas de aposta convergem num consenso claro: Espanha e França lideram
empatadas no topo, seguidas de Inglaterra. A versão atual do FielCup já não é
um modelo "só resultados": ela mistura Dixon-Coles com ranking FIFA e valor de
elenco. Isso aproxima o modelo do mercado, mas ainda preserva uma discordância
importante: **a Argentina aparece como favorita clara**.

## Divergência nº 1: por que o modelo ainda ama a Argentina

Esta é a discordância mais marcante. O mercado dá cerca de 9,5% para a
Argentina; o modelo dá 18,5%. Por quê?

O FielCup mede força de ataque e defesa a partir de resultados recentes, com
decaimento temporal. Nos dados, a Argentina tem uma defesa medida muito forte
e um histórico recente excelente: foi campeã mundial em 2022, venceu a Copa
América e teve uma campanha robusta nas Eliminatórias. Para um modelo que dá
peso real ao que aconteceu em campo, isso é evidência forte.

Os especialistas enxergam algo que o modelo ainda não mede bem: idade, desgaste
físico, ciclo de elenco e contexto tático. Messi terá 39 anos em 2026, e parte
do elenco campeão envelheceu. O mercado parece descontar mais esse risco do
que o FielCup.

## Divergência nº 2: por que França e Espanha sobem com talento

No modelo antigo, baseado só em resultados de seleção, a França ficava baixa
demais. A versão atual corrige parte desse problema: ranking FIFA e valor de
elenco entram como um prior de talento, então França e Espanha sobem para a
mesma vizinhança do consenso de mercado.

A força da França mora muito no valor individual do elenco — Mbappé e
companhia — e em jogadores que brilham em clubes de elite. O modelo puro de
resultados não sabe que Mbappé existe; ele só sabe que a seleção francesa nem
sempre goleou. O blend com talento dá ao FielCup parte dessa informação externa
sem abandonar o histórico de placares.

## O que o modelo acerta junto com os especialistas

Nem tudo é divergência, e isso é importante: a Inglaterra aparece em 3º nos
dois, a Espanha está no topo dos dois, a França voltou ao top 4 depois do
blend, e times como Portugal e Brasil ficam na mesma vizinhança de
probabilidade. O modelo também ainda reconhece seleções fortes fora do grupo
de favoritos óbvios, como Marrocos, que foi semifinalista em 2022.

## A lição metodológica

O modelo é forte onde resultados recentes refletem força real e ficou menos
cego a talento depois de incorporar ranking FIFA e valor de elenco. Ele ainda
não mede idade do elenco, lesões, motivação, esquema tático ou notícias de
última hora.

Casas de aposta combinam modelos estatísticos com todo esse conhecimento
contextual e com o dinheiro de milhares de apostadores. Divergir delas não é
um defeito a esconder: é uma oportunidade de explicar **o que seu modelo vê e
o que ele ainda não vê**.

Num portfólio, essa análise vale mais que o número em si. Ela mostra que você
entende as suposições do seu modelo, sabe diagnosticar onde ele falha, e
consegue contextualizar resultados em vez de tratá-los como verdade absoluta.

---

*Dados de mercado coletados em junho de 2026 de agregadores de odds
(ESPN, FOX Sports, CBS, Covers, oddschecker). Probabilidades implícitas
das odds são aproximadas e incluem a margem das casas.*
