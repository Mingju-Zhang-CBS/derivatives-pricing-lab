from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.special import ndtr


def black_forward(forward, strike, rate, volatility, maturity, call):
    forward, strike, rate, volatility, maturity, call = np.broadcast_arrays(forward, strike, rate, volatility, maturity, call)
    if not all(np.isfinite(value).all() for value in [forward, strike, rate, volatility, maturity]) or (forward <= 0).any() or (strike <= 0).any() or (volatility < 0).any() or (maturity <= 0).any():
        raise ValueError('Verified positive forward, strike, maturity and nonnegative volatility required')
    deviation = volatility * np.sqrt(maturity)
    active = deviation > 0
    first = np.log(forward / strike) / np.where(active, deviation, 1.) + deviation / 2
    second = first - deviation
    sign = np.where(call, 1., -1.)
    result = np.exp(-rate * maturity) * sign * (forward * ndtr(sign * first) - strike * ndtr(sign * second))
    boundary = np.exp(-rate * maturity) * np.maximum(sign * (forward - strike), 0.)
    return np.where(active, result, boundary)


def interval_distance(values, bid, ask):
    return np.maximum(np.maximum(np.asarray(bid) - values, values - np.asarray(ask)), 0.)


def lagged_volatility(spot):
    if spot.date.duplicated().any() or not spot.date.is_monotonic_increasing or not spot.close.gt(0).all():
        raise ValueError('Unique ordered positive underlying observations required')
    result = spot[['date', 'close']].copy()
    returns = np.log(result.close).diff()
    for window in [20, 60]:
        result[f'hv_{window}'] = returns.rolling(window, min_periods=window).std(ddof=1).shift(1) * np.sqrt(252)
    return result


def normalize(options, forwards, volatility, curves):
    options = options.copy()
    options['strike'] = options.strike_price / 1000
    options['days'] = (options.exdate - options.date).dt.days
    options = options.merge(forwards.rename(columns={'expiration': 'exdate', 'amsettlement': 'am_settlement'}),
                            on=['secid', 'date', 'exdate', 'am_settlement'], how='left', validate='many_to_one')
    options = options.merge(volatility, on='date', how='left', validate='many_to_one')
    options['rate'] = np.nan
    for date, indices in options.groupby('date').groups.items():
        nodes = curves.get(date)
        if nodes is None:
            continue
        maturities = options.loc[indices, 'days']
        inside = maturities.between(nodes.days.min(), nodes.days.max())
        options.loc[indices[inside], 'rate'] = np.interp(maturities[inside], nodes.days, nodes.rate / 100)
    conditions = {
        'wrong_security': options.secid.ne(108105),
        'exercise_or_settlement': ~options.exercise_style.eq('E') | ~options.am_settlement.eq(0) | ~options.ss_flag.astype(str).isin(['0', '0.0']),
        'contract_size': ~options.contract_size.eq(100),
        'days_to_expiry': ~options.days.between(14, 180),
        'missing_forward': ~options.forwardprice.gt(0),
        'moneyness': ~(options.strike / options.forwardprice).between(.8, 1.2),
        'invalid_quote': ~np.isfinite(options.best_bid) | ~np.isfinite(options.best_offer) | options.best_bid.lt(0) | options.best_offer.le(0) | options.best_bid.gt(options.best_offer),
        'curve_or_history': options[['rate', 'hv_20', 'hv_60']].isna().any(axis=1),
    }
    exclusion = {}
    keep = pd.Series(True, index=options.index)
    for reason, rejected in conditions.items():
        exclusion[reason] = int((keep & rejected).sum())
        keep &= ~rejected
    cleaned = options[keep].copy()
    if not cleaned.rate.between(-.1, .5).all():
        raise ValueError('Zero-rate units outside the verified decimal contract')
    return cleaned, exclusion


def evaluate(frame):
    frame = frame.copy()
    frame['year'] = frame.date.dt.year
    frame['tenor'] = pd.cut(frame.days, [13, 30, 90, 180], labels=['14-30', '31-90', '91-180'])
    for model, volatility in [('hv20', frame.hv_20), ('hv60', frame.hv_60), ('vendor_iv_consistency', frame.impl_volatility)]:
        eligible = np.isfinite(volatility) & volatility.gt(0)
        values = np.full(len(frame), np.nan)
        values[eligible] = black_forward(frame.forwardprice[eligible], frame.strike[eligible], frame.rate[eligible], volatility[eligible], frame.days[eligible] / 365, frame.cp_flag[eligible].eq('C'))
        frame[model] = values
        frame[model + '_distance'] = interval_distance(values, frame.best_bid, frame.best_offer)
        frame[model + '_inside'] = np.where(eligible, frame[model + '_distance'].eq(0).astype(float), np.nan)
    frame['relative_spread'] = (frame.best_offer - frame.best_bid) / ((frame.best_offer + frame.best_bid) / 2)
    return frame


def run(input_directory, output):
    input_directory, output = Path(input_directory), Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use an empty output directory')
    output.mkdir(parents=True, exist_ok=True)
    unit_contract = json.loads((input_directory / 'unit_contract.json').read_text())
    if unit_contract.get('strike_divisor') != 1000 or unit_contract.get('curve_rate_divisor') != 100 or unit_contract.get('premium_unit') != 'SPX_index_points' or not unit_contract.get('unit_sources_verified'):
        raise ValueError('Verified source unit contract required; no guessed units')
    source = json.loads((input_directory / 'source.json').read_text())
    protocol = Path(__file__).with_name('protocol.json')
    (output / 'protocol.json').write_bytes(protocol.read_bytes())
    forwards = pd.read_csv(input_directory / 'spx_forwards.csv.gz', parse_dates=['date', 'expiration'])
    forwards.columns = forwards.columns.str.lower()
    spot = pd.read_csv(input_directory / 'spx_spot.csv', parse_dates=['date']).sort_values('date')
    curve = pd.read_csv(input_directory / 'zero_curve.csv.gz', parse_dates=['date'])
    if forwards.duplicated(['secid', 'date', 'expiration', 'amsettlement']).any() or curve.duplicated(['date', 'days']).any():
        raise ValueError('Conflicting forward or curve keys; quarantine rather than choose latest')
    volatility = lagged_volatility(spot)
    curves = {date: group.sort_values('days') for date, group in curve.groupby('date')}
    exclusions, frames, total = {}, [], 0
    seen = set()
    for chunk in pd.read_csv(input_directory / 'spx_options.csv.gz', chunksize=200000, parse_dates=['date', 'exdate'], low_memory=False):
        total += len(chunk)
        cleaned, counts = normalize(chunk, forwards, volatility, curves)
        for reason, count in counts.items():
            exclusions[reason] = exclusions.get(reason, 0) + count
        if len(cleaned):
            keys = list(zip(cleaned.date.astype(str), cleaned.optionid))
            if len(set(keys)) != len(keys) or seen.intersection(keys):
                raise ValueError('Duplicate option/date result keys')
            seen.update(keys)
            frames.append(evaluate(cleaned)[['date', 'year', 'tenor', 'cp_flag', 'relative_spread', 'optionid', 'best_bid', 'best_offer', 'hv20', 'hv60', 'vendor_iv_consistency',
                                             'hv20_distance', 'hv60_distance', 'vendor_iv_consistency_distance', 'hv20_inside', 'hv60_inside', 'vendor_iv_consistency_inside']])
        print(json.dumps({'input_rows_processed': total, 'eligible_rows': sum(len(frame) for frame in frames)}), flush=True)
    if not frames:
        raise ValueError('No eligible quote records')
    result = pd.concat(frames, ignore_index=True)
    result.to_parquet(output / 'private_contract_results.parquet', index=False)
    summaries = []
    for year in range(2020, 2025):
        for kind in ['C', 'P']:
            for tenor in ['14-30', '31-90', '91-180']:
                group = result[(result.year == year) & (result.cp_flag == kind) & (result.tenor == tenor)]
                for model in ['hv20', 'hv60', 'vendor_iv_consistency']:
                    summaries.append(dict(year=year, kind=kind, tenor=tenor, model=model, quotes=len(group), evaluable=int(group[model].notna().sum()),
                                          inside_fraction=float(group[model + '_inside'].mean()) if group[model].notna().any() else None,
                                          mean_outside_distance=float(group[model + '_distance'].mean()) if group[model].notna().any() else None))
    summary = pd.DataFrame(summaries)
    summary.to_csv(output / 'slices.csv', index=False)
    pd.DataFrame([dict(reason=key, excluded=value) for key, value in exclusions.items()]).to_csv(output / 'exclusions.csv', index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for model, color in zip(['hv20', 'hv60', 'vendor_iv_consistency'], ['#234e70', '#36B3A8', '#b37743']):
        grouped = result.groupby('year')[[model + '_inside', model + '_distance']].mean()
        axes[0].plot(grouped.index, grouped[model + '_inside'], 'o-', label=model, color=color)
        axes[1].plot(grouped.index, grouped[model + '_distance'], 'o-', label=model, color=color)
    axes[0].set(title='Closing interval containment', xlabel='Year', ylabel='Fraction within observed bid/ask')
    axes[1].set(title='Distance outside interval', xlabel='Year', ylabel='Mean SPX index points')
    axes[0].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(output / 'valuation_intervals.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    result.groupby('year').size().plot.bar(ax=axes[0], color='#36B3A8')
    result.groupby('year').relative_spread.median().plot.bar(ax=axes[1], color='#234e70')
    axes[0].set(title='Eligible quote coverage', ylabel='Contract/date rows')
    axes[1].set(title='Median relative closing spread', ylabel='(ask-bid) / midpoint')
    fig.tight_layout(); fig.savefig(output / 'coverage_spreads.png', dpi=160); plt.close(fig)
    metrics = dict(data_kind=source['data_kind'], input_rows=total, eligible_rows=len(result), exclusions=exclusions, slices=len(summary),
                   years=sorted(result.year.unique().tolist()), public_derived_results_permission=source.get('public_derived_results_permission', False))
    (output / 'metrics.json').write_text(json.dumps(metrics, indent=2, allow_nan=False), encoding='utf-8')
    (output / 'REPORT.md').write_text('''# SPX end-of-day valuation diagnostics

This run is based on the input kind in metrics.json. Real licensed records and derived results remain private pending the applicable publication-rights assessment. Synthetic fixtures establish implementation behavior only.

![Valuation intervals](valuation_intervals.png)

![Coverage and spreads](coverage_spreads.png)

The models use lagged 20/60-session annualized log-return volatility, same-date vendor forward prices and same-date interpolated continuously compounded zero rates. Strike is divided by 1,000; rates by 100; premiums remain SPX index points. Contract dollar value is index points times 100. There is no ETF-per-share quote conversion. Positive vendor IV is optional and its reconstructed price is a circular consistency diagnostic, not an independent forecast. All fixed year/type/tenor slices and ordered exclusion counts are saved.

Development is 2020–2022, review is 2023 and historical confirmation is 2024. No volatility-window choice is selected using the review or confirmation outcomes. This is a predetermined valuation comparison rather than an options-return prediction task.

Missing forward/curve/history records, wrong settlement/type, wrong contract size, out-of-range moneyness and invalid intervals are explicitly excluded. Forward joins use security/date/expiration/AM-PM keys and reject duplicates. Bid/ask are closing cross-exchange observations; a positive bid is not evidence of executable depth. Data sources can have different EOD clocks. Our ACT/365 calendar-day maturity ignores hours and vendor-specific expiration handling; IV reconstruction discrepancies can expose these conventions rather than economic mispricing. No live quote, fill, queue, hedged profit or arbitrage claim follows from distance to a closing interval.

The protocol, source hashes, input hashes and output hashes identify this run. Raw contract results are saved separately from summary tables; both are private for licensed inputs. Public numerical-grid and synthetic-fixture reports carry their own labels.
''', encoding='utf-8')
    manifest = dict(protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest(), source_record=source, unit_contract=unit_contract,
                    inputs_sha256={name: hashlib.sha256((input_directory / name).read_bytes()).hexdigest() for name in ['spx_options.csv.gz', 'spx_forwards.csv.gz', 'spx_spot.csv', 'zero_curve.csv.gz']},
                    source_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in Path(__file__).parent.glob('*.py')},
                    outputs_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir() if path.is_file()})
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return metrics
