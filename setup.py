from setuptools import setup, find_packages

setup(
    name="jupiter-backtest",
    version="1.0.0",
    description="Crypto backtesting bot for Jupiter DEX on Solana",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "httpx>=0.27.0",
        "pandas>=2.2.0",
        "numpy>=1.26.0",
        "matplotlib>=3.8.0",
        "pyyaml>=6.0.0",
        "rich>=13.7.0",
        "click>=8.1.0",
    ],
    entry_points={
        "console_scripts": [
            "jupiter-backtest=src.main:main",
        ],
    },
)
