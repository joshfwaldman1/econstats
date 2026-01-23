"""
Smart Query Router for EconStats.

Handles complex queries that span multiple data sources:
- Comparison queries (US vs Eurozone)
- Multi-region queries
- Indicator extraction

Uses a hybrid approach:
1. Rule-based detection for common patterns
2. LLM fallback for ambiguous queries
"""

import re
from typing import Optional

# Region mappings to data sources
REGIONS = {
    # US - use FRED
    "us": {"source": "fred", "name": "United States", "aliases": ["usa", "america", "american", "united states"]},

    # International - use DBnomics
    "eurozone": {"source": "dbnomics", "name": "Eurozone", "aliases": ["euro area", "euro zone", "eu", "europe", "european"]},
    "uk": {"source": "dbnomics", "name": "United Kingdom", "aliases": ["britain", "british", "england", "united kingdom"]},
    "japan": {"source": "dbnomics", "name": "Japan", "aliases": ["japanese"]},
    "china": {"source": "dbnomics", "name": "China", "aliases": ["chinese", "prc"]},
    "germany": {"source": "dbnomics", "name": "Germany", "aliases": ["german"]},
    "canada": {"source": "dbnomics", "name": "Canada", "aliases": ["canadian"]},
    "mexico": {"source": "dbnomics", "name": "Mexico", "aliases": ["mexican"]},
    "india": {"source": "dbnomics", "name": "India", "aliases": ["indian"]},
    "brazil": {"source": "dbnomics", "name": "Brazil", "aliases": ["brazilian"]},
}

# Indicator mappings to series
# CRITICAL: Metadata ensures apples-to-apples comparisons
#   - measure_type: "real" or "nominal" or "rate"
#   - change_type: "yoy", "qoq", "level"
#   - transform: what to do with FRED level data ("yoy_pct" = calculate YoY % change)
INDICATORS = {
    "gdp": {
        "keywords": ["gdp", "growth", "economic growth", "output", "economy"],
        "fred_series": ["GDPC1"],  # Real GDP (level in billions)
        # FRED metadata - GDPC1 is a level, must transform to YoY growth
        "fred_metadata": {
            "GDPC1": {
                "measure_type": "real",
                "change_type": "level",  # Raw data is level
                "transform": "yoy_pct",  # Transform to YoY % change for comparison
                "display_as": "yoy",     # After transform, it's YoY growth
            }
        },
        "dbnomics_series": {
            "eurozone": "eurozone_gdp",
            "uk": "uk_gdp",
            "japan": "japan_gdp",
            "china": "china_gdp",
            "germany": "germany_gdp",
            "canada": "canada_gdp",
            "mexico": "mexico_gdp",
            "india": "india_gdp",
            "brazil": "brazil_gdp",
        },
        # All DBnomics GDP series are already YoY real growth rates
        "comparison_type": "yoy_real",
    },
    "inflation": {
        "keywords": ["inflation", "cpi", "prices", "consumer prices"],
        "fred_series": ["CPIAUCSL"],  # CPI (level, index)
        "fred_metadata": {
            "CPIAUCSL": {
                "measure_type": "index",
                "change_type": "level",
                "transform": "yoy_pct",  # Transform to YoY % change
                "display_as": "yoy",
            }
        },
        "dbnomics_series": {
            "eurozone": "eurozone_inflation",
            "uk": "uk_inflation",
            "japan": "japan_inflation",
            "china": "china_inflation",
        },
        "comparison_type": "yoy_rate",
    },
    "unemployment": {
        "keywords": ["unemployment", "jobless", "jobs"],
        "fred_series": ["UNRATE"],  # Already a rate level
        "fred_metadata": {
            "UNRATE": {
                "measure_type": "rate",
                "change_type": "level",
                "transform": None,  # No transform needed, display as-is
                "display_as": "level",
            }
        },
        "dbnomics_series": {
            "eurozone": "eurozone_unemployment",
            "germany": "germany_unemployment",
        },
        "comparison_type": "level_rate",
    },
    "rates": {
        "keywords": ["interest rate", "rates", "fed", "central bank", "policy rate"],
        "fred_series": ["FEDFUNDS"],  # Already a rate level
        "fred_metadata": {
            "FEDFUNDS": {
                "measure_type": "rate",
                "change_type": "level",
                "transform": None,
                "display_as": "level",
            }
        },
        "dbnomics_series": {
            "eurozone": "ecb_rate",
            "uk": "uk_bank_rate",
        },
        "comparison_type": "level_rate",
    },
}

# Comparison keywords
COMPARISON_KEYWORDS = [
    "compared to", "vs", "versus", "compare", "comparison",
    "relative to", "against", "and", "between"
]


def is_comparison_query(query: str) -> bool:
    """Check if query is asking for a comparison between regions."""
    query_lower = query.lower()

    # Check for comparison keywords
    has_comparison_word = any(kw in query_lower for kw in COMPARISON_KEYWORDS)

    # Check if multiple regions mentioned
    regions_found = extract_regions(query)
    has_multiple_regions = len(regions_found) >= 2

    # Also treat "US and X" as comparison even without explicit comparison words
    return has_comparison_word or has_multiple_regions


def extract_regions(query: str) -> list[dict]:
    """
    Extract all regions mentioned in query.

    Returns list of dicts: [{"key": "us", "source": "fred", "name": "United States"}, ...]
    """
    query_lower = query.lower()
    found = []

    for region_key, info in REGIONS.items():
        # Check region key itself
        if region_key in query_lower:
            found.append({"key": region_key, **info})
            continue

        # Check aliases
        for alias in info.get("aliases", []):
            if alias in query_lower:
                found.append({"key": region_key, **info})
                break

    # Dedupe while preserving order
    seen = set()
    unique = []
    for r in found:
        if r["key"] not in seen:
            seen.add(r["key"])
            unique.append(r)

    return unique


def extract_indicator(query: str) -> Optional[dict]:
    """
    Extract the economic indicator being asked about.

    Returns dict with indicator info or None.
    """
    query_lower = query.lower()

    best_match = None
    best_score = 0

    for indicator_key, info in INDICATORS.items():
        score = 0
        for kw in info["keywords"]:
            if kw in query_lower:
                score += len(kw)  # Longer matches score higher

        if score > best_score:
            best_score = score
            best_match = {"key": indicator_key, **info}

    return best_match


def route_comparison_query(query: str) -> Optional[dict]:
    """
    Route a comparison query to appropriate data sources.

    Returns:
        {
            "is_comparison": True,
            "regions": [{"key": "us", ...}, {"key": "eurozone", ...}],
            "indicator": {"key": "gdp", ...},
            "series_to_fetch": {
                "fred": ["GDPC1"],
                "dbnomics": ["eurozone_gdp"]
            },
            "explanation": "Comparing US and Eurozone GDP growth."
        }
    """
    if not is_comparison_query(query):
        return None

    regions = extract_regions(query)
    indicator = extract_indicator(query)

    if len(regions) < 2:
        # If only one region mentioned, assume US is the other
        us_mentioned = any(r["key"] == "us" for r in regions)
        if not us_mentioned and regions:
            regions.insert(0, {"key": "us", **REGIONS["us"]})

    if not indicator:
        # Default to GDP for general economy comparisons
        indicator = {"key": "gdp", **INDICATORS["gdp"]}

    # Build series to fetch from each source
    fred_series = []
    dbnomics_series = []

    for region in regions:
        if region["source"] == "fred":
            fred_series.extend(indicator.get("fred_series", []))
        else:
            series_key = indicator.get("dbnomics_series", {}).get(region["key"])
            if series_key:
                dbnomics_series.append(series_key)

    if not fred_series and not dbnomics_series:
        return None

    region_names = [r["name"] for r in regions]
    indicator_name = indicator["key"].upper()

    return {
        "is_comparison": True,
        "regions": regions,
        "indicator": indicator,
        "series_to_fetch": {
            "fred": fred_series,
            "dbnomics": dbnomics_series,
        },
        "explanation": f"Comparing {' and '.join(region_names)} {indicator_name}.",
    }


def smart_route_query(query: str) -> dict:
    """
    Main entry point for smart query routing.

    Returns routing instructions for the query.
    """
    # 1. Check for comparison queries
    comparison = route_comparison_query(query)
    if comparison:
        return comparison

    # 2. Check for single international region
    regions = extract_regions(query)
    intl_regions = [r for r in regions if r["source"] == "dbnomics"]

    if intl_regions and not any(r["key"] == "us" for r in regions):
        # Pure international query
        indicator = extract_indicator(query)
        if indicator:
            dbnomics_series = []
            for region in intl_regions:
                series_key = indicator.get("dbnomics_series", {}).get(region["key"])
                if series_key:
                    dbnomics_series.append(series_key)

            if dbnomics_series:
                return {
                    "is_comparison": False,
                    "source": "dbnomics",
                    "series": dbnomics_series,
                    "explanation": f"{intl_regions[0]['name']} {indicator['key']}.",
                }

    # 3. Default: let existing logic handle it
    return {
        "is_comparison": False,
        "source": "default",
        "series": [],
        "explanation": None,
    }


# Quick test
if __name__ == "__main__":
    print("Query Router Tests\n" + "=" * 50)

    test_queries = [
        "how has growth in the US compared to Eurozone?",
        "US vs China GDP",
        "compare US and UK inflation",
        "how is the eurozone doing?",
        "Japan unemployment rate",
        "Fed rate vs ECB rate",
        "how is the economy?",  # Should fall through to default
    ]

    for q in test_queries:
        print(f"\nQuery: '{q}'")
        result = smart_route_query(q)
        print(f"  Comparison: {result.get('is_comparison')}")
        if result.get('series_to_fetch'):
            print(f"  FRED: {result['series_to_fetch'].get('fred', [])}")
            print(f"  DBnomics: {result['series_to_fetch'].get('dbnomics', [])}")
        elif result.get('series'):
            print(f"  Series: {result['series']}")
        print(f"  Explanation: {result.get('explanation')}")
