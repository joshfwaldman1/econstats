#!/usr/bin/env python3
"""QA Agent: Interest Rates & Fed queries"""
import sys
sys.path.insert(0, '/Users/josh/Desktop/econstats/qa')
from qa_base import evaluate_queries

QUERIES = [
    "interest rates",
    "rates",
    "fed",
    "federal reserve",
    "fed funds rate",
    "federal funds rate",
    "fed policy",
    "monetary policy",
    "rate hikes",
    "rate cuts",
    "will the fed cut rates",
    "treasury yields",
    "10 year treasury",
    "2 year treasury",
    "yield curve",
    "inverted yield curve",
    "bond yields",
    "mortgage rates",
    "30 year mortgage",
    "borrowing costs",
]

if __name__ == "__main__":
    evaluate_queries(QUERIES, "Interest Rates & Fed", "/Users/josh/Desktop/econstats/qa/results_rates.json")
