# FielCup

World Cup 2026 forecasting project built with Python, SQL, Dixon-Coles ratings,
a talent prior and Monte Carlo simulation.

FielCup answers one question: **what is each nation's chance of winning the
2026 World Cup?** The project starts from historical international match data,
builds a SQLite analytics layer, estimates team strength, simulates the
tournament thousands of times and presents the result in a bilingual Streamlit
dashboard.

[Open the live app](https://fielcup.streamlit.app)

![status](https://img.shields.io/badge/status-active-C0392B)
![python](https://img.shields.io/badge/python-3.11+-141414)
![sql](https://img.shields.io/badge/SQL-SQLite-003B57)
![streamlit](https://img.shields.io/badge/dashboard-Streamlit-C0392B)
![license](https://img.shields.io/badge/license-MIT-green)

## Preview

The dashboard is bilingual and works on desktop and mobile.

<p align="center">
  <img src="docs/img/dashboard_mobile.png" width="250" alt="FielCup mobile dashboard in Portuguese">
  &nbsp;&nbsp;
  <img src="docs/img/dashboard_en.png" width="250" alt="FielCup mobile dashboard in English">
</p>

<p align="center">
  <img src="docs/img/analise_jogo.png" width="520" alt="Per-match statistical analysis in FielCup">
</p>

## Why This Project

This is a portfolio data analytics project designed to show an end-to-end
workflow:

- Data sourcing and cleaning from real football match history
- SQL-first analytics layer with SQLite
- Statistical modelling with Dixon-Coles goal probabilities
- Model improvement with FIFA ranking and squad-value talent signals
- Monte Carlo simulation of the full 48-team tournament
- Backtesting on the 2022 World Cup
- Interactive dashboard for exploring forecasts and match probabilities

## Current Forecast

Default model: results plus talent blend with `alpha = 0.6`.

| Rank | Nation | Title probability | Market implied probability |
| --- | --- | ---: | ---: |
| 1 | Argentina | 18.5% | ~9.5% |
| 2 | Spain | 14.8% | ~18% |
| 3 | England | 10.2% | ~12% |
| 4 | France | 9.8% | ~18% |
| 5 | Brazil | 7.6% | ~10% |
| 6 | Portugal | 6.4% | ~11% |

The `alpha` slider controls the blend between measured results and the talent
prior. `alpha = 1.0` reproduces the results-only model; lower values give more
weight to FIFA ranking and squad value.

## How It Works

1. **Data layer.** Raw and reference CSV files are loaded into
   `db/fielcup.db`. Feature engineering and sanity checks use SQL queries.
2. **Dixon-Coles model.** Team attack and defense strengths are fitted from
   historical match results with time decay and a low-score correction.
3. **Talent prior.** FIFA ranking points and squad value are normalized and
   blended with the results model to reduce obvious blind spots.
4. **Tournament simulation.** The 2026 group stage and knockout rounds are
   simulated with vectorized NumPy Monte Carlo runs.
5. **Validation.** The model is backtested on the 2022 World Cup using only
   pre-tournament data.
6. **Dashboard.** Streamlit exposes the forecast, alpha slider, match analysis
   and live score updates.

## Data Source

FielCup uses international match history derived from
[martj42/international_results](https://github.com/martj42/international_results),
an open football dataset with men's full international results from 1872 onward.

The main source file is `data/raw/results.csv`, which includes:

- `date`
- `home_team`
- `away_team`
- `home_score`
- `away_score`
- `tournament`
- `city`
- `country`
- `neutral`

More detail is documented in [docs/DATA_SOURCE.md](docs/DATA_SOURCE.md).

## Project Structure

```text
fielcup/
|-- app/
|   `-- dashboard.py              # Streamlit dashboard
|-- data/
|   |-- raw/results.csv           # historical match results
|   |-- reference/talento_2026.csv
|   `-- processed/                # fixtures, groups, model outputs
|-- db/
|   `-- fielcup.db                # SQLite database
|-- docs/
|   |-- DATA_SOURCE.md
|   |-- ACESSO_CELULAR.md
|   `-- PLANO_EXPANSAO.md
|-- scripts/
|   `-- smoke_test.py             # quick project health check
|-- src/
|   |-- database.py               # SQL layer
|   |-- features.py               # cleaning and feature engineering
|   |-- dixon_coles.py            # statistical model
|   |-- talento.py                # results + talent blend
|   |-- simulate.py               # Monte Carlo tournament simulation
|   |-- evaluate.py               # backtesting
|   `-- api_collector.py          # optional live result updates
`-- requirements.txt
```

## Quick Start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run a quick health check:

```bash
python scripts/smoke_test.py
```

Rebuild the pipeline:

```bash
python src/database.py
python src/features.py
python src/dixon_coles.py
python src/talento.py
python src/simulate.py --sims 50000 --alpha 0.6
python src/evaluate.py
```

Launch the dashboard:

```bash
streamlit run app/dashboard.py
```

## Optional Live Updates

The dashboard can import completed matches from API-Football during the
tournament. This is optional; manual score entry also works.

```bash
cp .env.example .env
export API_FOOTBALL_KEY="your_key"
python src/api_collector.py --update-results
python src/features.py && python src/dixon_coles.py && python src/simulate.py
```

## Documentation

- [Data source](docs/DATA_SOURCE.md)
- [Mobile access and deployment](docs/ACESSO_CELULAR.md)
- [Model vs expert consensus](docs/ANALISE_modelo_vs_especialistas.md)
- [Expansion plan](docs/PLANO_EXPANSAO.md)
- [Project notes in Portuguese](docs/SOBRE_O_PROJETO.md)

## Limitations

- The knockout bracket is simplified compared with FIFA's full fixed bracket.
- FIFA ranking and squad value are static snapshots.
- The talent blend is a modelling choice, not ground truth.
- Penalties, rare tiebreakers, injuries and tactical context are approximated.

## Tech Stack

Python, pandas, NumPy, SciPy, SQLite, SQL, Streamlit, Dixon-Coles modelling,
Monte Carlo simulation, API-Football and football analytics.

## License

Code in this repository is released under the MIT License. The football dataset
source is documented separately and should be credited when reused.
