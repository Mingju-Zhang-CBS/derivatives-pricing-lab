"""Black-Scholes-Merton prices, sensitivities, sampling and self-financing hedges."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.special import ndtr


def _parameters(spot, strike, rate, volatility, maturity, dividend_yield=0.):
    s,k,r,v,t,q = np.broadcast_arrays(*[np.asarray(x,dtype=float) for x in (spot,strike,rate,volatility,maturity,dividend_yield)])
    if not all(np.isfinite(x).all() for x in (s,k,r,v,t,q)):
        raise ValueError("Parameters must be finite")
    if np.any(s<=0) or np.any(k<=0) or np.any(v<0) or np.any(t<0):
        raise ValueError("Require spot,strike > 0 and volatility,maturity >= 0")
    return s,k,r,v,t,q


def price(spot, strike, rate, volatility, maturity, *, kind="call", dividend_yield=0.):
    """European option price; continuous rates/yields, annual decimal volatility."""
    if kind not in {"call","put"}: raise ValueError("kind must be call or put")
    s,k,r,v,t,q = _parameters(spot,strike,rate,volatility,maturity,dividend_yield)
    ds,dk=s*np.exp(-q*t),k*np.exp(-r*t)
    active=(v>0)&(t>0)
    denominator=np.where(active,v*np.sqrt(t),1.)
    d1=(np.log(s/k)+(r-q+.5*v*v)*t)/denominator
    d2=d1-v*np.sqrt(t)
    call=np.where(active,ds*ndtr(d1)-dk*ndtr(d2),np.maximum(ds-dk,0.))
    result=call if kind=="call" else call-ds+dk
    return np.maximum(result,0.)


def greeks(spot, strike, rate, volatility, maturity, *, kind="call", dividend_yield=0.):
    """Theta per year, vega/rho per unit decimal input; excludes expiry/zero-vol."""
    if kind not in {"call","put"}: raise ValueError("kind must be call or put")
    s,k,r,v,t,q=_parameters(spot,strike,rate,volatility,maturity,dividend_yield)
    if np.any(t<=0) or np.any(v<=0): raise ValueError("Greeks require positive maturity and volatility")
    root=np.sqrt(t); discount=np.exp(-q*t); bond=np.exp(-r*t)
    d1=(np.log(s/k)+(r-q+.5*v*v)*t)/(v*root); d2=d1-v*root
    density=np.exp(-.5*d1*d1)/np.sqrt(2*np.pi)
    sign=1 if kind=="call" else -1
    return {"delta":sign*discount*ndtr(sign*d1),
            "gamma":discount*density/(s*v*root),
            "vega":s*discount*density*root,
            "theta":-s*discount*density*v/(2*root)-sign*r*k*bond*ndtr(sign*d2)+sign*q*s*discount*ndtr(sign*d1),
            "rho":sign*k*t*bond*ndtr(sign*d2)}


@dataclass(frozen=True)
class MonteCarloResult:
    estimate: float
    standard_error: float
    ci_low: float
    ci_high: float
    paths: int
    independent_observations: int
    antithetic: bool


def monte_carlo(spot, strike, rate, volatility, maturity, *, paths=100_000, seed=42,
                antithetic=True, kind="call", dividend_yield=0., batch_size=10_000):
    """Terminal GBM sampling. Antithetic standard errors use independent PAIRS."""
    s,k,r,v,t,q=_parameters(spot,strike,rate,volatility,maturity,dividend_yield)
    if s.ndim: raise ValueError("Monte Carlo accepts scalar parameters")
    if kind not in {"call","put"}: raise ValueError("kind must be call or put")
    if not isinstance(paths,int) or paths<4 or (antithetic and paths%2):
        raise ValueError("paths must be >=4, and even for antithetic sampling")
    if not isinstance(batch_size,int) or batch_size<1: raise ValueError("batch_size must be positive")
    observations=paths//2 if antithetic else paths
    rng=np.random.default_rng(seed); count=0; mean=0.; m2=0.
    sign=1 if kind=="call" else -1
    for first in range(0,observations,batch_size):
        n=min(batch_size,observations-first); z=rng.standard_normal(n)
        def payoff(zvalue):
            terminal=s*np.exp((r-q-.5*v*v)*t+v*np.sqrt(t)*zvalue)
            return np.exp(-r*t)*np.maximum(sign*(terminal-k),0.)
        values=(payoff(z)+payoff(-z))/2 if antithetic else payoff(z)
        batch_mean=float(values.mean()); batch_m2=float(np.sum((values-batch_mean)**2))
        delta=batch_mean-mean; total=count+n
        m2+=batch_m2+delta*delta*count*n/total
        mean+=delta*n/total; count=total
    se=float(np.sqrt(m2/(count-1)/count))
    return MonteCarloResult(mean,se,mean-1.96*se,mean+1.96*se,paths,count,antithetic)


def gbm_paths(*, spot=100., drift=.06, volatility=.2, maturity=1., paths=6000, steps=252, seed=42):
    parameters=_parameters(spot,100.,0.,volatility,maturity)
    if parameters[0].ndim or np.asarray(drift).ndim or not np.isfinite(drift):
        raise ValueError("GBM parameters must be finite scalars")
    if not isinstance(paths,(int,np.integer)) or isinstance(paths,bool) or not isinstance(steps,(int,np.integer)) or isinstance(steps,bool):
        raise ValueError("Path and step counts must be integers")
    if paths<1 or steps<1 or maturity<=0: raise ValueError("Positive paths, steps and maturity required")
    rng=np.random.default_rng(seed); dt=maturity/steps
    increments=(drift-.5*volatility**2)*dt+volatility*np.sqrt(dt)*rng.standard_normal((paths,steps))
    return np.column_stack((np.full(paths,spot),spot*np.exp(np.cumsum(increments,axis=1))))


def hedge_pnl(stock_paths, *, strike=100., rate=.03, volatility=.2, maturity=1.,
              rebalance_steps=252, cost_bps=0., kind="call"):
    """Short one option; fund a delta hedge. No dividends; proportional stock costs.

    Prices supplied at the finest common grid are used only when observed.
    Costs apply at inception, every rebalance and final stock liquidation.
    """
    stock_paths=np.asarray(stock_paths,dtype=float)
    if stock_paths.ndim!=2 or stock_paths.shape[0]<1 or stock_paths.shape[1]<2 or not np.isfinite(stock_paths).all() or np.any(stock_paths<=0):
        raise ValueError("Need finite positive stock paths with an initial and terminal value")
    fine=stock_paths.shape[1]-1
    if not isinstance(rebalance_steps,int) or rebalance_steps<1 or fine%rebalance_steps:
        raise ValueError("Rebalance grid must divide the supplied path grid")
    if not np.isfinite(cost_bps) or cost_bps<0: raise ValueError("Nonnegative finite cost required")
    if maturity<=0: raise ValueError("Positive maturity required")
    coarse=stock_paths[:,::fine//rebalance_steps]; dt=maturity/rebalance_steps; cost=cost_bps/10_000
    delta=greeks(coarse[:,0],strike,rate,volatility,maturity,kind=kind)["delta"]
    cash=price(coarse[:,0],strike,rate,volatility,maturity,kind=kind)-delta*coarse[:,0]-np.abs(delta)*coarse[:,0]*cost
    for i in range(1,rebalance_steps+1):
        cash=cash*np.exp(rate*dt); spot=coarse[:,i]
        if i==rebalance_steps:
            sign=1 if kind=="call" else -1
            return cash+delta*spot-np.abs(delta)*spot*cost-np.maximum(sign*(spot-strike),0.)
        new_delta=greeks(spot,strike,rate,volatility,maturity-i*dt,kind=kind)["delta"]
        trade=new_delta-delta
        cash-=trade*spot+np.abs(trade)*spot*cost
        delta=new_delta
