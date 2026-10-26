from pathlib import Path
import json
import numpy as np
import pandas as pd
from .quotes import black_forward, run


def create_and_run(output):
    output = Path(output)
    data = output.parent / (output.name + '-synthetic-input')
    data.mkdir(parents=True)
    dates = pd.bdate_range('2019-01-01', '2024-12-31')
    rng = np.random.default_rng(20261026)
    spot = pd.DataFrame(dict(date=dates, secid=108105, close=4000*np.exp(np.cumsum(rng.normal(0, .2/np.sqrt(252), len(dates))))))
    spot.to_csv(data / 'spx_spot.csv', index=False)
    options, forwards, curves = [], [], []
    identifier = 0
    for date, level in zip(dates[dates.year >= 2020][::21], spot.loc[spot.date.dt.year >= 2020, 'close'].iloc[::21]):
        for days in [7, 30, 90, 180, 365]:
            curves.append(dict(date=date, days=days, rate=3.))
        for days in [20, 60, 120]:
            expiration = date + pd.Timedelta(days=days)
            forward = level*np.exp(.02*days/365)
            forwards.append(dict(secid=108105, date=date, expiration=expiration, amsettlement=0, forwardprice=forward))
            for ratio in [.85, 1., 1.15]:
                for kind in ['C', 'P']:
                    identifier += 1
                    mark = float(black_forward(forward, forward*ratio, .03, .2, days/365, kind == 'C'))
                    options.append(dict(secid=108105, date=date, exdate=expiration, optionid=identifier, cp_flag=kind,
                                        strike_price=forward*ratio*1000, best_bid=max(0, mark-.5), best_offer=mark+.5,
                                        am_settlement=0, contract_size=100, ss_flag=0, exercise_style='E', impl_volatility=.2))
    pd.DataFrame(options).to_csv(data / 'spx_options.csv.gz', index=False)
    pd.DataFrame(forwards).to_csv(data / 'spx_forwards.csv.gz', index=False)
    pd.DataFrame(curves).to_csv(data / 'zero_curve.csv.gz', index=False)
    (data / 'source.json').write_text(json.dumps(dict(data_kind='synthetic-fixture', public_derived_results_permission=True, seed=20261026)), encoding='utf-8')
    (data / 'unit_contract.json').write_text(json.dumps(dict(strike_divisor=1000, curve_rate_divisor=100, premium_unit='SPX_index_points', unit_sources_verified=True,
                                                          verification_scope='units assigned by fixture generator; no observed market data')), encoding='utf-8')
    return run(data, output)
