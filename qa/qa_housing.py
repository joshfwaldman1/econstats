#!/usr/bin/env python3
"""QA Agent: Housing queries"""
import sys
sys.path.insert(0, '/Users/josh/Desktop/econstats/qa')
from qa_base import evaluate_queries

QUERIES = [
    "housing",
    "housing market",
    "home prices",
    "house prices",
    "real estate",
    "home sales",
    "existing home sales",
    "new home sales",
    "housing starts",
    "building permits",
    "housing affordability",
    "rent prices",
    "case shiller",
    "housing inventory",
    "housing supply",
]

if __name__ == "__main__":
    evaluate_queries(QUERIES, "Housing", "/Users/josh/Desktop/econstats/qa/results_housing.json")
