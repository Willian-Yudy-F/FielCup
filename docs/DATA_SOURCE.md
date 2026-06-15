# Data Source

FielCup uses historical men's international football results derived from
[martj42/international_results](https://github.com/martj42/international_results).
That repository is a widely used open dataset for international football
results from 1872 onward.

## Main File Used

`data/raw/results.csv`

This file is the base of the FielCup modelling pipeline. It contains match-level
records with the following fields:

| Column | Meaning |
| --- | --- |
| `date` | Match date |
| `home_team` | Home team name |
| `away_team` | Away team name |
| `home_score` | Full-time home score, including extra time but excluding shootouts |
| `away_score` | Full-time away score, including extra time but excluding shootouts |
| `tournament` | Tournament or competition name |
| `city` | City or local area where the match was played |
| `country` | Country where the match was played |
| `neutral` | Whether the match was played at a neutral venue |

## How FielCup Uses It

The raw result history is loaded into SQLite by `src/database.py`, then queried
by the feature engineering and modelling scripts.

FielCup does not use player-level events from the source dataset. The forecast
is based on:

- final scores
- match dates
- home and away teams
- neutral venue flags
- tournament context
- external 2026 talent reference data in `data/reference/talento_2026.csv`

## Data Notes

- Olympic matches, youth teams, B teams and league-select teams are excluded by
  the upstream dataset.
- Shootout outcomes are not part of `results.csv`; scores are treated as the
  match score before shootout resolution.
- Team names follow the current team naming convention used by the upstream
  dataset.
- FielCup adds a separate 2026 World Cup fixture file and talent reference file
  for forecasting.

## Credit

When reusing this project or the raw match history, credit the upstream dataset:

```text
Data source: martj42/international_results
https://github.com/martj42/international_results
```
