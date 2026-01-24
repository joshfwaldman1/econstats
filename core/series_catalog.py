"""
Unified Series Catalog - Single source of truth for all economic series.

Consolidates metadata from:
- 9 plan JSON files (query → series mappings)
- series_rag.py (115 curated series)
- dbnomics.py (international series)
- stocks.py (market series)
- QUERY_SERIES_ALIGNMENT in app.py
"""

import json
import os
from typing import Optional
from dataclasses import dataclass

# Get the agents directory path
AGENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents")


@dataclass
class SeriesMetadata:
    """Metadata for a single economic series."""

    id: str
    name: str
    source: str  # "fred", "dbnomics", "polymarket"
    category: str  # "employment", "inflation", "gdp", etc.
    display: str  # "rate" (show as-is), "yoy_pct" (transform to YoY), "level"

    # Optional fields
    description: str = ""
    keywords: list = None
    demographic: str = None  # For demographic-specific series
    dbnomics_id: str = None  # For DBnomics series
    measure_type: str = None  # "real", "nominal", "rate", "index"
    change_type: str = None  # "yoy", "qoq", "mom", "level"
    frequency: str = None  # "daily", "weekly", "monthly", "quarterly", "annual"


# Core US series with metadata
CORE_SERIES = {
    # Employment
    "UNRATE": SeriesMetadata(
        id="UNRATE",
        name="Unemployment Rate",
        source="fred",
        category="employment",
        display="rate",
        keywords=["unemployment", "jobless", "labor market"],
    ),
    "PAYEMS": SeriesMetadata(
        id="PAYEMS",
        name="Total Nonfarm Payrolls",
        source="fred",
        category="employment",
        display="change",  # Show MoM change
        keywords=["jobs", "payrolls", "employment"],
    ),
    # GDP
    "GDPC1": SeriesMetadata(
        id="GDPC1",
        name="Real GDP",
        source="fred",
        category="gdp",
        display="yoy_pct",  # Transform level to YoY growth
        measure_type="real",
        change_type="level",
        keywords=["gdp", "growth", "economy", "output"],
    ),
    "A191RL1Q225SBEA": SeriesMetadata(
        id="A191RL1Q225SBEA",
        name="Real GDP Growth (SAAR)",
        source="fred",
        category="gdp",
        display="rate",  # Already a growth rate
        keywords=["gdp growth", "quarterly gdp"],
    ),
    # Inflation
    "CPIAUCSL": SeriesMetadata(
        id="CPIAUCSL",
        name="Consumer Price Index",
        source="fred",
        category="inflation",
        display="yoy_pct",  # Transform index to YoY inflation
        measure_type="index",
        change_type="level",
        keywords=["inflation", "cpi", "prices"],
    ),
    "CPILFESL": SeriesMetadata(
        id="CPILFESL",
        name="Core CPI (Ex Food & Energy)",
        source="fred",
        category="inflation",
        display="yoy_pct",
        keywords=["core inflation", "core cpi"],
    ),
    "PCEPILFE": SeriesMetadata(
        id="PCEPILFE",
        name="Core PCE (Fed's Target)",
        source="fred",
        category="inflation",
        display="yoy_pct",
        keywords=["pce", "fed target", "core pce"],
    ),
    # Interest Rates
    "FEDFUNDS": SeriesMetadata(
        id="FEDFUNDS",
        name="Federal Funds Rate",
        source="fred",
        category="fed_rates",
        display="rate",
        keywords=["fed", "interest rates", "monetary policy"],
    ),
    "DGS10": SeriesMetadata(
        id="DGS10",
        name="10-Year Treasury Yield",
        source="fred",
        category="fed_rates",
        display="rate",
        keywords=["treasury", "yields", "bonds"],
    ),
    "MORTGAGE30US": SeriesMetadata(
        id="MORTGAGE30US",
        name="30-Year Mortgage Rate",
        source="fred",
        category="housing",
        display="rate",
        keywords=["mortgage", "housing", "rates"],
    ),
    # Housing
    "CSUSHPINSA": SeriesMetadata(
        id="CSUSHPINSA",
        name="Case-Shiller Home Price Index",
        source="fred",
        category="housing",
        display="yoy_pct",
        keywords=["home prices", "housing", "real estate"],
    ),
    "HOUST": SeriesMetadata(
        id="HOUST",
        name="Housing Starts",
        source="fred",
        category="housing",
        display="level",
        keywords=["housing starts", "construction", "new homes"],
    ),
}

# International series (DBnomics)
INTERNATIONAL_SERIES = {
    "eurozone_gdp": SeriesMetadata(
        id="eurozone_gdp",
        name="Eurozone GDP Growth (YoY)",
        source="dbnomics",
        category="gdp",
        display="rate",  # Already YoY growth
        dbnomics_id="Eurostat/namq_10_gdp/Q.CLV_PCH_SM.SCA.B1GQ.EA20",
        measure_type="real",
        change_type="yoy",
        keywords=["eurozone", "europe", "eu", "gdp"],
    ),
    "eurozone_inflation": SeriesMetadata(
        id="eurozone_inflation",
        name="Eurozone Inflation (HICP)",
        source="dbnomics",
        category="inflation",
        display="rate",
        dbnomics_id="Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA",
        change_type="yoy",
        keywords=["eurozone", "europe", "inflation", "hicp"],
    ),
    "uk_gdp": SeriesMetadata(
        id="uk_gdp",
        name="UK GDP Growth (YoY)",
        source="dbnomics",
        category="gdp",
        display="rate",
        dbnomics_id="BOE/GDP/IHYR.Q",
        measure_type="real",
        change_type="yoy",
        keywords=["uk", "britain", "gdp"],
    ),
    "china_gdp": SeriesMetadata(
        id="china_gdp",
        name="China GDP Growth (YoY)",
        source="dbnomics",
        category="gdp",
        display="rate",
        dbnomics_id="IMF/WEO:2024-10/CHN.NGDP_RPCH.pcent_change",
        measure_type="real",
        change_type="yoy",
        keywords=["china", "gdp", "asia"],
    ),
}

# Combined catalog
SERIES_CATALOG = {**CORE_SERIES, **INTERNATIONAL_SERIES}


def get_series_metadata(series_id: str) -> Optional[SeriesMetadata]:
    """Get metadata for a series by ID."""
    return SERIES_CATALOG.get(series_id)


def find_series_by_keyword(keyword: str) -> list[SeriesMetadata]:
    """Find series matching a keyword."""
    keyword_lower = keyword.lower()
    matches = []
    for series in SERIES_CATALOG.values():
        if series.keywords:
            if any(keyword_lower in kw.lower() for kw in series.keywords):
                matches.append(series)
    return matches


def find_series_by_category(category: str) -> list[SeriesMetadata]:
    """Find all series in a category."""
    return [s for s in SERIES_CATALOG.values() if s.category == category]


def load_query_plans() -> dict:
    """Load all pre-computed query plans from JSON files."""
    plans = {}
    plan_files = [
        "plans_employment.json",
        "plans_inflation.json",
        "plans_gdp.json",
        "plans_housing.json",
        "plans_fed_rates.json",
        "plans_consumer.json",
        "plans_demographics.json",
        "plans_economy_overview.json",
        "plans_trade_markets.json",
    ]

    for filename in plan_files:
        filepath = os.path.join(AGENTS_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                file_plans = json.load(f)
                plans.update(file_plans)

    return plans


# Load plans at module import
QUERY_PLANS = load_query_plans()


def find_plan_for_query(query: str) -> Optional[dict]:
    """Find a pre-computed plan for a query."""
    query_lower = query.lower().strip()

    # Exact match
    if query_lower in QUERY_PLANS:
        return QUERY_PLANS[query_lower]

    # Partial match
    for plan_query, plan in QUERY_PLANS.items():
        if plan_query in query_lower or query_lower in plan_query:
            return plan

    return None


# Quick test
if __name__ == "__main__":
    print(f"Loaded {len(SERIES_CATALOG)} series")
    print(f"Loaded {len(QUERY_PLANS)} query plans")

    print("\n=== Sample Series ===")
    for sid, meta in list(SERIES_CATALOG.items())[:5]:
        print(f"{sid}: {meta.name} ({meta.source}, {meta.display})")

    print("\n=== Sample Plans ===")
    for query in ["unemployment rate", "inflation", "gdp growth"]:
        plan = find_plan_for_query(query)
        if plan:
            print(f"'{query}' → {plan.get('series', [])}")
