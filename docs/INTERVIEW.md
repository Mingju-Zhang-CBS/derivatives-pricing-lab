# Interview discussion guide

## Two-minute explanation

I implemented the published Black-Scholes-Merton model, analytical sensitivities, terminal Monte Carlo and a self-financing discrete hedge. Development was AI-assisted and all demonstration paths are simulated. The analytical price provides a numerical reference. Antithetic sampling illustrates the difference between path count and independent sample count, while common-path hedging illustrates the competing effects of discretization and transaction costs.

## Questions to be ready to answer

1. **Which measure is used?** Option valuation samples risk-neutral drift r-q. The hedging demonstration generates physical drift .06 while pricing and financing use .03. Under the ideal continuous model, replication does not depend on the physical drift; discrete realized errors can.
2. **What are Greek units?** Delta is per spot unit; gamma is the derivative of delta; vega/rho are per unit decimal volatility/rate. Theta is per year of calendar-time passage, hence minus the maturity derivative. One percentage point requires dividing vega/rho by 100.
3. **How is an antithetic standard error calculated?** Average each discounted payoff pair first. Those pair means are independent observations; estimate their variance and divide by the number of pairs. Merely doubling the path count and assuming independent legs is incorrect.
4. **Why batch the simulation?** Terminal European payoffs do not need full paths or all payoff samples stored. Merge batch means and centered second moments while preserving a correct sample variance.
5. **What happens at expiry or zero volatility?** Prices use intrinsic or deterministic discounted payoff. The Greeks API requires positive maturity and volatility so it does not hide singular boundaries behind arbitrary values.
6. **Describe the hedge cash flow.** Sell the option, buy delta shares and fund the remainder. Accrue cash interest; pay for stock changes and fees at each observed grid time. At maturity liquidate stock and settle the option payoff. Fees also apply at inception and liquidation.
7. **Why use common paths?** Changing rebalancing or costs should not change the underlying terminal stock outcome. A common finest grid makes comparisons more informative and reduces Monte Carlo differences between scenarios.
8. **Why can more hedging lower average P&L?** Finer rebalancing reduces ideal-model discretization error, but fees accumulate with trading. The exact tradeoff depends on the assumed cost and market model.
9. **Which checks are independent?** Put-call parity, a known analytical reference, central differences of prices, deterministic one-step cash accounting, and pair-level variance reconstruction check distinct aspects. Merely rerunning the same formula is insufficient.
10. **What does the speed number mean?** Seven warm runs of a fixed vectorized 10,000-option batch on the recorded environment. It is not an exchange latency, production SLA or cross-machine guarantee.

## Suggested live demonstration

Reconstruct the pair-based Monte Carlo standard error with a short NumPy example. Compare the analytic reference and confidence interval, then inspect the common-path hedge plot. Finish by stating which market risks the constant-volatility diffusion excludes.
