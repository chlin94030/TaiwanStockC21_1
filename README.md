# Alpha Radar V21.1 - Universe and Factor Research Lab (debugged startup / progress)

V21.1 primarily fixes invisible worker startup, error propagation and quota/progress diagnostics. The financial model, candidate registry and holdout rules are unchanged. See `V21_1_DEBUG_GUIDE.md`.

This is a **standalone research app**, not a patch to V20.3.1 and not an approved trading model. It compares trailing traded-value Top 100/200/300/500 universes and selects factor weights using past training data. Each selected configuration is evaluated on later chronological blocks and a final 24-month tail. No profitability or global optimum has been established.

## Install without disturbing the old application

Create a NEW repository/app for these files. Put `app.py` and the other Python files at the repository root. Use Python 3.11 or 3.12. Choose `app.py` as the Streamlit entry point. Do not overwrite or delete the old V20 application or its `data/` folder.

For a local installation:

```sh
python -m venv .venv
# Activate .venv using your operating system's normal command.
python -m pip install -r requirements.txt
streamlit run app.py
```

The app's data is stored in `data/v21_universe_lab/`. Keep that directory out of Git. An initial whole-market collection can take HOURS. A local computer or persistent worker is preferable for that initial collection; a hosted service may sleep, restart or erase temporary files. This code does not guarantee continuous operation on a sleeping Cloud host.

## Default: one-click collection and research

Select the current-official-roster data mode, then press the blue start/resume button once. The stages run automatically:

1. Freeze the complete current TWSE and TPEx official company masters.
2. Obtain the market trading calendar and actual raw daily prices, share volume and **Trading_money** for each security from FinMind.
3. Build all historical month-end turnover-ranked universes from the previous 252 MARKET sessions. No random 150-stock approximation is used.
4. Obtain adjusted OHLC via Yahoo/yfinance only for the UNION of all historical monthly selected names, plus 0050. That union can exceed 500 stocks even though each individual Top-500 pool contains 500 names.
5. Calculate each feature and outcome once; evaluate the registered finite profile set across all pools on the same dates.
6. Run purged chronological model selection, outer tests, freeze each horizon's final model, and evaluate it once on the final tail.
7. Save human-readable TXT, detailed JSON/CSV, selected weights and a CRC-checked small ZIP. An unfavorable verdict does not start another test.

FinMind documents 300 requests/hour without a token and 600/hour with a verified registered token. The code deliberately paces lower (260/520). An optional `FINMIND_TOKEN` can be supplied as an environment variable or Streamlit secret. Do NOT paste it into Git, a report, or this README. No sponsor-only bulk, adjusted-price or broker-branch endpoint is called. Entitlements, service availability and data licenses remain the provider's decision.

The adjusted-price source is independent of the raw amount source. Missing adjusted prices are not replaced with raw returns. If a source or data check blocks the job, progress and cached downloads are retained; the app does not fabricate a result or silently shrink a Top-500 test to 150 stocks.

## Essential scope distinction

Default automatic mode is **CURRENT_SNAPSHOT_DIAGNOSTIC**: the whole current official roster is used, but delisted historical names and historical changes of listing board have NOT been reconstructed. It is therefore not a survivorship-free historical Taiwan equity universe. Missing amount history can exclude a security according to the fixed data-eligibility rule; the original roster is retained. Source snapshots, eligible counts and limitations are exported.

For historical membership, historical market-cap comparisons, or revenue/EPS/institutional factors, use the normalized import mode described in `DATA_CONTRACT.md`. The importer enforces timestamps and required columns but cannot independently certify your data vendor's completeness or vintage accuracy.

A previous `v19_results.json` or 150-stock validation report is NOT price input and cannot establish full-market annual turnover ranks. The supplied prior report has not been converted into fake Top-500 data.

## What is optimized

The default registry contains 64 deterministic sparse profiles, including the old 80/20 baseline and single-factor controls. The directions and profile budget are fixed before evaluation. Pool size and factor weights are selected JOINTLY inside training for each 5/20/60-session horizon; the outer or final-test result does not select its own winner.

Training objective: matched net excess over 0050, penalized for extra transaction-cost stress, variation across three chronological training blocks, and unnecessary factor count. Missing selected outcomes receive a separately labelled worst-case slot-loss sensitivity during selection, NOT an invented observed return. A near-best simpler profile is preferred according to a fixed tolerance. See `PROTOCOL.md` for exact rules.

The winner is the **best within this finite registered search by the stated training objective**, not an exhaustive global optimum. There can be a best-ranked candidate with NO demonstrated advantage. The exported `selected_models.json` always has `production_approved=false` and does not authorize orders.

## Avoid repeating the previous overfitting cycle

Completed jobs with identical resolved configuration, code and import input do not rerun. The final tail is not used to retune. An explicit new end date or changed configuration creates a different experiment; doing so repeatedly until a favorable result appears is not independent validation. The default `exposed_through=2026-10-20` explicitly flags overlap with the previously studied era. No result claims an independent future blind test.

Changing the pool changes the question, but does not make old market outcomes unseen again. Do not lower coverage, costs or pass thresholds after looking at a failed final tail.

## Reading the result

`REPORT.txt` is the easiest output. `results.json` contains the audit trail. `selected_models.json` reports each training-selected pool and weights without approving deployment. Development candidate tables are TRAINING-ONLY; there is intentionally no competing-candidate final-tail leaderboard.

Interpret separately:

- pool equal-weight versus 0050: whether the chosen population itself differs favorably from the index;
- model versus the SAME pool: whether stock ranking adds value;
- selected model net versus 0050: the investment opportunity-cost comparison;
- outer versus final-tail results: whether selection survived later evaluation;
- known-case coverage, non-overlap counts, block intervals and cost stress: whether positive means are credible enough even as historical evidence.

`HISTORICAL_SUPPORT_ONLY`, `NOT_SUPPORTED` and `INSUFFICIENT_EVIDENCE` are research verdicts. These monthly holding-window studies are not a continuous capital-constrained daily NAV backtest, and do not validate intraday fills, stops, limit-up trading or production buy recommendations.

## Pause, resume and download

Pause is checked between bounded tasks and during quota waits. Completed downloads and imported SQL chunks remain. A fully saved feature checkpoint is hash-checked before reuse. If interrupted partway through feature generation, that phase may be recomputed from cached prices. Nested calculations can also be recomputed deterministically; they never require manual S/A/B stage promotion.

After a process restart, resume requires the application to run again and its files still to exist. Session State alone is not used as the durable job record. Download buttons read completed files and do not restart a study. Large raw histories are NOT embedded in the small result ZIP or exposed by the download buttons. Keep source data private and obey provider terms.

## Command-line and tests

```sh
# Automatic mode; reads config.json, supports FINMIND_TOKEN in the environment.
python run_lab.py --config config.json

# Set source_mode="import" in an import_config.json first.
python run_lab.py --config import_config.json --input-dir /path/to/dataset --root data/v21_import_lab

python -m pip install -r requirements-dev.txt
python -m pytest -q test_lab.py
```

To exercise code WITHOUT requesting real market data:

```sh
python demo_data.py --out demo_input
python run_lab.py --config demo_input/demo_config.json --input-dir demo_input --root demo_run
```

That demonstration deliberately uses smaller pools and synthetic prices. Its output is always labelled `SYNTHETIC_ENGINE_TEST_NOT_PERFORMANCE`; do not report its selected weights or returns as a stock strategy.

See `QA_STATUS.md` for what was actually tested and what remains unverified.
