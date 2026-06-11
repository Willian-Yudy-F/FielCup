# FielCup — World Cup 2026 Forecast

A statistical model that predicts every World Cup 2026 fixture and simulates the whole tournament 50,000 times to estimate each nation chance of winning the title. End-to-end data science pipeline: data collection, a Dixon-Coles goal model, Monte Carlo simulation, backtesting validation and a Streamlit dashboard.

## Model top 5

| # | Nation | Title prob. |
|---|--------|-------------|
| 1 | Argentina | 22.2% |
| 2 | Spain | 13.8% |
| 3 | England | 7.6% |
| 4 | Morocco | 5.7% |
| 5 | Brazil | 5.6% |

## How it works

1. Dixon-Coles model: goals follow a Poisson distribution combining attack strength, opponent defense and home advantage, with low-score correction and time decay, fit by maximum likelihood.
2. Neutral-venue aware: home advantage only applies to non-neutral games.
3. Monte Carlo: the tournament is simulated 50,000 times with FIFA group rules and the 8 best third-placed teams.
4. Validation: backtested on WC2022 (unseen), beating a naive baseline by +7.2% on the Brier score.

## Structure

- src/data_collection.py, features.py, dixon_coles.py, simulate.py, evaluate.py, api_collector.py
- app/dashboard.py — Streamlit dashboard
- data/ — raw and processed data

## Run

Install requirements.txt, then run the src scripts in order, and launch with: streamlit run app/dashboard.py

## Limitations

Simplified knockout bracket; the model sees only match results, not squad value or injuries. Portfolio project, not betting advice. Data: martj42/international_results.
