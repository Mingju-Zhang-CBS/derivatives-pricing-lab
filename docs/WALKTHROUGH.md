# Walkthrough: price, uncertainty and a self-financing hedge

## 1. Declare a complete model

The reference option has spot and strike 100, one year to maturity, continuous interest rate 3%, volatility 20% and zero dividends. Rates and volatility are decimal annual inputs. The model gives a call price of 9.413403 and put price of 6.457957.

Put-call parity checks the economic relation `C - P = S - K*exp(-r*T)`. Finite-difference checks compare how prices actually change with analytical delta, gamma, vega, theta and rho. Those checks address different failure modes from simply rerunning the price formula.

## 2. Keep Greek units explicit

The call delta is approximately 0.598706. Vega is approximately 38.666812 per unit decimal volatility, so a one-percentage-point volatility change has first-order price effect approximately 0.386668. Rho is approximately 50.457229 per unit interest-rate change, or 0.504572 per percentage point. Theta is approximately -5.380398 per year of calendar-time passage.

Greeks are local derivatives, not exact finite-shock prices. The interface rejects expiry/zero-volatility sensitivities rather than assigning a convenient value at a singular payoff boundary. Prices still handle those limiting cases.

## 3. Count independent Monte Carlo observations

Plain simulation samples 200,000 independent terminal normals. Antithetic simulation also evaluates 200,000 terminal paths, but pairs Z with -Z and therefore produces 100,000 independent pair observations.

For each pair, first average the two discounted payoffs. Estimate the sample variance of those averages and divide by the number of pairs to obtain the variance of the estimator. Treating correlated legs as independent would use the wrong uncertainty calculation.

The example's antithetic standard error is about 0.023705, versus 0.031761 for plain sampling at the same path count: a 25.4% reduction. Its absolute realized error is nevertheless larger for this seed. Variance reduction is a statement about the sampling distribution, not a guarantee that every individual estimate improves.

## 4. Fund the short-option hedge

Selling one call receives 9.413403. Buying 0.598706 shares at 100 costs 59.870633. Initial hedge cash is therefore approximately -50.457229 before trading costs: financing the stock requires borrowing within this idealized hedge account.

This differs from the long-only strategy project's no-overdraft policy. The two models solve different problems and disclose different financing assumptions. In this hedge model, positive or negative cash accrues at the same rate.

For a hypothetical one-step path from 100 to 110, with no trading costs:

```text
Initial cash = option premium - initial delta * initial stock
Final cash   = initial cash * exp(r*T)
Hedge P&L    = final cash + initial delta * terminal stock - call payoff
```

There is only one hedge step, so the residual is discretization error for this hypothetical path. It is not a replication guarantee or expected trading profit. The runnable example reconstructs this cash flow independently and compares it with the engine:

```text
python examples/explain_pricing.py
```

## 5. Rebalance on common paths and settle all costs

The full demonstration uses 6,000 exact-GBM stock paths on a finest grid of 252 intervals. Coarser 12- and 63-rebalance grids subsample the same paths. Thus comparisons share the underlying terminal outcomes.

At every nonterminal rebalance, the hedge buys or sells the change in delta, debits stock notional and pays proportional fees. Cash accrues between observations. At maturity it liquidates the stock position, pays liquidation fees and settles the option payoff. Initial acquisition also incurs a fee.

Frictionless hedge P&L standard deviation falls from about 1.9222 at 12 rebalances to 0.4430 at 252. At 5 bps, mean P&L becomes more negative as trading frequency rises. These results illustrate a risk/cost tradeoff conditional on the assumed model and paths.

## 6. Interpret the benchmark narrowly

The vectorized timing prices 10,000 options after warmup and takes a median over seven runs. It records Python, platform, library versions and sampled process RSS. It does not measure an exchange connection, order routing, concurrent production traffic or guaranteed tail latency.

Inspect [the MC table](../reports/demo/monte_carlo.csv), [the hedge table](../reports/demo/hedging.csv), [the source](../pricing_lab/core.py), [METHODS](METHODS.md) and [the tests](../tests/test_pricing.py). Market-model risk remains even when numerical checks pass.
