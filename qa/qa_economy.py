#!/usr/bin/env python3
"""QA Agent: Economy Overview & Recession queries"""
import sys
sys.path.insert(0, '/Users/josh/Desktop/econstats/qa')
from qa_base import evaluate_queries

QUERIES = [
    "how is the economy",
    "how is the economy doing",
    "economic overview",
    "state of the economy",
    "is the economy good",
    "is the economy bad",
    "us economy",
    "american economy",
    "economic outlook",
    "is there a recession",
    "are we in a recession",
    "recession risk",
    "recession indicators",
    "economic conditions",
    "economy 2024",
    "economy 2025",
    "soft landing",
    "hard landing",
    "economic forecast",
    "key economic indicators",
]

if __name__ == "__main__":
    evaluate_queries(QUERIES, "Economy Overview", "/Users/josh/Desktop/econstats/qa/results_economy.json")
