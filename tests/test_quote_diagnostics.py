import numpy as np
import pandas as pd
import pytest
from pricing_lab.diagnostics.quotes import black_forward, interval_distance, lagged_volatility, normalize
from pricing_lab.core import price


def test_forward_units_and_parity():
    spot, strike, rate, dividend, maturity, volatility = 4500., 4400., .04, .02, 60/365, .2
    forward = spot * np.exp((rate - dividend) * maturity)
    call = black_forward(forward, strike, rate, volatility, maturity, True)
    put = black_forward(forward, strike, rate, volatility, maturity, False)
    assert call == pytest.approx(price(spot, strike, rate, volatility, maturity, dividend_yield=dividend))
    assert call - put == pytest.approx(np.exp(-rate * maturity) * (forward - strike))
    assert 100 * call > call


def test_bid_ask_interval_distance_is_not_midpoint_error():
    np.testing.assert_array_equal(interval_distance(np.array([.5, 1.5, 3.]), 1., 2.), [.5, 0., 1.])


def test_volatility_uses_prior_session_and_rejects_conflicting_dates():
    dates = pd.bdate_range('2020-01-01', periods=100)
    spot = pd.DataFrame(dict(date=dates, close=np.exp(np.sin(np.arange(100))*.01)*4500))
    original = lagged_volatility(spot)
    spot.loc[80:, 'close'] *= 2
    changed = lagged_volatility(spot)
    pd.testing.assert_frame_equal(original.loc[:80, ['hv_20', 'hv_60']], changed.loc[:80, ['hv_20', 'hv_60']])
    with pytest.raises(ValueError):
        lagged_volatility(pd.concat([spot, spot.iloc[:1]]))
