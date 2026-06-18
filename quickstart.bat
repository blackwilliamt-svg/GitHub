@echo off
echo ============================================
echo  Jupiter DEX Backtesting Bot - Quick Start
echo ============================================
echo.

if not exist venv\Scripts\activate.bat (
    echo First time setup - installing dependencies...
    echo.
    call setup.bat
    echo.
)

call venv\Scripts\activate.bat

echo Running strategy comparison with synthetic data...
echo.
python -m src.main compare --synthetic --days 90 --output output

echo.
echo ============================================
echo  Charts saved to the output\ folder
echo ============================================
echo.
echo Try these commands next:
echo   run.bat backtest rsi --synthetic --days 120
echo   run.bat backtest ma_crossover --synthetic --stop-loss 0.05
echo   run.bat compare --synthetic --days 180
echo   run.bat tokens
echo   run.bat price SOL
echo.
pause
