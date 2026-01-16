#!/usr/bin/env python3
"""QA Agent: Trade, GDP & Markets queries"""
import sys
sys.path.insert(0, '/Users/josh/Desktop/econstats/qa')
from qa_base import evaluate_queries

QUERIES = [
    "gdp",
    "gdp growth",
    "economic growth",
    "real gdp",
    "industrial production",
    "manufacturing",
    "productivity",
    "trade",
    "trade deficit",
    "trade balance",
    "imports",
    "exports",
    "china trade",
    "dollar",
    "exchange rate",
    "stock market",
    "stocks",
    "s&p 500",
    "sp500",
    "oil",
    "crude oil",
    "commodities",
]

if __name__ == "__main__":
    evaluate_queries(QUERIES, "Trade, GDP & Markets", "/Users/josh/Desktop/econstats/qa/results_trade_gdp.json")
