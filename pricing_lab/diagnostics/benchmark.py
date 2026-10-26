from pathlib import Path
import hashlib
import itertools
import json
import platform

import numpy as np
import pandas as pd
from ..core import price, greeks


def compare_grid():
    import QuantLib as quantlib
    if quantlib.__version__ != '1.44':
        raise ValueError('This benchmark is locked to QuantLib 1.44')
    rows = []
    grid = itertools.product([80., 100., 120.], [80., 100., 120.], [-.01, 0., .05],
                             [.05, .2, .8], [1/365, 30/365, 1., 5.], [0., .03], ['call', 'put'])
    for spot, strike, rate, volatility, maturity, dividend, kind in grid:
        forward = spot * np.exp((rate - dividend) * maturity)
        calculator = quantlib.BlackCalculator(quantlib.PlainVanillaPayoff(quantlib.Option.Call if kind == 'call' else quantlib.Option.Put, strike),
                                             forward, volatility * np.sqrt(maturity), np.exp(-rate * maturity))
        own = dict(price=float(price(spot, strike, rate, volatility, maturity, kind=kind, dividend_yield=dividend)),
                   **{key: float(value) for key, value in greeks(spot, strike, rate, volatility, maturity, kind=kind, dividend_yield=dividend).items()})
        reference = dict(price=calculator.value(), delta=calculator.delta(spot), gamma=calculator.gamma(spot),
                         vega=calculator.vega(maturity), theta=calculator.theta(spot, maturity), rho=calculator.rho(maturity))
        rows.append(dict(spot=spot, strike=strike, rate=rate, volatility=volatility, maturity=maturity, dividend_yield=dividend, kind=kind,
                         **{key + '_error': own[key] - reference[key] for key in own}))
    return pd.DataFrame(rows)


def run(output):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new or empty directory')
    output.mkdir(parents=True, exist_ok=True)
    comparison = compare_grid()
    errors = comparison.filter(like='_error').abs().max()
    if (errors > 1e-8).any():
        raise AssertionError('Numerical benchmark tolerance exceeded')
    comparison.to_csv(output / 'grid.csv', index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(errors.index.str.replace('_error', ''), np.maximum(errors, 1e-16), color='#36B3A8')
    ax.set_yscale('log'); ax.set_ylabel('Maximum absolute difference (native sensitivity units)')
    ax.set_title('Analytical implementation vs QuantLib 1.44')
    fig.tight_layout(); fig.savefig(output / 'quantlib_errors.png', dpi=160); plt.close(fig)
    metrics = dict(cases=len(comparison), reference='QuantLib 1.44 BlackCalculator', max_absolute_errors=errors.to_dict(),
                   data_kind='deterministic-parameter-grid', tolerance=1e-8)
    (output / 'metrics.json').write_text(json.dumps(metrics, indent=2, allow_nan=False), encoding='utf-8')
    report = f'''# Independent numerical comparison

**{len(comparison):,} predetermined European call/put parameter cases**, including negative rates, one-day expiry, low/high volatility and nonzero continuous dividend yield. No market quotes are used here.

![Numerical differences](quantlib_errors.png)

|Quantity|Maximum absolute difference|
|---|---:|
''' + ''.join(f'|{key.replace("_error", "")}|{value:.4g}|\n' for key, value in errors.items()) + '''
## Conventions

The local Black–Scholes–Merton functions are compared with QuantLib's `BlackCalculator`, using F=S*exp((r-q)T), discount=exp(-rT) and standard deviation=sigma*sqrt(T). This avoids accidental calendar/day-count differences. Vega and rho are per unit decimal input; theta is per year. A per-percentage-point vega is this vega divided by 100. The tolerance is 1e-8 in each native unit; relative error is not meaningful when the reference is near zero.

## What this establishes

Agreement checks one implementation against a mature, separately authored library. It does not establish that lognormal volatility, constant rates, continuous dividends or a synchronized forward describe a real quoted contract. The quote study separately measures distances from bid/ask intervals. Terminal and zero-volatility boundaries remain covered by the original unit tests.

Run `python -m pricing_lab.diagnostics --benchmark --output local-runs/quantlib` after `pip install ".[test,benchmark]"`. QuantLib is BSD-3-Clause licensed; its authorship and license remain with its maintainers. No upstream contribution is claimed. [Source and license](https://www.quantlib.org/license.shtml).
'''
    (output / 'REPORT.md').write_text(report, encoding='utf-8')
    sources = [Path(__file__), Path(__file__).parents[1] / 'core.py']
    manifest = dict(python=platform.python_version(), source_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources},
                    outputs_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir()})
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return metrics
