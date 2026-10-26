# SPX: formulas, conventions and observed intervals

**Question:** How far do fixed historical-volatility marks fall from closing option quote intervals, and which discrepancies can be explained by conventions?

Three distinct experiments answer different questions:

|Experiment|Evidence|What it establishes|
|---|---|---|
|[QuantLib 1.44 comparison](../reports/quantlib/REPORT.md)|Deterministic parameter grid|Agreement of separately authored pricing and Greek implementations|
|[Synthetic quote fixture](../reports/quote-fixture/REPORT.md)|Generated underlying, rates, forwards and intervals|Executable joins, units, slices and report production|
|Licensed SPX workflow|Institutional OptionMetrics inputs; detailed results private|Historical quote diagnostics conditional on documented input conventions|

## Fixed study

SECID 108105, years 2020–2024, European exercise, PM settlement, standard 100-multiplier contracts, 14–180 calendar days to expiry and strike/forward 0.8–1.2. The [protocol](../pricing_lab/diagnostics/protocol.json) fixes 2020–2022 development, 2023 review and 2024 historical confirmation. Both 20- and 60-session volatility marks are always reported; the study does not select a winner using confirmation.

### Units and joins

OptionMetrics strike is stored times 1,000. Quotes remain SPX index points; contract dollars equal points times 100, as specified by [Cboe](https://www.cboe.com/tradable-products/sp-500/spx-options/spx-specifications). They do not enter the Defined Outcome project's ETF-per-share quote schema.

The historical embedded forward field can be empty. The independent Forward Price table is matched on security, observation date, expiration and AM/PM flag. Curves match the observation date, with continuous zero rates linearly interpolated between maturity nodes. No extrapolation or future curve fills are used. Rate percent-to-decimal scaling is recorded in the input unit contract and cross-checked, with remaining source uncertainty stated rather than hidden.

### Valuation example

For F=4,500, K=4,500, annual volatility 20%, continuous rate 3% and T=60/365, use `discount * [F*N(d1) - K*N(d2)]` for a call, with `d1=log(F/K)/(sigma*sqrt(T))+sigma*sqrt(T)/2`. The same forward/discount convention is checked against the independent numerical benchmark.

A model value of 101 inside bid=100, ask=102 has zero outside-interval distance even though its midpoint error may differ. A value of 104 has distance two index points, or $200 per standard contract. Neither quantity is an available arbitrage profit.

### Timing and interpretation

Historical volatility uses sample log-return standard deviation ending the previous observed session, annualized with sqrt(252). The current quote-date forward and curve are contemporaneous valuation inputs, not a next-day forecast. The inspected vendor v5 manual documents 15:59 ET historical option observations after July 2009 and underlying closing prices; observations must not be silently described as synchronized. Our calendar-day ACT/365 maturity also omits exact expiration hours and vendor-specific day handling.

Vendor IV is inverted from option prices. Rebuilding a price from it is therefore a circular consistency check, not an independent prediction result. Rate, dividend and forward construction can change across vendor versions. The code consumes the supplied curve and does not extend an old LIBOR methodology into periods where it has not been verified.

The report saves ordered exclusions, all year/call-put/tenor slices, coverage, spreads, interval containment and outside distance. Empty slices remain visible. Closing bid/ask does not establish depth, queue position or fill probability, and cannot calibrate the market-making lab's intraday customer demand.

## Reproduce

```bash
pip install ".[test,benchmark,research]"
python -m pricing_lab.diagnostics --benchmark --output local-runs/quantlib
python -m pricing_lab.diagnostics --fixture --output local-runs/quote-fixture
python -m pricing_lab.diagnostics --quotes private-data/options --output local-runs/licensed-options
```

The real input directory contains four independently acquired tables plus `unit_contract.json` and `source.json`. Raw and derived licensed outputs remain private pending applicable publication rights. Public fixtures are explicitly generated. The original pricing, simulation and hedging API remains available.

[Tests](../tests/test_quote_diagnostics.py) · [QuantLib license](https://www.quantlib.org/license.shtml) · [WRDS data policy](https://wrds-www.wharton.upenn.edu/pages/about/data-download-and-analysis-policy/) · [Main study](../README.md)
