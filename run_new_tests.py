"""Batch runner for strategy backtests."""
import subprocess
import sys

H_START = "2024-06-28"
H_END = "2026-06-28"
D_START = "2021-06-28"
D_END = "2026-06-28"

MULTI = ["--position-fraction", "0.20", "--max-positions", "5", "--initial-capital", "100000"]
RISK_H = ["--stop-loss", "0.05", "--trailing-after-profit", "0.03"]
RISK_D = ["--stop-loss", "0.10", "--trailing-after-profit", "0.05"]

BASE = [sys.executable, "main.py"]

TICKERS = ["TSLA", "AMD", "MSTR", "SMCI", "PLTR", "MARA"]

tests = []
for t in TICKERS:
    # RSI(14, 40/60) 1h
    tests.append((f"{t.lower()}_rsi_p14_4060_1h_multi", [
        "--ticker", t, "--start", H_START, "--end", H_END, "--interval", "1h",
        "--strategy", "rsi", "--rsi-period", "14", "--rsi-oversold", "40", "--rsi-overbought", "60",
        *MULTI, *RISK_H,
    ]))
    # RSI(10, 35/65) 1h
    tests.append((f"{t.lower()}_rsi_p10_3565_1h_multi", [
        "--ticker", t, "--start", H_START, "--end", H_END, "--interval", "1h",
        "--strategy", "rsi", "--rsi-period", "10", "--rsi-oversold", "35", "--rsi-overbought", "65",
        *MULTI, *RISK_H,
    ]))
    # BBands(10, 1.5σ) 1h
    tests.append((f"{t.lower()}_bb_p10_15s_1h_multi", [
        "--ticker", t, "--start", H_START, "--end", H_END, "--interval", "1h",
        "--strategy", "bbands", "--bb-period", "10", "--bb-std", "1.5",
        *MULTI, *RISK_H,
    ]))
    # VolSpike 1h
    tests.append((f"{t.lower()}_volspike_1h_multi", [
        "--ticker", t, "--start", H_START, "--end", H_END, "--interval", "1h",
        "--strategy", "volspike", "--vs-period", "20", "--vs-multiplier", "2.0", "--vs-drop", "0.01",
        *MULTI, *RISK_H,
    ]))
    # RSI+BB combo 1h
    tests.append((f"{t.lower()}_rsibb_1h_multi", [
        "--ticker", t, "--start", H_START, "--end", H_END, "--interval", "1h",
        "--strategy", "rsi_bb", "--rsi-period", "7", "--rsi-oversold", "35",
        "--bb-period", "20", "--bb-std", "1.5",
        *MULTI, *RISK_H,
    ]))
    # BBands(10, 1.5σ) daily
    tests.append((f"{t.lower()}_bb_p10_15s_daily_multi", [
        "--ticker", t, "--start", D_START, "--end", D_END, "--interval", "1d",
        "--strategy", "bbands", "--bb-period", "10", "--bb-std", "1.5",
        *MULTI, *RISK_D,
    ]))

total = len(tests)
for i, (name, args) in enumerate(tests, 1):
    output = f"reports/{name}.html"
    cmd = [*BASE, *args, "--output", output]
    print(f"\n[{i}/{total}] === {name} ===")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"  *** FAILED (exit {result.returncode}) ***")

# Regenerate summary
print(f"\n[DONE] Regenerating summary...")
subprocess.run([sys.executable, "gen_summary.py"])
print("===== ALL TESTS COMPLETE =====")
