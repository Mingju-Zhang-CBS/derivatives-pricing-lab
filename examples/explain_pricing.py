"""Reconstruct analytical units and one hypothetical hedge cash flow."""
import numpy as np
from pricing_lab.core import price,greeks,monte_carlo,hedge_pnl

def main():
    call=float(price(100,100,.03,.2,1));g=greeks(100,100,.03,.2,1)
    delta=float(g['delta']);cash=call-delta*100
    expected=cash*np.exp(.03)+delta*110-10
    actual=float(hedge_pnl(np.array([[100.,110.]]),rebalance_steps=1)[0])
    np.testing.assert_allclose(actual,expected,atol=1e-12)
    print('Call price:',round(call,6),'delta:',round(delta,6))
    print('Vega for a one-percentage-point volatility change:',round(float(g['vega'])/100,6))
    print('Initial financed cash:',round(cash,6))
    print('Hypothetical one-step 100 -> 110 hedge P&L:',round(actual,6))
    result=monte_carlo(100,100,.03,.2,1,paths=20_000,seed=42)
    print('Antithetic paths:',result.paths,'independent pair observations:',result.independent_observations)
    print('Sampling estimate and standard error:',result.estimate,result.standard_error)

if __name__=='__main__':main()
