# Mathematics, interfaces and measurement

`price(S,K,r,sigma,T,kind='call',dividend_yield=q)` supports broadcast NumPy inputs. Parameters are finite; S,K>0 and sigma,T>=0. Rates and dividend yields are continuous annual decimals. For T>0 and sigma>0:

`d1 = [log(S/K) + (r-q+sigma^2/2)*T] / (sigma*sqrt(T))`

`d2 = d1-sigma*sqrt(T)`

`C = S*exp(-q*T)*N(d1) - K*exp(-r*T)*N(d2)`

`P = C - S*exp(-q*T) + K*exp(-r*T)`.

At zero maturity the intrinsic payoff is returned; at zero volatility the deterministic discounted payoff is returned. Negative finite interest rates are allowed. Numerical underflow/overflow from extreme but finite financial parameters is not an intended operating regime.

`greeks(...)` returns delta, gamma, vega, theta and rho for **strictly positive** volatility and maturity. Vega is per unit absolute decimal volatility, rho per unit absolute decimal interest rate, theta per year of calendar-time passage. Divide vega and rho by 100 for a one-percentage-point input change; divide theta by the chosen annual day count for a daily convention. Expiry/zero-vol sensitivities are deliberately rejected rather than assigning an arbitrary value at a payoff kink.

`monte_carlo(...)` accepts scalar inputs and returns estimate, standard error, normal 95% interval, terminal path count and independent observation count. Under the risk-neutral measure, terminal S is `S0*exp((r-q-sigma^2/2)*T + sigma*sqrt(T)*Z)`. The payoff is discounted by exp(-r*T). Antithetic sampling uses Z and -Z, so each **pair mean** is one independent observation. Treating both legs as independent understates/overstates uncertainty depending on their covariance. Batch means and centered second moments are merged online. The normal interval is approximate and is not a test that every seed must contain the analytical price.

`gbm_paths(...)` uses exact GBM log increments. The demonstration uses physical drift .06 with pricing/financing rate .03, volatility .20, S0=K=100, maturity one year and seed 42. `hedge_pnl(paths,...)` sells one option at its model price, buys delta stock and funds the difference in a cash account. The hedging experiment has zero dividend yield. Each trade, including initial acquisition and terminal liquidation, pays absolute stock notional times the cost rate. Cash accrues at r between observations. At each nonterminal observation the new delta uses only that observation's stock price and remaining maturity. Terminal option payoff is settled after stock liquidation.

The finest grid contains 252 intervals; coarse grids use 12 or 63 observations by subsampling the same paths. Thus terminal prices and underlying randomness are common across cost/frequency comparisons. No jump, transaction impact, margin, stochastic volatility or discrete-dividend risk is modeled.

The demo reports MC error and standard error, hedge mean/std/left-tail P&L, and local resource use. The vectorized benchmark prices 10,000 options after a warmup and takes the median of seven timings. Wall time is machine-specific, includes Python dispatch, and is **not** order-routing latency. Process RSS is sampled every 10ms and can miss shorter peaks.

Reference: Black and Scholes (1973), [The Pricing of Options and Corporate Liabilities](https://doi.org/10.1086/260062); [Nobel Prize's account of the option-pricing method](https://www.nobelprize.org/prizes/economic-sciences/1997/press-release/). Equations, numerical assumptions and tests are explicitly provided here; no classroom implementation was used as source.
