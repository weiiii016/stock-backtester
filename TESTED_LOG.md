# Tested Strategies Log

Avoid re-running these combinations — they've been tested and found unprofitable.

## Strong Trending Stocks (B&H dominates, don't bother with active strategies)

| Ticker | Period | B&H Return | Notes |
|--------|--------|-----------|-------|
| NVDA | daily 5y | +2201% | All strategies lose massively to B&H |
| NVDA | 1h 2y | +48% | All strategies negative alpha |
| VOO | daily 5y | +95% | Index fund — B&H always wins |
| VOO | 1h 2y | +34% | All strategies negative alpha |
| AMD | 1h 2y | +213% | RSI/VolSpike/RSIBB all lose to B&H |
| TSLA | 1h 2y | +89% | All strategies negative alpha |
| PLTR | 1h 2y | +345% | All hourly strategies lose massively to B&H |

## Deleted Reports (significant losers)

### Round 1 (2026-06-28) — initial cleanup
- All NVDA reports (34 files) — alpha ranges from -6% to -2174%
- All VOO reports (21 files) — alpha ranges from -8% to -37%
- INTC negative-alpha hourly: bb_p10_2s, bb_p15_2s, bb_p20_15s, bb_p20_2s, bb_p30_15s, bb_p30_2s, dc, dca, macd, rsi, rsibb, sma (alpha -3% to -292%)
- COIN negative-alpha hourly BBands: bb10_2s, bb10_hourly, bb_p10_1s, bb_p15 variants, bb_p20_1s, bb_p30 variants (alpha -1% to -16%)

### Round 2 (2026-06-28) — new tickers cleanup
- All AMD (6 files) — B&H 213%, alpha -17% to -222%
- All TSLA (6 files) — B&H 89%, alpha -27% to -79%
- PLTR hourly (5 files) — B&H 345%, alpha -143% to -287%
- MSTR BB(10,1.5σ) 1h — alpha -8.32%, 0% win rate
- MSTR RSI_BB 1h — alpha -6.70%, 0% win rate
- MSTR VolSpike 1h — 0% win rate (alpha +8.7% only because B&H is -43%)
- SMCI BB(10,1.5σ) daily — only 4 trades, unreliable
- MARA RSI_BB 1h — alpha -0.29%
- MARA VolSpike 1h — alpha -2.58%

### Round 3 (2026-06-28) — full run cleanup (0% WR, < 5 trades, fails keep threshold)

**0% win rate:**
- COIN BB(10,2.0σ) 1h — alpha -8.50%
- COIN BB(20,1.0σ) 1h — alpha -7.05%
- COIN BB(30,1.5σ) 1h — alpha -5.92%
- MSTR BB(10,1.5σ) 1h — alpha -8.32%
- MSTR BB(15,1.0σ) 1h — alpha -3.32%
- MSTR RSI_BB 1h — alpha -6.70%
- MSTR VolSpike 1h — alpha +8.74% (0% WR despite positive alpha)

**< 5 trades:**
- SMCI BB(10,1.5σ) daily — 4 trades, alpha -124.84%

**Fails keep threshold (alpha ≤ -10% AND alpha ≤ -1/10 × B&H):**
- AMD (B&H 1h 214%, daily ~80%): RSI(14) 1h (-222%), RSI(10) 1h (-208%), MACD 1h (-224%), Donchian 1h (-180%), SMA 1h (-202%), RSIBB 1h (-70%), VolSpike 1h (-54%), BB daily (-160%), RSI daily (-476%)
- COIN (B&H 1h -33%): BB(15,1.5σ) 1h (-10.13%), VolSpike 1h (-20.17%)
- INTC (B&H 1h 292%, daily 144%): MACD 1h (-307%), RSI(14) 1h (-298%), RSI(10) 1h (-289%), SMA 1h (-288%), Donchian 1h (-273%), RSIBB 1h (-85%), RSI daily (-109%), BB daily 10y (-112%)
- NVDA (B&H 1h 51%, daily 867%): all hourly — BB(10,1.5σ) (-30.9%), BB(15,1.0σ) (-22.3%), BB(20,1.0σ) (-19.8%), MACD (-58%), Donchian (-44.7%), RSI(10) (-48.8%), RSI(14) (-42.2%), RSIBB (-48.5%), SMA (-47.3%), VolSpike (-38.5%); daily — BB (-166%), RSI (-828%)
- PLTR (B&H 1h 345%, daily 312%): RSI(14) 1h (-282%), RSI(10) 1h (-287%), MACD 1h (-351%), SMA 1h (-339%), Donchian 1h (-329%), BB(10,1.5σ) 1h (-143%), BB(15,1.0σ) 1h (-131%), RSIBB 1h (-161%), VolSpike 1h (-143%), RSI daily (-232%)
- SMCI: RSI daily (-704%)
- TSLA (B&H 1h 89%): all — RSI(14) 1h (-79%), RSI(10) 1h (-61%), MACD 1h (-99%), SMA 1h (-92%), RSI daily (-60%), BB(10,1.5σ) 1h (-36.3%), BB(10,1.5σ) daily (-48.6%), BB(15,1.0σ) 1h (-40.0%), Donchian 1h (-48.4%), RSIBB 1h (-45.8%), VolSpike 1h (-27.1%)
- VOO (B&H 1h 34%, daily 83%): all — BB(10,1.5σ) 1h (-10.1%), BB(10,1.5σ) daily (-27.0%), BB(15,1.0σ) (-17.7%), Donchian (-31.0%), MACD (-43.5%), RSI(10) (-28.6%), RSI(14) (-34.7%), RSI daily (-71%), RSIBB (-13.6%), SMA (-37.9%), VolSpike (-28.3%)

### Round 4 (2026-06-28) — explore run cleanup

**< 5 trades:**
- SMCI BB(15,1.5σ) daily — 4 trades, alpha -153.68%

**Fails keep threshold:**
- HOOD RSI(14,40/60) daily — alpha -183.25%, B&H 183%, threshold -18.3%
- RKLB RSI(14,40/60) daily — alpha -676.28%, B&H 672%, threshold -67.2%
- MSTR BB(20,1.5σ) daily — alpha -18.88%, B&H 31.9%, threshold -3.2%
- SMCI BB(20,1.5σ) daily — alpha -158.89%, B&H 762%, threshold -76.2%
- SMCI BB(20,1.0σ) daily — alpha -287.88%, B&H 762%, threshold -76.2%
- SMCI Donchian daily — alpha -725.34%, B&H 762%, threshold -76.2%

**Failed to generate (no hourly data or error):**
- All 7 new tickers hourly (RIOT, HOOD, SQ, SHOP, SOFI, RKLB, UPST × 9 strategies)
- SQ entirely (no daily either)

## Strategy-Ticker Patterns

- **BBands daily** is the alpha king — works on almost every ticker: PLTR (+346%), RKLB (+239%), COIN (+147%), HOOD (+144%), RIOT (+119%), SOFI (+116%), INTC (+66%), MARA (+54%), SHOP (+54%), MSTR (+39%)
- **RSI mean-reversion** works hourly on: COIN, SMCI, MARA, MSTR (volatile/mean-reverting)
- **RSI mean-reversion** fails on: NVDA, VOO, AMD, TSLA, PLTR, HOOD, RKLB (trending stocks)
- **RSI daily** works on: RIOT, UPST, MARA, COIN (volatile tickers with negative/flat B&H)
- **Donchian** works on: SMCI 1h (+97%), COIN daily (+84%), MSTR daily (+46%), MARA daily (+33%)
- **BBands hourly** mostly fails except INTC (too many false signals)
- **VolSpike** works on: INTC only
- **New tickers hourly** — all failed to generate (probably insufficient data window)
- **0% win rate** warning: MSTR & COIN hourly BBands/RSI_BB — too volatile
