#!/usr/bin/env python3
"""
Tests for the Query Understanding ("Thinking First") layer.

This module tests that queries are correctly understood and routed
before any data fetching happens.

Run: python tests/test_query_understanding.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.query_understanding import understand_query, get_routing_recommendation


def test_demographic_detection():
    """Test that demographic queries are correctly identified."""
    print("\n[TEST] Demographic Detection")
    print("-" * 40)

    test_cases = [
        ("How are Black workers doing?", ["black"]),
        ("Women unemployment rate", ["women"]),
        ("Hispanic labor force participation", ["hispanic"]),
        ("What is youth unemployment?", ["youth"]),
        ("How are veterans doing in the job market?", ["veteran"]),
    ]

    passed = 0
    for query, expected_demographics in test_cases:
        understanding = understand_query(query, verbose=False)
        actual = understanding.get('entities', {}).get('demographics', [])

        # Check if expected demographics are present (may have extras)
        found = all(d in actual for d in expected_demographics)
        status = "PASS" if found else "FAIL"
        print(f"  {status}: '{query}'")
        print(f"         Expected: {expected_demographics}, Got: {actual}")
        if found:
            passed += 1

    print(f"\n  Result: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_comparison_detection():
    """Test that comparison queries are correctly identified."""
    print("\n[TEST] Comparison Detection")
    print("-" * 40)

    test_cases = [
        ("US vs Eurozone GDP", True),
        ("Compare US and UK inflation", True),
        ("How does Black unemployment compare to overall?", True),
        ("What is the unemployment rate?", False),
        ("How is the economy doing?", False),
    ]

    passed = 0
    for query, expected_comparison in test_cases:
        understanding = understand_query(query, verbose=False)
        rec = get_routing_recommendation(understanding)
        actual = rec.get('use_comparison_router', False)

        status = "PASS" if actual == expected_comparison else "FAIL"
        print(f"  {status}: '{query}'")
        print(f"         Expected: {expected_comparison}, Got: {actual}")
        if actual == expected_comparison:
            passed += 1

    print(f"\n  Result: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_international_detection():
    """Test that international queries are correctly routed."""
    print("\n[TEST] International Detection")
    print("-" * 40)

    test_cases = [
        ("How is China's economy?", True),
        ("Eurozone inflation", True),
        ("UK unemployment rate", True),
        ("What is US GDP?", False),
        ("How are American workers doing?", False),
    ]

    passed = 0
    for query, expected_international in test_cases:
        understanding = understand_query(query, verbose=False)
        rec = get_routing_recommendation(understanding)
        actual = rec.get('use_international_data', False)

        status = "PASS" if actual == expected_international else "FAIL"
        print(f"  {status}: '{query}'")
        print(f"         Expected: {expected_international}, Got: {actual}")
        if actual == expected_international:
            passed += 1

    print(f"\n  Result: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_sector_detection():
    """Test that sector/industry queries are correctly identified."""
    print("\n[TEST] Sector Detection")
    print("-" * 40)

    test_cases = [
        ("Restaurant industry employment", ["restaurants"]),
        ("How is manufacturing doing?", ["manufacturing"]),
        ("Tech sector jobs", ["tech"]),
        ("Healthcare employment trends", ["healthcare"]),
    ]

    passed = 0
    for query, expected_sectors in test_cases:
        understanding = understand_query(query, verbose=False)
        actual = understanding.get('entities', {}).get('sectors', [])

        # Check if expected sectors are present
        found = all(s in actual for s in expected_sectors)
        status = "PASS" if found else "FAIL"
        print(f"  {status}: '{query}'")
        print(f"         Expected: {expected_sectors}, Got: {actual}")
        if found:
            passed += 1

    print(f"\n  Result: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_query_type_classification():
    """Test that query types are correctly classified."""
    print("\n[TEST] Query Type Classification")
    print("-" * 40)

    test_cases = [
        ("What is the Fed funds rate?", "factual"),
        ("How is the economy doing?", "analytical"),
        ("US vs Eurozone GDP", "comparison"),
        ("Will the Fed cut rates?", "forecast"),
    ]

    passed = 0
    for query, expected_type in test_cases:
        understanding = understand_query(query, verbose=False)
        actual = understanding.get('intent', {}).get('query_type', 'unknown')

        status = "PASS" if actual == expected_type else "FAIL"
        print(f"  {status}: '{query}'")
        print(f"         Expected: {expected_type}, Got: {actual}")
        if actual == expected_type:
            passed += 1

    print(f"\n  Result: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_pitfall_detection():
    """Test that pitfalls are correctly identified for demographic queries."""
    print("\n[TEST] Pitfall Detection")
    print("-" * 40)

    test_cases = [
        ("How are Black workers doing?", ["women", "UNRATE"]),  # Should warn about these
        ("Women's employment trends", ["Black", "Hispanic"]),    # Should warn about these
    ]

    passed = 0
    for query, should_mention in test_cases:
        understanding = understand_query(query, verbose=False)
        pitfalls = understanding.get('pitfalls', [])
        pitfalls_text = ' '.join(pitfalls).lower()

        # Check if any of the warning terms are mentioned
        found_any = any(term.lower() in pitfalls_text for term in should_mention)
        status = "PASS" if found_any else "FAIL"
        print(f"  {status}: '{query}'")
        print(f"         Should mention: {should_mention}")
        print(f"         Pitfalls: {pitfalls[:2] if pitfalls else 'None'}")
        if found_any:
            passed += 1

    print(f"\n  Result: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("QUERY UNDERSTANDING TESTS")
    print("=" * 60)

    results = {
        'demographic': test_demographic_detection(),
        'comparison': test_comparison_detection(),
        'international': test_international_detection(),
        'sector': test_sector_detection(),
        'query_type': test_query_type_classification(),
        'pitfalls': test_pitfall_detection(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_passed = sum(1 for v in results.values() if v)
    total_tests = len(results)

    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")

    print(f"\n  Overall: {total_passed}/{total_tests} test suites passed")
    print("=" * 60)

    return total_passed == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
