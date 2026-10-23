import numpy as np
import pytest
from pricing_lab.core import price,greeks,monte_carlo,gbm_paths,hedge_pnl

def test_parity_vectorization_and_zero_limits():
    s=np.array([70.,100.,130.]);q=.01;r=-.005;t=1.7
    call=price(s,100,r,.3,t,dividend_yield=q)
    put=price(s,100,r,.3,t,kind="put",dividend_yield=q)
    np.testing.assert_allclose(call-put,s*np.exp(-q*t)-100*np.exp(-r*t),atol=1e-12)
    np.testing.assert_allclose(price(s,100,.03,.2,0),[0,0,30])
    assert float(price(100,100,.03,0,1))==pytest.approx(100-100*np.exp(-.03))

@pytest.mark.parametrize("kind",["call","put"])
def test_greeks_against_independent_central_differences(kind):
    s,k,r,v,t,q=105.,100.,.04,.25,.8,.015
    g=greeks(s,k,r,v,t,kind=kind,dividend_yield=q)
    f=lambda S=s,R=r,V=v,T=t:float(price(S,k,R,V,T,kind=kind,dividend_yield=q))
    h=.001
    assert g["delta"]==pytest.approx((f(S=s+h)-f(S=s-h))/(2*h),rel=1e-6)
    assert g["gamma"]==pytest.approx((f(S=s+h)-2*f()+f(S=s-h))/h**2,rel=1e-4)
    h=1e-5
    assert g["vega"]==pytest.approx((f(V=v+h)-f(V=v-h))/(2*h),rel=1e-6)
    assert g["rho"]==pytest.approx((f(R=r+h)-f(R=r-h))/(2*h),rel=1e-6)
    assert g["theta"]==pytest.approx(-(f(T=t+h)-f(T=t-h))/(2*h),rel=1e-6)

def test_known_reference_price_and_invalid_inputs():
    assert float(price(100,100,.05,.2,1))==pytest.approx(10.450583572185565)
    for args in [(-1,100,.03,.2,1),(100,0,.03,.2,1),(100,100,.03,-.2,1),(100,100,float("nan"),.2,1)]:
        with pytest.raises(ValueError):price(*args)
    with pytest.raises(ValueError):greeks(100,100,.03,.2,0)
    with pytest.raises(ValueError):monte_carlo(100,100,.03,.2,1,paths=101)

def test_mc_standard_error_uses_pair_means_and_batching_is_stable():
    n=20000;z=np.random.default_rng(77).standard_normal(n//2)
    payoff=lambda x:np.exp(-.03)*np.maximum(100*np.exp((.03-.02)+.2*x)-100,0)
    independent=(payoff(z)+payoff(-z))/2
    result=monte_carlo(100,100,.03,.2,1,paths=n,seed=77,batch_size=113)
    assert result.estimate==pytest.approx(independent.mean(),abs=1e-12)
    assert result.standard_error==pytest.approx(independent.std(ddof=1)/np.sqrt(n//2),abs=1e-12)
    assert abs(result.estimate-float(price(100,100,.03,.2,1)))<5*result.standard_error

def test_self_financing_hedge_on_deterministic_one_step_path():
    paths=np.array([[100.,110.]])
    delta=float(greeks(100,100,.03,.2,1)["delta"])
    cash=float(price(100,100,.03,.2,1))-100*delta
    expected=cash*np.exp(.03)+delta*110-10
    assert hedge_pnl(paths,rebalance_steps=1)[0]==pytest.approx(expected)

def test_costs_lower_pnl_on_identical_paths_and_finer_hedging_reduces_error():
    paths=gbm_paths(paths=3000,seed=100)
    fine=hedge_pnl(paths,rebalance_steps=252)
    coarse=hedge_pnl(paths,rebalance_steps=12)
    costly=hedge_pnl(paths,rebalance_steps=252,cost_bps=5)
    assert np.all(costly<fine)
    assert fine.std()<coarse.std()
    with pytest.raises(ValueError):hedge_pnl(paths,rebalance_steps=13)

def test_gbm_rejects_nonfinite_drift_and_invalid_simulation_counts():
    with pytest.raises(ValueError):gbm_paths(drift=np.nan)
    with pytest.raises(ValueError):gbm_paths(paths=2.5)
    with pytest.raises(ValueError):gbm_paths(steps=True)
    with pytest.raises(ValueError):gbm_paths(spot=[100,101])
    with pytest.raises(ValueError):hedge_pnl(np.empty((0,253)))
