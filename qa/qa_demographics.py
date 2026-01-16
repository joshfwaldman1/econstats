#!/usr/bin/env python3
"""QA Agent: Demographics queries - CRITICAL for testing aggregate vs demographic-specific"""
import sys
sys.path.insert(0, '/Users/josh/Desktop/econstats/qa')
from qa_base import evaluate_queries

QUERIES = [
    "women",
    "women employment",
    "women unemployment",
    "women in the workforce",
    "women labor force",
    "female employment",
    "female unemployment",
    "how are women doing in the economy",
    "working women",
    "gender employment gap",
    "men employment",
    "men unemployment",
    "black unemployment",
    "african american unemployment",
    "hispanic unemployment",
    "latino unemployment",
    "white unemployment",
    "youth unemployment",
    "teen unemployment",
    "older workers",
    "racial unemployment gap",
    "prime age workers",
]

if __name__ == "__main__":
    evaluate_queries(QUERIES, "Demographics", "/Users/josh/Desktop/econstats/qa/results_demographics.json")
