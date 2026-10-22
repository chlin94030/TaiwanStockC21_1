# V21 finite universe / factor selection protocol

## Experiment identity

This new authorized universe study is distinct from the closed V20 C1/C2 experiment. It does not relabel, resume or overwrite those outcomes. Before fetching or evaluating data it records configuration, actual registration time, candidate definitions, code hash and imported input hash. Identical completed jobs do not restart. Explicitly changing settings/end-date produces a different experiment and must not be presented as another independent proof merely because its ID changed.

## Universe and feature time

For each full month end T with a mature 60-session exit, calculate actual daily traded-value average over the previous252 MARKET sessions inclusive of T. Require all252 amount observations, recent20 amount >=TWD5m and at least95% active observed days in the last60 sessions. Rank eligible securities and declare nested Top100/200/300/500 lists. Next-session open is the assumed entry. Do not use calendar-year totals that include later months.

Every requested pool is evaluated on the SAME calendar. Fewer than500 eligible amount histories on a required date stops the default study; it does not become a hidden smaller universe. Current official roster mode preserves current-snapshot/survivorship limitations. Historical import is a separate declared scope.

Factor percentile reference is the same-date UNION of all preregistered pools (normally Top500). Do not re-rank percentiles separately inside Top100,200,300,500. Source adjusted OHLC is used coherently for technical ratios; actual raw amount and shares remain independent of adjusted-price scaling.

The14 predefined factor directions are: liquidity20, high252, momentum20, momentum60, momentum120_skip20, signed trend_eff60, downside60 resilience, reversal5, volume_impulse, money_flow20, breakout20, pullback20, rsi_recovery and macd_acceleration. Optional imported PIT factors add4 more without pretending missing fields are usable.

## Finite model family

Default64 profiles are registered before outcome comparison. They include the prior liquidity80/high20 control, single-factor controls, predefined diverse mixtures and seeded sparse mixtures. Generated weights are positive in tenth increments, use at most4 factors and sum to1. Single-factor controls can have100% on one feature; generated multi-factor candidates cap an individual weight at70%. The registry is not every possible factor interaction or a global numerical optimization.

With4 universes,64 profiles and3 horizons there are768 universe/profile/horizon configurations. That number is a computational search count, NOT768 independent trials. Optional cap pools increase the declared family; optional factors alter the registered profiles and require a new experiment ID.

## What inner selection does

There are no other fitted prediction coefficients: the weight vector and pool are the hyperparameters. Before each outer block, only earlier signal dates whose full holding-period label EXIT is strictly earlier than the test boundary minus5 market sessions are eligible. This excludes overlapping future labels, not just overlapping exact cutoff dates.

Eligible historical candidate outcomes are assessed over3 contiguous chronological training-selection blocks. The objective is:

```
mean_excess_vs_0050_using_explicit_missing_slot_loss_sensitivity
- extra_roundtrip_cost * mean_filled_capital_weight
- 0.5 * stdev(three_block_means)
- 0.0005 * (active_factor_count - 1)
```

Every candidate needs95% matched observed-date coverage. Unknown selected outcomes are NOT filled with zero: an explicitly separate loss-floor sensitivity charges up to100% loss of the unknown funded slot in the selection objective. Observed performance remains unknown. This conservative sensitivity is not an estimate of what the missing stock actually returned.

Profiles within0.001 of the best objective use a deterministic simpler-first tie rule. More complicated profiles are not adopted for negligible training improvement. Pool and profile are selected jointly INSIDE this process, never from outer/holdout performance.

## Outer and final evaluation

Defaults: at least24 eligible training-selection months, expanding training,6-month chronological outer blocks, at least3 evaluated outer blocks. The longest label horizon requires additional maturity distance, so horizon fold counts can differ. Test dates remain identical across all pools within a horizon.

Reserve the last24 mature monthly signal dates as a final tail. Pick ONE final configuration per horizon using only purged dates before that tail. Save its final-freeze file BEFORE producing its final-tail records. Report only that frozen model on the tail. Do not rank competing profiles on that tail or refit after seeing its verdict. Outer evaluations measure the historical performance of the selection procedure, not the exact same final weights in every earlier fold.

The old exposed era is explicitly retained as exposed: the default `exposed_through=2026-10-20` warns when the tail overlaps it. The code never calls a historical tail a proved independent future holdout. Chronological separation controls within-run leakage, not the user's or designer's prior exposure to the market era.

## Outcomes and controls

Each model fixes5 funded slots at T with a T-only capacity rule; fewer selected positions leave cash. Next open above a declared4% gap is a known stock no-fill cash slot. Missing entry/exit information is unknown, not cash and not an ex-post0050 substitution. A suspended/zero-volume benchmark return is missing, not0%. Stock cash/no-fill and unknown exit are different states.

Observed net returns use configured fees, tax and slippage (illustrative test parameters, not brokerage advice), and additionally report a50bp stock round-trip stress. Unknown selected slots cannot be discarded to inflate the remaining-stock average. The full same-pool equal-weight control retains its planned denominator and unknown constituents; consequently comparison coverage may be insufficient.

This experiment does NOT automatically route to cash or0050 based on the former market regime gate. That changes the selection question intentionally: test the universe and ranking without making a failed market-timing policy select the answer.0050 remains the reference investment and uses its separate configured tax.

Report three separate effects: pool-versus0050, selected model-versusits pool, selected model-versus0050. Same-pool baselines and fixed80/20 controls use the pre-holdout development data in the universe control table. Single-factor IC and chosen-factor removal are training diagnostics only, not causal claims or proof of future explanatory power.

## Acceptance (does not mean best live model)

For BOTH final-tail excess-vs0050 and excess-vsown-pool endpoints require >=95% known-date coverage and >=6 usable globally non-overlapping cases. Then require mean excess >=0.002, positive moving-block95% lower and positive non-overlap95% lower. Additional cost stress must remain positive. Outer OOS coverage must also be>=95%, and its mean excess and extra-cost stress must be positive.

The block resampling uses4 consecutive monthly observations; IID95% intervals are also reported, but are not the primary support rule. Non-overlap dates are selected chronologically before examining missing results. These intervals are descriptive, not familywise/multiple-testing-adjusted significance or proof of independence.

Possible final verdicts: HISTORICAL_SUPPORT_ONLY, NOT_SUPPORTED, INSUFFICIENT_EVIDENCE. Synthetic input always overrides the financial verdict to SYNTHETIC_ENGINE_TEST_NOT_PERFORMANCE. None grants automatic orders or production approval. The0.2-point acceptance floor is perholding window, NOT an annual target or a promise of the user's desired performance leap.

## Explicit exclusions

No continuous daily capital-constrained NAV, no exact daily portfolio MDD, no real intraday/limit-price fill simulation, no actual brokerage execution, no independently verified historical corporate-action vintages, and no automatic reconstruction of historical listings or financial revisions. Endpoint closed-trade/non-overlap curve summaries must not be described as a full daily portfolio backtest.

Nothing automatically adds more seeds, searches after a failed final tail, or lowers a gate to obtain a pass.
