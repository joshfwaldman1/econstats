"""
Unified Data Catalog for EconStats.

This module provides a comprehensive catalog of all economic data series
across all data sources (FRED, Zillow, EIA, Alpha Vantage, DBnomics, Polymarket).
It enables unified search, discovery, and embedding generation for semantic search.

Architecture:
1. CatalogEntry dataclass defines unified schema for all series
2. UNIFIED_CATALOG dict aggregates all series from all sources
3. Search functions enable keyword/category-based discovery
4. Export function generates text for embedding-based semantic search

Usage:
    from core.unified_catalog import (
        search_catalog,
        get_series_for_category,
        list_categories,
        get_all_entries,
        export_for_embeddings,
        UNIFIED_CATALOG
    )

    # Search by keyword
    results = search_catalog("inflation housing rent")

    # Get all series in a category
    housing_series = get_series_for_category("housing")

    # Export for embedding generation
    embedding_data = export_for_embeddings()
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
import re


# =============================================================================
# UNIFIED SCHEMA
# =============================================================================

@dataclass
class CatalogEntry:
    """
    Unified schema for all economic data series across all sources.

    Attributes:
        id: Series identifier (unique within source, e.g., "UNRATE", "zillow_zori_national")
        name: Human-readable name for display
        source: Data source ("fred", "zillow", "eia", "alphavantage", "dbnomics", "polymarket")
        description: 1-2 sentence description optimized for semantic/vector search
        category: High-level category (e.g., "employment", "housing", "inflation")
        subcategory: More specific subcategory (e.g., "prices", "starts", "rent")
        keywords: List of search keywords for matching user queries
        frequency: Data frequency ("daily", "weekly", "monthly", "quarterly", "annual")
        unit: Unit of measurement ("percent", "dollars", "thousands", "index", etc.)
        display_as: How to display the data ("level", "yoy_pct", "mom_change", "rate")
        measure_type: Type of measurement ("real", "nominal", "rate", "index")
        change_type: Type of change ("level", "yoy", "qoq", "mom")
        fred_equivalent: FRED series ID if this series has an equivalent in FRED (for deduplication)
    """
    id: str
    name: str
    source: str
    description: str
    category: str
    subcategory: str
    keywords: List[str]
    frequency: str
    unit: str
    display_as: str = "level"
    measure_type: str = "nominal"
    change_type: str = "level"
    fred_equivalent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def get_search_text(self) -> str:
        """
        Generate combined text for semantic search / embedding.
        Combines name, description, keywords, and category info.
        """
        keyword_text = " ".join(self.keywords)
        return f"{self.name}. {self.description} Category: {self.category}, {self.subcategory}. Keywords: {keyword_text}"


# =============================================================================
# CATEGORY AND SUBCATEGORY MAPPINGS
# =============================================================================

# Standard categories for organizing all series
CATEGORIES = {
    "employment": "Jobs, labor market, unemployment, payrolls, wages",
    "housing": "Home prices, rents, housing starts, building permits, mortgage rates",
    "inflation": "Consumer prices, CPI, PCE, producer prices, cost of living",
    "gdp": "Economic growth, output, production, GDP components",
    "interest_rates": "Fed funds, treasury yields, mortgage rates, bond yields",
    "financial_markets": "Stocks, bonds, commodities, forex, volatility",
    "consumer": "Consumer spending, sentiment, retail sales, savings",
    "trade": "Imports, exports, trade balance, dollar index",
    "energy": "Oil, gas, electricity, energy prices and production",
    "government": "Fiscal policy, debt, deficits, government spending",
    "international": "Foreign economies, global indicators, cross-country comparisons",
    "fed_policy": "Federal Reserve policy, projections, dot plot, FOMC",
    "recession": "Recession indicators, economic cycles, leading indicators",
    "predictions": "Forward-looking market expectations, prediction markets",
}


# =============================================================================
# BUILD CATALOG FROM ALL SOURCES
# =============================================================================

def _build_fred_entries() -> Dict[str, CatalogEntry]:
    """
    Build catalog entries from FRED series catalog.

    Imports from agents/series_rag.py and converts to unified schema.
    """
    try:
        from agents.series_rag import FRED_SERIES_CATALOG
    except ImportError:
        FRED_SERIES_CATALOG = []

    entries = {}

    # Category mapping based on series characteristics
    def infer_category(series_id: str, name: str, desc: str) -> tuple:
        """Infer category and subcategory from series metadata."""
        name_lower = name.lower()
        desc_lower = desc.lower()
        combined = f"{name_lower} {desc_lower}"

        # Employment-related
        if any(term in combined for term in ["unemployment", "payroll", "employment", "jobs", "labor", "wage", "earning", "claims"]):
            if "wage" in combined or "earning" in combined:
                return "employment", "wages"
            elif "claims" in combined:
                return "employment", "claims"
            elif "unemployment" in combined:
                return "employment", "unemployment"
            else:
                return "employment", "jobs"

        # Housing
        if any(term in combined for term in ["housing", "home", "house", "mortgage", "rent", "shelter", "permit", "construction"]):
            if "mortgage" in combined:
                return "housing", "mortgage"
            elif "rent" in combined or "shelter" in combined:
                return "housing", "rent"
            elif "price" in combined or "value" in combined:
                return "housing", "prices"
            elif "start" in combined or "permit" in combined:
                return "housing", "construction"
            else:
                return "housing", "general"

        # Inflation
        if any(term in combined for term in ["cpi", "inflation", "price index", "pce", "deflator"]):
            if "core" in combined:
                return "inflation", "core"
            elif "food" in combined:
                return "inflation", "food"
            elif "energy" in combined or "gas" in combined:
                return "inflation", "energy"
            elif "shelter" in combined:
                return "inflation", "shelter"
            else:
                return "inflation", "headline"

        # GDP
        if any(term in combined for term in ["gdp", "production", "industrial", "capacity"]):
            return "gdp", "growth"

        # Interest rates
        if any(term in combined for term in ["treasury", "yield", "fed fund", "interest rate"]):
            if "mortgage" in combined:
                return "interest_rates", "mortgage"
            elif "spread" in combined:
                return "interest_rates", "spread"
            else:
                return "interest_rates", "treasuries"

        # Financial markets
        if any(term in combined for term in ["s&p", "dow", "nasdaq", "stock", "vix", "volatility", "equity"]):
            return "financial_markets", "equities"

        # Consumer
        if any(term in combined for term in ["consumer", "retail", "spending", "sentiment", "saving"]):
            if "sentiment" in combined or "confidence" in combined:
                return "consumer", "sentiment"
            elif "retail" in combined:
                return "consumer", "retail"
            else:
                return "consumer", "spending"

        # Trade
        if any(term in combined for term in ["trade", "export", "import", "dollar index", "exchange"]):
            return "trade", "balance"

        # Energy
        if any(term in combined for term in ["oil", "crude", "gas", "energy", "coal", "petroleum"]):
            return "energy", "prices"

        # Government
        if any(term in combined for term in ["debt", "deficit", "government", "federal", "fiscal"]):
            if "debt" in combined:
                return "government", "debt"
            else:
                return "government", "spending"

        # Fed policy
        if any(term in combined for term in ["fomc", "projection", "dot plot", "sep"]):
            return "fed_policy", "projections"

        # Recession
        if any(term in combined for term in ["recession", "sahm", "leading"]):
            return "recession", "indicators"

        # Commodities
        if any(term in combined for term in ["gold", "silver", "commodity"]):
            return "financial_markets", "commodities"

        # Default
        return "other", "general"

    def infer_frequency(series_id: str, desc: str) -> str:
        """Infer frequency from series metadata."""
        desc_lower = desc.lower()
        if "daily" in desc_lower:
            return "daily"
        elif "weekly" in desc_lower:
            return "weekly"
        elif "quarterly" in desc_lower:
            return "quarterly"
        elif "annual" in desc_lower or "yearly" in desc_lower:
            return "annual"
        else:
            return "monthly"  # Default for most FRED series

    def infer_unit(name: str, desc: str) -> str:
        """Infer unit from series metadata."""
        combined = f"{name.lower()} {desc.lower()}"
        if "percent" in combined or "rate" in combined:
            return "percent"
        elif "dollar" in combined or "$" in combined or "price" in combined:
            return "dollars"
        elif "thousand" in combined:
            return "thousands"
        elif "million" in combined:
            return "millions"
        elif "billion" in combined:
            return "billions"
        elif "index" in combined:
            return "index"
        else:
            return "units"

    def infer_display(category: str, subcategory: str, name: str) -> str:
        """Infer how to display this series."""
        name_lower = name.lower()
        if "growth" in name_lower or "change" in name_lower:
            return "yoy_pct"
        elif category in ["employment", "gdp"] and "rate" not in name_lower:
            return "level"
        elif "rate" in name_lower or "percent" in name_lower:
            return "rate"
        else:
            return "level"

    def extract_keywords(name: str, desc: str) -> List[str]:
        """Extract keywords from series metadata."""
        combined = f"{name} {desc}".lower()
        # Remove common words
        stopwords = {"the", "a", "an", "of", "in", "for", "to", "and", "or", "is", "are", "was", "were", "be", "been", "has", "have", "had", "this", "that", "with"}
        words = re.findall(r'\b[a-z]+\b', combined)
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        return unique[:15]  # Limit to 15 keywords

    for series in FRED_SERIES_CATALOG:
        series_id = series.get("id", "")
        name = series.get("name", "")
        description = series.get("description", "")

        if not series_id or not name:
            continue

        category, subcategory = infer_category(series_id, name, description)
        frequency = infer_frequency(series_id, description)
        unit = infer_unit(name, description)
        display_as = infer_display(category, subcategory, name)
        keywords = extract_keywords(name, description)

        # Determine measure_type and change_type
        desc_lower = description.lower()
        name_lower = name.lower()

        if "real" in desc_lower or "inflation-adjusted" in desc_lower:
            measure_type = "real"
        elif "index" in desc_lower or "index" in name_lower:
            measure_type = "index"
        elif "rate" in name_lower:
            measure_type = "rate"
        else:
            measure_type = "nominal"

        if "year-over-year" in desc_lower or "yoy" in desc_lower:
            change_type = "yoy"
        elif "quarter-over-quarter" in desc_lower or "qoq" in desc_lower:
            change_type = "qoq"
        elif "month-over-month" in desc_lower or "mom" in desc_lower:
            change_type = "mom"
        else:
            change_type = "level"

        # Enhance description for better semantic search
        enhanced_desc = f"{description} This is a {frequency} {category} indicator from FRED (Federal Reserve Economic Data), published by BLS/BEA/Federal Reserve."

        entries[series_id] = CatalogEntry(
            id=series_id,
            name=name,
            source="fred",
            description=enhanced_desc,
            category=category,
            subcategory=subcategory,
            keywords=keywords,
            frequency=frequency,
            unit=unit,
            display_as=display_as,
            measure_type=measure_type,
            change_type=change_type,
        )

    return entries


def _build_zillow_entries() -> Dict[str, CatalogEntry]:
    """
    Build catalog entries from Zillow series catalog.
    """
    try:
        from agents.zillow import ZILLOW_SERIES
    except ImportError:
        ZILLOW_SERIES = {}

    entries = {}

    for series_id, info in ZILLOW_SERIES.items():
        name = info.get("name", series_id)
        description = info.get("description", "")
        frequency = info.get("frequency", "monthly")
        unit = info.get("units", "dollars")
        keywords = info.get("keywords", [])
        change_type = info.get("change_type", "level")
        measure_type = info.get("measure_type", "nominal")

        # Determine category and subcategory
        if "rent" in name.lower() or "zori" in series_id.lower():
            category = "housing"
            subcategory = "rent"
        elif "home value" in name.lower() or "zhvi" in series_id.lower():
            category = "housing"
            subcategory = "prices"
        else:
            category = "housing"
            subcategory = "general"

        # Determine display_as
        if "yoy" in series_id or change_type == "yoy":
            display_as = "yoy_pct"
        else:
            display_as = "level"

        # Enhance description for semantic search
        enhanced_desc = f"{description} This is a {frequency} housing market indicator from Zillow Research, tracking actual market {subcategory}. More timely than CPI shelter measures."

        entries[series_id] = CatalogEntry(
            id=series_id,
            name=name,
            source="zillow",
            description=enhanced_desc,
            category=category,
            subcategory=subcategory,
            keywords=keywords,
            frequency=frequency,
            unit=unit,
            display_as=display_as,
            measure_type=measure_type,
            change_type=change_type,
        )

    return entries


def _build_eia_entries() -> Dict[str, CatalogEntry]:
    """
    Build catalog entries from EIA series catalog.
    """
    try:
        from agents.eia import EIA_SERIES
    except ImportError:
        EIA_SERIES = {}

    entries = {}

    for series_id, info in EIA_SERIES.items():
        name = info.get("name", series_id)
        description = info.get("description", "")
        frequency = info.get("frequency", "weekly")
        unit = info.get("units", "units")
        keywords = info.get("keywords", [])
        change_type = info.get("change_type", "level")
        measure_type = info.get("measure_type", "nominal")
        fred_equivalent = info.get("fred_equivalent")

        # Determine subcategory
        name_lower = name.lower()
        if "crude" in name_lower or "oil" in name_lower:
            subcategory = "oil"
        elif "gasoline" in name_lower or "gas" in name_lower:
            subcategory = "gasoline"
        elif "natural gas" in name_lower:
            subcategory = "natural_gas"
        elif "electricity" in name_lower:
            subcategory = "electricity"
        elif "stock" in name_lower or "inventory" in name_lower:
            subcategory = "inventories"
        elif "production" in name_lower:
            subcategory = "production"
        else:
            subcategory = "general"

        # Enhance description for semantic search
        enhanced_desc = f"{description} This is a {frequency} energy indicator from the US Energy Information Administration (EIA). Provides timely data on US energy markets and prices."

        entries[series_id] = CatalogEntry(
            id=series_id,
            name=name,
            source="eia",
            description=enhanced_desc,
            category="energy",
            subcategory=subcategory,
            keywords=keywords,
            frequency=frequency,
            unit=unit,
            display_as="level",
            measure_type=measure_type,
            change_type=change_type,
            fred_equivalent=fred_equivalent,
        )

    return entries


def _build_alphavantage_entries() -> Dict[str, CatalogEntry]:
    """
    Build catalog entries from Alpha Vantage series catalog.
    """
    try:
        from agents.alphavantage import ALPHAVANTAGE_SERIES
    except ImportError:
        ALPHAVANTAGE_SERIES = {}

    entries = {}

    for series_id, info in ALPHAVANTAGE_SERIES.items():
        name = info.get("name", series_id)
        description = info.get("description", "")
        frequency = info.get("frequency", "daily")
        unit = info.get("units", "units")
        keywords = info.get("keywords", [])
        change_type = info.get("change_type", "level")
        measure_type = info.get("measure_type", "nominal")
        fred_equivalent = info.get("fred_equivalent")

        # Determine category and subcategory
        name_lower = name.lower()
        desc_lower = description.lower()

        if any(term in name_lower for term in ["spy", "qqq", "dia", "iwm", "s&p", "nasdaq", "dow", "russell"]):
            category = "financial_markets"
            subcategory = "equities"
        elif "vix" in name_lower or "volatility" in name_lower:
            category = "financial_markets"
            subcategory = "volatility"
        elif "treasury" in name_lower:
            category = "interest_rates"
            subcategory = "treasuries"
        elif "gdp" in name_lower:
            category = "gdp"
            subcategory = "growth"
        elif "cpi" in name_lower or "inflation" in name_lower:
            category = "inflation"
            subcategory = "headline"
        elif "unemployment" in name_lower:
            category = "employment"
            subcategory = "unemployment"
        elif "fed" in name_lower:
            category = "interest_rates"
            subcategory = "fed_funds"
        elif "sentiment" in name_lower:
            category = "consumer"
            subcategory = "sentiment"
        elif "retail" in name_lower:
            category = "consumer"
            subcategory = "retail"
        elif "payroll" in name_lower:
            category = "employment"
            subcategory = "jobs"
        elif "oil" in name_lower or "crude" in name_lower or "brent" in name_lower:
            category = "energy"
            subcategory = "oil"
        elif "natural gas" in name_lower:
            category = "energy"
            subcategory = "natural_gas"
        elif "gold" in name_lower:
            category = "financial_markets"
            subcategory = "commodities"
        elif "exchange" in name_lower or "forex" in name_lower or any(fx in name_lower for fx in ["eur", "usd", "jpy", "gbp"]):
            category = "trade"
            subcategory = "forex"
        elif "dollar" in name_lower and "index" in name_lower:
            category = "trade"
            subcategory = "forex"
        else:
            category = "financial_markets"
            subcategory = "general"

        # Enhance description for semantic search
        enhanced_desc = f"{description} This is a {frequency} financial market indicator from Alpha Vantage, providing real-time and historical market data."

        entries[series_id] = CatalogEntry(
            id=series_id,
            name=name,
            source="alphavantage",
            description=enhanced_desc,
            category=category,
            subcategory=subcategory,
            keywords=keywords,
            frequency=frequency,
            unit=unit,
            display_as="level",
            measure_type=measure_type,
            change_type=change_type,
            fred_equivalent=fred_equivalent,
        )

    return entries


def _build_dbnomics_entries() -> Dict[str, CatalogEntry]:
    """
    Build catalog entries from DBnomics international series catalog.
    """
    try:
        from agents.dbnomics import INTERNATIONAL_SERIES
    except ImportError:
        INTERNATIONAL_SERIES = {}

    entries = {}

    for series_id, info in INTERNATIONAL_SERIES.items():
        name = info.get("name", series_id)
        description = info.get("description", "")
        frequency = info.get("frequency", "annual")
        keywords = info.get("keywords", [])
        change_type = info.get("change_type", "level")
        measure_type = info.get("measure_type", "nominal")
        provider = info.get("provider", "DBnomics")

        # Determine category and subcategory
        if "gdp" in series_id or "gdp" in name.lower():
            category = "international"
            subcategory = "gdp"
            unit = "percent"
        elif "inflation" in series_id or "inflation" in name.lower() or "cpi" in name.lower():
            category = "international"
            subcategory = "inflation"
            unit = "percent"
        elif "unemployment" in series_id or "unemployment" in name.lower():
            category = "international"
            subcategory = "unemployment"
            unit = "percent"
        elif "rate" in series_id or "rate" in name.lower():
            category = "interest_rates"
            subcategory = "policy_rates"
            unit = "percent"
        else:
            category = "international"
            subcategory = "general"
            unit = "units"

        # Determine display_as
        if change_type == "yoy":
            display_as = "yoy_pct"
        else:
            display_as = "level"

        # Enhance description for semantic search with country/region context
        country_keywords = ["eurozone", "euro area", "uk", "britain", "japan", "china", "germany", "canada", "mexico", "india", "brazil", "ecb"]
        country_match = [kw for kw in country_keywords if kw in series_id.lower() or kw in name.lower()]
        country_context = country_match[0].title() if country_match else "International"

        enhanced_desc = f"{description} This is {country_context} economic data from {provider} via DBnomics. Enables cross-country economic comparisons."

        entries[series_id] = CatalogEntry(
            id=series_id,
            name=name,
            source="dbnomics",
            description=enhanced_desc,
            category=category,
            subcategory=subcategory,
            keywords=keywords,
            frequency=frequency,
            unit=unit,
            display_as=display_as,
            measure_type=measure_type,
            change_type=change_type,
        )

    return entries


def _build_polymarket_entries() -> Dict[str, CatalogEntry]:
    """
    Build catalog entries from Polymarket prediction markets.

    Note: Polymarket provides forward-looking predictions, not historical data.
    """
    try:
        from agents.polymarket import ECONOMIC_EVENTS
    except ImportError:
        ECONOMIC_EVENTS = {}

    entries = {}

    for slug, info in ECONOMIC_EVENTS.items():
        display_name = info.get("display_name", slug)
        category_type = info.get("category", "predictions")
        keywords = info.get("keywords", [])
        market_type = info.get("market_type", "binary")

        # Determine category and subcategory based on market category
        if category_type == "recession":
            category = "recession"
            subcategory = "predictions"
            description = f"Polymarket prediction market for US recession probability. Forward-looking indicator based on trader sentiment and betting activity. Market type: {market_type}."
        elif category_type == "gdp":
            category = "gdp"
            subcategory = "predictions"
            description = f"Polymarket prediction market for GDP growth. Forward-looking indicator based on trader sentiment. Market type: {market_type}."
        elif category_type == "fed":
            category = "fed_policy"
            subcategory = "predictions"
            description = f"Polymarket prediction market for Federal Reserve rate decisions. Forward-looking indicator for Fed policy. Market type: {market_type}."
        elif category_type == "tariffs":
            category = "trade"
            subcategory = "predictions"
            description = f"Polymarket prediction market for tariff policy outcomes. Forward-looking indicator for trade policy. Market type: {market_type}."
        else:
            category = "predictions"
            subcategory = category_type
            description = f"Polymarket prediction market: {display_name}. Forward-looking market-based forecast. Market type: {market_type}."

        entries[f"polymarket_{slug}"] = CatalogEntry(
            id=f"polymarket_{slug}",
            name=display_name,
            source="polymarket",
            description=description,
            category=category,
            subcategory=subcategory,
            keywords=keywords + ["polymarket", "prediction", "forecast", "betting", "odds"],
            frequency="real-time",
            unit="probability",
            display_as="probability",
            measure_type="probability",
            change_type="level",
        )

    return entries


# =============================================================================
# BUILD THE UNIFIED CATALOG
# =============================================================================

def _build_unified_catalog() -> Dict[str, CatalogEntry]:
    """
    Build the complete unified catalog by aggregating all sources.

    Returns:
        Dictionary mapping series_id to CatalogEntry for all sources.
    """
    catalog = {}

    # Add entries from each source
    # Order matters for deduplication - FRED first as primary source
    fred_entries = _build_fred_entries()
    catalog.update(fred_entries)

    zillow_entries = _build_zillow_entries()
    catalog.update(zillow_entries)

    eia_entries = _build_eia_entries()
    catalog.update(eia_entries)

    alphavantage_entries = _build_alphavantage_entries()
    catalog.update(alphavantage_entries)

    dbnomics_entries = _build_dbnomics_entries()
    catalog.update(dbnomics_entries)

    polymarket_entries = _build_polymarket_entries()
    catalog.update(polymarket_entries)

    return catalog


# Build the catalog at module load time
UNIFIED_CATALOG: Dict[str, CatalogEntry] = _build_unified_catalog()


# =============================================================================
# SEARCH FUNCTIONS
# =============================================================================

def search_catalog(query: str, max_results: int = 20) -> List[CatalogEntry]:
    """
    Search the unified catalog by keyword.

    Performs case-insensitive keyword matching across:
    - Series name
    - Description
    - Keywords
    - Category and subcategory

    Args:
        query: Search query string (can contain multiple words)
        max_results: Maximum number of results to return

    Returns:
        List of matching CatalogEntry objects, sorted by relevance score

    Example:
        >>> results = search_catalog("unemployment rate")
        >>> for entry in results[:5]:
        ...     print(f"{entry.source}: {entry.name}")
    """
    query_lower = query.lower()
    query_terms = query_lower.split()

    results = []

    for series_id, entry in UNIFIED_CATALOG.items():
        # Build searchable text
        searchable = (
            f"{entry.name} {entry.description} "
            f"{' '.join(entry.keywords)} "
            f"{entry.category} {entry.subcategory}"
        ).lower()

        # Score based on term matches
        score = 0
        for term in query_terms:
            if term in searchable:
                # Boost for exact matches in name or keywords
                if term in entry.name.lower():
                    score += 5
                elif term in entry.keywords:
                    score += 3
                else:
                    score += 1

        # Boost for category/subcategory match
        if query_lower in entry.category or query_lower in entry.subcategory:
            score += 2

        if score > 0:
            results.append((entry, score))

    # Sort by score descending, then by name
    results.sort(key=lambda x: (-x[1], x[0].name))

    return [entry for entry, score in results[:max_results]]


def get_series_for_category(category: str, subcategory: Optional[str] = None) -> List[CatalogEntry]:
    """
    Get all series in a specific category (and optionally subcategory).

    Args:
        category: Category name (e.g., "employment", "housing", "inflation")
        subcategory: Optional subcategory name (e.g., "wages", "rent", "core")

    Returns:
        List of CatalogEntry objects in the category

    Example:
        >>> housing_series = get_series_for_category("housing")
        >>> rent_series = get_series_for_category("housing", "rent")
    """
    results = []
    category_lower = category.lower()
    subcategory_lower = subcategory.lower() if subcategory else None

    for series_id, entry in UNIFIED_CATALOG.items():
        if entry.category.lower() == category_lower:
            if subcategory_lower is None or entry.subcategory.lower() == subcategory_lower:
                results.append(entry)

    # Sort by source (FRED first), then name
    source_order = {"fred": 0, "zillow": 1, "eia": 2, "alphavantage": 3, "dbnomics": 4, "polymarket": 5}
    results.sort(key=lambda x: (source_order.get(x.source, 99), x.name))

    return results


def list_categories() -> List[str]:
    """
    List all available categories in the catalog.

    Returns:
        Sorted list of unique category names

    Example:
        >>> categories = list_categories()
        >>> print(categories)
        ['consumer', 'employment', 'energy', 'financial_markets', ...]
    """
    categories = set()
    for entry in UNIFIED_CATALOG.values():
        categories.add(entry.category)
    return sorted(categories)


def list_subcategories(category: str) -> List[str]:
    """
    List all subcategories within a category.

    Args:
        category: Category name

    Returns:
        Sorted list of unique subcategory names in that category

    Example:
        >>> subcats = list_subcategories("employment")
        >>> print(subcats)
        ['claims', 'jobs', 'unemployment', 'wages']
    """
    subcategories = set()
    category_lower = category.lower()
    for entry in UNIFIED_CATALOG.values():
        if entry.category.lower() == category_lower:
            subcategories.add(entry.subcategory)
    return sorted(subcategories)


def get_all_entries() -> List[CatalogEntry]:
    """
    Get all entries in the catalog.

    Returns:
        List of all CatalogEntry objects

    Example:
        >>> all_entries = get_all_entries()
        >>> print(f"Total series: {len(all_entries)}")
    """
    return list(UNIFIED_CATALOG.values())


def get_entry_by_id(series_id: str) -> Optional[CatalogEntry]:
    """
    Get a specific catalog entry by series ID.

    Args:
        series_id: The series identifier

    Returns:
        CatalogEntry if found, None otherwise

    Example:
        >>> entry = get_entry_by_id("UNRATE")
        >>> print(entry.description)
    """
    return UNIFIED_CATALOG.get(series_id)


def get_entries_by_source(source: str) -> List[CatalogEntry]:
    """
    Get all entries from a specific data source.

    Args:
        source: Data source name ("fred", "zillow", "eia", "alphavantage", "dbnomics", "polymarket")

    Returns:
        List of CatalogEntry objects from that source

    Example:
        >>> zillow_entries = get_entries_by_source("zillow")
        >>> print(f"Zillow series: {len(zillow_entries)}")
    """
    source_lower = source.lower()
    return [entry for entry in UNIFIED_CATALOG.values() if entry.source.lower() == source_lower]


def get_series_with_fred_equivalent() -> Dict[str, str]:
    """
    Get mapping of non-FRED series to their FRED equivalents.

    Useful for deduplication or preferring FRED data when available.

    Returns:
        Dictionary mapping source series ID to FRED series ID

    Example:
        >>> equivalents = get_series_with_fred_equivalent()
        >>> print(equivalents.get("eia_wti_crude"))  # "DCOILWTICO"
    """
    equivalents = {}
    for series_id, entry in UNIFIED_CATALOG.items():
        if entry.fred_equivalent and entry.source != "fred":
            equivalents[series_id] = entry.fred_equivalent
    return equivalents


# =============================================================================
# EMBEDDING EXPORT
# =============================================================================

def export_for_embeddings() -> List[Dict[str, str]]:
    """
    Export catalog entries in format suitable for embedding generation.

    Returns list of dicts with:
    - id: Series identifier
    - text_for_embedding: Combined text optimized for semantic search

    The text_for_embedding combines:
    - Series name
    - Enhanced description
    - Keywords
    - Category and subcategory context

    Returns:
        List of dicts ready for embedding API calls

    Example:
        >>> embedding_data = export_for_embeddings()
        >>> for item in embedding_data[:3]:
        ...     print(f"{item['id']}: {item['text_for_embedding'][:100]}...")
    """
    results = []

    for series_id, entry in UNIFIED_CATALOG.items():
        # Build comprehensive text for embedding
        keyword_text = ", ".join(entry.keywords)

        text_for_embedding = (
            f"{entry.name}. "
            f"{entry.description} "
            f"Category: {entry.category}, subcategory: {entry.subcategory}. "
            f"Data source: {entry.source}. "
            f"Frequency: {entry.frequency}. "
            f"Keywords: {keyword_text}."
        )

        results.append({
            "id": series_id,
            "source": entry.source,
            "text_for_embedding": text_for_embedding,
        })

    return results


def get_catalog_stats() -> Dict[str, Any]:
    """
    Get statistics about the unified catalog.

    Returns:
        Dictionary with catalog statistics

    Example:
        >>> stats = get_catalog_stats()
        >>> print(f"Total series: {stats['total_series']}")
        >>> print(f"Sources: {stats['by_source']}")
    """
    stats = {
        "total_series": len(UNIFIED_CATALOG),
        "by_source": {},
        "by_category": {},
        "by_frequency": {},
    }

    for entry in UNIFIED_CATALOG.values():
        # Count by source
        stats["by_source"][entry.source] = stats["by_source"].get(entry.source, 0) + 1

        # Count by category
        stats["by_category"][entry.category] = stats["by_category"].get(entry.category, 0) + 1

        # Count by frequency
        stats["by_frequency"][entry.frequency] = stats["by_frequency"].get(entry.frequency, 0) + 1

    return stats


# =============================================================================
# MAIN / TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("EconStats Unified Data Catalog")
    print("=" * 70)

    # Get catalog stats
    stats = get_catalog_stats()
    print(f"\nTotal series in catalog: {stats['total_series']}")

    print("\nSeries by source:")
    for source, count in sorted(stats['by_source'].items(), key=lambda x: -x[1]):
        print(f"  {source}: {count}")

    print("\nSeries by category:")
    for category, count in sorted(stats['by_category'].items(), key=lambda x: -x[1]):
        print(f"  {category}: {count}")

    print("\n" + "-" * 70)
    print("Search Test: 'inflation housing rent'")
    print("-" * 70)
    results = search_catalog("inflation housing rent", max_results=10)
    for entry in results:
        print(f"  [{entry.source}] {entry.id}: {entry.name}")

    print("\n" + "-" * 70)
    print("Category Test: 'employment' series")
    print("-" * 70)
    employment_series = get_series_for_category("employment")
    print(f"  Found {len(employment_series)} employment series")
    for entry in employment_series[:5]:
        print(f"    [{entry.source}] {entry.id}: {entry.name}")

    print("\n" + "-" * 70)
    print("Embedding Export Sample")
    print("-" * 70)
    embedding_data = export_for_embeddings()
    print(f"  Total entries for embedding: {len(embedding_data)}")
    if embedding_data:
        sample = embedding_data[0]
        print(f"\n  Sample entry:")
        print(f"    ID: {sample['id']}")
        print(f"    Text: {sample['text_for_embedding'][:200]}...")

    print("\n" + "=" * 70)
    print("Catalog build complete!")
    print("=" * 70)
