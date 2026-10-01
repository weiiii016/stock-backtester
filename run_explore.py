"""Explore new tickers & parameter combos to find positive-alpha strategies."""
import subprocess
import sys
import os

BASE = [sys.executable, "main.py"]
MULTI = ["--position-fraction", "0.20", "--max-positions", "5", "--initial-capital", "100000"]
RISK_H = ["--stop-loss", "0.05", "--trailing-after-profit", "0.03"]
RISK_D = ["--stop-loss", "0.10", "--trailing-after-profit", "0.05"]

H_START = "2024-06-28"
H_END = "2026-06-28"
D_START = "2021-06-28"
D_END = "2026-06-28"

# New volatile tickers to explore
NEW_TICKERS = ["RIOT", "HOOD", "SQ", "SHOP", "SOFI", "RKLB", "UPST"]

# Best strategies from our findings
STRATEGIES_HOURLY = {
    "rsi_p14_4060": ["--strategy", "rsi", "--rsi-period", "14", "--rsi-oversold", "40", "--rsi-overbought", "60"],
    "rsi_p10_3565": ["--strategy", "rsi", "--rsi-period", "10", "--rsi-oversold", "35", "--rsi-overbought", "65"],
    "bb_p10_15s":   ["--strategy", "bbands", "--bb-period", "10", "--bb-std", "1.5"],
    "bb_p15_1s":    ["--strategy", "bbands", "--bb-period", "15", "--bb-std", "1.0"],
    "sma_5_13":     ["--strategy", "sma", "--short-window", "5", "--long-window", "13"],
    "macd":         ["--strategy", "macd", "--macd-fast", "5", "--macd-slow", "13", "--macd-signal", "4"],
    "donchian":     ["--strategy", "donchian", "--dc-entry", "20", "--dc-exit", "10"],
    "rsibb":        ["--strategy", "rsi_bb", "--rsi-period", "7", "--rsi-oversold", "35", "--bb-period", "20", "--bb-std", "1.5"],
    "volspike":     ["--strategy", "volspike", "--vs-period", "20", "--vs-multiplier", "2.0", "--vs-drop", "0.01"],
}

STRATEGIES_DAILY = {
    "bb_p10_15s": ["--strategy", "bbands", "--bb-period", "10", "--bb-std", "1.5"],
    "rsi_p14_4060": ["--strategy", "rsi", "--rsi-period", "14", "--rsi-oversold", "40", "--rsi-overbought", "60"],
}

# Also test new BBands daily params on existing winning tickers
EXTRA_DAILY = {
    "bb_p15_15s": ["--strategy", "bbands", "--bb-period", "15", "--bb-std", "1.5"],
    "bb_p20_1s":  ["--strategy", "bbands", "--bb-period", "20", "--bb-std", "1.0"],
    "bb_p20_15s": ["--strategy", "bbands", "--bb-period", "20", "--bb-std", "1.5"],
}
EXTRA_DAILY_TICKERS = ["COIN", "PLTR", "MSTR", "MARA", "SMCI", "INTC"]

# Also test Donchian daily on tickers where hourly Donchian worked
DONCHIAN_DAILY = {
    "donchian_d": ["--strategy", "donchian", "--dc-entry", "20", "--dc-exit", "10"],
}
DONCHIAN_DAILY_TICKERS = ["SMCI", "MSTR", "COIN", "MARA"]

tests = []

# 1) New tickers: full strategy suite (hourly + daily)
for t in NEW_TICKERS:
    tl = t.lower()
    for sname, sargs in STRATEGIES_HOURLY.items():
        tests.append((f"{tl}_{sname}_1h_multi", [
            "--ticker", t, "--start", H_START, "--end", H_END, "--interval", "1h",
            *sargs, *MULTI, *RISK_H,
        ]))
    for sname, sargs in STRATEGIES_DAILY.items():
        tests.append((f"{tl}_{sname}_daily_multi", [
            "--ticker", t, "--start", D_START, "--end", D_END, "--interval", "1d",
            *sargs, *MULTI, *RISK_D,
        ]))

# 2) Extra BBands daily params on winning tickers
for t in EXTRA_DAILY_TICKERS:
    tl = t.lower()
    for sname, sargs in EXTRA_DAILY.items():
        tests.append((f"{tl}_{sname}_daily_multi", [
            "--ticker", t, "--start", D_START, "--end", D_END, "--interval", "1d",
            *sargs, *MULTI, *RISK_D,
        ]))

# 3) Donchian daily on selected tickers
for t in DONCHIAN_DAILY_TICKERS:
    tl = t.lower()
    for sname, sargs in DONCHIAN_DAILY.items():
        tests.append((f"{tl}_{sname}_daily_multi", [
            "--ticker", t, "--start", D_START, "--end", D_END, "--interval", "1d",
            *sargs, *MULTI, *RISK_D,
        ]))

# Skip existing
filtered = []
for name, args in tests:
    path = f"reports/{name}.html"
    if os.path.exists(path):
        print(f"[SKIP] {name}")
    else:
        filtered.append((name, args))

total = len(filtered)
print(f"\n{len(tests) - total} skipped, {total} to run\n")

for i, (name, args) in enumerate(filtered, 1):
    output = f"reports/{name}.html"
    cmd = [*BASE, *args, "--output", output]
    print(f"\n[{i}/{total}] === {name} ===")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"  *** FAILED (exit {result.returncode}) ***")

print(f"\n[DONE] Regenerating summary...")
subprocess.run([sys.executable, "gen_summary.py"])
print("===== ALL COMPLETE =====")
