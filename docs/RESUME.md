# Resume drafts and evidence

Use after reviewing the code, reproducing the study and being able to explain it. Development was AI-assisted. These drafts describe the new portfolio implementation, not an employer assignment, actual market performance or original invention of the method. Counts and numerical statements below refer to the checked-in run; refresh them if the report changes.

## Two English bullets

- Implemented vectorized Black-Scholes-Merton prices and analytical Greeks, validating numerical identities and sensitivities against finite differences and comparing plain and antithetic Monte Carlo estimates with up to 200,000 simulated terminal paths.
- Benchmarked 10,000-option pricing batches at a median 0.570 ms over seven warm runs in the recorded Python environment, and evaluated nine rebalancing/cost configurations on 6,000 common simulated stock paths to quantify discrete hedge error and transaction-cost tradeoffs.

## Evidence and restrictions

- Measured batch workload and environment: [metrics](../reports/demo/metrics.json), [manifest](../reports/demo/manifest.json).
- Simulation counts, uncertainty and hedge outcomes: [MC table](../reports/demo/monte_carlo.csv), [hedge table](../reports/demo/hedging.csv), [report](../reports/demo/REPORT.md).
- Speed is machine-specific. It is neither order latency nor an improvement over an unmeasured implementation. Simulated hedging P&L is not actual option trading performance.
- Relevant tests: parity, boundary inputs, finite-difference Greeks, independent pair-variance reconstruction and one-step hedge accounting.
