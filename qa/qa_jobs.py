#!/usr/bin/env python3
"""QA Agent: Jobs & Employment queries"""
import sys
sys.path.insert(0, '/Users/josh/Desktop/econstats/qa')
from qa_base import evaluate_queries

QUERIES = [
    "jobs",
    "job market",
    "employment",
    "unemployment",
    "unemployment rate",
    "how is the job market",
    "labor market",
    "hiring",
    "job growth",
    "job openings",
    "jolts",
    "payrolls",
    "nonfarm payrolls",
    "jobs report",
    "weekly jobless claims",
    "initial claims",
    "labor force participation",
    "prime age employment",
    "is the labor market tight",
    "underemployment",
    "u6 unemployment",
    "job quits",
    "quit rate",
    "layoffs",
    "full employment",
]

if __name__ == "__main__":
    evaluate_queries(QUERIES, "Jobs & Employment", "/Users/josh/Desktop/econstats/qa/results_jobs.json")
