@echo off
cd /d "%~dp0"
powershell.exe -ExecutionPolicy Bypass -File "tools\run_mt5_backtest.ps1" -Symbol "XAUUSD" -Period "M15" -PresetName "RSIFibEA_xau_v42_quant_edge_2k.set" -FromDate "2026.06.01" -ToDate "2026.08.01" -Deposit 2000
pause
