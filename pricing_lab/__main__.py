from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .core import price, greeks, monte_carlo, gbm_paths, hedge_pnl
from .runtime import Measurement, manifest, dump, require_empty_output


def run(output):
    out=require_empty_output(output)
    config={"spot":100.,"strike":100.,"rate":.03,"volatility":.2,"maturity":1.,
            "seed":42,"mc_paths":[2000,10000,50000,200000],"hedge_paths":6000,
            "fine_steps":252,"rebalance_steps":[12,63,252],"cost_bps":[0.,5.,10.],"physical_drift":.06}
    exact=float(price(100,100,.03,.2,1))
    rows=[]
    with Measurement() as measured:
        for anti in [False,True]:
            for n in config["mc_paths"]:
                start=time.perf_counter()
                mc=monte_carlo(100,100,.03,.2,1,paths=n,antithetic=anti,seed=42)
                row=asdict(mc);row.update(absolute_error=abs(mc.estimate-exact),seconds=time.perf_counter()-start)
                rows.append(row)
        paths=gbm_paths(seed=42,paths=config["hedge_paths"],drift=config["physical_drift"])
        hedge=[]
        for frequency in config["rebalance_steps"]:
            for bps in config["cost_bps"]:
                pnl=hedge_pnl(paths,rebalance_steps=frequency,cost_bps=bps)
                q=float(np.quantile(pnl,.05))
                hedge.append({"rebalances":frequency,"cost_bps":bps,"mean_pnl":float(pnl.mean()),
                              "pnl_std":float(pnl.std(ddof=1)),"p05":q,"worst_5pct_mean":float(pnl[pnl<=q].mean())})
        # Median of seven warm runs for a fixed, vectorized 10k-option workload.
        spots=np.linspace(60,150,10_000); price(spots,100,.03,.2,1)
        durations=[]
        for _ in range(7):
            start=time.perf_counter();price(spots,100,.03,.2,1);durations.append(time.perf_counter()-start)
    convergence=pd.DataFrame(rows);convergence.to_csv(out/"monte_carlo.csv",index=False)
    hedges=pd.DataFrame(hedge);hedges.to_csv(out/"hedging.csv",index=False)
    summary={"data_kind":"simulated","analytical_call":exact,"analytical_put":float(price(100,100,.03,.2,1,kind="put")),
             "greeks":{k:float(v) for k,v in greeks(100,100,.03,.2,1).items()},
             "benchmark":{"batch_options":10000,"repetitions":7,"median_seconds":float(np.median(durations)),
                          "options_per_second":float(10000/np.median(durations))},
             "measurement":measured.result,"monte_carlo":rows,"hedging":hedge}
    dump(out/"metrics.json",summary)
    fingerprint=hashlib.sha256(paths.tobytes()).hexdigest()
    dump(out/"manifest.json",manifest(config,fingerprint,"simulated"))
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout="constrained")
    for anti,group in convergence.groupby("antithetic"):
        label="Antithetic pairs" if anti else "Plain MC"
        axes[0].errorbar(group.paths,group.estimate,yerr=1.96*group.standard_error,marker="o",capsize=3,label=label)
        axes[1].loglog(group.paths,group.standard_error,"o-",label=label)
    axes[0].axhline(exact,color="black",linestyle="--",label="Analytical")
    axes[0].set(xscale="log",xlabel="Terminal paths",ylabel="Call price",title="Estimate and 95% normal interval")
    axes[1].set(xlabel="Terminal paths",ylabel="Standard error",title="Sampling uncertainty")
    for ax in axes:ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.savefig(out/"mc_convergence.png",dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout="constrained")
    for bps,group in hedges.groupby("cost_bps"):
        axes[0].plot(group.rebalances,group.mean_pnl,"o-",label=f"{bps:g} bps")
        axes[1].plot(group.rebalances,group.pnl_std,"o-",label=f"{bps:g} bps")
    axes[0].set(xlabel="Rebalances in one year",ylabel="Mean hedge P&L per option",title="Costs accumulate with trading")
    axes[1].set(xlabel="Rebalances in one year",ylabel="Hedge P&L standard deviation",title="Discretization and transaction costs")
    for ax in axes:ax.legend();ax.grid(alpha=.2)
    fig.savefig(out/"hedging_tradeoff.png",dpi=160);plt.close(fig)
    plain=convergence[(convergence.paths==200000)&~convergence.antithetic].iloc[0]
    anti=convergence[(convergence.paths==200000)&convergence.antithetic].iloc[0]
    daily=hedges[(hedges.rebalances==252)&(hedges.cost_bps==5)].iloc[0]
    (out/"REPORT.md").write_text(f"""# Pricing and hedging experiment

All results use simulated GBM paths and fixed parameters. One-year ATM call: S=K=100, r=3%, volatility=20%, no dividends. No market data or execution record is used.

- Analytical call price: **{exact:.6f}**.
- 200,000 plain terminal paths: estimate {plain.estimate:.6f}, standard error {plain.standard_error:.6f}.
- 200,000 antithetic terminal paths: estimate {anti.estimate:.6f}, standard error {anti.standard_error:.6f}. The independent sampling units are pairs.
- Daily hedge at 5 bps stock trading cost: mean P&L {daily.mean_pnl:.6f}, standard deviation {daily.pnl_std:.6f} per short option.
- Fixed 10,000-option vectorized batch: median {np.median(durations)*1000:.3f} ms over seven warm runs. This is a local batch benchmark, not exchange order latency.

![Monte Carlo convergence](mc_convergence.png)

![Hedging tradeoff](hedging_tradeoff.png)

## Interpretation

The analytical solution is a numerical reference under the assumed model. Antithetic draws can reduce sampling error; their standard error must be computed from pair means. More frequent frictionless hedging reduces discretization risk in this experiment. Trading costs create a competing effect and lower the mean short-option hedge P&L.

## Limits and reproduction

The stock follows exactly the assumed diffusion, with constant volatility and no dividends in the hedging experiment. There are no jumps, stochastic volatility, bid/ask quotes, financing spreads or margin constraints. A single fixed seed is illustrative. Confidence intervals are asymptotic normal sampling intervals, not guarantees that an individual run contains the analytical value. See `manifest.json` for configuration, source hashes and environment; `metrics.json` records sampled process memory and timing.
""",encoding="utf-8")
    print(f"Pricing demo complete: analytical call={exact:.6f}; simulated paths only.")


def main():
    parser=argparse.ArgumentParser(description="Offline pricing, Monte Carlo and hedging demonstration")
    parser.add_argument("--output",default="local-runs/demo")
    args=parser.parse_args();run(args.output)

if __name__=="__main__":main()
