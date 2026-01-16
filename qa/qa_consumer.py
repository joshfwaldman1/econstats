#!/usr/bin/env python3
"""QA Agent: Consumer queries"""
import sys
sys.path.insert(0, '/Users/josh/Desktop/econstats/qa')
from qa_base import evaluate_queries

QUERIES = [
    "consumer spending",
    "retail sales",
    "consumer sentiment",
    "consumer confidence",
    "spending",
    "consumption",
    "personal spending",
    "consumer",
    "michigan consumer sentiment",
    "savings rate",
    "personal savings",
    "consumer debt",
    "household debt",
    "credit card debt",
    "personal income",
    "disposable income",
]

if __name__ == "__main__":
    evaluate_queries(QUERIES, "Consumer", "/Users/josh/Desktop/econstats/qa/results_consumer.json")
