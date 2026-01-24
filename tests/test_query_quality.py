#!/usr/bin/env python3
"""
Automated query quality tests for EconStats.

Run this script morning and evening to catch regressions.
Usage: python tests/test_query_quality.py
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import reasoning_query_plan, find_query_plan
from agents.query_router import smart_route_query

# =============================================================================
# TEST CASES
# =============================================================================

# Format: (query, expected_series, description)
# expected_series can be a list of required series or a callable that validates

DIRECT_MAPPING_TESTS = [
    ("What is the Fed funds rate?", ["FEDFUNDS"], "Fed rate should return FEDFUNDS"),
    ("interest rates", ["FEDFUNDS", "DGS10"], "Interest rates should include FEDFUNDS and treasuries"),
    ("core inflation", ["CPILFESL"], "Core inflation should return CPILFESL"),
    ("core cpi", ["CPILFESL"], "Core CPI should return CPILFESL"),
    ("mortgage rates", ["MORTGAGE30US"], "Mortgage rates should return MORTGAGE30US"),
    ("housing market", ["CSUSHPINSA", "HOUST"], "Housing market should include prices and starts"),
    ("Is a recession coming?", ["T10Y2Y", "GDPC1"], "Recession query should include yield curve and GDP"),
    ("GDP growth", ["GDPC1"], "GDP growth should return GDPC1"),
    ("unemployment rate", ["UNRATE"], "Unemployment should return UNRATE"),
    ("consumer sentiment", ["UMCSENT"], "Consumer sentiment should return UMCSENT"),
]

COMPARISON_TESTS = [
    ("US vs Eurozone GDP", {"fred": ["GDPC1"], "dbnomics": ["eurozone_gdp"]}, "Should return both US and Eurozone GDP"),
    ("Compare US and China growth", {"fred": ["GDPC1"], "dbnomics": ["china_gdp"]}, "Should return both US and China GDP"),
    ("US vs Europe inflation", {"fred": ["CPIAUCSL"], "dbnomics": ["eurozone_inflation"]}, "Should return both inflation measures"),
]

INTERNATIONAL_TESTS = [
    ("How is China's economy?", "dbnomics", ["china_gdp"], "China query should route to DBnomics"),
    ("Japan inflation", "dbnomics", ["japan_inflation"], "Japan inflation should route to DBnomics"),
    ("UK economy", "dbnomics", ["uk_gdp"], "UK query should route to DBnomics"),
]

# Series that should NEVER appear for certain queries (negative tests)
NEGATIVE_TESTS = [
    ("What is the Fed funds rate?", ["CPIAUCSL", "PCEPILFE", "BBKMGDP"], "Fed rate should NOT return inflation/GDP"),
    ("core inflation", ["PAYEMS", "UNRATE"], "Inflation query should NOT return employment"),
]


def run_tests():
    """Run all test suites and report results."""
    print("=" * 70)
    print(f"ECONSTATS QUERY QUALITY TESTS - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    total_tests = 0
    passed = 0
    failed = 0
    failures = []

    # Test 1: Direct Mappings
    print("\n[1/4] DIRECT MAPPING TESTS")
    print("-" * 40)
    for query, expected, description in DIRECT_MAPPING_TESTS:
        total_tests += 1
        result = reasoning_query_plan(query, verbose=False)
        series = result.get('series', [])

        # Check if all expected series are present
        missing = [s for s in expected if s not in series]
        if not missing:
            print(f"  PASS: {query}")
            passed += 1
        else:
            print(f"  FAIL: {query}")
            print(f"        Expected: {expected}")
            print(f"        Got: {series}")
            print(f"        Missing: {missing}")
            failed += 1
            failures.append((query, description, expected, series))

    # Test 2: Comparison Queries
    print("\n[2/4] COMPARISON TESTS")
    print("-" * 40)
    for query, expected, description in COMPARISON_TESTS:
        total_tests += 1
        result = smart_route_query(query)

        if not result.get('is_comparison'):
            print(f"  FAIL: {query}")
            print(f"        Not detected as comparison!")
            failed += 1
            failures.append((query, description, expected, result))
            continue

        series_to_fetch = result.get('series_to_fetch', {})
        fred = series_to_fetch.get('fred', [])
        dbnomics = series_to_fetch.get('dbnomics', [])

        fred_ok = all(s in fred for s in expected.get('fred', []))
        dbnomics_ok = all(s in dbnomics for s in expected.get('dbnomics', []))

        if fred_ok and dbnomics_ok:
            print(f"  PASS: {query}")
            passed += 1
        else:
            print(f"  FAIL: {query}")
            print(f"        Expected FRED: {expected.get('fred')}, Got: {fred}")
            print(f"        Expected DBnomics: {expected.get('dbnomics')}, Got: {dbnomics}")
            failed += 1
            failures.append((query, description, expected, {'fred': fred, 'dbnomics': dbnomics}))

    # Test 3: International Routing
    print("\n[3/4] INTERNATIONAL ROUTING TESTS")
    print("-" * 40)
    for query, expected_source, expected_series, description in INTERNATIONAL_TESTS:
        total_tests += 1
        result = smart_route_query(query)

        source = result.get('source', 'default')
        series = result.get('series', [])

        source_ok = source == expected_source
        series_ok = all(s in series for s in expected_series)

        if source_ok and series_ok:
            print(f"  PASS: {query}")
            passed += 1
        else:
            print(f"  FAIL: {query}")
            print(f"        Expected source: {expected_source}, Got: {source}")
            print(f"        Expected series: {expected_series}, Got: {series}")
            failed += 1
            failures.append((query, description, {'source': expected_source, 'series': expected_series}, result))

    # Test 4: Negative Tests (should NOT contain certain series)
    print("\n[4/4] NEGATIVE TESTS (should NOT contain)")
    print("-" * 40)
    for query, forbidden, description in NEGATIVE_TESTS:
        total_tests += 1
        result = reasoning_query_plan(query, verbose=False)
        series = result.get('series', [])

        found_forbidden = [s for s in forbidden if s in series]
        if not found_forbidden:
            print(f"  PASS: {query}")
            passed += 1
        else:
            print(f"  FAIL: {query}")
            print(f"        Should NOT contain: {forbidden}")
            print(f"        But found: {found_forbidden}")
            failed += 1
            failures.append((query, description, f"NOT {forbidden}", series))

    # Summary
    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed}/{total_tests} passed, {failed} failed")
    print("=" * 70)

    if failures:
        print("\nFAILURES:")
        for query, desc, expected, got in failures:
            print(f"\n  {query}")
            print(f"    {desc}")
            print(f"    Expected: {expected}")
            print(f"    Got: {got}")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
