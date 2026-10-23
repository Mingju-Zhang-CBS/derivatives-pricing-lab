# Pricing and hedging experiment

All results use simulated GBM paths and fixed parameters. One-year ATM call: S=K=100, r=3%, volatility=20%, no dividends. No market data or execution record is used.

- Analytical call price: **9.413403**.
- 200,000 plain terminal paths: estimate 9.428070, standard error 0.031761.
- 200,000 antithetic terminal paths: estimate 9.437465, standard error 0.023705. The independent sampling units are pairs.
- Daily hedge at 5 bps stock trading cost: mean P&L -0.315624, standard deviation 0.457004 per short option.
- Fixed 10,000-option vectorized batch: median 0.570 ms over seven warm runs. This is a local batch benchmark, not exchange order latency.

![Monte Carlo convergence](mc_convergence.png)

![Hedging tradeoff](hedging_tradeoff.png)

## Interpretation

The analytical solution is a numerical reference under the assumed model. Antithetic draws can reduce sampling error; their standard error must be computed from pair means. More frequent frictionless hedging reduces discretization risk in this experiment. Trading costs create a competing effect and lower the mean short-option hedge P&L.

## Limits and reproduction

The stock follows exactly the assumed diffusion, with constant volatility and no dividends in the hedging experiment. There are no jumps, stochastic volatility, bid/ask quotes, financing spreads or margin constraints. A single fixed seed is illustrative. Confidence intervals are asymptotic normal sampling intervals, not guarantees that an individual run contains the analytical value. See `manifest.json` for configuration, source hashes and environment; `metrics.json` records sampled process memory and timing.
