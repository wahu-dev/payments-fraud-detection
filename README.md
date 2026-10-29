# Real-Time Payments Fraud Detection

Detecting fraudulent transfers in a mobile and instant-payments system **before the money moves**,
and deciding which alerts a fraud team should review when it can only check a limited number per day.

![CI](https://github.com/wahu-dev/payments-fraud-detection/actions/workflows/ci.yml/badge.svg)

> **Status: stage 1 of 5 complete.** Data load, leakage audit, time-aware behaviour features in SQL,
> and a rules baseline. Model results will be added as later stages land.

## Business problem

Instant payments (SEPA Instant in the EU, FedNow and Zelle in the US, mobile money in Africa) settle
in seconds and cannot be recalled. The typical fraud is an account takeover: the fraudster empties
the victim's account with a transfer to a **mule account**, then cashes out. A payments provider
must decide in real time which transfers to stop or send for review, with a fraud team that can only
investigate a few hundred alerts a day.

## Data

[PaySim](https://www.kaggle.com/datasets/ealaxi/paysim1): 6.36 million mobile money transactions
over about 31 days (743 hours), simulated from the real logs of an African mobile money service. About 0.13%
are fraud, all of them transfers or cash-outs. The data is not stored in this repo; the pipeline
downloads it.

## Stage 1: data, leakage and the rules baseline

```
PaySim CSV ──► DuckDB ──► SQL features ──► validation ──► leakage audit ──► rules baseline
                          (sql/features)   (fails loudly)  (one column at     (alerts per day,
                                                            a time)            fraud value caught)
```

- **Leakage audit.** PaySim is famous for 0.99+ scores that would never hold in production. They
  come from post-transaction balances, which do not exist when a payment is being decided. The audit
  scores every column on its own and the pipeline excludes those fields, with the reason recorded in
  `config/config.yaml`. Tests fail if they ever reach the model table.
- **Behaviour features in SQL**, using only earlier hours: how many transfers the recipient received
  before and in the last 24 hours, how much money, how long the recipient has been active, whether it
  is new, whether the transfer empties the sender's account.
- **Time-based split:** train on days 1-13, tune on days 14-15, test on days 16-17. Days 18-31 are
  kept as a separate stress test, because normal traffic in the simulator almost stops after day 17
  while fraud continues (see the decision log).
- **Rules baseline:** three readable rules plus the legacy flag in the data, measured as alerts per
  day, recall and **fraud value caught**, also under a 200-alerts-per-day budget.

See the [decision log](docs/decision_log.md) for every choice and what was rejected.

## Roadmap

1. ✅ Data load, leakage audit, SQL behaviour features, time-based split, rules baseline
2. Isolation Forest (unsupervised) vs LightGBM (supervised) vs hybrid, tuned on the validation days
3. Cost-based thresholds: fraud losses vs review costs under a daily alert budget
4. Reason codes for every alert and an error analysis of the fraud that gets through
5. Real-time scoring API, drift monitoring, Docker

## How to run

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
pytest                           # unit tests

python -m src.pipeline --sample  # synthetic sample, a few seconds
python -m src.pipeline           # real data (downloads PaySim with your Kaggle key)
```

## Project structure

```
config/config.yaml        paths, feature list, forbidden columns, split, rules, alert budget
sql/features/             feature logic, one SELECT per file, run in order
src/                      pipeline code (download, load, validate, leakage audit, rules, metrics)
tests/                    unit tests with hand-checked expected values
docs/decision_log.md      decisions and the reasons behind them
```

## Author

**Ann Wahu**, data scientist. [Portfolio](https://wahu-dev.github.io) ·
[LinkedIn](https://www.linkedin.com/in/ann-wahu/) · [GitHub](https://github.com/wahu-dev)
