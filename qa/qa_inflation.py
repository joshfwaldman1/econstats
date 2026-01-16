#!/usr/bin/env python3
"""QA Agent: Inflation & Prices queries"""
import sys
sys.path.insert(0, '/Users/josh/Desktop/econstats/qa')
from qa_base import evaluate_queries

QUERIES = [
    "inflation",
    "cpi",
    "consumer price index",
    "core inflation",
    "core cpi",
    "pce",
    "pce inflation",
    "core pce",
    "what does the fed target",
    "fed inflation target",
    "price increases",
    "cost of living",
    "prices",
    "inflation rate",
    "is inflation high",
    "is inflation coming down",
    "food prices",
    "grocery prices",
    "gas prices",
    "gasoline prices",
    "oil prices",
    "rent inflation",
    "shelter inflation",
    "housing inflation",
    "services inflation",
]

if __name__ == "__main__":
    evaluate_queries(QUERIES, "Inflation & Prices", "/Users/josh/Desktop/econstats/qa/results_inflation.json")
