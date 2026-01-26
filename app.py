#!/usr/bin/env python3
"""
EconStats - Streamlit Economic Data Dashboard
Ask questions in plain English and get charts of economic data from FRED.
Incorporates economist intuitions for proper data selection and presentation.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.parse import urlencode, quote
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# Load environment variables from .env if available
try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

# Import ensemble query plan generator (optional, graceful fallback)
try:
    from agents.agent_ensemble import call_ensemble_for_app, generate_ensemble_description, suggest_missing_dimensions, validate_series_relevance, validate_presentation
    ENSEMBLE_AVAILABLE = True
except Exception:
    # Catch all exceptions (including KeyError on some Python versions)
    ENSEMBLE_AVAILABLE = False

# Import RAG-based series retrieval (recommended approach)
try:
    from agents.series_rag import rag_query_plan
    RAG_AVAILABLE = True
except Exception:
    # Catch all exceptions (including KeyError on some Python versions)
    RAG_AVAILABLE = False

# Import Polymarket prediction markets (forward-looking sentiment)
try:
    from agents.polymarket import (
        find_relevant_predictions,
        format_prediction_for_display,
        synthesize_prediction_narrative,
        format_predictions_box,
        get_predictions_for_query,
    )
    POLYMARKET_AVAILABLE = True
except Exception:
    POLYMARKET_AVAILABLE = False

# Import stock market query plans
try:
    from agents.stocks import find_market_plan, is_market_query, MARKET_SERIES
    STOCKS_AVAILABLE = True
except Exception:
    STOCKS_AVAILABLE = False

# Import economist reasoning (AI-first approach)
try:
    from core.economist_reasoning import reason_about_query
    REASONING_AVAILABLE = True
except Exception:
    REASONING_AVAILABLE = False

# Import query logger for learning from searches
try:
    from core.query_logger import log_query as log_query_detailed
    QUERY_LOGGING = True
except Exception:
    QUERY_LOGGING = False

# Import news context for dynamic explanations
try:
    from core.news_context import get_economic_context
    NEWS_CONTEXT_AVAILABLE = True
except Exception:
    NEWS_CONTEXT_AVAILABLE = False

# Import indicator context for rich economic interpretation
try:
    from core.indicator_context import (
        get_indicator_context,
        interpret_indicator,
        get_related_indicators,
        INDICATOR_CONTEXT,
    )
    INDICATOR_CONTEXT_AVAILABLE = True
except Exception:
    INDICATOR_CONTEXT_AVAILABLE = False

# Import DBnomics for international data (IMF, Eurostat, ECB, etc.)
try:
    from agents.dbnomics import find_international_plan, is_international_query, get_observations_dbnomics
    DBNOMICS_AVAILABLE = True
except Exception:
    DBNOMICS_AVAILABLE = False

# Import smart query router for comparison queries
try:
    from agents.query_router import smart_route_query, is_comparison_query
    QUERY_ROUTER_AVAILABLE = True
except Exception:
    QUERY_ROUTER_AVAILABLE = False

# Import Zillow for housing/rent market data
try:
    from agents.zillow import get_zillow_series, search_zillow_series, ZILLOW_SERIES, synthesize_housing_narrative
    ZILLOW_AVAILABLE = True
except Exception:
    ZILLOW_AVAILABLE = False

# Import EIA for energy data
try:
    from agents.eia import get_eia_series, search_eia_series, EIA_SERIES, synthesize_energy_narrative
    EIA_AVAILABLE = True
except Exception:
    EIA_AVAILABLE = False

# Import Alpha Vantage for stocks and economic data
try:
    from agents.alphavantage import get_alphavantage_series, search_alphavantage_series, ALPHAVANTAGE_SERIES, synthesize_market_narrative
    ALPHAVANTAGE_AVAILABLE = True
except Exception:
    ALPHAVANTAGE_AVAILABLE = False

# Import Fed SEP (Summary of Economic Projections) for FOMC forecasts and guidance
try:
    from agents.fed_sep import (
        is_sep_query,
        is_fed_related_query,
        get_sep_for_query,
        get_fed_guidance_for_query,
        format_sep_for_display,
        get_sep_series_data,
        get_current_fed_funds_rate,
        get_recent_fomc_summary,
        SEP_SERIES,
        FOMC_STATEMENT_SUMMARIES,
    )
    SEP_AVAILABLE = True
except Exception:
    SEP_AVAILABLE = False

# Import historical analogues for context (1994 soft landing, 2008 crisis, etc.)
try:
    from core.historical_analogues import get_analogue_summary, find_analogues
    ANALOGUES_AVAILABLE = True
except Exception:
    ANALOGUES_AVAILABLE = False

# Import health check indicators for "how is X doing?" queries
# This provides curated multi-dimensional indicator sets for entities like
# megacap firms, labor market, consumers, housing, etc.
try:
    from core.health_check_indicators import (
        route_health_check_query,
        is_health_check_query,
        detect_health_check_entity,
        get_health_check_series,
        HEALTH_CHECK_ENTITIES,
    )
    HEALTH_CHECK_AVAILABLE = True
except Exception:
    HEALTH_CHECK_AVAILABLE = False

# Import unified catalog for coverage checking
# This tells us if we have data for a query or need to show a proxy
try:
    from core.unified_catalog import (
        check_query_coverage,
        get_coverage_disclaimer,
        search_catalog,
        UNIFIED_CATALOG,
    )
    COVERAGE_CHECK_AVAILABLE = True
except Exception:
    COVERAGE_CHECK_AVAILABLE = False

# Import premium economist analysis for deeper insights
try:
    from core.economist_analysis import (
        get_premium_analysis,
        EconomistAnalysis,
        format_analysis_as_html,
    )
    PREMIUM_ANALYSIS_AVAILABLE = True
except Exception:
    PREMIUM_ANALYSIS_AVAILABLE = False

# Import recession scorecard for recession-related queries
try:
    from agents.recession_scorecard import (
        is_recession_query,
        build_recession_scorecard,
        format_scorecard_for_display,
    )
    RECESSION_SCORECARD_AVAILABLE = True
except Exception:
    RECESSION_SCORECARD_AVAILABLE = False

# Import temporal intent detection for COMPARE vs FILTER vs CURRENT handling
try:
    from core.temporal_intent import (
        detect_temporal_intent,
        TemporalIntent,
        NAMED_PERIODS,
    )
    from core.multi_period_fetcher import (
        fetch_multi_period_data,
        compute_comparison_metrics,
        MultiPeriodData,
    )
    from core.comparison_narrative import (
        generate_comparison_narrative,
        format_comparison_insight,
    )
    from core.intent_validator import (
        validate_data_matches_intent,
        self_correct_if_needed,
    )
    TEMPORAL_INTENT_AVAILABLE = True
except Exception as e:
    TEMPORAL_INTENT_AVAILABLE = False

# Import Query Understanding - "Thinking First" layer
# This deeply analyzes query intent BEFORE any routing decisions
try:
    from agents.query_understanding import understand_query, get_routing_recommendation
    QUERY_UNDERSTANDING_AVAILABLE = True
except Exception:
    QUERY_UNDERSTANDING_AVAILABLE = False


# =============================================================================
# CACHING LAYER
# =============================================================================
# Simple in-memory cache with TTL to avoid re-fetching the same data repeatedly.
# Economic data doesn't change frequently, so a 15-minute TTL is reasonable.

_api_cache = {}
_cache_ttl_seconds = 900  # 15 minutes


def _get_cache_key(func_name: str, *args, **kwargs) -> str:
    """
    Generate a cache key from function name and arguments.

    Args:
        func_name: Name of the function being cached
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        String cache key
    """
    # Sort kwargs for consistent key generation
    sorted_kwargs = sorted(kwargs.items())
    key_parts = [func_name, str(args), str(sorted_kwargs)]
    return ':'.join(key_parts)


def _get_from_cache(cache_key: str):
    """
    Retrieve data from cache if it exists and hasn't expired.

    Args:
        cache_key: Cache key to look up

    Returns:
        Cached data if valid, None otherwise
    """
    if cache_key in _api_cache:
        cached_data, cached_time = _api_cache[cache_key]
        age_seconds = (datetime.now() - cached_time).total_seconds()
        if age_seconds < _cache_ttl_seconds:
            return cached_data
        else:
            # Expired - remove from cache
            del _api_cache[cache_key]
    return None


def _set_cache(cache_key: str, data):
    """
    Store data in cache with current timestamp.

    Args:
        cache_key: Cache key to store under
        data: Data to cache
    """
    _api_cache[cache_key] = (data, datetime.now())


def _clear_expired_cache():
    """
    Remove expired entries from cache to prevent unbounded memory growth.
    Called periodically to clean up old entries.
    """
    now = datetime.now()
    expired_keys = [
        key for key, (_, cached_time) in _api_cache.items()
        if (now - cached_time).total_seconds() >= _cache_ttl_seconds
    ]
    for key in expired_keys:
        del _api_cache[key]


def get_cache_stats() -> dict:
    """
    Get statistics about the current cache state.

    Returns:
        Dictionary with cache statistics including total entries, expired entries, etc.
    """
    now = datetime.now()
    total_entries = len(_api_cache)
    expired_entries = sum(
        1 for _, (_, cached_time) in _api_cache.items()
        if (now - cached_time).total_seconds() >= _cache_ttl_seconds
    )
    valid_entries = total_entries - expired_entries

    return {
        'total_entries': total_entries,
        'valid_entries': valid_entries,
        'expired_entries': expired_entries,
        'ttl_seconds': _cache_ttl_seconds,
    }


def clear_all_cache():
    """
    Clear all cache entries. Useful for debugging or forcing fresh data.
    """
    global _api_cache
    _api_cache = {}


def parse_followup_command(query: str, previous_series: list = None) -> dict:
    """
    Parse common follow-up commands locally without calling Claude API.

    Returns dict with interpretation if recognized, or None if needs Claude.
    Handles: transformations, time ranges, chart types, combine/separate.
    """
    q = query.lower().strip()
    result = None

    # === TRANSFORMATION COMMANDS ===
    # Year-over-year
    if re.search(r'\b(yoy|year[\s-]*over[\s-]*year|yearly\s+change|annual\s+(%\s+)?change)\b', q):
        result = {
            'show_yoy': True,
            'show_mom': False,
            'show_avg_annual': False,
            'is_followup': True,
            'keep_previous_series': True,
            'explanation': 'Showing year-over-year percent change.',
        }

    # Month-over-month
    elif re.search(r'\b(mom|month[\s-]*over[\s-]*month|monthly\s+change)\b', q):
        result = {
            'show_yoy': False,
            'show_mom': True,
            'show_avg_annual': False,
            'is_followup': True,
            'keep_previous_series': True,
            'explanation': 'Showing month-over-month percent change.',
        }

    # Annual average
    elif re.search(r'\b(annual\s+average|yearly\s+average|average\s+annual|avg\s+annual|switch\s+to\s+(annual|yearly)|show\s+(annual|yearly))\b', q):
        result = {
            'show_yoy': False,
            'show_mom': False,
            'show_avg_annual': True,
            'is_followup': True,
            'keep_previous_series': True,
            'explanation': 'Showing annual averages.',
        }

    # Percent change from start of chart
    elif re.search(r'\b(percent|%|pct)\s*(change)?\s*(from|since)\s*(start|beginning|first)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'pct_change_from_start': True,
            'explanation': 'Showing percent change from start of chart period.',
        }

    # Cumulative change
    elif re.search(r'\bcumulative\s*(change|growth)?\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'pct_change_from_start': True,
            'explanation': 'Showing cumulative percent change from start.',
        }

    # Back to raw/original
    elif re.search(r'\b(raw\s+data|original|actual\s+(data|values)|back\s+to\s+(level|normal)|remove\s+transformation)\b', q):
        result = {
            'show_yoy': False,
            'show_mom': False,
            'show_avg_annual': False,
            'is_followup': True,
            'keep_previous_series': True,
            'explanation': 'Showing original values.',
        }

    # === TIME RANGE COMMANDS ===
    # "last N years" or "zoom to N years"
    elif match := re.search(r'\b(last|past|zoom\s+to|show)\s+(\d+)\s+years?\b', q):
        years = int(match.group(2))
        # Validate: 1-100 years is reasonable
        years = max(1, min(years, 100))
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': years,
            'explanation': f'Showing last {years} years.',
        }

    # "since YYYY"
    elif match := re.search(r'\bsince\s+(\d{4})\b', q):
        start_year = int(match.group(1))
        current_year = datetime.now().year
        # Validate: year must be 1900-current and result in positive years
        if 1900 <= start_year <= current_year:
            years = current_year - start_year + 1
            result = {
                'is_followup': True,
                'keep_previous_series': True,
                'years_override': years,
                'explanation': f'Showing data since {start_year}.',
            }
        else:
            # Invalid year - ignore the temporal reference
            pass

    # "all data" / "all time" / "max data" / "full chart"
    elif re.search(r'\b(all\s+(available\s+)?(data|time|history)|full\s+(history|chart)|max\s+(data|chart|history)|show\s+everything|complete\s+history)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': None,  # None means all available data
            'explanation': 'Showing all available data.',
        }

    # "zoom in" / "zoom out"
    elif re.search(r'\bzoom\s*(in|closer)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': 2,
            'explanation': 'Zooming in to last 2 years.',
        }
    elif re.search(r'\bzoom\s*(out|back)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': 20,
            'explanation': 'Zooming out to 20 years.',
        }

    # "pre-covid" / "pre-pandemic" / "before 2020"
    elif re.search(r'\b(pre[\s-]?(covid|pandemic|2020)|before\s+(covid|pandemic|the\s+pandemic|2020))\b', q):
        years_from_2017 = datetime.now().year - 2017 + 1
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': years_from_2017,
            'filter_end_date': '2020-02-29',
            'explanation': 'Showing pre-COVID data (through February 2020).',
        }

    # "during covid" / "pandemic period"
    elif re.search(r'\b(during\s+(covid|pandemic|the\s+pandemic)|covid\s+era|pandemic\s+period)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': 5,
            'filter_start_date': '2020-03-01',
            'filter_end_date': '2021-12-31',
            'explanation': 'Showing COVID pandemic period (March 2020 - December 2021).',
        }

    # "post-covid" / "after pandemic" / "recovery period"
    elif re.search(r'\b(post[\s-]?(covid|pandemic)|after\s+(covid|pandemic|the\s+pandemic)|recovery\s+period)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': 4,
            'filter_start_date': '2022-01-01',
            'explanation': 'Showing post-COVID recovery period (2022 onward).',
        }

    # "great recession" / "financial crisis" / "2008 recession"
    elif re.search(r'\b(great\s+recession|during\s+(?:the\s+)?recession|2008\s+(?:recession|crisis)|financial\s+crisis)\b', q):
        current_year = datetime.now().year
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': current_year - 2007 + 1,
            'filter_start_date': '2007-12-01',
            'filter_end_date': '2009-06-30',
            'explanation': 'Showing Great Recession period (December 2007 - June 2009).',
        }

    # Normalize/index to 100 (for comparing different scales)
    elif re.search(r'\b(normalize|index(\s+to\s+100)?|rebase|scale\s+to\s+(100|same))\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'normalize': True,
            'explanation': 'Indexing all series to 100 at start of chart for comparison.',
        }

    # === CHART COMMANDS ===
    # Combine charts
    elif re.search(r'\b(combine|single\s+chart|one\s+chart|same\s+chart|overlay)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'combine_chart': True,
            'explanation': 'Combining series on one chart.',
        }

    # Separate charts
    elif re.search(r'\b(separate|split|individual\s+chart)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'combine_chart': False,
            'explanation': 'Showing series on separate charts.',
        }

    # Bar chart
    elif re.search(r'\b(bar\s+chart|show\s+as\s+bar|switch\s+to\s+bar)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'chart_type': 'bar',
            'explanation': 'Switching to bar chart.',
        }

    # Line chart
    elif re.search(r'\b(line\s+chart|show\s+as\s+line|switch\s+to\s+line)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'chart_type': 'line',
            'explanation': 'Switching to line chart.',
        }

    # Area chart
    elif re.search(r'\b(area\s+chart|show\s+as\s+area|switch\s+to\s+area|filled\s+chart)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'chart_type': 'area',
            'explanation': 'Switching to area chart.',
        }

    # === ADD SERIES (common keywords) ===
    # Quick keyword matches for adding common series
    add_match = re.search(r'\b(add|include|overlay|compare\s+(?:to|with)|what\s+about)\s+(.+?)(?:\s+to\s+(?:this|the\s+chart))?[?.!]?\s*$', q)
    if add_match and not result:
        hint = add_match.group(2).strip()
        # Map common terms to series
        series_map = {
            'inflation': ['CPIAUCSL'],
            'cpi': ['CPIAUCSL'],
            'core inflation': ['CPILFESL'],
            'core cpi': ['CPILFESL'],
            'pce': ['PCEPI'],
            'core pce': ['PCEPILFE'],
            'unemployment': ['UNRATE'],
            'jobs': ['PAYEMS'],
            'payrolls': ['PAYEMS'],
            'job openings': ['JTSJOL'],
            'gdp': ['A191RL1Q225SBEA', 'A191RO1Q156NBEA'],
            'gdp growth': ['A191RL1Q225SBEA'],
            'annual gdp': ['A191RL1A225NBEA'],
            'core gdp': ['PB0000031Q225SBEA'],
            'private demand': ['PB0000031Q225SBEA'],
            'fed funds': ['FEDFUNDS'],
            'fed funds rate': ['FEDFUNDS'],
            'federal funds': ['FEDFUNDS'],
            'interest rates': ['FEDFUNDS', 'DGS10'],
            '10 year': ['DGS10'],
            '2 year': ['DGS2'],
            'yield curve': ['T10Y2Y'],
            'treasury': ['DGS10', 'DGS2'],
            'treasury rates': ['DGS10', 'DGS2'],
            'mortgage': ['MORTGAGE30US'],
            'mortgage rates': ['MORTGAGE30US'],
            # Note: 'rates' alone is ambiguous - removed to avoid defaulting to wrong series
            # Instead, require more specific terms like 'interest rates', 'unemployment rate', etc.
            'unemployment rate': ['UNRATE'],
            'inflation rate': ['CPIAUCSL'],
            'wages': ['CES0500000003'],
            'wage growth': ['CES0500000003'],
            'oil': ['DCOILWTICO', 'DCOILBRENTEU'],
            'oil prices': ['DCOILWTICO', 'DCOILBRENTEU'],
            'gas': ['GASREGW'],
            'gas prices': ['GASREGW'],
            'housing': ['CSUSHPINSA'],
            'home prices': ['CSUSHPINSA'],
            'house prices': ['CSUSHPINSA'],
            'housing starts': ['HOUST'],
            'building permits': ['PERMIT'],
            'sentiment': ['UMCSENT'],
            'consumer sentiment': ['UMCSENT'],
            'confidence': ['UMCSENT'],
            'retail': ['RSXFS'],
            'retail sales': ['RSXFS'],
            'industrial production': ['INDPRO'],
            'consumer spending': ['PCE'],
            'personal income': ['PI'],
            'savings rate': ['PSAVERT'],
            'claims': ['ICSA'],
            'jobless claims': ['ICSA'],
        }

        for keyword, series_ids in series_map.items():
            if keyword in hint:
                result = {
                    'series': series_ids,
                    'is_followup': True,
                    'add_to_previous': True,
                    'combine_chart': True,
                    'explanation': f'Adding {keyword} to the chart.',
                }
                break

    # If we got a result, add the previous series if needed
    if result and previous_series:
        if result.get('keep_previous_series') and 'series' not in result:
            result['series'] = previous_series
        elif result.get('add_to_previous') and 'series' in result:
            # Combine with previous, avoiding duplicates
            combined = list(previous_series)
            for s in result['series']:
                if s not in combined:
                    combined.append(s)
            result['series'] = combined[:4]  # Max 4 series

    return result


def extract_temporal_filter(query: str) -> dict | None:
    """
    Extract temporal references from a query and return date filter parameters.

    Handles:
    - Year references: "inflation in 2022", "gdp during 2019"
    - Relative references: "last year", "this year", "past 2 years"
    - Period references: "pre-covid", "during the recession", "before 2020"

    Returns dict with filter params or None if no temporal reference found.
    """
    import re
    q = query.lower().strip()
    now = datetime.now()
    current_year = now.year

    # === Specific year reference ===
    # "in 2022", "during 2019", "for 2020", "2021 data"
    if match := re.search(r'\b(?:in|during|for|from)?\s*((?:19|20)\d{2})\b', q):
        year = int(match.group(1))
        # Validate year is not in the future and is reasonable (1950-current)
        if 1950 <= year <= current_year:
            return {
                'temporal_focus': f'{year}',
                'filter_start_date': f'{year}-01-01',
                'filter_end_date': f'{year}-12-31',
                'years_override': max(2, current_year - year + 2),
                'explanation': f'Showing data for {year}.',
            }
        elif year > current_year:
            # Future year requested - return warning
            return {
                'temporal_focus': f'{year} (future)',
                'invalid_temporal': True,
                'explanation': f'Note: {year} is in the future. Showing latest available data.',
            }

    # === Year range ===
    # "from 2018 to 2022", "between 2015 and 2020"
    if match := re.search(r'\b(?:from|between)\s*((?:19|20)\d{2})\s*(?:to|and|-)\s*((?:19|20)\d{2})\b', q):
        start_year = int(match.group(1))
        end_year = int(match.group(2))
        # Validate and fix inverted ranges
        if start_year > end_year:
            start_year, end_year = end_year, start_year  # Swap if inverted
        # Cap end year at current year
        end_year = min(end_year, current_year)
        if 1950 <= start_year <= current_year:
            return {
                'temporal_focus': f'{start_year}-{end_year}',
                'filter_start_date': f'{start_year}-01-01',
                'filter_end_date': f'{end_year}-12-31',
                'years_override': max(2, current_year - start_year + 2),
                'explanation': f'Showing data from {start_year} to {end_year}.',
            }

    # === Relative year references ===
    # "last year"
    if re.search(r'\blast\s+year\b', q):
        last_year = current_year - 1
        return {
            'temporal_focus': f'{last_year}',
            'filter_start_date': f'{last_year}-01-01',
            'filter_end_date': f'{last_year}-12-31',
            'years_override': 3,
            'explanation': f'Showing data for {last_year}.',
        }

    # "this year"
    if re.search(r'\bthis\s+year\b', q):
        return {
            'temporal_focus': f'{current_year}',
            'filter_start_date': f'{current_year}-01-01',
            'years_override': 2,
            'explanation': f'Showing data for {current_year} so far.',
        }

    # "past/last N years"
    if match := re.search(r'\b(?:past|last)\s+(\d+)\s+years?\b', q):
        n_years = int(match.group(1))
        return {
            'temporal_focus': f'past {n_years} years',
            'years_override': n_years,
            'explanation': f'Showing data for the past {n_years} years.',
        }

    # === Period references ===
    # "pre-covid", "before pandemic", "before 2020"
    if re.search(r'\b(pre[\s-]?(covid|pandemic|2020)|before\s+(covid|pandemic|the\s+pandemic|2020))\b', q):
        years_from_2017 = current_year - 2017 + 1
        return {
            'temporal_focus': 'pre-COVID',
            'filter_end_date': '2020-02-29',
            'years_override': years_from_2017,
            'explanation': 'Showing pre-COVID data (through February 2020).',
        }

    # "during covid", "pandemic period"
    if re.search(r'\b(during\s+(covid|pandemic|the\s+pandemic)|covid\s+era|pandemic\s+period)\b', q):
        return {
            'temporal_focus': 'COVID period',
            'filter_start_date': '2020-03-01',
            'filter_end_date': '2021-12-31',
            'years_override': 5,
            'explanation': 'Showing COVID pandemic period (March 2020 - December 2021).',
        }

    # "post-covid", "after pandemic"
    if re.search(r'\b(post[\s-]?(covid|pandemic)|after\s+(covid|pandemic|the\s+pandemic)|recovery\s+period)\b', q):
        return {
            'temporal_focus': 'post-COVID',
            'filter_start_date': '2022-01-01',
            'years_override': 4,
            'explanation': 'Showing post-COVID recovery period (2022 onward).',
        }

    # "during the recession", "great recession"
    if re.search(r'\b(great\s+recession|during\s+(?:the\s+)?recession|2008\s+(?:recession|crisis)|financial\s+crisis)\b', q):
        return {
            'temporal_focus': 'Great Recession',
            'filter_start_date': '2007-12-01',
            'filter_end_date': '2009-06-30',
            'years_override': current_year - 2007 + 1,
            'explanation': 'Showing Great Recession period (December 2007 - June 2009).',
        }

    return None


# Load pre-computed query plans directly from JSON files (no merge step needed)
import glob

def load_query_plans():
    """Load all query plans from agents/*.json files."""
    plans = {}
    agents_dir = os.path.join(os.path.dirname(__file__), 'agents')
    for plan_file in glob.glob(os.path.join(agents_dir, 'plans_*.json')):
        try:
            with open(plan_file, 'r') as f:
                plans.update(json.load(f))
        except Exception as e:
            print(f"Warning: Could not load {plan_file}: {e}")
    return plans

QUERY_PLANS = load_query_plans()

# Smart query matching with normalization and fuzzy matching
import difflib

def normalize_query(query: str) -> str:
    """Normalize a query for better matching."""
    q = query.lower().strip()
    # Remove common filler phrases
    fillers = [
        r'^what is\s+', r'^what are\s+', r'^show me\s+', r'^show\s+',
        r'^tell me about\s+', r'^how is\s+', r'^how are\s+',
        r'^what\'s\s+', r'^whats\s+', r'^give me\s+',
        r'^can you show\s+', r'^i want to see\s+',
        r'\?$', r'\.+$', r'\s+the\s+', r'^the\s+'
    ]
    for filler in fillers:
        q = re.sub(filler, ' ', q)
    # Collapse whitespace and strip
    q = ' '.join(q.split()).strip()
    return q

# Synonym mappings: alternate phrasings -> canonical query terms
QUERY_SYNONYMS = {
    # Unemployment synonyms
    'jobless rate': 'unemployment',
    'joblessness': 'unemployment',
    'out of work': 'unemployment',
    'unemployment rate': 'unemployment',
    'u3': 'unemployment',
    'u6': 'u6 unemployment',
    'jobs report': 'employment',
    'jobless': 'unemployment',
    'unemployed': 'unemployment',
    'looking for work': 'unemployment',
    'cant find a job': 'unemployment',
    'no jobs': 'unemployment',
    'layoffs': 'unemployment',
    'getting fired': 'unemployment',
    'job losses': 'unemployment',
    'people losing jobs': 'unemployment',

    # Inflation synonyms
    'price increases': 'inflation',
    'cost of living': 'inflation',
    'consumer prices': 'cpi',
    'price index': 'cpi',
    'price growth': 'inflation',
    'prices': 'inflation',
    'everything expensive': 'inflation',
    'things cost more': 'inflation',
    'groceries': 'food inflation',
    'food prices': 'food inflation',
    'grocery prices': 'food inflation',
    'supermarket prices': 'food inflation',
    'eggs': 'food inflation',
    'milk prices': 'food inflation',
    'gas prices': 'gasoline',
    'fuel prices': 'gasoline',
    'petrol prices': 'gasoline',
    'at the pump': 'gasoline',
    'filling up': 'gasoline',
    'sticker shock': 'inflation',
    'shrinkflation': 'inflation',

    # Jobs/employment synonyms
    'job growth': 'jobs',
    'employment growth': 'jobs',
    'hiring': 'jobs',
    'payroll': 'payrolls',
    'nonfarm payrolls': 'payrolls',
    'job market': 'labor market',
    'labour market': 'labor market',
    'jobs': 'employment',
    'work': 'employment',
    'workers': 'employment',
    'workforce': 'labor force',
    'working': 'employment',
    'getting hired': 'employment',
    'job openings': 'jolts',
    'help wanted': 'jolts',
    'positions available': 'jolts',
    'vacancies': 'jolts',
    'quit rate': 'quits',
    'people quitting': 'quits',
    'the great resignation': 'quits',

    # GDP synonyms
    'economic growth': 'gdp',
    'economy': 'economic outlook',
    'growth rate': 'gdp growth',
    'gdp growth rate': 'gdp growth',
    'economy doing': 'economic outlook',
    'how we doing': 'economic outlook',
    'are we in a recession': 'recession risk',
    'recession coming': 'recession risk',
    'economic slowdown': 'recession risk',
    'soft landing': 'economic outlook',
    'hard landing': 'recession risk',
    'output': 'gdp',
    'production': 'industrial production',
    'manufacturing': 'industrial production',
    'factories': 'industrial production',

    # Interest rate synonyms
    'fed funds': 'fed funds rate',
    'federal funds': 'fed funds rate',
    'interest rates': 'rates',
    'borrowing costs': 'rates',
    'mortgage': 'mortgage rates',
    'home loan rates': 'mortgage rates',
    'interest': 'rates',
    'the fed': 'federal reserve',
    'powell': 'federal reserve',
    'jerome powell': 'federal reserve',
    'fomc': 'federal reserve',
    'rate hike': 'fed funds rate',
    'rate cut': 'fed funds rate',
    'raising rates': 'fed funds rate',
    'cutting rates': 'fed funds rate',
    'prime rate': 'rates',
    'apr': 'rates',
    'credit card rates': 'rates',
    'car loan rates': 'auto loan rates',
    'auto rates': 'auto loan rates',

    # Wages synonyms
    'pay': 'wages',
    'earnings': 'wages',
    'salaries': 'wages',
    'compensation': 'wages',
    'real wages': 'wages adjusted for inflation',
    'wage growth': 'wages',
    'paycheck': 'wages',
    'paychecks': 'wages',
    'income': 'wages',
    'take home pay': 'wages',
    'hourly pay': 'wages',
    'minimum wage': 'wages',
    'how much people make': 'wages',
    'what people earn': 'wages',
    'salary growth': 'wages',
    'raises': 'wages',

    # Housing synonyms
    'home prices': 'housing prices',
    'house prices': 'housing prices',
    'real estate': 'housing',
    'property prices': 'housing prices',
    'housing costs': 'shelter inflation',
    'rent costs': 'rent inflation',
    'housing expenses': 'shelter inflation',
    'home affordability': 'housing affordability',
    'rent': 'housing',
    'renting': 'rent inflation',
    'apartment prices': 'rent inflation',
    'apartment costs': 'rent inflation',
    'buying a house': 'housing',
    'buying a home': 'housing',
    'home buying': 'housing',
    'housing market': 'housing',
    'can i afford a house': 'housing affordability',
    'home ownership': 'housing',
    'new homes': 'housing starts',
    'home construction': 'housing starts',
    'building permits': 'housing permits',

    # Natural language queries
    'is the economy growing': 'economic growth',
    'is the economy good': 'economic outlook',
    'how is the economy': 'economic outlook',
    'whats happening with': 'economic outlook',
    'what about': 'economic outlook',
    'tell me about': 'economic outlook',
    'show me': 'economic outlook',
    'give me': 'economic outlook',

    # Stock market and investment synonyms
    'stock market': 'stocks',
    'equities': 'stocks',
    's&p': 'sp500',
    's&p 500': 'sp500',
    'bond yields': 'treasury yields',
    'yield curve': 'treasury spread',
    'recession': 'recession risk',
    'downturn': 'recession risk',
    'consumer spending': 'consumption',
    'retail': 'retail sales',
    'the market': 'stocks',
    'wall street': 'stocks',
    'dow': 'stocks',
    'nasdaq': 'stocks',
    'my 401k': 'stocks',
    'retirement account': 'stocks',
    'portfolio': 'stocks',
    'investing': 'stocks',
    'bonds': 'treasury yields',
    'treasuries': 'treasury yields',
    't-bills': 'treasury yields',
    'treasury bills': 'treasury yields',
    'treasury bonds': 'treasury yields',

    # Consumer and spending synonyms
    'spending': 'consumption',
    'shopping': 'retail sales',
    'buying stuff': 'retail sales',
    'consumer confidence': 'consumer sentiment',
    'how people feel': 'consumer sentiment',
    'are people spending': 'consumption',
    'credit cards': 'consumer credit',
    'household debt': 'consumer credit',
    'people in debt': 'consumer credit',
    'saving': 'personal savings',
    'savings rate': 'personal savings',
    'are people saving': 'personal savings',

    # Trade and international synonyms
    'imports': 'trade',
    'exports': 'trade',
    'trade deficit': 'trade',
    'trade war': 'tariffs',
    'china trade': 'trade',
    'tariffs': 'trade',
    'global trade': 'trade',
    'foreign trade': 'trade',
    'dollar': 'exchange rates',
    'currency': 'exchange rates',
    'strong dollar': 'exchange rates',
    'weak dollar': 'exchange rates',

    # Energy and commodities synonyms
    'oil': 'oil prices',
    'crude': 'oil prices',
    'crude oil': 'oil prices',
    'oil price': 'oil prices',
    'barrel of oil': 'oil prices',
    'energy prices': 'energy inflation',
    'electricity': 'energy inflation',
    'power prices': 'energy inflation',
    'utilities': 'energy inflation',
    'gold': 'gold prices',
    'gold price': 'gold prices',
    'commodities': 'commodity prices',

    # Common misspellings and variations
    'unemplyment': 'unemployment',
    'unemployement': 'unemployment',
    'infation': 'inflation',
    'inflaton': 'inflation',
    'intrest': 'interest',
    'intreset': 'interest',
    'mortage': 'mortgage',
    'morgage': 'mortgage',
    'reccession': 'recession',
    'recesion': 'recession',
    'econimic': 'economic',
    'econmic': 'economic',
}

def apply_synonyms(query: str) -> str:
    """Apply synonym mappings to normalize query terms.

    Uses word-boundary matching to avoid corrupting substrings.
    E.g., 'pay' -> 'wages' should NOT corrupt 'payrolls' -> 'wagesrolls'.
    """
    import re
    q = query.lower().strip()
    # Check for exact match first
    if q in QUERY_SYNONYMS:
        return QUERY_SYNONYMS[q]
    # Sort synonyms by length (longest first) to match multi-word phrases before single words
    sorted_synonyms = sorted(QUERY_SYNONYMS.items(), key=lambda x: len(x[0]), reverse=True)
    # Check if query contains a synonym phrase (with word boundaries)
    for synonym, canonical in sorted_synonyms:
        # Use word boundary regex to avoid substring corruption
        # \b matches word boundary (start/end of word)
        pattern = r'\b' + re.escape(synonym) + r'\b'
        if re.search(pattern, q):
            q = re.sub(pattern, canonical, q)
    return q

# Demographic keywords for routing queries to correct demographic group
# Using word-boundary matching to avoid false positives (e.g., "policewomen" matching "men")
DEMOGRAPHIC_KEYWORDS = {
    # Race/Ethnicity
    'black': 'black', 'african american': 'black', 'african-american': 'black',
    'hispanic': 'hispanic', 'latino': 'hispanic', 'latina': 'hispanic',
    'asian': 'asian',
    'white': 'white',
    # Gender
    'women': 'women', 'female': 'women', "women's": 'women', 'woman': 'women',
    'men': 'men', 'male': 'men', "men's": 'men',
    # Age
    'youth': 'youth', 'teen': 'youth', 'young': 'youth', 'teenager': 'youth',
    'older': 'older', 'senior': 'older', 'elderly': 'older',
    'prime age': 'prime age', 'prime-age': 'prime age',
    # Nativity
    'immigrant': 'immigrant', 'foreign-born': 'immigrant', 'foreign born': 'immigrant',
    # Veterans (was missing!)
    'veteran': 'veteran', 'veterans': 'veteran',
    # Disabled (was missing!)
    'disabled': 'disabled', 'disability': 'disabled',
}

def extract_demographic_groups(query: str) -> list[str]:
    """
    Extract ALL demographic groups from query (not just the first).

    Returns list of canonical demographic group names.
    Uses word-boundary matching to avoid false positives.

    Examples:
    - "Black women workers" → ['black', 'women']
    - "Hispanic immigrants" → ['hispanic', 'immigrant']
    - "unemployment rate" → []
    """
    import re
    query_lower = query.lower()
    found_groups = set()

    # Sort by keyword length (longest first) to match multi-word phrases first
    sorted_keywords = sorted(DEMOGRAPHIC_KEYWORDS.items(), key=lambda x: len(x[0]), reverse=True)

    for keyword, group in sorted_keywords:
        # Use word boundaries to avoid substring false positives
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, query_lower):
            found_groups.add(group)

    return list(found_groups)


def extract_demographic_group(query: str) -> str | None:
    """
    Extract PRIMARY demographic group from query for routing.
    Returns the first canonical demographic group name, or None if no demographic detected.

    For compound demographics like "Black women", use extract_demographic_groups() instead.
    This function exists for backward compatibility with routing logic.
    """
    groups = extract_demographic_groups(query)
    return groups[0] if groups else None


# US States for geographic detection
US_STATES = {
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york',
    'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon',
    'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
    'west virginia', 'wisconsin', 'wyoming', 'dc', 'district of columbia'
}

US_REGIONS = {'midwest', 'northeast', 'south', 'west', 'pacific', 'mountain', 'southeast', 'southwest'}


def detect_geographic_scope(query: str) -> dict:
    """
    Detect if query asks about a specific state or region.

    Returns dict with:
    - type: 'national', 'state', or 'region'
    - name: The detected geographic name (or 'US' for national)
    """
    query_lower = query.lower()

    # Check for states
    for state in US_STATES:
        if state in query_lower:
            # Avoid false positive: "Georgia" could be the country
            if state == 'georgia' and 'country' in query_lower:
                continue
            return {'type': 'state', 'name': state}

    # Check for regions
    for region in US_REGIONS:
        if region in query_lower:
            return {'type': 'region', 'name': region}

    return {'type': 'national', 'name': 'US'}


def get_smart_date_range(query: str, default_years: int = 8) -> int | None:
    """
    Determine smart date range based on query content.

    Returns:
        Number of years to show, or None for all available data.

    Queries about historical events or long-term trends should show more data.
    Most queries benefit from focused recent data (default 8 years).
    """
    q = query.lower()

    # Queries that should show ALL available data
    if any(pattern in q for pattern in [
        'all time', 'all data', 'full history', 'max data', 'complete history',
        'since 1950', 'since 1960', 'since 1970', 'since 1980',
        'historical trend', 'long-term trend', 'long term trend',
        'over the decades', 'over decades',
    ]):
        return None  # All data

    # Queries that need more context (15-20 years)
    if any(pattern in q for pattern in [
        'great recession', '2008', 'financial crisis', 'housing crisis',
        'compared to', 'comparison', 'vs pre-pandemic', 'before covid',
        'over the years', 'historically', 'history of',
        'long-run', 'long run', 'long-term', 'long term', 'secular trend',
    ]):
        return 20

    # Queries about specific recent periods (keep default)
    # "how is the economy", "current inflation", etc. → 8 years is good

    return default_years


def strip_question_words(query: str) -> str:
    """
    Strip question words and phrases from the beginning of a query.
    This helps with matching queries like "what is the unemployment rate" to "unemployment".
    """
    q = query.lower().strip()
    # Question patterns to strip (order matters - longer patterns first)
    question_patterns = [
        r'^what has been happening with\s+',
        r'^what is happening with\s+',
        r'^what\'s happening with\s+',
        r'^can you tell me about\s+',
        r'^tell me about\s+',
        r'^can you show me\s+',
        r'^i want to see\s+',
        r'^i\'d like to see\s+',
        r'^please show me\s+',
        r'^what is the\s+',
        r'^what are the\s+',
        r'^what\'s the\s+',
        r'^how is the\s+',
        r'^how are the\s+',
        r'^why is the\s+',
        r'^why are the\s+',
        r'^where is the\s+',
        r'^when is the\s+',
        r'^show me the\s+',
        r'^what is\s+',
        r'^what are\s+',
        r'^what\'s\s+',
        r'^whats\s+',
        r'^how is\s+',
        r'^how are\s+',
        r'^why is\s+',
        r'^why are\s+',
        r'^show me\s+',
        r'^show\s+',
        r'^give me\s+',
    ]
    for pattern in question_patterns:
        q = re.sub(pattern, '', q)
    # Also strip trailing question marks and punctuation
    q = re.sub(r'[\?\.\!]+$', '', q)
    return q.strip()


def calculate_word_overlap_score(query_words: set, plan_key: str) -> float:
    """
    Calculate word overlap score between query and plan key.
    Returns a score from 0 to 1 based on how many words overlap.
    """
    plan_words = set(plan_key.lower().split())
    if not query_words or not plan_words:
        return 0.0
    # Count matching words
    matching = query_words & plan_words
    if not matching:
        return 0.0
    # Score based on proportion of plan words that match (rewards specific matches)
    # Also consider proportion of query words that match (rewards relevance)
    plan_coverage = len(matching) / len(plan_words)
    query_coverage = len(matching) / len(query_words)
    # Weighted average - plan coverage matters more (we want to match the plan)
    return 0.6 * plan_coverage + 0.4 * query_coverage


def find_query_plan(query: str, threshold: float = 0.65) -> dict | None:
    """
    Find the best matching query plan using normalization and fuzzy matching.
    Returns the plan dict if found, None otherwise.

    Matching strategies (in order):
    1. Exact match on original/normalized/synonym-mapped query
    2. Plan synonym list matching
    3. Demographic-aware matching
    4. Keyword extraction and boosting (inflation, prices, job market, etc.)
    5. Partial phrase matching ("tight job market" -> "job market")
    6. Word overlap scoring
    7. Fuzzy matching with dynamic threshold (lower for short queries)
    8. Key term extraction fallback
    """
    if not QUERY_PLANS:
        return None

    # Normalize the input query
    normalized = normalize_query(query)
    original_lower = query.lower().strip()

    # Strip question words for better matching
    question_stripped = strip_question_words(original_lower)

    # Apply synonym mappings (e.g., "jobless rate" -> "unemployment")
    synonym_mapped = apply_synonyms(normalized)

    # Also apply synonyms to question-stripped version
    synonym_mapped_stripped = apply_synonyms(question_stripped)

    # 1. Exact match on original (fastest)
    if original_lower in QUERY_PLANS:
        return QUERY_PLANS[original_lower]

    # 2. Exact match on normalized
    if normalized in QUERY_PLANS:
        return QUERY_PLANS[normalized]

    # 2b. Exact match on synonym-mapped query
    if synonym_mapped in QUERY_PLANS:
        return QUERY_PLANS[synonym_mapped]

    # 2c. Exact match on question-stripped version
    if question_stripped in QUERY_PLANS:
        return QUERY_PLANS[question_stripped]

    # 2d. Exact match on synonym-mapped question-stripped version
    if synonym_mapped_stripped in QUERY_PLANS:
        return QUERY_PLANS[synonym_mapped_stripped]

    # 3. Check synonyms - some plans have a "synonyms" list for alternate names
    for plan_key, plan in QUERY_PLANS.items():
        synonyms = plan.get('synonyms', [])
        if original_lower in synonyms or normalized in synonyms or question_stripped in synonyms:
            return plan
        # Also check if query is a fuzzy match to any synonym
        for syn in synonyms:
            if difflib.SequenceMatcher(None, normalized, syn).ratio() > 0.65:
                return plan

    # 3.5 Demographic-aware matching - CRITICAL to prevent cross-demographic confusion
    # e.g., "Black workers" should NOT match "women doing in economy"
    query_demographic = extract_demographic_group(query)
    all_queries = list(QUERY_PLANS.keys())

    if query_demographic:
        # Filter plans to only those with the SAME demographic group
        demographic_queries = [q for q in all_queries if extract_demographic_group(q) == query_demographic]
        if demographic_queries:
            # Try fuzzy match within demographic-specific plans only
            matches = difflib.get_close_matches(normalized, demographic_queries, n=1, cutoff=0.5)
            if matches:
                return QUERY_PLANS[matches[0]]
            # If no fuzzy match, return shortest matching plan (most specific)
            demographic_queries.sort(key=len)
            return QUERY_PLANS[demographic_queries[0]]

    # === SMART MATCHING STRATEGIES ===

    # 4. Keyword extraction and boosting
    # If query contains specific keywords, boost related plans
    keyword_boosts = {
        # Inflation-related keywords
        'inflation': ['inflation', 'cpi', 'pce', 'prices', 'price index'],
        'prices': ['inflation', 'cpi', 'pce', 'prices', 'price index', 'shelter inflation', 'food inflation', 'energy inflation'],
        'cost of living': ['inflation', 'cpi', 'real wages'],
        'expensive': ['inflation', 'cpi', 'prices'],
        'costly': ['inflation', 'cpi', 'prices'],
        # Job market keywords
        'job market': ['labor market', 'jobs', 'employment', 'unemployment', 'payrolls'],
        'tight labor': ['labor market', 'unemployment', 'job openings'],
        'hiring': ['jobs', 'payrolls', 'job openings', 'employment'],
        'layoffs': ['unemployment', 'initial claims', 'jobs'],
        'workers': ['employment', 'labor market', 'wages'],
        # Housing keywords
        'housing': ['housing', 'home prices', 'housing starts', 'mortgage rates'],
        'home': ['housing', 'home prices', 'housing starts', 'mortgage rates'],
        'rent': ['rent inflation', 'shelter inflation', 'housing'],
        'mortgage': ['mortgage rates', 'housing'],
        # Fed/rates keywords
        'fed': ['fed funds rate', 'fed', 'interest rates', 'monetary policy'],
        'interest': ['rates', 'fed funds rate', 'treasury yields', 'mortgage rates'],
        'rates': ['rates', 'fed funds rate', 'treasury yields', 'mortgage rates'],
    }

    query_words_set = set(normalized.split())
    query_stripped_words = set(question_stripped.split())

    # Check for keyword boosts
    for keyword, boost_terms in keyword_boosts.items():
        if keyword in normalized or keyword in question_stripped:
            # Find plans that match any of the boost terms
            boosted_plans = []
            for plan_key in all_queries:
                plan_lower = plan_key.lower()
                for boost_term in boost_terms:
                    if boost_term in plan_lower:
                        boosted_plans.append(plan_key)
                        break
            if boosted_plans:
                # Filter out demographic mismatches
                if not query_demographic:
                    boosted_plans = [p for p in boosted_plans if not extract_demographic_group(p)]
                if boosted_plans:
                    # Find best fuzzy match among boosted plans
                    best = difflib.get_close_matches(normalized, boosted_plans, n=1, cutoff=0.4)
                    if best:
                        return QUERY_PLANS[best[0]]

    # 5. Partial phrase matching
    # "tight job market" should match "job market", "current labor market" should match "labor market"
    key_phrases = ['job market', 'labor market', 'job openings', 'wage growth', 'price growth',
                   'gdp growth', 'economic growth', 'housing market', 'stock market',
                   'interest rates', 'mortgage rates', 'treasury yields', 'initial claims',
                   'consumer spending', 'retail sales', 'home prices', 'housing prices']

    for phrase in key_phrases:
        if phrase in normalized or phrase in question_stripped:
            # Direct match to plan with this phrase
            if phrase in QUERY_PLANS:
                return QUERY_PLANS[phrase]
            # Find plans containing this phrase
            phrase_matches = [q for q in all_queries if phrase in q]
            if phrase_matches:
                # Filter out demographic mismatches
                if not query_demographic:
                    phrase_matches = [p for p in phrase_matches if not extract_demographic_group(p)]
                if phrase_matches:
                    # Return the most specific (shortest) match
                    phrase_matches.sort(key=len)
                    return QUERY_PLANS[phrase_matches[0]]

    # 6. Dynamic threshold based on query length
    # Short queries need less strict matching since there's less text to compare
    word_count = len(normalized.split())
    if word_count <= 2:
        dynamic_threshold = 0.50  # More lenient for short queries like "jobs" or "cpi data"
    elif word_count <= 4:
        dynamic_threshold = 0.55  # Slightly lenient for medium queries
    else:
        dynamic_threshold = threshold  # Use default for longer queries

    # 7. Word overlap scoring - find plans with best word overlap
    # This helps match "current unemployment rate data" to "unemployment"
    overlap_scores = []
    for plan_key in all_queries:
        # Skip demographic plans if query has no demographic
        plan_demographic = extract_demographic_group(plan_key)
        if not query_demographic and plan_demographic:
            continue
        score = calculate_word_overlap_score(query_stripped_words, plan_key)
        if score > 0.3:  # Minimum threshold for word overlap
            overlap_scores.append((plan_key, score))

    if overlap_scores:
        # Sort by score descending
        overlap_scores.sort(key=lambda x: x[1], reverse=True)
        # If top score is significantly better than others, use it
        if overlap_scores[0][1] >= 0.5:
            return QUERY_PLANS[overlap_scores[0][0]]
        # Otherwise, use fuzzy matching among top candidates
        top_candidates = [p[0] for p in overlap_scores[:5]]
        best = difflib.get_close_matches(normalized, top_candidates, n=1, cutoff=0.4)
        if best:
            return QUERY_PLANS[best[0]]

    # 8. Fuzzy match - find closest query in plans (for non-demographic queries)
    # Try matching against synonym-mapped query first
    matches = difflib.get_close_matches(synonym_mapped, all_queries, n=1, cutoff=dynamic_threshold)
    if matches:
        # Double-check: don't return a demographic plan for a non-demographic query
        match_demographic = extract_demographic_group(matches[0])
        if not query_demographic and match_demographic:
            pass  # Skip this match, it's a demographic plan for non-demographic query
        else:
            return QUERY_PLANS[matches[0]]

    # Try matching against normalized query
    matches = difflib.get_close_matches(normalized, all_queries, n=1, cutoff=dynamic_threshold)
    if matches:
        match_demographic = extract_demographic_group(matches[0])
        if not query_demographic and match_demographic:
            pass  # Skip demographic mismatch
        else:
            return QUERY_PLANS[matches[0]]

    # Try matching against original (for cases like typos)
    matches = difflib.get_close_matches(original_lower, all_queries, n=1, cutoff=dynamic_threshold)
    if matches:
        match_demographic = extract_demographic_group(matches[0])
        if not query_demographic and match_demographic:
            pass  # Skip demographic mismatch
        else:
            return QUERY_PLANS[matches[0]]

    # Try matching against question-stripped version
    matches = difflib.get_close_matches(question_stripped, all_queries, n=1, cutoff=dynamic_threshold)
    if matches:
        match_demographic = extract_demographic_group(matches[0])
        if not query_demographic and match_demographic:
            pass  # Skip demographic mismatch
        else:
            return QUERY_PLANS[matches[0]]

    # 9. Word-based matching for longer queries (fallback)
    # If query contains key economic terms, try to match those
    key_terms = ['inflation', 'unemployment', 'gdp', 'jobs', 'rates', 'housing',
                 'wages', 'recession', 'fed', 'cpi', 'pce', 'payrolls']
    for term in key_terms:
        if term in normalized:
            # Find all plans containing this term
            term_matches = [q for q in all_queries if term in q]
            if term_matches:
                # Filter out demographic mismatches
                if not query_demographic:
                    term_matches = [q for q in term_matches if not extract_demographic_group(q)]
                if term_matches:
                    # Find best match among these
                    best = difflib.get_close_matches(normalized, term_matches, n=1, cutoff=0.4)
                    if best:
                        return QUERY_PLANS[best[0]]
                    # If still no fuzzy match, return the simplest one (shortest)
                    term_matches.sort(key=len)
                    return QUERY_PLANS[term_matches[0]]

    return None


def is_holistic_query(query: str) -> bool:
    """
    Detect 'how is X doing?' style queries that need multi-dimensional answers.

    These queries should trigger augmented search (RAG + FRED) to provide
    comprehensive answers covering multiple dimensions rather than relying
    solely on pre-computed single-topic plans.

    Examples:
    - "How are restaurants doing?" -> True (needs employment + prices + wages)
    - "How is the economy for immigrants?" -> True (needs demographic-specific series)
    - "What about small businesses?" -> True (open-ended, needs multiple angles)
    - "What is the unemployment rate?" -> False (specific question, use precomputed)
    - "restaurant prices" -> False (narrow focus, precomputed is fine)
    """
    q = query.lower().strip()

    # Pattern 1: "how is/are X doing?"
    if q.startswith('how') and ('doing' in q or 'performing' in q or 'faring' in q or 'going' in q):
        return True

    # Pattern 2: "how is the economy/market for X?"
    if q.startswith('how') and ('economy' in q or 'market' in q or 'sector' in q or 'industry' in q):
        return True

    # Pattern 3: "what's happening with/in X?" (open-ended)
    if ("what's happening" in q or "what is happening" in q or
        "whats happening" in q or "what has been happening" in q):
        return True

    # Pattern 4: "tell me about X" / "explain X" / "give me X" (open-ended)
    if q.startswith('tell me about') or q.startswith('explain') or q.startswith('give me'):
        return True

    # Pattern 5: "overview of X" / "state of X" / "outlook"
    if 'overview' in q or 'state of' in q or 'outlook' in q or 'summary' in q:
        return True

    # Pattern 6: "what about X?" (open-ended follow-up style)
    if q.startswith('what about'):
        return True

    # Pattern 7: "how does X compare" / comparison queries
    if 'compare' in q or 'versus' in q or ' vs ' in q:
        return True

    # Pattern 8: Questions about specific demographics or groups
    # These need specialized series, not generic ones
    demographic_terms = ['immigrants', 'foreign-born', 'women', 'men', 'black',
                        'hispanic', 'asian', 'white', 'veterans', 'disabled',
                        'young', 'older', 'youth', 'teenage', 'seniors',
                        'native-born', 'college', 'high school']
    if any(term in q for term in demographic_terms):
        # But only if it's an open-ended question
        if q.startswith('how') or 'for ' in q or 'among ' in q or q.startswith('what'):
            return True

    # Pattern 9: Industry/sector open-ended queries
    industry_terms = ['restaurants', 'retail', 'manufacturing', 'construction',
                     'healthcare', 'tech', 'technology', 'hospitality', 'small business']
    if any(term in q for term in industry_terms):
        if q.startswith('how') or 'doing' in q or 'sector' in q:
            return True

    return False


# Google Sheets helper - reusable connection
def get_sheets_client():
    """Get authenticated Google Sheets client, or None if not configured."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        if not hasattr(st, 'secrets') or 'gcp_service_account' not in st.secrets:
            return None

        creds_dict = dict(st.secrets['gcp_service_account'])
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception:
        return None


# Query logging - logs ALL queries to Google Sheets
def log_query(query: str, series: list, source: str = "unknown"):
    """Log every query to Google Sheets for analytics."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    series_str = ', '.join(series) if series else ''

    # Always log to console
    print(f"[QUERY] {timestamp} | {query} | Series: {series_str} | Source: {source}")

    # Save to Google Sheets
    try:
        client = get_sheets_client()
        if not client:
            return True

        sheet_url = st.secrets.get('QUERY_LOG_SHEET_URL', '')
        if not sheet_url:
            # Fall back to feedback sheet if no separate query log sheet
            sheet_url = st.secrets.get('FEEDBACK_SHEET_URL', '')

        if sheet_url:
            spreadsheet = client.open_by_url(sheet_url)
            # Try to use "Queries" worksheet, create if doesn't exist
            try:
                sheet = spreadsheet.worksheet('Queries')
            except:
                # Worksheet doesn't exist, use first sheet
                sheet = spreadsheet.sheet1
            sheet.append_row([timestamp, query, series_str, source])
        return True
    except Exception as e:
        print(f"[QUERY LOG ERROR] {e}")
        return False


# Feedback storage - logs to console (visible in Streamlit Cloud logs)
# Optionally saves to Google Sheets if configured
def save_feedback(query: str, series: list, vote: str, comment: str = ""):
    """Save user feedback. Always logs to console, optionally to Google Sheets."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    series_str = ', '.join(series) if series else ''

    # Always log to console (visible in Streamlit Cloud "Manage app" → "Logs")
    print(f"[FEEDBACK] {timestamp} | {vote.upper()} | Query: {query} | Series: {series_str} | Comment: {comment}")

    # Try Google Sheets if configured
    try:
        client = get_sheets_client()
        if not client:
            return True

        sheet_url = st.secrets.get('FEEDBACK_SHEET_URL', '')
        if sheet_url:
            spreadsheet = client.open_by_url(sheet_url)
            # Try to use "Feedback" worksheet, fall back to first sheet
            try:
                sheet = spreadsheet.worksheet('Feedback')
            except:
                sheet = spreadsheet.sheet1
            sheet.append_row([timestamp, query, series_str, vote, comment])
        return True
    except Exception as e:
        # Google Sheets failed, but we already logged to console
        return True

# Configuration - use Streamlit secrets for deployment, env vars for local
def get_secret(key, default=''):
    """Get secret from Streamlit secrets or environment variable."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    return os.environ.get(key, default)

FRED_API_KEY = get_secret('FRED_API_KEY', 'c43c82548c611ec46800c51f898026d6')
FRED_BASE = 'https://api.stlouisfed.org/fred'
ANTHROPIC_API_KEY = get_secret('ANTHROPIC_API_KEY', '')

# Ensure API keys are available to ensemble module via environment
if ANTHROPIC_API_KEY:
    os.environ['ANTHROPIC_API_KEY'] = ANTHROPIC_API_KEY

# NBER Recession periods (peaks and troughs)
RECESSIONS = [
    {'start': '1929-08-01', 'end': '1933-03-01'},
    {'start': '1937-05-01', 'end': '1938-06-01'},
    {'start': '1945-02-01', 'end': '1945-10-01'},
    {'start': '1948-11-01', 'end': '1949-10-01'},
    {'start': '1953-07-01', 'end': '1954-05-01'},
    {'start': '1957-08-01', 'end': '1958-04-01'},
    {'start': '1960-04-01', 'end': '1961-02-01'},
    {'start': '1969-12-01', 'end': '1970-11-01'},
    {'start': '1973-11-01', 'end': '1975-03-01'},
    {'start': '1980-01-01', 'end': '1980-07-01'},
    {'start': '1981-07-01', 'end': '1982-11-01'},
    {'start': '1990-07-01', 'end': '1991-03-01'},
    {'start': '2001-03-01', 'end': '2001-11-01'},
    {'start': '2007-12-01', 'end': '2009-06-01'},
    {'start': '2020-02-01', 'end': '2020-04-01'},
]


def describe_recent_trend(dates: list, values: list, data_type: str = 'level', frequency: str = 'monthly', show_absolute_change: bool = False) -> str:
    """
    Describe what's happening in the recent data - the actual trend.
    Returns a human-readable sentence about the recent trend.

    Args:
        show_absolute_change: If True (e.g. for PAYEMS), show absolute changes not percentages
    """
    if not dates or not values or len(values) < 3:
        return ""

    # Determine how many data points to look at based on frequency
    if frequency == 'quarterly':
        lookback = min(4, len(values) - 1)  # Last 4 quarters
        period_name = "quarter"
    else:
        lookback = min(6, len(values) - 1)  # Last 6 months
        period_name = "month"

    recent_values = values[-lookback:]

    if len(recent_values) < 2:
        return ""

    # Calculate trend direction
    first_val = recent_values[0]
    last_val = recent_values[-1]

    if first_val == 0:
        return ""

    # Count consecutive direction changes
    up_count = sum(1 for i in range(1, len(recent_values)) if recent_values[i] > recent_values[i-1])
    down_count = sum(1 for i in range(1, len(recent_values)) if recent_values[i] < recent_values[i-1])
    flat_count = len(recent_values) - 1 - up_count - down_count

    # Check for consecutive moves in same direction
    consecutive_up = 0
    consecutive_down = 0
    for i in range(len(recent_values) - 1, 0, -1):
        if recent_values[i] > recent_values[i-1]:
            if consecutive_down == 0:
                consecutive_up += 1
            else:
                break
        elif recent_values[i] < recent_values[i-1]:
            if consecutive_up == 0:
                consecutive_down += 1
            else:
                break
        else:
            break

    # Describe the trend
    if data_type in ['rate', 'spread', 'growth_rate']:
        change = last_val - first_val
        if consecutive_up >= 3:
            return f"Has risen for {consecutive_up} consecutive {period_name}s, up {abs(change):.1f} pp over this period."
        elif consecutive_down >= 3:
            return f"Has declined for {consecutive_down} consecutive {period_name}s, down {abs(change):.1f} pp over this period."
        elif abs(change) >= 0.5:
            direction = "risen" if change > 0 else "fallen"
            return f"Has {direction} {abs(change):.1f} pp over the past {lookback} {period_name}s."
        elif flat_count >= lookback - 1:
            return f"Has been relatively stable over the past {lookback} {period_name}s."
    elif show_absolute_change:
        # Employment counts like PAYEMS - show absolute change in thousands, not %
        change = last_val - first_val
        # Format as full number (data is in thousands, so multiply by 1000)
        def format_change(val):
            full_val = abs(val) * 1000
            if full_val >= 1000000:
                return f"{full_val/1000000:.1f} million"
            else:
                return f"{full_val:,.0f}"

        if consecutive_up >= 3:
            return f"Has added jobs for {consecutive_up} consecutive {period_name}s, adding {format_change(change)} over this period."
        elif consecutive_down >= 3:
            return f"Has lost jobs for {consecutive_down} consecutive {period_name}s, shedding {format_change(change)} over this period."
        elif abs(change) >= 100:  # At least 100k change
            direction = "added" if change > 0 else "lost"
            return f"Has {direction} {format_change(change)} jobs over the past {lookback} {period_name}s."
        elif flat_count >= lookback - 1:
            return f"Has been relatively stable over the past {lookback} {period_name}s."
    else:
        pct_change = ((last_val - first_val) / abs(first_val)) * 100
        if consecutive_up >= 3:
            return f"Has risen for {consecutive_up} consecutive {period_name}s, up {abs(pct_change):.1f}% over this period."
        elif consecutive_down >= 3:
            return f"Has declined for {consecutive_down} consecutive {period_name}s, down {abs(pct_change):.1f}% over this period."
        elif abs(pct_change) >= 3:
            direction = "risen" if pct_change > 0 else "fallen"
            return f"Has {direction} {abs(pct_change):.1f}% over the past {lookback} {period_name}s."
        elif flat_count >= lookback - 1:
            return f"Has been relatively stable over the past {lookback} {period_name}s."

    return ""


def generate_narrative_context(dates: list, values: list, data_type: str = 'level', db_info: dict = None) -> dict:
    """
    Generate smart narrative context from time series data.
    Returns factual comparisons without prescriptive claims.

    Args:
        db_info: Optional dict with series metadata (cumulative, show_absolute_change, etc.)
    """
    if not dates or not values or len(values) < 2:
        return {}

    if db_info is None:
        db_info = {}

    context = {}
    latest = values[-1]
    latest_date = dates[-1]
    current_year = datetime.now().year
    show_absolute = db_info.get('show_absolute_change', False)

    try:
        # Helper: calculate average for a given year
        def year_average(year):
            year_vals = [v for d, v in zip(dates, values)
                        if d.startswith(str(year))]
            return sum(year_vals) / len(year_vals) if year_vals else None

        # Helper: format absolute change for employment data (data is in thousands)
        def format_job_diff(val):
            full_val = abs(val) * 1000
            if full_val >= 1000000:
                return f"{full_val/1000000:.1f} million"
            else:
                return f"{full_val:,.0f}"

        # 1. Compare to 2019 average (pre-COVID baseline)
        # Skip for employment counts (show_absolute) - comparing absolute levels is not meaningful
        # since employment naturally grows with population. Job GROWTH is what matters.
        avg_2019 = year_average(2019)
        if avg_2019 is not None and not show_absolute:
            if data_type in ['rate', 'spread', 'growth_rate']:
                diff = latest - avg_2019
                if abs(diff) >= 0.3:  # Meaningful difference for rates
                    direction = "above" if diff > 0 else "below"
                    context['vs_2019'] = f"{abs(diff):.1f} pp {direction} 2019 avg"
            elif avg_2019 != 0:
                pct_diff = ((latest - avg_2019) / abs(avg_2019)) * 100
                if abs(pct_diff) >= 3:  # Meaningful difference for levels
                    direction = "above" if pct_diff > 0 else "below"
                    context['vs_2019'] = f"{abs(pct_diff):.0f}% {direction} 2019 avg"

        # 2. Compare to prior full year average (e.g., 2024 if we're in 2025)
        # Skip for employment counts - comparing absolute levels to prior year average is not meaningful
        prior_year = current_year - 1
        latest_date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
        if latest_date_obj.year == current_year and latest_date_obj.month >= 3 and not show_absolute:
            avg_prior = year_average(prior_year)
            if avg_prior is not None:
                if data_type in ['rate', 'spread', 'growth_rate']:
                    diff = latest - avg_prior
                    if abs(diff) >= 0.2:
                        direction = "above" if diff > 0 else "below"
                        context['vs_prior_year'] = f"{abs(diff):.1f} pp {direction} {prior_year} avg"
                elif avg_prior != 0:
                    pct_diff = ((latest - avg_prior) / abs(avg_prior)) * 100
                    if abs(pct_diff) >= 2:
                        direction = "above" if pct_diff > 0 else "below"
                        context['vs_prior_year'] = f"{abs(pct_diff):.0f}% {direction} {prior_year} avg"

        # 3. Historical high/low with dates (last 10 years or available data)
        ten_years_ago = (datetime.now() - timedelta(days=3650)).strftime('%Y-%m-%d')
        recent_start_idx = next((i for i, d in enumerate(dates) if d >= ten_years_ago), 0)
        recent_values = values[recent_start_idx:]
        recent_dates = dates[recent_start_idx:]

        # Skip high/low comparisons for cumulative series (like total payrolls) - levels grow with population
        is_cumulative = db_info.get('cumulative', False)

        if recent_values and not is_cumulative:
            max_val = max(recent_values)
            min_val = min(recent_values)
            max_idx = recent_values.index(max_val)
            min_idx = recent_values.index(min_val)
            max_date = datetime.strptime(recent_dates[max_idx], '%Y-%m-%d').strftime('%b %Y')
            min_date = datetime.strptime(recent_dates[min_idx], '%Y-%m-%d').strftime('%b %Y')

            # Only mention if current is near high/low
            if max_val > 0:
                pct_from_high = (max_val - latest) / max_val * 100
                if pct_from_high <= 2:
                    context['at_high'] = f"10-year high"
                elif pct_from_high <= 10:
                    context['near_high'] = f"near 10-year high ({max_date})"

            if min_val != max_val:
                if data_type in ['rate', 'spread', 'growth_rate']:
                    diff_from_low = latest - min_val
                    if diff_from_low <= 0.3:
                        context['at_low'] = f"10-year low"
                    elif diff_from_low <= 1.0:
                        context['near_low'] = f"near 10-year low ({min_date})"
                else:
                    pct_from_low = (latest - min_val) / (max_val - min_val) * 100 if max_val != min_val else 50
                    if pct_from_low <= 5:
                        context['at_low'] = f"10-year low"
                    elif pct_from_low <= 15:
                        context['near_low'] = f"near 10-year low ({min_date})"

        # For cumulative series like payrolls, show monthly change instead
        if is_cumulative and len(values) >= 2:
            monthly_change = values[-1] - values[-2]
            context['monthly_change'] = monthly_change

        # 4. Trend direction (consecutive months in same direction)
        if len(values) >= 4:
            changes = [values[i] - values[i-1] for i in range(-1, -min(13, len(values)), -1)]

            consec_up = 0
            for c in changes:
                if c > 0:
                    consec_up += 1
                else:
                    break

            consec_down = 0
            for c in changes:
                if c < 0:
                    consec_down += 1
                else:
                    break

            if consec_up >= 3:
                context['trend'] = f"up {consec_up} consecutive months"
            elif consec_down >= 3:
                context['trend'] = f"down {consec_down} consecutive months"

    except Exception as e:
        pass  # Fail silently, narrative context is supplementary

    return context


# Series database with rich economist-style descriptions (CEA/Brookings/Zandi tone)
SERIES_DB = {
    # Employment - Establishment Survey (CES)
    'PAYEMS': {
        'name': 'Total Nonfarm Payrolls',
        'unit': 'Thousands of Persons',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'cumulative': True,  # Skip "at high" comparisons - levels always grow with population
        'show_absolute_change': True,  # NEVER show as %, always show job changes like "+256,000"
        'change_benchmark': {
            'breakeven_low': 50,  # in thousands - updated for 2020s demographics
            'breakeven_high': 75,
            'text': "Due to slowing population and labor force growth, the economy now needs only 50,000-75,000 new jobs per month to keep pace—down from 100K+ historically.",
        },
        'bullets': [
            'The single most important monthly indicator of labor market health. This is the "jobs number" that moves markets on the first Friday of each month. It counts wage and salary workers on U.S. non-farm establishment payrolls.',
            'Context matters: Due to slowing population and labor force growth (aging workforce, lower immigration, declining birth rates), the economy now needs only 50,000-75,000 new jobs per month to keep pace—down from 100K+ historically. Gains above 150,000 signal robust hiring; consistently below 50,000 suggests softening. During recessions, this figure turns sharply negative—800,000+ monthly losses at the depths of 2008-09.'
        ]
    },
    'CES0500000003': {
        'name': 'Average Hourly Earnings (Private)',
        'unit': 'Dollars per Hour',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'can_inflate_adjust': True,
        'bullets': [
            'Measures the average hourly pay for private-sector workers—a key indicator of whether economic gains are reaching American households. When wage growth outpaces inflation, workers see real improvements in living standards.',
            'The Federal Reserve watches wage growth closely as part of its inflation mandate. Wage growth of 3-3.5% is generally consistent with the Fed\'s 2% inflation target (accounting for productivity growth). Sustained wage growth above 4-5% can signal inflationary pressure, while stagnant wages—even with low unemployment—suggest workers lack bargaining power.'
        ]
    },
    'LES1252881600Q': {
        'name': 'Real Median Weekly Earnings',
        'unit': '1982-84 Dollars',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'level',
        'bullets': [
            'Real median weekly earnings directly measure purchasing power—what workers can actually buy with their paychecks after accounting for inflation. When this rises, the typical full-time worker is getting ahead; when it falls, inflation is eating into living standards.',
            'This is the definitive answer to "are wages keeping up with inflation." Unlike comparing nominal wage growth to CPI separately, this series already does the math. The median (not average) ensures results aren\'t skewed by high earners.'
        ]
    },

    # Employment - Household Survey (CPS)
    'UNRATE': {
        'name': 'Unemployment Rate (U-3)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'benchmark': {
            'value': 4.0,
            'comparison': 'above',  # 'above' means above benchmark is worse
            'text': "Economists generally estimate full employment around 4%.",
        },
        'bullets': [
            'The headline unemployment rate measures the share of Americans who are actively looking for work but cannot find it. This is the figure cited in news reports and used to gauge the health of the labor market.',
            'Historical context: Rates below 4% are historically rare and typically signal a very tight labor market. The rate peaked at 10% during the Great Recession and briefly hit 14.7% in April 2020 during COVID lockdowns. Important caveat: This measure excludes "discouraged workers" who\'ve stopped looking and part-time workers who want full-time jobs. The broader U-6 measure captures these groups and typically runs 3-4 percentage points higher.'
        ]
    },
    'LNS12300060': {
        'name': 'Prime-Age Employment-Population Ratio (25-54)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'bullets': [
            'Many economists consider this the single best measure of labor market health. It shows the share of Americans aged 25-54 who are employed—avoiding distortions from retiring Baby Boomers and students staying in school longer.',
            'This measure tells us whether the economy is actually putting working-age Americans into jobs. The pre-pandemic peak was 80.4% in January 2020. Unlike the unemployment rate, this metric captures people who\'ve left the workforce entirely. A rising prime-age employment ratio alongside falling unemployment is the clearest sign of genuine labor market improvement.'
        ]
    },
    'LNS11300000': {
        'name': 'Labor Force Participation Rate',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'bullets': [
            'Measures the share of the adult population either working or actively seeking work. This indicator reveals whether Americans are engaged in the labor market or sitting on the sidelines.',
            'The participation rate rose steadily for decades as women entered the workforce, peaking at 67.3% in 2000. It has since declined due to population aging, rising disability rates, and more young adults pursuing education. The COVID pandemic caused a sharp drop as workers—particularly women with caregiving responsibilities—left the labor force.'
        ]
    },
    'LNS11300060': {
        'name': 'Prime-Age Labor Force Participation Rate (25-54)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'bullets': [
            'Focuses on workers in their prime earning years (25-54), filtering out demographic effects from an aging population. This is a cleaner measure of whether working-age Americans are engaged with the labor market.',
            'The U.S. has seen a notable decline in prime-age male participation over recent decades—a trend that concerns economists as it suggests some working-age men have disconnected from the labor force entirely. Potential causes include disability, opioid addiction, declining job opportunities for non-college workers, and criminal records limiting employment options.'
        ]
    },

    # JOLTS
    'JTSJOL': {
        'name': 'Job Openings (JOLTS)',
        'unit': 'Thousands',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Counts the number of unfilled job positions across the economy. High job openings signal strong labor demand—employers are actively trying to hire. This data comes from the Job Openings and Labor Turnover Survey (JOLTS).',
            'The ratio of job openings to unemployed workers is a key measure of labor market "tightness." In a balanced market, this ratio is around 1.0. When it rises well above 1.0 (as it did in 2021-22, reaching nearly 2.0), workers have significant bargaining power and can command higher wages. Below 1.0 suggests slack in the labor market.'
        ]
    },
    'JTSHIR': {
        'name': 'Hires (JOLTS)',
        'unit': 'Thousands',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Counts the number of new hires each month across all nonfarm establishments. High hires indicate active labor market churn—people moving into new jobs. This is a key JOLTS indicator alongside job openings and quits.',
            'Context: Hires typically run 5-6 million per month in a healthy labor market. When hires exceed separations (quits + layoffs), total employment grows. A decline in hires often signals employer caution and potential labor market weakening ahead.'
        ]
    },
    'JTSQUR': {
        'name': 'Quits Rate (JOLTS)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'benchmark': {
            'value': 2.3,
            'comparison': 'above',
            'text': "Pre-pandemic quits rate averaged ~2.3%. Higher rates indicate worker confidence; lower rates suggest caution.",
        },
        'bullets': [
            'The percentage of workers who voluntarily quit their jobs each month. High quit rates signal worker confidence—people only quit when they believe they can find something better. Low quit rates indicate caution or fear.',
            'The "Great Resignation" of 2021-22 saw quit rates hit record 3.0%. A quit rate above 2.5% indicates a hot labor market with strong worker bargaining power; below 2.0% suggests workers are staying put due to uncertainty.'
        ]
    },
    'JTSLDL': {
        'name': 'Layoffs & Discharges (JOLTS)',
        'unit': 'Thousands',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Counts involuntary separations—workers who were laid off or fired. Rising layoffs signal employer distress and potential recession. This is a lagging indicator, typically rising after economic problems are already underway.',
            'Context: Layoffs typically run 1.5-1.8 million per month in normal times. Spikes above 2 million signal significant labor market stress. During the 2020 COVID shock, layoffs briefly exceeded 10 million per month.'
        ]
    },

    # Unemployment Insurance Claims (Weekly)
    'ICSA': {
        'name': 'Initial Jobless Claims',
        'unit': 'Number',
        'source': 'U.S. Employment and Training Administration',
        'sa': True,
        'frequency': 'weekly',
        'data_type': 'level',
        'benchmark': {
            'value': 225000,
            'comparison': 'above',
            'text': "Pre-pandemic, claims below 225K signaled a healthy labor market. Claims above 300K suggest significant job losses.",
        },
        'bullets': [
            'The most timely indicator of labor market conditions. Released every Thursday, initial claims count workers filing for unemployment benefits for the first time. This data arrives weeks before the monthly jobs report, making it a crucial early warning signal.',
            'Context: Pre-pandemic, claims ran 200-220K weekly in a healthy market. Claims spiked to nearly 7 million weekly in March 2020. Levels persistently above 300K suggest elevated layoffs; below 225K indicates strong labor demand. Economists often look at the 4-week moving average to smooth week-to-week volatility.'
        ]
    },
    'CCSA': {
        'name': 'Continuing Jobless Claims',
        'unit': 'Number',
        'source': 'U.S. Employment and Training Administration',
        'sa': True,
        'frequency': 'weekly',
        'data_type': 'level',
        'bullets': [
            'Counts the total number of people receiving unemployment benefits—a measure of ongoing unemployment duration. While initial claims show new layoffs, continuing claims reveal how quickly (or slowly) displaced workers find new jobs.',
            'Rising continuing claims alongside falling initial claims can indicate workers are having trouble finding new employment, even as layoffs slow. This was a key dynamic during the slow recovery from the Great Recession. Falling continuing claims with stable initial claims suggests a healthy churn where laid-off workers quickly find new positions.'
        ]
    },

    # Inflation - CPI
    'CPIAUCSL': {
        'name': 'Consumer Price Index (All Items)',
        'unit': 'Index 1982-84=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'CPI Inflation Rate (Headline)',
        'yoy_unit': '% Change YoY',
        'benchmark': {
            'value': 2.0,
            'comparison': 'above',
            'text': "The Fed targets 2% inflation (on PCE, which typically runs slightly below CPI).",
            'applies_to_yoy': True,
        },
        'bullets': [
            'The Consumer Price Index is the most widely cited measure of inflation in the United States. It tracks the prices urban consumers pay for a basket of goods and services—everything from rent and groceries to gasoline and healthcare.',
            'Why it matters to households: CPI directly affects Americans\' purchasing power. It\'s also used to adjust Social Security benefits, income tax brackets, and TIPS bond returns. The Federal Reserve targets 2% annual inflation; rates persistently above this level erode household budgets and can force the Fed to raise interest rates, slowing economic growth.'
        ]
    },
    'CPILFESL': {
        'name': 'Core CPI (Less Food & Energy)',
        'unit': 'Index 1982-84=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Core CPI Inflation Rate',
        'yoy_unit': '% Change YoY',
        'benchmark': {
            'value': 2.0,
            'comparison': 'above',
            'text': "The Fed targets 2% inflation. Core CPI typically runs slightly above PCE, so ~2.5% core CPI often aligns with the Fed's 2% PCE target.",
            'applies_to_yoy': True,
        },
        'bullets': [
            'Core inflation strips out volatile food and energy prices to reveal the underlying trend in prices. While headline inflation captures what consumers actually pay, core inflation better reflects persistent price pressures that monetary policy can address.',
            'Economists focus on core inflation because food and energy prices swing wildly based on weather, geopolitics, and speculation—factors largely outside the Fed\'s control. When core inflation is elevated, it typically signals that price pressures have become "sticky" and embedded in the economy through wages, rents, and services. This is much harder to reverse than a temporary oil price spike.'
        ]
    },
    'CUSR0000SAH1': {
        'name': 'CPI: Shelter',
        'unit': 'Index 1982-84=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Shelter Inflation Rate',
        'yoy_unit': '% Change YoY',
        'benchmark': {
            'value': 3.5,
            'comparison': 'above',
            'text': "Shelter costs are the largest CPI component (~33%). Pre-pandemic shelter inflation averaged ~3.5% annually.",
            'applies_to_yoy': True,
        },
        'bullets': [
            'Housing costs (rent and owners\' equivalent rent) make up roughly one-third of the CPI basket—the largest single component. When shelter inflation surges, it pulls overall inflation higher and is felt acutely by household budgets.',
            'Critical caveat: CPI shelter lags actual market rents by approximately 12 months due to how the BLS measures it (surveying existing leases that turn over slowly). This means market rent declines won\'t show up in CPI shelter for many months. Economists watching for inflation to ease look at private rent indexes like Zillow or Apartment List for leading signals.'
        ]
    },
    'CUSR0000SEHA': {
        'name': 'CPI: Rent of Primary Residence',
        'unit': 'Index 1982-84=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Rent Inflation Rate',
        'yoy_unit': '% Change YoY',
        'benchmark': {
            'value': 4.0,
            'comparison': 'above',
            'text': "Pre-pandemic rent inflation averaged 3-4% annually. Above 5% indicates tight rental markets.",
            'applies_to_yoy': True,
        },
        'bullets': [
            'Measures rent changes for tenant-occupied housing—what renters actually pay each month. This is a key component of CPI shelter.',
            'Rent inflation tends to be sticky because most leases are annual. Changes in market rents take time to flow through to the CPI measure, creating a significant lag of 12+ months.'
        ]
    },
    'CUSR0000SEHC': {
        'name': "CPI: Owners' Equivalent Rent",
        'unit': 'Index 1982-84=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': "Owners' Equivalent Rent Inflation",
        'yoy_unit': '% Change YoY',
        'benchmark': {
            'value': 4.0,
            'comparison': 'above',
            'text': "OER typically tracks actual rent inflation closely. Above 5% indicates housing cost pressure.",
            'applies_to_yoy': True,
        },
        'bullets': [
            "Measures what homeowners would pay to rent their own homes. This is the largest single component of CPI, making up about 24% of the total index.",
            "OER is somewhat controversial because homeowners don't actually pay rent. Critics argue it doesn't capture actual housing costs like mortgage payments, property taxes, or maintenance. But it's designed to measure housing service consumption, not investment returns."
        ]
    },
    'CUSR0000SAF11': {
        'name': 'CPI: Food at Home',
        'unit': 'Index 1982-84=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Grocery Price Inflation',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Tracks prices for groceries—food purchased at stores for home consumption. This is what people mean when they talk about grocery prices. Food at home makes up about 8% of the CPI basket.',
            'Grocery prices are heavily influenced by commodity costs (grains, meat, dairy) and can be volatile due to weather, disease outbreaks, and supply chain issues. During 2022, grocery inflation exceeded 10%—the highest in decades—due to supply chain disruptions and input cost pressures.'
        ]
    },
    'CUSR0000SEFV': {
        'name': 'CPI: Food Away from Home',
        'unit': 'Index 1982-84=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Restaurant Price Inflation',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Tracks prices for food purchased at restaurants, fast food, and other food-service establishments. Labor costs are a major component, so this category is sensitive to wage pressures in the service sector.',
            'Restaurant prices tend to be stickier than grocery prices because they\'re driven by labor costs, rent, and other service expenses that don\'t adjust as quickly as commodity prices. Once restaurant prices rise, they rarely fall—making this a key indicator of persistent inflation.'
        ]
    },
    'CUSR0000SETB01': {
        'name': 'CPI: Gasoline (All Types)',
        'unit': 'Index 1982-84=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Gasoline Price Inflation',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Tracks gasoline prices in the CPI basket. Gasoline is one of the most visible and volatile components of inflation—consumers see prices daily on gas station signs and quickly feel changes in their wallets.',
            'Gas prices drive headline inflation volatility but are excluded from "core" measures because they\'re determined by global oil markets, not domestic economic conditions. A $1 change in gas prices adds or subtracts roughly 0.4 percentage points to headline CPI inflation.'
        ]
    },
    'GASREGW': {
        'name': 'Regular Gasoline Price',
        'unit': 'Dollars per Gallon',
        'source': 'U.S. Energy Information Administration',
        'sa': False,
        'frequency': 'weekly',
        'data_type': 'price',
        'bullets': [
            'The national average retail price for a gallon of regular gasoline. This is the price consumers actually see at the pump and is one of the most closely watched consumer prices in America.',
            'Gas prices are driven primarily by crude oil costs (about 50-60% of the price), plus refining costs, taxes, and distribution/marketing. The U.S. consumes about 9 million barrels of gasoline per day. Every 1-cent change in gas prices transfers about $1 billion annually between consumers and producers.'
        ]
    },

    # Inflation - PCE (Fed's preferred)
    'PCEPI': {
        'name': 'PCE Price Index',
        'unit': 'Index 2017=100',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'PCE Inflation Rate',
        'yoy_unit': '% Change YoY',
        'benchmark': {
            'value': 2.0,
            'comparison': 'above',
            'text': "The Fed targets 2% inflation.",
            'applies_to_yoy': True,
        },
        'bullets': [
            'The Personal Consumption Expenditures price index is the Federal Reserve\'s preferred measure of inflation. When Fed officials say they target "2% inflation," they mean PCE. It\'s broader than CPI and better captures how consumers actually spend.',
            'PCE differs from CPI in important ways: it includes spending by employers and government on behalf of households (like employer-provided health insurance), and it adjusts for consumers substituting cheaper alternatives when prices rise. PCE inflation typically runs 0.3-0.5 percentage points below CPI.'
        ]
    },
    'PCEPILFE': {
        'name': 'Core PCE Price Index',
        'unit': 'Index 2017=100',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Core PCE Inflation Rate',
        'yoy_unit': '% Change YoY',
        'benchmark': {
            'value': 2.0,
            'comparison': 'above',  # above target is concerning
            'text': "The Fed's explicit inflation target is 2%.",
            'applies_to_yoy': True,  # benchmark applies to YoY transformation
        },
        'bullets': [
            'This is the single most important inflation measure for monetary policy. The Federal Reserve\'s explicit inflation target is 2% on core PCE. Every FOMC statement, press conference, and Summary of Economic Projections references this metric.',
            'When core PCE runs persistently above 2%, the Fed faces pressure to raise interest rates to cool demand. When it runs below 2%, the Fed has room to keep rates low to support employment. Core PCE running at 4-5% in 2022-23 drove the most aggressive Fed rate-hiking cycle in four decades.'
        ]
    },
    'PCE': {
        'name': 'Personal Consumption Expenditures',
        'unit': 'Billions of Dollars',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'show_yoy': True,
        'yoy_name': 'Consumer Spending Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Personal Consumption Expenditures is the broadest measure of consumer spending in nominal (current dollar) terms. It includes spending on goods and services and represents roughly 70% of GDP.',
            'This is different from the PCE Price Index (PCEPI) which measures inflation. PCE shows actual spending levels, useful for tracking the size and growth of consumer demand.'
        ]
    },

    # GDP
    'GDPC1': {
        'name': 'Real Gross Domestic Product',
        'unit': 'Billions of Chained 2017 Dollars',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'level',
        'bullets': [
            'Real GDP is the broadest measure of economic output—the total value of all goods and services produced in the United States, adjusted for inflation. It\'s the definitive measure of whether the economy is growing or shrinking.',
            'The "real" distinction matters enormously: nominal GDP can rise simply because prices are rising, not because the economy is producing more. Real GDP strips out inflation to show actual output growth. Two consecutive quarters of declining real GDP is often cited as a recession rule-of-thumb, though the official arbiter (NBER) considers multiple factors.'
        ]
    },
    'A191RL1Q225SBEA': {
        'name': 'Quarterly GDP Growth (Annualized)',
        'unit': '% Change (SAAR)',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'growth_rate',
        'benchmark': {
            'value': 2.0,
            'text': "This is the volatile quarterly rate. Trend growth is ~2% annualized, but this measure swings widely quarter to quarter.",
            'comparison': 'above',
            'ranges': [(0, 2, 'below trend'), (2, 3, 'trend growth'), (3, 4, 'robust'), (4, 100, 'boom pace')],
        },
        'bullets': [
            'This is the headline GDP number reported in the news—it shows one quarter\'s growth extrapolated to an annual rate. While timely, it can be volatile and misleading (it swung from -28% to +35% during COVID).',
            'For a more stable picture of economic growth, the year-over-year measure is more reliable. This quarterly rate is best used to spot turning points, not to assess underlying economic health.'
        ]
    },
    'A191RO1Q156NBEA': {
        'name': 'Annual GDP Growth (Year-over-Year)',
        'unit': '% Change from Year Ago',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'growth_rate',
        'benchmark': {
            'value': 2.0,
            'text': "Trend U.S. growth is ~2% annually. Above 3% is strong; below 1% signals weakness.",
            'comparison': 'above',
            'ranges': [(0, 1, 'weak'), (1, 2, 'below trend'), (2, 3, 'trend growth'), (3, 4, 'strong'), (4, 100, 'boom')],
        },
        'bullets': [
            'This is the most meaningful measure of economic growth—it shows how much the economy has actually expanded compared to a year ago, smoothing out quarterly volatility.',
            'Unlike the quarterly annualized rate (which can swing wildly), year-over-year growth provides a stable picture of economic momentum. Trend U.S. growth is ~2%; sustained growth above 3% is strong.'
        ]
    },
    'A191RL1A225NBEA': {
        'name': 'Annual Real GDP Growth',
        'unit': '% Change',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': False,
        'frequency': 'annual',
        'data_type': 'growth_rate',
        'benchmark': {
            'value': 2.0,
            'text': "Trend U.S. growth is ~2% annually. Above 3% is robust growth; below 0% is a contraction year.",
            'comparison': 'above',
            'ranges': [(-10, 0, 'contraction'), (0, 2, 'below trend'), (2, 3, 'trend growth'), (3, 4, 'robust'), (4, 100, 'boom')],
        },
        'bullets': [
            'This is the definitive measure of annual economic growth: how much total real GDP in one calendar year exceeded the prior year. For 2024, this was 2.8%—meaning the U.S. produced 2.8% more goods and services than in 2023.',
            'Why it matters: The quarterly annualized rate (headline GDP) can be volatile. This annual measure tells you how the economy actually performed over a full year. Economists reference this when discussing long-term economic health, comparing across years, or assessing policy impacts.'
        ]
    },
    'PB0000031Q225SBEA': {
        'name': 'Real Final Sales to Private Domestic Purchasers',
        'unit': '% Change (Annualized)',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'growth_rate',
        'benchmark': {
            'value': 2.5,
            'text': "This 'core GDP' measure typically grows around 2-3% in healthy expansions. It's been found to be a better predictor of future growth than headline GDP.",
            'comparison': 'above',
            'ranges': [(-10, 0, 'contraction'), (0, 2, 'weak'), (2, 3.5, 'healthy'), (3.5, 100, 'strong')],
        },
        'bullets': [
            'This is what economists call "core GDP"—it strips out the most volatile components (government spending, exports, and inventory changes) to focus on private domestic demand: consumer spending plus business fixed investment.',
            'Why it matters: The Council of Economic Advisers has found this to be a better predictor of future growth than headline GDP. When core GDP is strong but headline GDP is weak (due to inventory drawdown or trade deficit), it often signals the economy is healthier than the headline suggests. Watch for divergences between this and headline GDP.'
        ]
    },
    'GDPNOW': {
        'name': 'Atlanta Fed GDPNow Estimate',
        'unit': '% Change (SAAR)',
        'source': 'Federal Reserve Bank of Atlanta',
        'sa': True,
        'frequency': 'daily',
        'data_type': 'growth_rate',
        'benchmark': {
            'value': 2.0,
            'text': "GDPNow is a real-time estimate of current-quarter GDP growth. Compare to trend growth of ~2%.",
            'comparison': 'above',
            'ranges': [(0, 2, 'below trend'), (2, 3, 'trend'), (3, 4, 'strong'), (4, 100, 'very strong')],
        },
        'bullets': [
            'GDPNow is the Atlanta Fed\'s "nowcast" of real GDP growth for the current quarter, updated as new economic data comes in. It provides the most timely estimate of where GDP is tracking before the official BEA release.',
            'Unlike official GDP (released ~1 month after quarter ends), GDPNow updates continuously. It\'s not a forecast—it\'s a model-based estimate using the same methodology as BEA. Watch how it evolves as data releases come in.'
        ]
    },

    # GDP Components (for "gdp components" query)
    'PCECC96': {
        'name': 'Real Personal Consumption Expenditures (Quarterly)',
        'unit': 'Billions of Chained 2017 Dollars',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'level',
        'bullets': [
            'Real personal consumption expenditures in the GDP accounts—the inflation-adjusted measure of consumer spending that makes up roughly 70% of GDP.',
            'PCE includes spending on goods and services by households. It is the largest component of GDP and the primary driver of economic growth.'
        ]
    },
    'PCEC96': {
        'name': 'Real Personal Consumption Expenditures',
        'unit': 'Billions of Chained 2017 Dollars',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'show_yoy': True,
        'yoy_name': 'Real Consumer Spending Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Monthly real PCE is the inflation-adjusted measure of consumer spending, accounting for roughly 70% of GDP. This is the broadest measure of consumer activity.',
            'Unlike retail sales (which only captures goods), PCE includes services like healthcare, education, and financial services—capturing the full breadth of consumer spending.'
        ]
    },
    'GPDIC1': {
        'name': 'Real Gross Private Domestic Investment',
        'unit': 'Billions of Chained 2017 Dollars',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'level',
        'bullets': [
            'Real gross private domestic investment includes business spending on equipment, structures, intellectual property, residential investment, and changes in inventories.',
            'Investment is the most volatile component of GDP and a key driver of business cycles. Strong investment signals business confidence in future growth.'
        ]
    },
    'GCEC1': {
        'name': 'Real Government Consumption Expenditures',
        'unit': 'Billions of Chained 2017 Dollars',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'level',
        'bullets': [
            'Government consumption expenditures and gross investment at all levels (federal, state, and local), measured in real terms.',
            'Government spending represents roughly 17-18% of GDP and includes both purchases of goods and services and investment in infrastructure.'
        ]
    },
    'EXPGSC1': {
        'name': 'Real Exports of Goods and Services',
        'unit': 'Billions of Chained 2017 Dollars',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'level',
        'bullets': [
            'Real exports represents the value of goods and services produced in the U.S. and sold abroad.',
            'Exports add to GDP as they represent domestic production consumed by foreign buyers. A strong dollar tends to reduce exports.'
        ]
    },
    'IMPGSC1': {
        'name': 'Real Imports of Goods and Services',
        'unit': 'Billions of Chained 2017 Dollars',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'level',
        'bullets': [
            'Real imports represents the value of goods and services produced abroad and consumed in the U.S.',
            'Imports are subtracted from GDP because they represent foreign production. Rising imports often signal strong domestic demand.'
        ]
    },

    # Interest Rates
    'FEDFUNDS': {
        'name': 'Federal Funds Effective Rate',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'rate',
        'bullets': [
            'The federal funds rate is the most important interest rate in the world. It\'s the rate banks charge each other for overnight loans, and it\'s the primary tool the Federal Reserve uses to influence the economy. Nearly every other interest rate in the U.S. economy moves with it.',
            'How it affects you: When the Fed raises this rate, borrowing becomes more expensive across the board—mortgages, car loans, credit cards, business loans. This slows spending and investment, cooling inflation but also slowing growth. Near 0% signals emergency stimulus mode (as during 2008-2015 and 2020-2022); rates above 5% signal aggressive inflation-fighting.'
        ]
    },
    'DGS10': {
        'name': '10-Year Treasury Yield',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'rate',
        'bullets': [
            'The 10-year Treasury yield is the benchmark interest rate for the U.S. economy. It\'s what the government pays to borrow for 10 years, and it serves as the foundation for mortgage rates, corporate bond yields, and long-term financial planning.',
            'Unlike the fed funds rate, the 10-year yield is set by market forces—it reflects investor expectations about future growth, inflation, and Fed policy over the next decade. When the 10-year yield rises sharply, it increases borrowing costs across the economy even if the Fed hasn\'t moved. Mortgage rates typically run about 1.5-2.5 percentage points above the 10-year yield.'
        ]
    },
    'DGS2': {
        'name': '2-Year Treasury Yield',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'rate',
        'bullets': [
            'The 2-year Treasury yield is the market\'s best real-time estimate of where the Fed will set interest rates over the next two years. It moves quickly in response to Fed communications and economic data.',
            'Bond traders watch the 2-year closely to gauge expectations for Fed policy. When the 2-year yield rises above the 10-year yield (an "inverted yield curve"), it\'s historically been one of the most reliable recession warning signals—this inversion has preceded every U.S. recession since the 1970s, typically by 12-18 months.'
        ]
    },
    'T10Y2Y': {
        'name': '10-Year Minus 2-Year Treasury Spread',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'spread',
        'benchmark': {
            'value': 0.0,
            'comparison': 'below',
            'text': "When this spread goes negative (inverted yield curve), it's a recession warning signal—has preceded every U.S. recession since 1970.",
        },
        'bullets': [
            'The yield curve spread measures the difference between long-term and short-term interest rates. Normally positive (investors demand more to lend for longer), this spread turns negative ("inverts") when markets expect economic trouble ahead.',
            'An inverted yield curve has predicted every U.S. recession since 1970 with remarkable accuracy. The logic: investors accept lower long-term rates because they expect the Fed will need to cut rates to fight a recession. The spread was deeply inverted through much of 2023, though the lag between inversion and recession varies from several months to two years.'
        ]
    },
    'T5YIE': {
        'name': '5-Year Breakeven Inflation Rate',
        'unit': 'Percent',
        'source': 'Federal Reserve Bank of St. Louis',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'rate',
        'benchmark': {
            'value': 2.0,
            'comparison': 'above',
            'text': "When breakevens rise significantly above 2%, markets expect inflation to exceed the Fed's target.",
        },
        'bullets': [
            "Derived from the difference between nominal 5-year Treasuries and 5-year TIPS (inflation-protected securities). Shows what bond markets expect average inflation to be over the next 5 years.",
            "This market-based measure of inflation expectations is closely watched by the Fed. Well-anchored expectations near 2% support price stability; rising breakevens can signal inflation concerns are building."
        ]
    },
    'T10YIE': {
        'name': '10-Year Breakeven Inflation Rate',
        'unit': 'Percent',
        'source': 'Federal Reserve Bank of St. Louis',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'rate',
        'benchmark': {
            'value': 2.0,
            'comparison': 'above',
            'text': "Values persistently above 2.5% suggest markets expect inflation to exceed the Fed's target over the long run.",
        },
        'bullets': [
            "The difference between 10-year nominal Treasury yields and 10-year TIPS yields. Represents what markets expect annual inflation to average over the next decade.",
            "Long-term breakevens are particularly important because they reflect deep structural expectations about inflation. When these stay near 2%, it suggests the Fed retains credibility on its inflation-fighting commitment."
        ]
    },
    'MICH': {
        'name': 'University of Michigan: Inflation Expectation',
        'unit': 'Percent',
        'source': 'University of Michigan',
        'sa': False,
        'frequency': 'monthly',
        'data_type': 'rate',
        'benchmark': {
            'value': 3.0,
            'comparison': 'above',
            'text': "Consumer inflation expectations above 3% are concerning because they can become self-fulfilling.",
        },
        'bullets': [
            "Measures what consumers expect inflation to be over the next year, based on the University of Michigan's Surveys of Consumers. This is one of the most closely watched measures of inflation expectations.",
            "Consumer expectations matter because they influence behavior: if people expect higher prices, they may demand higher wages and spend sooner, potentially making inflation worse. The Fed monitors this closely as part of keeping expectations 'anchored' near 2%."
        ]
    },
    'MORTGAGE30US': {
        'name': '30-Year Fixed Mortgage Rate',
        'unit': 'Percent',
        'source': 'Freddie Mac',
        'sa': False,
        'frequency': 'weekly',
        'data_type': 'rate',
        'bullets': [
            'The 30-year fixed mortgage rate determines the monthly cost of homeownership for millions of Americans. Small changes in this rate translate to large differences in affordability—at 3%, a $400,000 home costs $1,686/month in principal and interest; at 7%, the same home costs $2,661/month.',
            'This rate generally tracks the 10-year Treasury yield plus a spread for risk (typically 1.5-2.5 percentage points). When rates rose from 3% to 7% in 2022-23, it effectively priced many buyers out of the market and froze existing homeowners in place (the "lock-in effect"), dramatically reducing housing market activity.'
        ]
    },
    'MORTGAGE15US': {
        'name': '15-Year Fixed Mortgage Rate',
        'unit': 'Percent',
        'source': 'Freddie Mac',
        'sa': False,
        'frequency': 'weekly',
        'data_type': 'rate',
        'bullets': [
            'The 15-year fixed mortgage rate offers lower rates than the 30-year in exchange for higher monthly payments. Popular with refinancers and buyers who can afford larger payments.',
            'The 15-year rate typically runs 0.5-0.75 percentage points below the 30-year rate due to lower duration risk for lenders. Borrowers save substantially on total interest paid over the life of the loan.'
        ]
    },
    'DFEDTARU': {
        'name': 'Fed Funds Target Upper Bound',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'rate',
        'bullets': [
            "The upper bound of the Federal Reserve's target range for the federal funds rate. Since 2008, the Fed has set a target range rather than a single target.",
            'The effective fed funds rate typically trades within this band. Watching the target bounds shows exactly when the Fed changed policy at FOMC meetings.'
        ]
    },
    'DFEDTARL': {
        'name': 'Fed Funds Target Lower Bound',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'rate',
        'bullets': [
            "The lower bound of the Federal Reserve's target range for the federal funds rate. Along with the upper bound, this defines the corridor for overnight rates.",
            'When the lower bound hits zero, the Fed has reached the "zero lower bound" and must turn to unconventional tools like quantitative easing.'
        ]
    },
    'DGS30': {
        'name': '30-Year Treasury Yield',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'rate',
        'bullets': [
            'The 30-year Treasury yield represents the longest-duration benchmark in the Treasury market. It reflects investor expectations about growth, inflation, and Fed policy over a very long horizon.',
            'The 30-year yield is less sensitive to Fed policy changes than shorter maturities but highly sensitive to inflation expectations. Pension funds and insurance companies are major buyers of long-dated Treasuries.'
        ]
    },
    'DGS3MO': {
        'name': '3-Month Treasury Yield',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'rate',
        'bullets': [
            'The 3-month Treasury bill yield tracks very closely with the federal funds rate and serves as the benchmark for money market funds.',
            'When the 3-month yield exceeds longer-term yields, it signals an inverted yield curve at the short end—a classic recession warning signal.'
        ]
    },

    # Housing
    'CSUSHPINSA': {
        'name': 'S&P/Case-Shiller National Home Price Index',
        'unit': 'Index Jan 2000=100',
        'source': 'S&P Dow Jones Indices LLC',
        'sa': False,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Home Price Growth (YoY)',
        'yoy_unit': '% Change YoY',
        'benchmark': {
            'value': 5.0,
            'comparison': 'above',
            'text': "Long-run home price appreciation averages 3-5% annually. Growth above 10% may signal overheating.",
            'applies_to_yoy': True,
        },
        'bullets': [
            'The Case-Shiller index is the gold standard for tracking U.S. home prices. It uses a "repeat sales" methodology—tracking the same homes over time—to provide the cleanest measure of actual price changes. An index value of 300 means prices have tripled since January 2000.',
            'Housing wealth matters enormously to household finances: home equity is the largest source of wealth for most American families. Rising home prices increase consumer spending through wealth effects, while falling prices can devastate household balance sheets—as the 2008 financial crisis demonstrated.'
        ]
    },
    'HOUST': {
        'name': 'Housing Starts',
        'unit': 'Thousands of Units (Annual Rate)',
        'source': 'U.S. Census Bureau',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Housing starts counts new residential construction projects breaking ground. It\'s a leading indicator—homebuilders only begin projects when they\'re confident about future demand, so starts often signal the economy\'s direction.',
            'The U.S. faces a structural housing shortage estimated at 3-5 million units, built up over a decade of underbuilding following the 2008 crash. Healthy starts typically run 1.2-1.6 million annually. During the housing bust of 2009, starts collapsed to just 478,000—a level that contributed to years of housing undersupply.'
        ]
    },
    'EXHOSLUSM495S': {
        'name': 'Existing Home Sales',
        'unit': 'Millions of Units (Annual Rate)',
        'source': 'National Association of Realtors',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Existing home sales measures transactions of previously-owned homes. This is the largest segment of the housing market—roughly 85-90% of all home sales are existing homes rather than new construction.',
            'Sales volume depends heavily on mortgage rates (affordability), inventory (what\'s available), and prices. The 2022-23 rate surge from 3% to 7% created a "lock-in effect"—existing homeowners stayed put rather than give up their low-rate mortgages, suppressing both inventory and sales volume.'
        ]
    },
    'HSN1F': {
        'name': 'New One Family Houses Sold',
        'unit': 'Thousands of Units (Annual Rate)',
        'source': 'U.S. Census Bureau',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'New home sales tracks purchases of newly-built single-family homes. While smaller than existing sales, new home sales are a leading indicator—they reflect builder confidence and require significant economic activity (construction, materials, labor).',
            'New home sales are more sensitive to mortgage rates and builder capacity. Unlike existing homes, builders can offer incentives and rate buydowns, making new homes relatively more competitive when rates rise.'
        ]
    },
    'PERMIT': {
        'name': 'Building Permits',
        'unit': 'Thousands of Units (Annual Rate)',
        'source': 'U.S. Census Bureau',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Building permits is the earliest signal of new residential construction—filed before construction begins. This makes it a leading indicator of future housing supply and construction activity.',
            'Permits lead housing starts by 1-3 months. Economists watch permits for early signs of housing market turning points. Sustained growth in permits signals builders expect strong future demand.'
        ]
    },

    # Housing Prices (Additional)
    'MSPUS': {
        'name': 'Median Sales Price of Houses Sold',
        'unit': 'Dollars',
        'source': 'U.S. Census Bureau',
        'sa': False,
        'frequency': 'quarterly',
        'data_type': 'level',
        'bullets': [
            'The median sales price represents the middle point of all home sales—half sold for more, half for less. Unlike average price, the median is not skewed by extremely expensive homes, making it more representative of typical home values.',
            'This is often the most intuitive price measure for consumers. However, it can be affected by the mix of homes selling (more luxury homes = higher median even if prices are flat). For pure price trends, Case-Shiller is more accurate.'
        ]
    },
    'ASPUS': {
        'name': 'Average Sales Price of Houses Sold',
        'unit': 'Dollars',
        'source': 'U.S. Census Bureau',
        'sa': False,
        'frequency': 'quarterly',
        'data_type': 'level',
        'bullets': [
            'The average sales price is the mean of all home sale prices. It tends to be higher than median because expensive homes pull the average up.',
            'The average is more sensitive to luxury home sales and can be more volatile than the median. It\'s useful for tracking total housing market value but less representative of what typical buyers pay.'
        ]
    },
    'USSTHPI': {
        'name': 'FHFA House Price Index',
        'unit': 'Index 1980:Q1=100',
        'source': 'Federal Housing Finance Agency',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'FHFA Home Price Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'The FHFA House Price Index covers homes with mortgages backed by Fannie Mae or Freddie Mac. It has broader geographic coverage than Case-Shiller since it includes all states and metro areas.',
            'Like Case-Shiller, FHFA uses a repeat-sales methodology for accuracy. The main difference: FHFA only includes homes with conforming mortgages (under the loan limit), while Case-Shiller includes all sales regardless of financing.'
        ]
    },

    # Vacancy & Homeownership
    'RHORUSQ156N': {
        'name': 'Homeownership Rate',
        'unit': 'Percent',
        'source': 'U.S. Census Bureau',
        'sa': False,
        'frequency': 'quarterly',
        'data_type': 'rate',
        'benchmark': {
            'value': 65.0,
            'comparison': 'context',
            'text': "The long-run average homeownership rate is around 65%. Peaked at 69% before the 2008 crisis, bottomed at 63% in 2016.",
        },
        'bullets': [
            'The homeownership rate measures the percentage of households that own their home rather than rent. It reflects affordability, access to credit, demographic trends, and cultural preferences.',
            'Homeownership peaked at 69% in 2004 during the housing bubble, then fell to 63% by 2016 as foreclosures and tighter lending took their toll. It has since recovered to around 65-66%, near the historical average.'
        ]
    },
    'RHVRUSQ156N': {
        'name': 'Homeowner Vacancy Rate',
        'unit': 'Percent',
        'source': 'U.S. Census Bureau',
        'sa': False,
        'frequency': 'quarterly',
        'data_type': 'rate',
        'benchmark': {
            'value': 1.5,
            'comparison': 'above',
            'text': "Normal vacancy is around 1.5%. Above 2.5% signals oversupply; below 1% indicates very tight market.",
        },
        'bullets': [
            'The homeowner vacancy rate measures the percentage of for-sale homes that are vacant. Low vacancy indicates strong demand and limited inventory; high vacancy suggests oversupply or weak demand.',
            'This rate spiked above 2.8% during the 2008-2010 foreclosure crisis as unsold homes flooded the market. It has since fallen to historic lows below 1%, reflecting the severe housing shortage.'
        ]
    },
    'RRVRUSQ156N': {
        'name': 'Rental Vacancy Rate',
        'unit': 'Percent',
        'source': 'U.S. Census Bureau',
        'sa': False,
        'frequency': 'quarterly',
        'data_type': 'rate',
        'benchmark': {
            'value': 7.0,
            'comparison': 'context',
            'text': "Normal rental vacancy is 6-8%. Below 5% indicates very tight rental market with upward pressure on rents.",
        },
        'bullets': [
            'The rental vacancy rate measures the percentage of rental units that are vacant and available. Low vacancy gives landlords pricing power and pushes rents higher; high vacancy favors renters.',
            'Rental vacancy has been low since 2021, contributing to rapid rent increases. Tight rental markets often reflect housing undersupply, population growth, or high homeownership costs pushing people to rent.'
        ]
    },

    # Construction Pipeline
    'COMPUTSA': {
        'name': 'Housing Units Completed',
        'unit': 'Thousands of Units (Annual Rate)',
        'source': 'U.S. Census Bureau',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Housing completions measure when new residential units are actually finished and ready for occupancy. This is the final stage of the construction pipeline after permits and starts.',
            'Completions lag starts by 6-12 months depending on construction type. Multifamily buildings take longer to complete than single-family homes. Rising completions add to housing supply and can moderate price growth.'
        ]
    },
    'UNDCONTSA': {
        'name': 'Housing Units Under Construction',
        'unit': 'Thousands of Units',
        'source': 'U.S. Census Bureau',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Units under construction measures homes currently being built—started but not yet completed. This is the construction pipeline that will become future housing supply.',
            'A large pipeline suggests more supply coming to market, which could moderate prices. Extended construction times (from labor or material shortages) can keep units "under construction" longer, delaying supply relief.'
        ]
    },
    'PRRESCONS': {
        'name': 'Private Residential Construction Spending',
        'unit': 'Millions of Dollars (Annual Rate)',
        'source': 'U.S. Census Bureau',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Residential construction spending measures total investment in new homes, improvements, and additions. It captures the economic activity generated by housing construction.',
            'This series includes both new construction and improvements to existing homes. It\'s a key component of GDP and reflects both housing demand and construction costs (labor and materials).'
        ]
    },

    # Affordability
    'FIXHAI': {
        'name': 'Housing Affordability Index',
        'unit': 'Index',
        'source': 'National Association of Realtors',
        'sa': False,
        'frequency': 'monthly',
        'data_type': 'index',
        'benchmark': {
            'value': 100,
            'comparison': 'below',
            'text': "Index of 100 means a median-income family can exactly afford the median home. Above 100 = more affordable; below 100 = less affordable.",
        },
        'bullets': [
            'The Housing Affordability Index combines home prices, mortgage rates, and median family income into a single measure. An index of 100 means a median-income family has exactly enough to qualify for a median-priced home.',
            'Higher values mean housing is more affordable; lower values mean it\'s less affordable. The index fell sharply in 2022-23 as rates rose and prices stayed high, reaching the lowest levels since the 1980s.'
        ]
    },

    # Metro Case-Shiller Indexes
    'SFXRSA': {
        'name': 'Case-Shiller Home Price Index: San Francisco',
        'unit': 'Index Jan 2000=100',
        'source': 'S&P Dow Jones Indices',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'SF Home Price Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Tracks home prices in the San Francisco metro area using the Case-Shiller repeat-sales methodology.',
            'San Francisco has some of the highest home prices in the nation, driven by tech industry wealth and constrained housing supply. Prices are highly sensitive to tech sector performance and interest rates.'
        ]
    },
    'LXXRSA': {
        'name': 'Case-Shiller Home Price Index: Los Angeles',
        'unit': 'Index Jan 2000=100',
        'source': 'S&P Dow Jones Indices',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'LA Home Price Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Tracks home prices in the Los Angeles metro area using the Case-Shiller repeat-sales methodology.',
            'LA is one of the least affordable major markets due to high prices relative to local incomes. The market experienced dramatic boom-bust cycles in both the early 1990s and 2008 financial crisis.'
        ]
    },
    'NYXRSA': {
        'name': 'Case-Shiller Home Price Index: New York',
        'unit': 'Index Jan 2000=100',
        'source': 'S&P Dow Jones Indices',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'NYC Home Price Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Tracks home prices in the New York metro area using the Case-Shiller repeat-sales methodology.',
            'New York prices tend to be more stable than other coastal metros, with smaller boom-bust swings. The market is driven by finance industry wealth and severe land constraints in Manhattan.'
        ]
    },
    'CHXRSA': {
        'name': 'Case-Shiller Home Price Index: Chicago',
        'unit': 'Index Jan 2000=100',
        'source': 'S&P Dow Jones Indices',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Chicago Home Price Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Tracks home prices in the Chicago metro area using the Case-Shiller repeat-sales methodology.',
            'Chicago has more moderate price levels than coastal cities, with prices that never fully recovered to pre-2008 peaks until recently. The market reflects Midwest economics and less constrained land supply.'
        ]
    },
    'MIXRSA': {
        'name': 'Case-Shiller Home Price Index: Miami',
        'unit': 'Index Jan 2000=100',
        'source': 'S&P Dow Jones Indices',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Miami Home Price Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Tracks home prices in the Miami metro area using the Case-Shiller repeat-sales methodology.',
            'Miami experienced one of the most extreme boom-bust cycles in 2008 and has seen strong appreciation since 2020 driven by pandemic migration from high-tax states.'
        ]
    },
    'DAXRSA': {
        'name': 'Case-Shiller Home Price Index: Dallas',
        'unit': 'Index Jan 2000=100',
        'source': 'S&P Dow Jones Indices',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Dallas Home Price Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Tracks home prices in the Dallas metro area using the Case-Shiller repeat-sales methodology.',
            'Dallas avoided the 2008 crash that hit coastal markets due to more conservative lending and abundant land for development. Has seen strong growth since 2020 from corporate relocations and population influx.'
        ]
    },
    'SEXRSA': {
        'name': 'Case-Shiller Home Price Index: Seattle',
        'unit': 'Index Jan 2000=100',
        'source': 'S&P Dow Jones Indices',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Seattle Home Price Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Tracks home prices in the Seattle metro area using the Case-Shiller repeat-sales methodology.',
            'Seattle prices are driven by tech industry wealth (Amazon, Microsoft) and geographic constraints. One of the fastest-appreciating markets of the 2010s.'
        ]
    },
    'PHXRSA': {
        'name': 'Case-Shiller Home Price Index: Phoenix',
        'unit': 'Index Jan 2000=100',
        'source': 'S&P Dow Jones Indices',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Phoenix Home Price Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Tracks home prices in the Phoenix metro area using the Case-Shiller repeat-sales methodology.',
            'Phoenix experienced the most extreme boom-bust of any major market in 2008. Has seen rapid appreciation since 2020 due to remote work migration and relative affordability compared to California.'
        ]
    },

    # Consumer
    'UMCSENT': {
        'name': 'University of Michigan Consumer Sentiment',
        'unit': 'Index 1966:Q1=100',
        'source': 'University of Michigan',
        'sa': False,
        'frequency': 'monthly',
        'data_type': 'index',
        'bullets': [
            'Consumer sentiment measures how optimistic Americans feel about their personal finances and the broader economy. Since consumer spending drives roughly 70% of GDP, sentiment is a leading indicator of future spending patterns.',
            'Index interpretation: A reading around 100 is neutral (matching the 1966 baseline). Above 100 signals optimism; below 100 signals pessimism. The index hit historic lows around 50 during the 2022 inflation surge, even as unemployment remained near historic lows—reflecting the real pain of rising prices for household budgets.'
        ]
    },
    'RSXFS': {
        'name': 'Retail Sales (ex. Food Services)',
        'unit': 'Millions of Dollars',
        'source': 'U.S. Census Bureau',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'can_inflate_adjust': True,
        'bullets': [
            'Retail sales measures consumer spending at stores and online—a real-time pulse on the American consumer. Strong retail sales signal confident households; weakness can foreshadow broader economic trouble.',
            'Important caveats: This series is highly volatile month-to-month and subject to significant revisions. Look at 3-month trends rather than single months. Also note this is nominal (not inflation-adjusted), so real spending growth requires comparing against price increases.'
        ]
    },
    'PSAVERT': {
        'name': 'Personal Saving Rate',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'benchmark': {
            'value': 7.0,
            'comparison': 'below',
            'text': "The long-run average is around 7%. Rates below 5% suggest stretched consumers; above 10% indicates elevated caution or forced saving.",
        },
        'bullets': [
            'Shows what percentage of after-tax income Americans save rather than spend. The savings rate reflects both consumer confidence and financial cushion—low rates may signal households are stretched or confident; high rates often indicate uncertainty or inability to spend (as during lockdowns).',
            'Historical context: The savings rate spiked to 33% in April 2020 when pandemic stimulus arrived but spending opportunities vanished. It then fell below 3% in 2022 as inflation eroded purchasing power and households drew down savings. Rates persistently below 5% can signal vulnerability—less buffer if job losses or unexpected expenses hit.'
        ]
    },

    # Consumer Credit & Debt
    'TOTALSL': {
        'name': 'Total Consumer Credit Outstanding',
        'unit': 'Billions of Dollars',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Total consumer credit includes all short- and intermediate-term credit extended to individuals, excluding loans secured by real estate. This covers credit cards, auto loans, student loans, and other personal loans.',
            'Rising consumer credit can indicate confidence and spending power, but rapid growth may signal overextension. Total consumer credit topped $5 trillion in 2023, with growth driven largely by auto and student loans.'
        ]
    },
    'REVOLSL': {
        'name': 'Revolving Consumer Credit Outstanding',
        'unit': 'Billions of Dollars',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Revolving credit is primarily credit card debt—credit that can be borrowed, repaid, and borrowed again. It\'s the most flexible and typically highest-interest form of consumer debt.',
            'Credit card balances are a real-time indicator of consumer financial stress. Balances that grow faster than incomes may indicate stretched households relying on expensive credit to maintain spending.'
        ]
    },
    'NONREVSL': {
        'name': 'Nonrevolving Consumer Credit Outstanding',
        'unit': 'Billions of Dollars',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Nonrevolving credit includes auto loans, student loans, and other installment loans with fixed payment schedules. These are typically larger, longer-term obligations than credit card debt.',
            'Auto loan growth signals vehicle affordability and consumer confidence in making major purchases. Student loan growth reflects education costs and financing trends. Together they represent the bulk of non-mortgage consumer debt.'
        ]
    },
    'TDSP': {
        'name': 'Household Debt Service Payments as % of Disposable Income',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'rate',
        'benchmark': {
            'value': 10.0,
            'comparison': 'above',
            'text': "Debt service above 12% historically signals stressed households. Below 10% suggests manageable debt loads.",
        },
        'bullets': [
            'This ratio shows what percentage of after-tax income goes to required debt payments (mortgage and consumer debt). It\'s a key measure of household financial health and debt burden.',
            'The debt service ratio peaked near 13% before the 2008 financial crisis, then fell to historic lows around 9% as households deleveraged and rates stayed low. Rising rates push this ratio higher even without new borrowing.'
        ]
    },

    # Stocks
    'SP500': {
        'name': 'S&P 500 Index',
        'unit': 'Index',
        'source': 'S&P Dow Jones Indices LLC',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'index',
        'bullets': [
            'The S&P 500 is the most widely followed stock market index in the world—the closest thing to a single number for "the stock market." It tracks 500 of the largest U.S. companies, representing roughly $40 trillion in market value and about 80% of total U.S. stock market capitalization.',
            'Stock prices are forward-looking, reflecting expectations about future corporate profits. The long-term average return is roughly 10% annually (7% after inflation), but with significant volatility. Stock wealth affects consumer spending: rising markets create a "wealth effect" that boosts confidence and spending, while crashes do the opposite.'
        ]
    },

    # Industrial Production & Manufacturing
    'INDPRO': {
        'name': 'Industrial Production Index',
        'unit': 'Index 2017=100',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Industrial Production Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Measures real output of the manufacturing, mining, and electric and gas utilities industries. This is the primary measure of industrial activity in the U.S.',
            'Industrial production is more cyclical than GDP and often signals turning points earlier. A sustained decline often precedes or accompanies recession.'
        ]
    },
    'IPMAN': {
        'name': 'Industrial Production: Manufacturing',
        'unit': 'Index 2017=100',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Manufacturing Output Growth',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Measures physical output of the manufacturing sector specifically, excluding mining and utilities.',
            'Manufacturing output is closely watched as a barometer of goods-producing activity and global trade competitiveness.'
        ]
    },
    'TCU': {
        'name': 'Capacity Utilization: Total Industry',
        'unit': 'Percent of Capacity',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'benchmark': {
            'value': 80.0,
            'comparison': 'above',
            'text': "Capacity utilization above 80% historically signals inflationary pressure; below 75% indicates significant slack.",
        },
        'bullets': [
            'Shows what percentage of industrial capacity is being used. High utilization (above 80%) can signal inflationary pressure as firms hit production limits.',
            'Low capacity utilization indicates economic slack and room for growth without inflation. The long-run average is around 78-80%.'
        ]
    },

    # Leading Indicators
    'USSLIND': {
        'name': 'Leading Index for the United States',
        'unit': 'Percent',
        'source': 'Federal Reserve Bank of Philadelphia',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'benchmark': {
            'value': 0.0,
            'comparison': 'below',
            'text': "Negative readings signal expected economic contraction in the coming months.",
        },
        'bullets': [
            'The Leading Index forecasts economic growth 6 months ahead. It combines multiple indicators including housing permits, initial claims, and interest rate spreads into a single forward-looking measure.',
            'Persistently negative readings have preceded recessions, though false signals do occur. The index is more reliable for predicting slowdowns than for timing the exact onset of recession.'
        ]
    },
    'BBKMLEIX': {
        'name': 'Brave-Butters-Kelley Leading Index',
        'unit': 'Standard Deviations',
        'source': 'Federal Reserve Bank of Chicago',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'benchmark': {
            'value': 0.0,
            'comparison': 'below',
            'text': "Negative readings signal expected economic slowdown.",
        },
        'bullets': [
            'The BBK Leading Index forecasts economic growth using dynamic factor analysis of 490 monthly indicators. Positive values indicate expected above-trend growth; negative values signal slowdown.',
            'This index provides a forward-looking view of where the economy is headed over the next several months. Persistent negative readings have historically preceded recessions.'
        ]
    },
    'CFNAI': {
        'name': 'Chicago Fed National Activity Index',
        'unit': 'Index',
        'source': 'Federal Reserve Bank of Chicago',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'index',
        'benchmark': {
            'value': -0.7,
            'comparison': 'below',
            'text': "Readings below -0.7 following a period of growth have historically been associated with recession.",
        },
        'bullets': [
            'The CFNAI is a weighted average of 85 monthly indicators of national economic activity. A zero value means the economy is expanding at its historical trend; positive indicates above-trend growth.',
            'The 3-month moving average (CFNAIMA3) is often preferred for reducing volatility. Readings above +0.7 may signal emerging inflationary pressure; below -0.7 following expansion suggests recession risk.'
        ]
    },
    'SAHMREALTIME': {
        'name': 'Sahm Rule Recession Indicator',
        'unit': 'Percentage Points',
        'source': 'Federal Reserve Bank of St. Louis',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'benchmark': {
            'value': 0.5,
            'comparison': 'above',
            'text': "A reading of 0.5 or higher signals recession has likely begun.",
        },
        'bullets': [
            'The Sahm Rule triggers when the 3-month average unemployment rate rises 0.5 percentage points above its low from the prior 12 months. It has identified every U.S. recession since 1970 with no false positives.',
            'Named after economist Claudia Sahm, who developed it as a trigger for automatic stabilizers. Unlike yield curve inversion which leads by 12-18 months, the Sahm Rule signals recession has already started—useful for fast policy response.'
        ]
    },

    # Productivity
    'OPHNFB': {
        'name': 'Nonfarm Business Sector: Labor Productivity',
        'unit': 'Index 2017=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'index',
        'show_yoy': True,
        'yoy_name': 'Labor Productivity Growth',
        'yoy_unit': '% Change YoY',
        'benchmark': {
            'value': 2.0,
            'comparison': 'above',
            'text': "Long-run productivity growth averages 1.5-2% annually. Higher rates signal efficiency gains; sustained low rates limit real wage growth.",
            'applies_to_yoy': True,
        },
        'bullets': [
            'Labor productivity measures output per hour worked—the key to rising living standards over time. When workers produce more per hour, businesses can pay higher real wages without raising prices.',
            'Productivity growth averaged 2.8% in the 1950s-60s, slowed to 1.5% from 1973-1995, surged to 2.5% during the late-1990s tech boom, then returned to ~1.5% through 2019. Some economists see AI potentially driving a new productivity acceleration.'
        ]
    },

    # Demographics
    'LNS14000002': {
        'name': 'Unemployment Rate - Women',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'bullets': [
            'Tracks unemployment specifically for women aged 16 and over. Gender-specific labor data helps identify whether economic gains and losses are shared broadly or concentrated in particular groups.',
            'The COVID-19 recession was initially labeled a "she-cession" because women—concentrated in hard-hit service industries and bearing disproportionate childcare burdens—saw sharper job losses than men. Remarkably, women\'s unemployment fell below men\'s in 2022 for the first time in decades, reflecting strong recovery in service-sector employment.'
        ]
    },
    'LNS12300062': {
        'name': 'Prime-Age Employment-Population Ratio - Women (25-54)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'bullets': [
            'The share of women aged 25-54 who are employed—the single best measure of women\'s labor market progress. By focusing on prime working years, it avoids distortions from education and retirement patterns.',
            'This metric hit an all-time high of 75.3% in 2024, finally surpassing the previous peak from 2000. The rise reflects both cyclical recovery and structural changes in women\'s workforce attachment. However, the U.S. still lags peer countries like Canada and Germany in prime-age women\'s employment, partly due to limited paid family leave and childcare support.'
        ]
    },
    'LNS11300002': {
        'name': 'Labor Force Participation Rate - Women',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'bullets': [
            'One of the most dramatic economic transformations of the 20th century: women\'s labor force participation rose from 34% in 1950 to peak at 60% in 2000. This massive increase in the workforce powered decades of economic growth.',
            'After 2000, participation plateaued and slightly declined—unlike in peer countries where it continued rising. Researchers point to the U.S. lack of paid family leave, affordable childcare, and workplace flexibility policies that other developed nations provide. COVID caused a sharp drop as women absorbed caregiving responsibilities, though most of this decline has since reversed.'
        ]
    },

    # Demographics - Men
    'LNS14000001': {
        'name': 'Unemployment Rate - Men',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'bullets': [
            'Tracks unemployment specifically for men aged 16 and over. Men\'s unemployment tends to be more cyclical than women\'s, rising faster during recessions (particularly in construction and manufacturing downturns) and falling faster in recoveries.',
            'Historically, men had lower unemployment rates than women, but this pattern reversed in recent decades. Since 2010, women\'s unemployment has often been equal to or lower than men\'s, reflecting structural shifts in the economy toward service-sector jobs where women are more concentrated.'
        ]
    },
    'LNS12300061': {
        'name': 'Prime-Age Employment-Population Ratio - Men (25-54)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'benchmark': {
            'value': 86.0,
            'comparison': 'below',
            'text': "Prime-age men's employment ratio peaked at ~89% in the late 1990s. Levels below 86% indicate significant labor market weakness for men.",
        },
        'bullets': [
            'The share of men aged 25-54 who are employed—the single best measure of men\'s labor market health. This metric has shown a troubling long-term decline, falling from 94% in 1960 to around 86% today.',
            'The decline reflects structural changes: manufacturing job losses, increased disability claims, opioid crisis impacts, and rising incarceration. Unlike the unemployment rate, this measure captures men who have dropped out of the labor force entirely—a significant and often overlooked economic and social challenge.'
        ]
    },
    'LNS11300001': {
        'name': 'Labor Force Participation Rate - Men',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'bullets': [
            'The share of men aged 16 and over who are either working or actively looking for work. Men\'s participation has been declining steadily for decades—from 86% in 1950 to around 68% today.',
            'This long-term decline has multiple causes: more men pursuing higher education, earlier retirement, rising disability enrollment, and discouraged workers dropping out. The decline is most pronounced among men without college degrees, reflecting the changing nature of the American economy.'
        ]
    },

    # Demographics - By Race
    'LNS14000003': {
        'name': 'Unemployment Rate - White',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'bullets': [
            'Unemployment rate for White workers. This serves as a baseline for comparing labor market outcomes across racial groups, as White workers make up the largest share of the U.S. workforce.',
            'White unemployment is typically lower than the overall rate and substantially lower than Black or Hispanic unemployment. During the pre-pandemic period of 2019, White unemployment fell to historic lows around 3.0%.'
        ]
    },
    'LNS14000006': {
        'name': 'Unemployment Rate - Black or African American',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'benchmark': {
            'value': 6.0,
            'comparison': 'above',
            'text': "Black unemployment below 6% is historically exceptional—it only first occurred in 2019. The historical average is around 10-12%.",
        },
        'bullets': [
            'Unemployment rate for Black or African American workers. Black unemployment has historically run about twice the White unemployment rate—a persistent gap that has existed since this data began in 1972.',
            'This gap reflects systemic barriers including discrimination, geographic concentration in areas with fewer jobs, lower access to professional networks, and disparities in educational and training opportunities. When Black unemployment falls below 6%, as it did briefly in 2019 and again in 2023, it represents a historically strong labor market for Black workers.'
        ]
    },
    'LNS14000009': {
        'name': 'Unemployment Rate - Hispanic or Latino',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'benchmark': {
            'value': 5.0,
            'comparison': 'above',
            'text': "Hispanic unemployment below 5% indicates a very strong labor market. The historical average is around 7-8%.",
        },
        'bullets': [
            'Unemployment rate for Hispanic or Latino workers. Hispanic unemployment typically falls between White and Black rates, though this gap has narrowed over time.',
            'Hispanic workers are heavily concentrated in construction, agriculture, and service industries—sectors that are particularly cyclical. This means Hispanic unemployment often rises faster during recessions and falls faster during recoveries. In recent years, Hispanic unemployment has reached historic lows, sometimes falling below the overall rate.'
        ]
    },
    'U6RATE': {
        'name': 'U-6 Unemployment Rate (Broad)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
        'benchmark': {
            'value': 8.0,
            'comparison': 'above',
            'text': "U-6 below 8% indicates a healthy labor market. It typically runs 3-4 percentage points above the headline U-3 rate.",
        },
        'bullets': [
            'The broadest measure of unemployment, including: (1) unemployed workers, (2) discouraged workers who have stopped looking, (3) other marginally attached workers, and (4) part-time workers who want full-time jobs. This captures labor market slack that the headline U-3 rate misses.',
            'U-6 is sometimes called the "real" unemployment rate because it includes people who want to work more but can\'t find opportunities. It typically runs 3-4 percentage points above the headline rate. During the depths of the 2009 recession, U-6 peaked at nearly 18%, even as the headline rate showed "only" 10%.'
        ]
    },

    # Commodities & Trade
    'DCOILWTICO': {
        'name': 'Crude Oil Prices: WTI',
        'unit': 'Dollars per Barrel',
        'source': 'Federal Reserve Bank of St. Louis',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'price',
        'bullets': [
            'West Texas Intermediate (WTI) is the U.S. benchmark for crude oil prices. Oil is the lifeblood of the global economy—it powers transportation, heats homes, and serves as feedstock for countless products from plastics to pharmaceuticals.',
            'Oil prices directly affect consumers through gasoline costs and ripple through the economy via transportation and production costs. Sharp price increases act like a tax on consumers and businesses, often tipping economies into recession. The U.S. shale revolution has made America the world\'s largest oil producer, reducing (but not eliminating) vulnerability to global supply disruptions.'
        ]
    },
    'DCOILBRENTEU': {
        'name': 'Crude Oil Prices: Brent',
        'unit': 'Dollars per Barrel',
        'source': 'Federal Reserve Bank of St. Louis',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'price',
        'bullets': [
            'Brent crude is the global benchmark for oil prices, used to price roughly two-thirds of the world\'s internationally traded crude. Named after the Brent oilfield in the North Sea, it represents European and African crude supply.',
            'The WTI-Brent spread reveals U.S. supply conditions: when WTI trades below Brent, U.S. production is abundant. When they converge, the U.S. is more connected to global markets. Brent often leads WTI in reacting to Middle East geopolitical events.'
        ]
    },
    'IMPCH': {
        'name': 'U.S. Imports from China',
        'unit': 'Millions of Dollars',
        'source': 'U.S. Census Bureau',
        'sa': False,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'Measures the total value of goods shipped from China to the United States. China has been America\'s largest source of imports for decades, though trade tensions and supply chain diversification have begun shifting patterns.',
            'Trade data reflects both economic conditions (imports rise when U.S. consumers are spending freely) and policy choices (tariffs reduce imports). Some goods recorded as imports from other countries like Vietnam or Mexico may actually be Chinese goods re-routed to avoid tariffs—a pattern called "transshipment" that complicates the data.'
        ]
    },
    'BOPGSTB': {
        'name': 'Trade Balance (Goods & Services)',
        'unit': 'Millions of Dollars',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
        'bullets': [
            'The trade balance measures exports minus imports. A negative number (deficit) means the U.S. buys more from abroad than it sells. The U.S. has run persistent trade deficits since the 1970s, currently in the range of $60-80 billion monthly.',
            'Despite political rhetoric, trade deficits aren\'t inherently bad. They partly reflect strong U.S. consumer demand, the dollar\'s role as the global reserve currency, and America\'s relative attractiveness for foreign investment. Economists generally focus more on whether trade is balanced over time and whether it supports productive economic activity.'
        ]
    },

    # === ZILLOW HOUSING DATA (NON-FRED) ===
    'zillow_zori_national': {
        'name': 'Zillow Observed Rent Index (ZORI)',
        'unit': 'Dollars per Month',
        'source': 'Zillow Research',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
    },
    'zillow_rent_yoy': {
        'name': 'Zillow Rent YoY Growth',
        'unit': 'Percent',
        'source': 'Zillow Research',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'growth_rate',
    },
    'zillow_zhvi_national': {
        'name': 'Zillow Home Value Index (ZHVI)',
        'unit': 'Dollars',
        'source': 'Zillow Research',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'level',
    },
    'zillow_home_value_yoy': {
        'name': 'Zillow Home Value YoY Growth',
        'unit': 'Percent',
        'source': 'Zillow Research',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'growth_rate',
    },

    # === EIA ENERGY DATA (NON-FRED) ===
    'eia_wti_crude': {
        'name': 'WTI Crude Oil Price',
        'unit': 'Dollars per Barrel',
        'source': 'U.S. Energy Information Administration',
        'sa': False,
        'frequency': 'weekly',
        'data_type': 'price',
    },
    'eia_brent_crude': {
        'name': 'Brent Crude Oil Price',
        'unit': 'Dollars per Barrel',
        'source': 'U.S. Energy Information Administration',
        'sa': False,
        'frequency': 'weekly',
        'data_type': 'price',
    },
    'eia_gasoline_retail': {
        'name': 'Retail Gasoline Price',
        'unit': 'Dollars per Gallon',
        'source': 'U.S. Energy Information Administration',
        'sa': False,
        'frequency': 'weekly',
        'data_type': 'price',
    },
    'eia_diesel_retail': {
        'name': 'Retail Diesel Price',
        'unit': 'Dollars per Gallon',
        'source': 'U.S. Energy Information Administration',
        'sa': False,
        'frequency': 'weekly',
        'data_type': 'price',
    },
    'eia_natural_gas_henry_hub': {
        'name': 'Natural Gas Price (Henry Hub)',
        'unit': 'Dollars per MMBtu',
        'source': 'U.S. Energy Information Administration',
        'sa': False,
        'frequency': 'weekly',
        'data_type': 'price',
    },
    'eia_crude_stocks': {
        'name': 'US Crude Oil Inventories',
        'unit': 'Millions of Barrels',
        'source': 'U.S. Energy Information Administration',
        'sa': False,
        'frequency': 'weekly',
        'data_type': 'level',
    },
    'eia_crude_production': {
        'name': 'US Crude Oil Production',
        'unit': 'Thousands of Barrels per Day',
        'source': 'U.S. Energy Information Administration',
        'sa': False,
        'frequency': 'weekly',
        'data_type': 'level',
    },

    # === ALPHA VANTAGE MARKET DATA (NON-FRED) ===
    'av_spy': {
        'name': 'S&P 500 ETF (SPY)',
        'unit': 'Dollars',
        'source': 'Alpha Vantage',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'price',
    },
    'av_treasury_10y': {
        'name': '10-Year Treasury Yield',
        'unit': 'Percent',
        'source': 'Alpha Vantage',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'rate',
    },
    'av_treasury_2y': {
        'name': '2-Year Treasury Yield',
        'unit': 'Percent',
        'source': 'Alpha Vantage',
        'sa': False,
        'frequency': 'daily',
        'data_type': 'rate',
    },
}


# =============================================================================
# AUTO-DETECTION: Can these series be combined on one chart?
# =============================================================================

def can_combine_series(series_ids: list) -> tuple[bool, str]:
    """
    Determine if series can be meaningfully combined on one chart based on unit compatibility.

    Args:
        series_ids: List of FRED series IDs to check

    Returns:
        Tuple of (can_combine: bool, reason: str)

    Logic:
        - All percentage rates (unemployment, inflation, yields) → COMBINE
        - All indexes (CPI, PCE, Case-Shiller) → COMBINE (can normalize)
        - All dollar amounts → COMBINE
        - Mixed units (thousands vs percent) → SEPARATE
    """
    if len(series_ids) < 2:
        return False, "Need at least 2 series to combine"

    if len(series_ids) > 4:
        return False, "Too many series (>4) for readable chart"

    # Get metadata for each series
    units = []
    data_types = []

    for sid in series_ids:
        info = SERIES_DB.get(sid, {})
        unit = info.get('unit', '').lower()
        dtype = info.get('data_type', 'unknown')
        units.append(unit)
        data_types.append(dtype)

    # Rule 1: All rates (unemployment, participation, etc.) → COMBINE
    if all(dt == 'rate' for dt in data_types):
        return True, "All series are rates (percentages) - compatible for comparison"

    # Rule 2: All units contain "percent" → COMBINE
    if all('percent' in u for u in units):
        return True, "All series are percentages - compatible for comparison"

    # Rule 3: All units contain "index" → COMBINE (can be normalized)
    if all('index' in u for u in units):
        return True, "All series are indexes - can be normalized for comparison"

    # Rule 4: All units contain "dollars" or currency → COMBINE
    if all('dollar' in u or '$' in u for u in units):
        return True, "All series are dollar amounts - compatible for comparison"

    # Rule 5: All levels that are conceptually similar (e.g., both employment counts)
    # Check if all are "Thousands of Persons" - employment data
    if all('thousands of persons' in u for u in units):
        return True, "All series are employment counts - compatible for comparison"

    # Rule 6: Mixed but related - rates and levels that could work with dual axis
    # e.g., job openings (thousands) vs unemployment rate (percent)
    # These are commonly compared but need care
    has_rate = any(dt == 'rate' for dt in data_types)
    has_level = any(dt == 'level' for dt in data_types)

    if has_rate and has_level and len(series_ids) == 2:
        # Two series, one rate one level - could use dual Y-axis
        return True, "Rate vs level comparison - will use appropriate scaling"

    # Default: Don't combine if units are too different
    unique_unit_types = set()
    for u in units:
        if 'percent' in u:
            unique_unit_types.add('percent')
        elif 'index' in u:
            unique_unit_types.add('index')
        elif 'dollar' in u:
            unique_unit_types.add('dollar')
        elif 'thousands' in u:
            unique_unit_types.add('thousands')
        elif 'millions' in u:
            unique_unit_types.add('millions')
        elif 'billions' in u:
            unique_unit_types.add('billions')
        else:
            unique_unit_types.add('other')

    if len(unique_unit_types) == 1:
        return True, f"All series share compatible units"

    return False, f"Mixed units ({', '.join(unique_unit_types)}) - separate charts recommended"


def suggest_chart_groups(series_ids: list) -> list:
    """
    For queries with 3+ series, suggest logical groupings for separate charts.

    Groups series by:
    1. Unit compatibility (rates together, levels together)
    2. Conceptual relationship (inflation measures, employment measures)

    Returns:
        List of chart group dicts: [{"series": [...], "title": "..."}, ...]
    """
    if len(series_ids) <= 2:
        return []  # No grouping needed

    # Categorize series by type
    rates = []
    levels_employment = []
    levels_other = []
    indexes = []

    for sid in series_ids:
        info = SERIES_DB.get(sid, {})
        unit = info.get('unit', '').lower()
        dtype = info.get('data_type', 'unknown')
        name = info.get('name', sid)

        if dtype == 'rate' or 'percent' in unit:
            rates.append((sid, name))
        elif 'index' in unit:
            indexes.append((sid, name))
        elif 'thousands of persons' in unit or 'employment' in name.lower():
            levels_employment.append((sid, name))
        else:
            levels_other.append((sid, name))

    groups = []

    # Group rates together
    if len(rates) >= 2:
        groups.append({
            "series": [s[0] for s in rates],
            "title": "Rates (%)",
            "combine": True
        })
    elif len(rates) == 1:
        groups.append({
            "series": [rates[0][0]],
            "title": rates[0][1],
            "combine": False
        })

    # Group indexes together
    if len(indexes) >= 2:
        groups.append({
            "series": [s[0] for s in indexes],
            "title": "Price Indexes",
            "combine": True,
            "show_yoy": True  # Indexes usually shown as YoY change
        })
    elif len(indexes) == 1:
        groups.append({
            "series": [indexes[0][0]],
            "title": indexes[0][1],
            "combine": False,
            "show_yoy": True
        })

    # Group employment levels together
    if len(levels_employment) >= 2:
        groups.append({
            "series": [s[0] for s in levels_employment],
            "title": "Employment",
            "combine": True
        })
    elif len(levels_employment) == 1:
        groups.append({
            "series": [levels_employment[0][0]],
            "title": levels_employment[0][1],
            "combine": False
        })

    # Other levels
    for sid, name in levels_other:
        groups.append({
            "series": [sid],
            "title": name,
            "combine": False
        })

    return groups


# Query mappings with economist intuitions
QUERY_MAP = {
    # Economy overview - show the big picture (annual GDP for stability)
    'economy': {'series': ['A191RO1Q156NBEA', 'UNRATE', 'CPIAUCSL'], 'combine': False},
    'how is the economy': {'series': ['A191RO1Q156NBEA', 'UNRATE', 'CPIAUCSL'], 'combine': False},
    'economic overview': {'series': ['A191RO1Q156NBEA', 'UNRATE', 'CPIAUCSL'], 'combine': False},
    'recession': {'series': ['A191RO1Q156NBEA', 'UNRATE', 'T10Y2Y'], 'combine': False},

    # Jobs - start simple with payrolls + unemployment
    'job market': {'series': ['PAYEMS', 'UNRATE'], 'combine': False},
    'jobs': {'series': ['PAYEMS', 'UNRATE'], 'combine': False},
    'employment': {'series': ['PAYEMS', 'UNRATE'], 'combine': False},
    'labor market': {'series': ['PAYEMS', 'UNRATE'], 'combine': False},
    'unemployment': {'series': ['UNRATE'], 'combine': False},
    'hiring': {'series': ['PAYEMS', 'JTSJOL'], 'combine': False},
    'job openings': {'series': ['JTSJOL'], 'combine': False},

    # Labor market health (deeper) - use prime-age
    'labor market health': {'series': ['LNS12300060', 'UNRATE'], 'combine': False},
    'labor market tight': {'series': ['LNS12300060', 'JTSJOL', 'UNRATE'], 'combine': False},
    'participation': {'series': ['LNS11300060', 'LNS11300000'], 'combine': True},
    'prime age': {'series': ['LNS12300060'], 'combine': False},

    # Inflation - CPI for general, PCE for Fed
    'inflation': {'series': ['CPIAUCSL', 'CPILFESL'], 'combine': True},
    'cpi': {'series': ['CPIAUCSL'], 'combine': False},
    'core inflation': {'series': ['CPILFESL'], 'combine': False},
    'pce': {'series': ['PCEPI', 'PCEPILFE'], 'combine': True},
    'fed inflation': {'series': ['PCEPILFE'], 'combine': False},
    'rent inflation': {'series': ['CUSR0000SAH1'], 'combine': False},
    'shelter': {'series': ['CUSR0000SAH1'], 'combine': False},

    # GDP - Annual (YoY), quarterly, core GDP, and GDPNow
    'gdp': {'series': ['A191RO1Q156NBEA', 'A191RL1Q225SBEA', 'PB0000031Q225SBEA', 'GDPNOW'], 'combine': False},
    'gdp growth': {'series': ['A191RO1Q156NBEA', 'A191RL1Q225SBEA', 'PB0000031Q225SBEA', 'GDPNOW'], 'combine': False},
    'economic growth': {'series': ['A191RO1Q156NBEA', 'A191RL1Q225SBEA', 'PB0000031Q225SBEA', 'GDPNOW'], 'combine': False},
    'real gdp': {'series': ['GDPC1'], 'combine': False},
    'annual gdp': {'series': ['A191RL1A225NBEA', 'A191RO1Q156NBEA'], 'combine': False},
    'annual gdp growth': {'series': ['A191RL1A225NBEA', 'A191RO1Q156NBEA'], 'combine': False},
    'yearly gdp': {'series': ['A191RL1A225NBEA', 'A191RO1Q156NBEA'], 'combine': False},
    'core gdp': {'series': ['PB0000031Q225SBEA'], 'combine': False},
    'private demand': {'series': ['PB0000031Q225SBEA'], 'combine': False},
    'final sales': {'series': ['PB0000031Q225SBEA'], 'combine': False},

    # Interest rates
    'interest rates': {'series': ['FEDFUNDS', 'DGS10'], 'combine': True},
    'rates': {'series': ['FEDFUNDS', 'DGS10'], 'combine': True},
    'fed': {'series': ['FEDFUNDS'], 'combine': False},
    'fed funds': {'series': ['FEDFUNDS'], 'combine': False},
    'treasury': {'series': ['DGS10', 'DGS2'], 'combine': True},
    'yield curve': {'series': ['T10Y2Y'], 'combine': False},
    'mortgage': {'series': ['MORTGAGE30US'], 'combine': False},

    # Housing
    'housing': {'series': ['CSUSHPINSA', 'HOUST'], 'combine': False},
    'home prices': {'series': ['CSUSHPINSA'], 'combine': False},
    'housing market': {'series': ['CSUSHPINSA', 'MORTGAGE30US'], 'combine': False},

    # Consumer
    'consumer': {'series': ['RSXFS', 'UMCSENT'], 'combine': False},
    'consumer sentiment': {'series': ['UMCSENT'], 'combine': False},
    'retail sales': {'series': ['RSXFS'], 'combine': False},

    # Stocks
    'stock market': {'series': ['SP500'], 'combine': False},
    'stocks': {'series': ['SP500'], 'combine': False},

    # Demographics
    'women': {'series': ['LNS14000002', 'LNS12300062', 'LNS11300002'], 'combine': False},
    'women labor': {'series': ['LNS14000002', 'LNS12300062', 'LNS11300002'], 'combine': False},
    'women employment': {'series': ['LNS14000002', 'LNS12300062'], 'combine': False},

    # Trade & Commodities
    'oil': {'series': ['DCOILWTICO', 'DCOILBRENTEU'], 'combine': True},
    'oil prices': {'series': ['DCOILWTICO', 'DCOILBRENTEU'], 'combine': True},
    'china': {'series': ['IMPCH'], 'combine': False},
    'china trade': {'series': ['IMPCH'], 'combine': False},
    'trade': {'series': ['BOPGSTB'], 'combine': False},
    'trade deficit': {'series': ['BOPGSTB'], 'combine': False},

    # Wages
    'wages': {'series': ['CES0500000003'], 'combine': False},
    'earnings': {'series': ['CES0500000003'], 'combine': False},
}

QUICK_SEARCHES = {
    "Jobs": "job market",
    "Inflation": "inflation",
    "GDP": "gdp growth",
    "Rates": "interest rates",
    "Housing": "housing",
    "Women": "women labor",
    "Oil": "oil prices",
    "China": "china trade",
}

TIME_PERIODS = {
    "5 Years": 5,
    "10 Years": 10,
    "20 Years": 20,
    "All Available": None,
}

# Comprehensive economist prompt with intuitions
ECONOMIST_PROMPT_BASE = """You are an expert economist helping interpret economic data questions for the FRED (Federal Reserve Economic Data) database. Think like Jason Furman or a top policy economist.

## YOUR JOB
Interpret the user's question and return EITHER:
1. Specific FRED series IDs if you know them
2. Good search terms to find the right series in FRED's search API

IMPORTANT: For ANY topic you don't have memorized series IDs for, ALWAYS provide search_terms. FRED has 800,000+ series covering almost any economic topic - auto sales, semiconductor production, restaurant employment, avocado prices, etc. If unsure of exact IDs, give search terms.

## CORE PRINCIPLES
1. **MULTI-DIMENSIONAL ANSWERS**: Any "how is X doing?" question needs MULTIPLE dimensions, not one metric. Think like an economist writing a briefing:
   - Industry health → employment + prices + wages + output
   - Economy health → GDP + jobs + inflation + rates
   - Demographic group → employment + unemployment + participation + wages
   - Housing → prices + sales + starts + affordability
   A single metric is an INCOMPLETE answer.
2. BE COMPREHENSIVE: Include up to 4 series that tell different parts of the story.
3. USE SEASONALLY ADJUSTED DATA by default.
4. For topics you don't know exact series for, provide SPECIFIC search terms.
5. Each series should add unique insight - don't include redundant measures.
6. EVERY CHART MUST HAVE AN EXPLANATORY BULLET.

## WELL-KNOWN SERIES

### Employment
- PAYEMS = Nonfarm payrolls (THE jobs number, from establishment survey)
- UNRATE = Unemployment rate (U-3, from household survey)
- LNS12300060 = Prime-age (25-54) employment-population ratio (BEST labor market health measure)
- CES0500000003 = Average hourly earnings
- JTSJOL = Job openings (JOLTS)

### Sector Employment (use these patterns)
- MANEMP = Manufacturing employment
- USCONS = Construction employment
- USTRADE = Retail trade employment
- USFIRE = Finance employment
- USEHS = Education & health employment
- USLAH = Leisure & hospitality employment
- USINFO = Information sector employment
- USPBS = Professional & business services

### Inflation
- CPIAUCSL = CPI All Items (headline inflation)
- CPILFESL = Core CPI (ex food & energy)
- PCEPILFE = Core PCE (Fed's target measure)
- CUSR0000SAH1 = CPI Shelter
- CUSR0000SETB01 = CPI Gasoline

### GDP & Output
- GDPC1 = Real GDP level (billions of chained 2017 dollars)
- A191RL1Q225SBEA = Real GDP growth rate (quarterly, annualized) - the headline number
- A191RO1Q156NBEA = Real GDP growth (quarter vs same quarter last year) - more stable, shows 12-month trend
- A191RL1A225NBEA = Annual real GDP growth (full year vs prior year) - the definitive annual measure
- PB0000031Q225SBEA = Real Final Sales to Private Domestic Purchasers ("core GDP") - excludes volatile gov't, trade, inventories; better predictor of future growth per CEA
- INDPRO = Industrial production

### Interest Rates
- FEDFUNDS = Fed funds rate
- DGS10 = 10-year Treasury
- DGS2 = 2-year Treasury
- MORTGAGE30US = 30-year mortgage rate
- T10Y2Y = Yield curve spread

### Housing
- CSUSHPINSA = Case-Shiller home prices
- HOUST = Housing starts
- PERMIT = Building permits
- EXHOSLUSM495S = Existing home sales

### Consumer
- RSXFS = Retail sales
- UMCSENT = Consumer sentiment
- TOTALSA = Total vehicle sales

### Trade & International
- BOPGSTB = Trade balance
- DTWEXBGS = Trade-weighted dollar index
- IMPCH = Imports from China

### Commodities
- DCOILWTICO = WTI crude oil
- GASREGW = Regular gas price
- PPIACO = Producer price index commodities

### Demographics - Women
- LNS14000002 = Unemployment rate for women
- LNS12300062 = Prime-age employment-population ratio for women (25-54) - BEST measure
- LNS11300002 = Labor force participation rate for women

### Demographics - Men
- LNS14000001 = Unemployment rate for men
- LNS12300061 = Prime-age employment-population ratio for men (25-54)
- LNS11300001 = Labor force participation rate for men

### Demographics - By Race
- LNS14000006 = Unemployment rate - Black or African American
- LNS14000009 = Unemployment rate - Hispanic or Latino
- LNS14000003 = Unemployment rate - White

### Demographics - Foreign-Born / Immigrants
- LNU04073395 = Unemployment rate - Foreign born
- LNU02073395 = Employment level - Foreign born
- LNU01373395 = Labor force - Foreign born
- LNU02073413 = Employment level - Native born (for comparison)
- Search for "foreign born employment" or "immigrant labor" for additional series

## CRITICAL RULE FOR DEMOGRAPHIC QUESTIONS
When asked about a specific demographic group (women, men, Black workers, Hispanic workers, immigrants, foreign-born, etc.), NEVER use aggregate series like PAYEMS (total nonfarm payrolls) or UNRATE (overall unemployment). These tell you nothing about that specific group. Instead, use the demographic-specific series listed above. For example:
- "How are women doing?" → Use LNS14000002, LNS12300062, LNS11300002 (women-specific series)
- "Black unemployment" → Use LNS14000006 (Black unemployment rate)
- "How is the economy for immigrants?" → Use LNU04073395 (foreign-born unemployment), LNU02073395 (foreign-born employment), plus search for wages
- Do NOT mix in PAYEMS, UNRATE, GDP, or other aggregate measures that don't break down by demographic.

## DESCRIBING JOB GAINS (PAYEMS)
When describing employment/jobs data from PAYEMS, use these metrics:
- Monthly job gains (e.g., "The economy added 200,000 jobs in January")
- Average monthly job gains over 3 months, 6 months, or 12 months (e.g., "averaging 180,000 jobs per month over the past quarter")
- Annual jobs growth relative to previous years (e.g., "2024 added 2.4 million jobs vs 2.7 million in 2023")

Do NOT use year-over-year job growth as a percentage or millions figure. Economists don't describe employment that way - they focus on monthly gains and averages.

## INDUSTRY/SECTOR HEALTH QUERIES
When asked "how is [industry] doing?" or about an industry's health, provide a HOLISTIC view with multiple dimensions:
1. **Employment** - Jobs in that sector (e.g., USLAH for leisure/hospitality, MANEMP for manufacturing)
2. **Prices** - Relevant CPI component (e.g., CUSR0000SEFV for food away from home/restaurants)
3. **Wages/Earnings** - Sector-specific earnings if available, or search for it
4. **Output/Sales** - Production index or sales data if relevant

Examples:
- "How are restaurants doing?" → USLAH (leisure/hospitality jobs), CUSR0000SEFV (restaurant prices), search for "food services earnings"
- "How is manufacturing doing?" → MANEMP (manufacturing jobs), INDPRO (industrial production), CES3000000008 (manufacturing earnings)
- "How is construction doing?" → USCONS (construction jobs), search for "construction spending", CES2000000008 (construction earnings)

Do NOT just return one metric (like prices alone) - give the full picture.

## FOR UNKNOWN TOPICS
If the user asks about something not listed above (e.g., "semiconductor production", "restaurant sales", "California unemployment", "auto manufacturing"), provide search_terms like:
- "semiconductor production index"
- "restaurant sales receipts"
- "California unemployment rate"
- "motor vehicle manufacturing employment"

FRED's search API will find the right series.

## COMBINE_CHART RULES - WHEN TO COMBINE SERIES

**DEFAULT TO COMBINING** when series are related and have compatible units. Users find comparisons more insightful than isolated charts.

**COMBINE (combine_chart=true) when:**
- Series share units (all percentages, all rates, all indexes, all dollar amounts)
- User asks to compare, even implicitly ("inflation and wages", "unemployment by group")
- Series answer related aspects of the same question

**CONCRETE EXAMPLES - COMBINE:**
- "CPI vs PCE inflation" → Both YoY % rates → COMBINE
- "Headline vs core inflation" → Both YoY % → COMBINE
- "UNRATE vs U6RATE" → Both unemployment rates (%) → COMBINE
- "Wages vs inflation" → Both YoY % growth → COMBINE (shows if wages keep up)
- "Black vs White unemployment" → Both rates (%) → COMBINE (shows disparity)
- "2-year vs 10-year Treasury" → Both yields (%) → COMBINE (shows yield curve)
- "Job openings vs unemployment" → Comparison intent → COMBINE
- "Manufacturing vs healthcare jobs" → Both YoY % growth → COMBINE

**SEPARATE (combine_chart=false) when:**
- "How is the economy?" → Multiple unrelated concepts (jobs, inflation, GDP) → SEPARATE
- "Total payrolls and unemployment rate" → Thousands vs percent, no comparison intent → SEPARATE
- More than 4 series with different scales → Too cluttered → SEPARATE

**KEY PRINCIPLE:** If user mentions TWO things together, they probably want to compare them. Combine unless units are fundamentally incompatible (e.g., millions of jobs vs percentage rate).

## ***CRITICAL RULES FOR EXPLANATIONS***

**DO NOT HALLUCINATE DATES!** Only use dates that come from actual data. If you don't know the exact date, say "recent data" or "latest available". NEVER make up dates.

**PAYROLLS = CHANGES, NOT LEVELS!** For employment/payroll data:
- BAD: "Total nonfarm payrolls are 159.5 million"
- GOOD: "The economy added 150K jobs last month" or "Job growth has averaged 180K/month"
- ALWAYS focus on monthly gains, 3-month averages, year-over-year changes
- The LEVEL of total employment is almost meaningless - CHANGES tell the story

## RESPONSE FORMAT
Return JSON only:
{
  "series": ["SERIES_ID1", "SERIES_ID2"],
  "search_terms": ["specific search term 1", "specific search term 2"],
  "explanation": "Brief explanation of why these series answer the question",
  "show_yoy": false,
  "show_mom": false,
  "show_avg_annual": false,
  "combine_chart": false,
  "is_followup": false,
  "add_to_previous": false
}

CRITICAL: If you're not 100% sure of exact series IDs, ALWAYS include search_terms. It's better to search than guess wrong.

USER QUESTION: """

# Follow-up prompt that includes context
FOLLOWUP_PROMPT = """You are an expert economist helping with a FOLLOW-UP question about economic data.

## PREVIOUS CONTEXT
The user previously asked: "{previous_query}"
We showed them these series: {previous_series}
Series names: {series_names}

## FOLLOW-UP INTERPRETATION
The user is now asking a follow-up. Common follow-up requests include:
- "Show me year-over-year" → set show_yoy: true, keep same series
- "Show month-over-month" → set show_mom: true, keep same series
- "Add unemployment to this" → set add_to_previous: true, add new series
- "Compare this to housing" → might want new chart or combined
- "What about for women?" → might want demographic breakdown
- "Average annual change" → set show_avg_annual: true
- "Go back further" or "show 20 years" → same series, different time range
- "Combine these" → set combine_chart: true

## RESPONSE FORMAT
Return JSON only:
{{
  "series": ["SERIES_ID1"],  // New series to add, or same series if just changing view
  "search_terms": [],
  "explanation": "What we're showing and why",
  "show_yoy": false,  // Year-over-year percent change
  "show_mom": false,  // Month-over-month percent change
  "show_avg_annual": false,  // Average annual values
  "combine_chart": false,  // Combine all series on one chart
  "is_followup": true,
  "add_to_previous": false,  // true = add new series to previous results
  "keep_previous_series": true  // false = replace previous series entirely
}}

If the user's question is NOT a follow-up (completely new topic), set is_followup: false.

USER FOLLOW-UP: """


def call_claude(query: str, previous_context: dict = None) -> dict:
    """Call Claude API to interpret the economic question.

    Args:
        query: The user's question
        previous_context: Dict with 'query', 'series', 'series_names' for follow-ups
    """
    default_response = {
        'series': [],
        'search_terms': [query],
        'explanation': '',
        'show_yoy': False,
        'show_mom': False,
        'show_avg_annual': False,
        'combine_chart': False,
        'is_followup': False,
        'add_to_previous': False,
        'keep_previous_series': False
    }

    if not ANTHROPIC_API_KEY:
        return default_response

    # Build prompt based on whether this is a follow-up
    if previous_context and previous_context.get('series'):
        prompt = FOLLOWUP_PROMPT.format(
            previous_query=previous_context.get('query', ''),
            previous_series=previous_context.get('series', []),
            series_names=previous_context.get('series_names', [])
        ) + query
    else:
        prompt = ECONOMIST_PROMPT_BASE + query

    url = 'https://api.anthropic.com/v1/messages'
    payload = {
        'model': 'claude-opus-4-5-20251101',
        'max_tokens': 1024,
        'messages': [{'role': 'user', 'content': prompt}]
    }
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01'
    }

    try:
        req = Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            content = result['content'][0]['text']
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            parsed = json.loads(content.strip())
            # Ensure all expected keys exist
            for key in default_response:
                if key not in parsed:
                    parsed[key] = default_response[key]
            return parsed
    except Exception as e:
        return default_response


# ============================================================================
# QA VALIDATION LAYER
# Validates query-series alignment and optionally uses Gemini as second opinion
# ============================================================================

# Keywords that should map to specific series categories
QUERY_SERIES_ALIGNMENT = {
    # Inflation keywords should return inflation series
    'inflation': ['CPIAUCSL', 'CPILFESL', 'PCEPI', 'PCEPILFE', 'CUSR0000'],
    'prices': ['CPIAUCSL', 'CPILFESL', 'PCEPI', 'CUSR0000', 'CSUSHPINSA'],
    'cpi': ['CPIAUCSL', 'CPILFESL', 'CUSR0000'],
    'pce': ['PCEPI', 'PCEPILFE', 'PCE'],

    # Employment keywords should return employment series
    'unemployment': ['UNRATE', 'U6RATE', 'LNS'],
    'jobs': ['PAYEMS', 'UNRATE', 'JTS', 'LNS'],
    'employment': ['PAYEMS', 'UNRATE', 'LNS', 'EPOP'],
    'labor': ['PAYEMS', 'UNRATE', 'LNS', 'LFPR', 'JTS'],
    'payroll': ['PAYEMS', 'CES'],

    # GDP/growth keywords
    'gdp': ['GDP', 'A191', 'GDPC1', 'GDPNOW'],
    'growth': ['GDP', 'A191', 'GDPC1'],
    'recession': ['GDP', 'SAHM', 'T10Y2Y', 'CFNAI', 'BBKMLEIX'],

    # Rates keywords should return rate series
    'interest rate': ['FEDFUNDS', 'DFF', 'DGS', 'T10Y'],
    'fed fund': ['FEDFUNDS', 'DFF'],
    'mortgage': ['MORTGAGE', 'MORTGAGE30US', 'MORTGAGE15US'],
    'treasury': ['DGS', 'T10Y', 'T5Y'],
    'yield': ['DGS', 'T10Y', 'T5Y', 'T10Y2Y'],

    # Housing keywords - distinguish between prices vs costs
    'housing': ['CSUSHPINSA', 'HOUST', 'MORTGAGE', 'PERMIT', 'HSN', 'CUSR0000SAH'],
    'home price': ['CSUSHPINSA', 'MSPUS', 'ASPUS'],
    'housing cost': ['CUSR0000SAH', 'CUSR0000SEHA', 'CUSR0000SEHC'],  # Shelter/rent inflation
    'rent': ['CUSR0000SEHA', 'CUSR0000SEHC', 'CUSR0000SAH'],
    'shelter': ['CUSR0000SAH', 'CUSR0000SEHA', 'CUSR0000SEHC'],

    # Wage keywords
    'wage': ['CES0500000003', 'LES1252881600', 'AHETPI'],
    'earnings': ['CES0500000003', 'LES1252881600', 'AHETPI'],
    'income': ['PI', 'DSPIC', 'MEHOINUSA'],

    # Trade/International
    'trade': ['BOPGSTB', 'NETEXP', 'EXPGS', 'IMPGS'],
    'export': ['EXPGS', 'BOPTEXP', 'BOPGEXP'],
    'import': ['IMPGS', 'BOPTIMP', 'BOPGIMP'],
    'deficit': ['BOPGSTB', 'FYFSD'],

    # Consumer Behavior
    'consumer confidence': ['UMCSENT', 'CSCICP'],
    'consumer sentiment': ['UMCSENT', 'CSCICP'],
    'consumer spending': ['PCE', 'PCEC96', 'RSAFS'],
    'retail': ['RSAFS', 'MRTSSM', 'RRSFS'],
    'spending': ['PCE', 'PCEC96', 'RSAFS'],

    # Manufacturing/Production
    'manufacturing': ['IPMAN', 'INDPRO', 'NAPMPI', 'MANEMP'],
    'industrial': ['INDPRO', 'IPMAN', 'IPB50001'],
    'production': ['INDPRO', 'IPMAN', 'OUTMS'],

    # Savings/Debt
    'savings': ['PSAVERT', 'PMSAVE'],
    'debt': ['TDSP', 'GFDEBTN', 'CCLACBW027SBOG'],
    'credit': ['CCLACBW027SBOG', 'BUSLOANS', 'TOTCI'],

    # Markets
    'stock': ['SP500', 'DJIA', 'NASDAQCOM', 'VIXCLS'],
    'market': ['SP500', 'DJIA', 'NASDAQCOM'],

    # Money/Fed Policy
    'money supply': ['M2SL', 'M1SL', 'BOGMBASE'],
    'm2': ['M2SL', 'M2V'],

    # Producer Prices
    'ppi': ['PPIACO', 'PPIFIS', 'WPSID62'],
    'producer price': ['PPIACO', 'PPIFIS'],

    # Business
    'corporate profit': ['CP', 'CPROFIT'],
    'business investment': ['PRFI', 'PNFI'],
    'small business': ['NFIB', 'RSAFS', 'USFIRE', 'BUSLOANS'],

    # Energy/Commodities
    'oil': ['DCOILWTICO', 'DCOILBRENTEU', 'CPIENGSL'],
    'gas': ['GASREGW', 'APU000074714', 'CPIENGSL'],
    'energy': ['DCOILWTICO', 'CPIENGSL', 'IPG211111CS'],
    'commodity': ['DCOILWTICO', 'PPIACO', 'PCEPI'],

    # Construction/Infrastructure
    'construction': ['TTLCONS', 'USCONS', 'PERMIT', 'HOUST'],
    'building': ['PERMIT', 'HOUST', 'TTLCONS'],

    # Auto/Vehicles
    'auto': ['TOTALSA', 'IPG3361T3S', 'ALTSALES'],
    'vehicle': ['TOTALSA', 'IPG3361T3S', 'ALTSALES'],
    'car': ['TOTALSA', 'USAUCSFRCONDM', 'CUSR0000SETA01'],

    # Technology/Services
    'technology': ['IPG334', 'USINFO', 'IPG3361T3S'],
    'tech': ['IPG334', 'USINFO'],
    'software': ['IPG334', 'USINFO'],

    # Healthcare
    'healthcare': ['USHCS', 'CPIMEDSL', 'USPBS'],
    'medical': ['CPIMEDSL', 'PCE', 'USHCS'],
    'health': ['USHCS', 'CPIMEDSL'],

    # Food/Restaurants
    'food': ['CPIUFDSL', 'CUSR0000SAF', 'USFIRE'],
    'restaurant': ['USFIRE', 'CPIUFDSL', 'RSAFS'],
    'grocery': ['CPIUFDSL', 'CUSR0000SAF'],

    # Transportation/Logistics
    'transport': ['CPIAPPSL', 'CUSR0000SAT', 'RAILFRTINTERMODAL'],
    'shipping': ['RAILFRTINTERMODAL', 'CUSR0000SAT'],
    'trucking': ['CUSR0000SAT', 'RAILFRTINTERMODAL'],

    # Education
    'education': ['USGOVT', 'CPIENGSL'],

    # Demographic - Race/Ethnicity (CRITICAL: prevents cross-demographic confusion)
    'black': ['LNS14000006', 'LNS12300006', 'LNS11300006'],
    'african american': ['LNS14000006', 'LNS12300006', 'LNS11300006'],
    'hispanic': ['LNS14000009', 'LNS12300009', 'LNS11300009'],
    'latino': ['LNS14000009', 'LNS12300009', 'LNS11300009'],
    'latina': ['LNS14000009', 'LNS12300009', 'LNS11300009'],
    'asian': ['LNS14000004', 'LNS14032183'],
    'white': ['LNS14000003', 'LNS12300003', 'LNS11300003'],

    # Demographic - Gender
    'women': ['LNS14000002', 'LNS12300062', 'LNS11300002'],
    'female': ['LNS14000002', 'LNS12300062', 'LNS11300002'],
    'men': ['LNS14000001', 'LNS12300061', 'LNS11300001'],
    'male': ['LNS14000001', 'LNS12300061', 'LNS11300001'],

    # Demographic - Age
    'youth': ['LNS14000012', 'LNS14000036'],
    'teen': ['LNS14000012'],
    'young worker': ['LNS14000012', 'LNS14000036', 'LNS14000089'],
    'older worker': ['LNS14000095', 'LNS14000097'],
    'prime age': ['LNS12300060', 'LNS11300060', 'LNS14000089'],

    # Demographic - Nativity
    'immigrant': ['LNU04073395', 'LNU02073395', 'LNU01073395'],
    'foreign-born': ['LNU04073395', 'LNU02073395', 'LNU01073395'],
    'foreign born': ['LNU04073395', 'LNU02073395', 'LNU01073395'],
}


def validate_query_series_alignment(query: str, series: list) -> dict:
    """
    Validate that returned series make sense for the query.

    Returns dict with:
        - is_valid: bool
        - confidence: float (0-1)
        - issues: list of potential problems
        - suggestion: str if there's a better match
    """
    if not series:
        return {'is_valid': False, 'confidence': 0, 'issues': ['No series returned'], 'suggestion': None}

    q = query.lower()
    issues = []
    matches_found = 0

    # Check if query keywords align with returned series
    for keyword, expected_prefixes in QUERY_SERIES_ALIGNMENT.items():
        if keyword in q:
            # Check if any returned series matches expected prefixes
            keyword_matched = False
            for s in series:
                for prefix in expected_prefixes:
                    if s.startswith(prefix) or prefix in s:
                        keyword_matched = True
                        matches_found += 1
                        break
                if keyword_matched:
                    break

            if not keyword_matched:
                issues.append(f"Query mentions '{keyword}' but no matching series found")

    # Calculate confidence
    if matches_found > 0:
        confidence = min(1.0, 0.5 + (matches_found * 0.2))
    elif not issues:
        confidence = 0.7  # No keywords matched, but no issues either
    else:
        confidence = 0.3

    return {
        'is_valid': len(issues) == 0 or matches_found > 0,
        'confidence': confidence,
        'issues': issues,
        'suggestion': None
    }


def log_query_resolution(query: str, source: str, series: list, validation: dict = None,
                         explanation: str = "", reasoning_indicators: list = None,
                         is_comparison: bool = False, sources: dict = None):
    """
    Log query resolutions for analysis and improvement.

    Uses the detailed query logger to track:
    - Which queries use precomputed plans vs reasoning vs API
    - What series are returned
    - Patterns that need improvement
    """
    # Use the detailed logger if available
    if QUERY_LOGGING:
        try:
            log_query_detailed(
                query=query,
                series=series,
                method=source,
                explanation=explanation,
                reasoning_indicators=reasoning_indicators,
                is_comparison=is_comparison,
                sources=sources,
            )
        except Exception as e:
            print(f"[Logging] Error: {e}")

    # Also log to console for debugging
    print(f"[QUERY] {query} | Method: {source} | Series: {series}")


def call_economist_reviewer(query: str, series_data: list, original_explanation: str) -> str:
    """Call a second Claude agent to review and improve the explanation.

    This agent sees the actual data values AND recent news context to explain
    not just WHAT is happening but WHY.

    Args:
        query: The user's original question
        series_data: List of (series_id, dates, values, info) tuples with actual data
        original_explanation: The initial explanation from the first agent

    Returns:
        Improved explanation string
    """
    if not ANTHROPIC_API_KEY or not series_data:
        return original_explanation

    # Fetch recent news context for dynamic explanations
    news_context = ""
    if NEWS_CONTEXT_AVAILABLE:
        try:
            news_context = get_economic_context(query)
        except Exception as e:
            print(f"[NewsContext] Error: {e}")
            news_context = ""

    # Build a summary of the data for the reviewer
    data_summary = []
    for series_id, dates, values, info in series_data:
        if not values:
            continue
        name = info.get('name', info.get('title', series_id))
        unit = info.get('unit', info.get('units', ''))
        latest = values[-1]
        latest_date = dates[-1]

        # For payroll changes, use original values for YoY calculation
        # (transformed data is monthly changes, not levels)
        monthly_change = None
        avg_3mo_change = None
        avg_12mo_change = None

        if info.get('is_payroll_change') and info.get('original_values'):
            orig_values = info['original_values']
            # Monthly changes from original data
            if len(orig_values) >= 2:
                monthly_change = orig_values[-1] - orig_values[-2]
            if len(orig_values) >= 4:
                # Average of last 3 months
                changes_3mo = [orig_values[i] - orig_values[i-1] for i in range(-3, 0)]
                avg_3mo_change = sum(changes_3mo) / 3
            if len(orig_values) >= 13:
                # Average of last 12 months
                changes_12mo = [orig_values[i] - orig_values[i-1] for i in range(-12, 0)]
                avg_12mo_change = sum(changes_12mo) / 12
                yoy_change = orig_values[-1] - orig_values[-12]
            else:
                yoy_change = None
            # Also report the original latest value (total jobs)
            latest = orig_values[-1]
            unit = 'Thousands of Persons'
            name = info.get('original_name', 'Total Nonfarm Payrolls')
        elif len(values) >= 12:
            year_ago_val = values[-12]
            yoy_change = latest - year_ago_val
        else:
            yoy_change = None

        # Get min/max in recent period (use original values for payroll changes)
        vals_for_stats = info.get('original_values', values) if info.get('is_payroll_change') else values
        recent_vals = vals_for_stats[-60:] if len(vals_for_stats) >= 60 else vals_for_stats
        recent_min = min(recent_vals)
        recent_max = max(recent_vals)

        summary = {
            'series_id': series_id,
            'name': name,
            'unit': unit,  # Include unit so Claude can format properly
            'latest_value': round(latest, 2),
            'latest_date': latest_date,
            'yoy_change': round(yoy_change, 2) if yoy_change else None,
            'recent_5yr_min': round(recent_min, 2),
            'recent_5yr_max': round(recent_max, 2),
        }

        # PRE-COMPUTE ALL COMPARISONS - LLMs can't do math reliably
        # YoY direction (for ALL series)
        if yoy_change is not None:
            if yoy_change > 0.01:
                summary['yoy_direction'] = 'UP from year ago'
            elif yoy_change < -0.01:
                summary['yoy_direction'] = 'DOWN from year ago'
            else:
                summary['yoy_direction'] = 'UNCHANGED from year ago'

            # YoY percent change (for non-zero base)
            # For payroll changes, compare this month's change to same-month-last-year's change
            if info.get('is_payroll_change') and info.get('original_values'):
                orig_values = info['original_values']
                if len(orig_values) >= 14:
                    # Current month's job change
                    current_change = orig_values[-1] - orig_values[-2]
                    # Same month last year's job change (13 months back)
                    year_ago_change = orig_values[-13] - orig_values[-14]
                    # CRITICAL: Include actual year-ago value so LLM doesn't hallucinate
                    summary['year_ago_job_change'] = round(year_ago_change, 1)
                    summary['current_job_change'] = round(current_change, 1)
                    if year_ago_change != 0:
                        yoy_pct = ((current_change - year_ago_change) / abs(year_ago_change)) * 100
                        summary['yoy_percent_change'] = round(yoy_pct, 1)
                        if yoy_pct > 0:
                            summary['yoy_percent_direction'] = f'UP {abs(yoy_pct):.1f}% from year ago (was {year_ago_change:.0f}K)'
                        elif yoy_pct < 0:
                            summary['yoy_percent_direction'] = f'DOWN {abs(yoy_pct):.1f}% from year ago (was {year_ago_change:.0f}K)'
            elif len(values) >= 12 and values[-12] != 0:
                yoy_pct = (yoy_change / abs(values[-12])) * 100
                summary['yoy_percent_change'] = round(yoy_pct, 1)
                if yoy_pct > 0:
                    summary['yoy_percent_direction'] = f'UP {abs(yoy_pct):.1f}% from year ago'
                elif yoy_pct < 0:
                    summary['yoy_percent_direction'] = f'DOWN {abs(yoy_pct):.1f}% from year ago'

        # Position in recent range (for ALL series)
        if recent_max > recent_min:
            range_size = recent_max - recent_min
            position = (latest - recent_min) / range_size
            if position > 0.9:
                summary['position_in_range'] = 'NEAR 5-year HIGH'
            elif position < 0.1:
                summary['position_in_range'] = 'NEAR 5-year LOW'
            elif position > 0.5:
                summary['position_in_range'] = 'ABOVE middle of 5-year range'
            else:
                summary['position_in_range'] = 'BELOW middle of 5-year range'

        # Recent average comparison (for ALL series)
        if len(recent_vals) >= 12:
            recent_avg = sum(recent_vals[-12:]) / 12
            summary['recent_12mo_avg'] = round(recent_avg, 2)
            if latest > recent_avg * 1.02:  # 2% threshold
                summary['vs_recent_avg'] = 'ABOVE recent 12-month average'
            elif latest < recent_avg * 0.98:
                summary['vs_recent_avg'] = 'BELOW recent 12-month average'
            else:
                summary['vs_recent_avg'] = 'NEAR recent 12-month average'

        # Month-over-month change (for ALL series with enough data)
        if len(values) >= 2:
            mom_change = values[-1] - values[-2]
            summary['mom_change'] = round(mom_change, 2)
            if mom_change > 0.01:
                summary['mom_direction'] = 'UP from previous month'
            elif mom_change < -0.01:
                summary['mom_direction'] = 'DOWN from previous month'
            else:
                summary['mom_direction'] = 'UNCHANGED from previous month'

        # 3-month trend (for ALL series)
        if len(values) >= 4:
            three_months_ago = values[-4]
            three_mo_change = latest - three_months_ago
            if three_mo_change > 0.01:
                summary['3mo_direction'] = 'UP over past 3 months'
            elif three_mo_change < -0.01:
                summary['3mo_direction'] = 'DOWN over past 3 months'
            else:
                summary['3mo_direction'] = 'FLAT over past 3 months'

        # Add job growth stats for payroll data
        if monthly_change is not None:
            summary['monthly_job_change'] = round(monthly_change, 1)
            # Direction of monthly change
            if monthly_change > 0:
                summary['monthly_direction'] = 'GAINED jobs'
            elif monthly_change < 0:
                summary['monthly_direction'] = 'LOST jobs'
            else:
                summary['monthly_direction'] = 'NO CHANGE in jobs'

        if avg_3mo_change is not None:
            summary['avg_monthly_change_3mo'] = round(avg_3mo_change, 1)
            # 3-month trend direction
            if avg_3mo_change > 0:
                summary['3mo_trend'] = 'GAINING jobs (3-mo avg)'
            elif avg_3mo_change < 0:
                summary['3mo_trend'] = 'LOSING jobs (3-mo avg)'
            else:
                summary['3mo_trend'] = 'FLAT (3-mo avg)'

            # Monthly vs 3-month comparison
            if monthly_change is not None:
                if monthly_change > avg_3mo_change + 10:  # 10K threshold for "above"
                    summary['monthly_vs_3mo_avg'] = 'ABOVE 3-month average'
                elif monthly_change < avg_3mo_change - 10:
                    summary['monthly_vs_3mo_avg'] = 'BELOW 3-month average'
                else:
                    summary['monthly_vs_3mo_avg'] = 'NEAR 3-month average'

        if avg_12mo_change is not None:
            summary['avg_monthly_change_12mo'] = round(avg_12mo_change, 1)
            # 12-month trend direction
            if avg_12mo_change > 0:
                summary['12mo_trend'] = 'GAINING jobs (12-mo avg)'
            elif avg_12mo_change < 0:
                summary['12mo_trend'] = 'LOSING jobs (12-mo avg)'
            else:
                summary['12mo_trend'] = 'FLAT (12-mo avg)'

            # Monthly vs 12-month comparison
            if monthly_change is not None:
                if monthly_change > avg_12mo_change + 10:
                    summary['monthly_vs_12mo_avg'] = 'ABOVE 12-month average'
                elif monthly_change < avg_12mo_change - 10:
                    summary['monthly_vs_12mo_avg'] = 'BELOW 12-month average'
                else:
                    summary['monthly_vs_12mo_avg'] = 'NEAR 12-month average'

        data_summary.append(summary)

    # DEBUG: Log what we're sending to the LLM
    print(f"\n[EconomistReviewer] === DATA BEING SENT TO LLM ===")
    print(f"[EconomistReviewer] Query: {query}")
    print(f"[EconomistReviewer] Series count: {len(data_summary)}")
    for s in data_summary:
        print(f"\n[EconomistReviewer] Series: {s.get('name', s.get('series_id', 'unknown'))}")
        print(f"[EconomistReviewer]   Raw: latest={s.get('latest_value')} | yoy_change={s.get('yoy_change')} | min={s.get('recent_5yr_min')} | max={s.get('recent_5yr_max')}")
        print(f"[EconomistReviewer]   Pre-computed: yoy_dir={s.get('yoy_direction', 'MISSING')} | vs_avg={s.get('vs_recent_avg', 'MISSING')} | range={s.get('position_in_range', 'MISSING')}")
        if s.get('monthly_job_change') is not None:
            print(f"[EconomistReviewer]   Jobs: monthly={s.get('monthly_job_change')} | 12mo_avg={s.get('avg_monthly_change_12mo')} | vs_12mo={s.get('monthly_vs_12mo_avg', 'MISSING')}")
    print(f"[EconomistReviewer] === FULL JSON ===")
    print(json.dumps(data_summary, indent=2))
    print(f"[EconomistReviewer] === END ===\n")

    # Build indicator context section using the indicator_context module
    indicator_context_section = ""
    if INDICATOR_CONTEXT_AVAILABLE:
        context_parts = []
        for s in data_summary:
            series_id = s.get('series_id', '')
            ctx = get_indicator_context(series_id)
            if ctx:
                # Add rich interpretation context for this indicator
                context_parts.append(
                    f"  {series_id} ({ctx.name}): {ctx.why_it_matters}"
                )
                # Add threshold information if available
                if ctx.thresholds:
                    threshold_str = ", ".join([
                        f"{t['value']}={name}"
                        for name, t in list(ctx.thresholds.items())[:3]
                    ])
                    context_parts.append(f"    Key levels: {threshold_str}")
        if context_parts:
            indicator_context_section = "\nINDICATOR CONTEXT (why these metrics matter):\n" + "\n".join(context_parts) + "\n"

    # Build the prompt with optional news context
    news_section = ""
    if news_context:
        news_section = f"""
RECENT NEWS & CONTEXT:
{news_context}
"""

    prompt = f"""You are a top economist like Jason Furman (former CEA Chair) or Claudia Sahm (Sahm Rule creator) writing an economic briefing. Your explanations should be substantive, insightful, and connect the dots - not just describe the data.

USER QUESTION: {query}

DATA (with pre-computed comparisons - trust these, don't recalculate):
{json.dumps(data_summary, indent=2)}
{indicator_context_section}{news_section}
BACKGROUND: {original_explanation}

KEY INTERPRETATION RULES (apply these automatically):
- Yield curve (T10Y2Y): If NEGATIVE, it's INVERTED - this has preceded every recession since 1970 (12-18 month lead)
- Sahm Rule (SAHMREALTIME): If > 0.5, recession signal with 100% historical accuracy
- Core PCE (PCEPILFE): Fed's explicit 2% target - above 2.5% = Fed stays hawkish; below 2% = Fed may ease
- Initial claims (ICSA): Rising above 300K is concerning; above 400K signals recession
- Unemployment (UNRATE): <4% = tight labor market; >5% = slack; >7% = recession territory
- Job gains (PAYEMS change): >200K/month = strong; 100-200K = moderate; <100K = concerning
- Prime-age employment (LNS12300060): 80%+ = strong; <77% = weak - cleanest labor market measure

HOW TO CONNECT MULTIPLE INDICATORS:
- Labor market tightness: Low unemployment + High job openings + High quits = tight → wage pressure → inflation concern
- Fed reaction function: High inflation → Fed raises rates → Higher mortgage rates → Housing cools
- Consumer health: Jobs + Wages - Inflation = Real wage growth → Supports (or constrains) spending
- Recession signals: Yield curve inverts → Claims rise → Sahm Rule triggers → GDP contracts

Write a Furman/Sahm-quality briefing:

1. LEAD WITH THE ANSWER (one clear sentence)
   - Answer the question directly. No "looking at the data..." preamble.

2. EXPLAIN THE CAUSAL MECHANISM (most important)
   - WHY is this happening? Not just what.
   - Connect to specific drivers: Fed policy? Consumer behavior? Labor dynamics? Supply constraints?
   - If multiple indicators, weave them into ONE coherent narrative showing cause → effect

3. HISTORICAL/THRESHOLD CONTEXT
   - Is this unusual? Near key thresholds?
   - Apply the interpretation rules above if relevant

4. FORWARD-LOOKING IMPLICATIONS
   - What does this mean for the path ahead?
   - What would need to change to alter that trajectory?

FORMAT: 4-5 bullet points (•). Be specific with numbers and dates.

CRITICAL RULES:
- USE the pre-computed comparisons in the data (yoy_direction, position_in_range, etc.) - these are mathematically verified
- Convert dates: "2025-12-01" → "December 2025"
- Convert units: "1764.6 thousands" → "about 1.8 million"
- NO generic phrases: "driven by strong consumer spending" not "due to various factors"
- NO meta-commentary: "The data shows..." - just answer directly
- CONNECT THE DOTS: If showing multiple indicators, explain how they relate to each other"""

    url = 'https://api.anthropic.com/v1/messages'
    payload = {
        'model': 'claude-sonnet-4-20250514',  # Sonnet is faster for this task
        'max_tokens': 1000,  # More room for substantive Furman/Sahm-style explanations
        'messages': [{'role': 'user', 'content': prompt}]
    }
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01'
    }

    try:
        req = Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
            improved = result['content'][0]['text'].strip()
            # Clean up any markdown or quotes
            improved = improved.strip('"\'')
            # Strip any HTML tags that LLM might have generated
            import re
            improved = re.sub(r'<[^>]+>', '', improved)
            return improved if improved else original_explanation
    except Exception as e:
        return original_explanation


def _build_data_summary_for_ensemble(series_data: list) -> list:
    """Build data summary in format expected by ensemble description generator.

    Args:
        series_data: List of (series_id, dates, values, info) tuples

    Returns:
        List of dicts with series data for the ensemble
    """
    data_summary = []
    for series_id, dates, values, info in series_data:
        if not values:
            continue
        name = info.get('name', info.get('title', series_id))
        unit = info.get('unit', info.get('units', ''))
        latest = values[-1]
        latest_date = dates[-1]

        # Calculate YoY change
        monthly_change = None
        avg_3mo_change = None
        avg_12mo_change = None

        if info.get('is_payroll_change') and info.get('original_values'):
            orig_values = info['original_values']
            if len(orig_values) >= 2:
                monthly_change = orig_values[-1] - orig_values[-2]
            if len(orig_values) >= 4:
                changes_3mo = [orig_values[i] - orig_values[i-1] for i in range(-3, 0)]
                avg_3mo_change = sum(changes_3mo) / 3
            if len(orig_values) >= 13:
                changes_12mo = [orig_values[i] - orig_values[i-1] for i in range(-12, 0)]
                avg_12mo_change = sum(changes_12mo) / 12
                yoy_change = orig_values[-1] - orig_values[-12]
            else:
                yoy_change = None
            latest = orig_values[-1]
            unit = 'Thousands of Persons'
            name = info.get('original_name', 'Total Nonfarm Payrolls')
        elif len(values) >= 12:
            year_ago_val = values[-12]
            yoy_change = latest - year_ago_val
        else:
            yoy_change = None

        # Get min/max in recent period
        vals_for_stats = info.get('original_values', values) if info.get('is_payroll_change') else values
        recent_vals = vals_for_stats[-60:] if len(vals_for_stats) >= 60 else vals_for_stats
        recent_min = min(recent_vals)
        recent_max = max(recent_vals)

        summary = {
            'series_id': series_id,
            'name': name,
            'unit': unit,
            'latest_value': round(latest, 2),
            'latest_date': latest_date,
            'yoy_change': round(yoy_change, 2) if yoy_change else None,
            'recent_5yr_min': round(recent_min, 2),
            'recent_5yr_max': round(recent_max, 2),
        }

        if monthly_change is not None:
            summary['monthly_job_change'] = round(monthly_change, 1)
        if avg_3mo_change is not None:
            summary['avg_monthly_change_3mo'] = round(avg_3mo_change, 1)
        if avg_12mo_change is not None:
            summary['avg_monthly_change_12mo'] = round(avg_12mo_change, 1)

        data_summary.append(summary)

    return data_summary


# Short descriptions matching how economists actually describe these metrics
SHORT_DESCRIPTIONS = {
    # Inflation - economists focus on YoY % change, not index levels
    'CPIAUCSL': "consumer price inflation; the Fed targets 2%",
    'CPILFESL': "core inflation excluding volatile food and energy",
    'PCEPI': "the Fed's preferred inflation measure",
    'PCEPILFE': "the Fed's 2% inflation target; the most important inflation metric for policy",
    'CUSR0000SAH1': "shelter costs, the largest CPI component (~1/3 of the basket)",
    'CUSR0000SAF11': "grocery prices",
    # Employment - PAYEMS is about monthly gains, not levels
    'PAYEMS': "monthly job gains; ~100K needed to keep pace with population growth",
    'UNRATE': "share of the labor force jobless and actively seeking work; ~4-4.5% is full employment",
    'U6RATE': "broader unemployment including discouraged and underemployed workers",
    'JTSJOL': "job openings, measuring employer demand for labor",
    'JTSQUR': "quits rate; workers quit more when confident about job market",
    'JTSHIR': "hires rate; measures actual hiring activity",
    'JTSLDL': "layoffs and discharges; measures involuntary separations",
    'ICSA': "new unemployment filings, the most timely labor market indicator",
    'CCSA': "continuing unemployment claims; how many remain unemployed",
    'CIVPART': "labor force participation rate; share of adults working or looking",
    'LNS11300060': "prime-age (25-54) participation rate; cleanest participation measure",
    'LNS12300060': "prime-age (25-54) employment rate, the cleanest measure of labor market health",
    'CES0500000003': "average hourly earnings for private workers",
    'AHETPI': "hourly earnings for production/nonsupervisory workers",
    'LES1252881600Q': "inflation-adjusted median weekly earnings, showing whether workers are gaining or losing purchasing power",
    # GDP - quarterly annualized rate, ~2% is trend growth
    'GDPC1': "real GDP, the broadest measure of economic output",
    'A191RL1Q225SBEA': "quarterly GDP growth (annualized); ~2% is trend growth",
    'A191RO1Q156NBEA': "GDP growth vs. a year ago, more stable than quarterly",
    # Interest Rates
    'FEDFUNDS': "the Fed's policy rate that influences all borrowing costs",
    'DGS10': "the benchmark rate for mortgages and long-term borrowing",
    'DGS2': "reflects market expectations for near-term Fed policy",
    'T10Y2Y': "yield spread between 10yr and 2yr Treasuries; inversion has historically preceded recessions",
    'T5YIE': "5-year breakeven inflation rate from TIPS; shows market inflation expectations",
    'T10YIE': "10-year breakeven inflation rate; long-term market inflation expectations",
    'MICH': "consumer inflation expectations from University of Michigan survey",
    'MORTGAGE30US': "determines monthly payments for most homebuyers",
    'MORTGAGE15US': "15-year mortgage rate, lower than 30-year for faster payoff",
    # Housing
    'CSUSHPINSA': "home prices using repeat-sales methodology (the gold standard)",
    'HOUST': "new construction starts, a leading economic indicator",
    'EXHOSLUSM495S': "existing home sales volume",
    'PERMIT': "building permits, signaling future construction activity",
    'FIXHAI': "housing affordability index; above 100 means typical family can afford typical home",
    # Consumer
    'UMCSENT': "consumer sentiment; spending drives ~70% of GDP",
    'PCE': "total consumer spending in dollars",
    'RSXFS': "retail sales excluding food services",
    # Leading Indicators
    'USSLIND': "leading economic index forecasting turning points",
    'BBKMLEIX': "leading index using 490 indicators to forecast growth",
    'CFNAI': "current economic activity relative to trend (0 = trend growth)",
    'SAHMREALTIME': "recession indicator; triggers at 0.5 when recession has likely begun",
}


def generate_clear_analysis(series_id: str, dates: list, values: list, info: dict) -> dict:
    """Generate concise, plain-language chart bullet.

    Produces a single bullet combining what the metric measures with current value.
    Example: "measures purchasing power directly. Currently up 1.35% YoY as of Q3 2025."

    Args:
        series_id: FRED series ID
        dates: List of date strings
        values: List of numeric values
        info: Series metadata dict

    Returns:
        dict with 'title' (metric name) and 'bullets' (single concise bullet)
    """
    name = info.get('name', info.get('title', series_id))

    # Simple, clean title
    title = name
    if info.get('is_yoy'):
        if 'YoY' not in title and 'Year' not in title:
            title = f"{title} (Year-over-Year Change)"

    if not values or len(values) < 2:
        return {'title': title, 'bullets': []}

    unit = info.get('unit', info.get('units', ''))
    latest = values[-1]
    latest_date = dates[-1]

    db_info = SERIES_DB.get(series_id, {})
    data_type = db_info.get('data_type', 'level')
    frequency = db_info.get('frequency', 'monthly')

    # Format latest date
    try:
        latest_date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
        if frequency == 'quarterly':
            quarter = (latest_date_obj.month - 1) // 3 + 1
            date_str = f"Q{quarter} {latest_date_obj.year}"
        else:
            date_str = latest_date_obj.strftime('%B %Y')
    except:
        date_str = latest_date

    # Get short description
    short_desc = SHORT_DESCRIPTIONS.get(series_id, "")

    # Calculate previous value for change calculations
    prev_value = values[-2] if len(values) >= 2 else latest

    # Format current value based on series type and how economists discuss it
    is_rate = data_type in ['rate', 'growth_rate'] or 'percent' in unit.lower() or info.get('is_yoy')

    # Special handling for PAYEMS - economists focus on monthly job gains, not levels
    if series_id == 'PAYEMS':
        monthly_change = (latest - prev_value) * 1000  # Convert from thousands
        if monthly_change >= 0:
            current_part = f"+{monthly_change:,.0f} jobs in {date_str}."
        else:
            current_part = f"{monthly_change:,.0f} jobs in {date_str}."
    elif is_rate:
        direction = "up" if latest > 0 else "down" if latest < 0 else "flat"
        current_part = f"Currently {direction} {abs(latest):.1f}% as of {date_str}."
    elif data_type == 'spread':
        if latest < 0:
            current_part = f"Currently inverted at {latest:.2f} percentage points as of {date_str}."
        else:
            current_part = f"Currently at {latest:.2f} percentage points as of {date_str}."
    elif latest >= 1000000:
        current_part = f"Currently at {latest/1000000:.1f} million as of {date_str}."
    elif latest >= 1000:
        current_part = f"Currently at {latest:,.0f} as of {date_str}."
    else:
        current_part = f"Currently at {latest:.2f} as of {date_str}."

    # Combine description + current value into single bullet
    if short_desc:
        bullet = f"{short_desc.capitalize().rstrip('.')}. {current_part}"
    else:
        bullet = current_part

    return {'title': title, 'bullets': [bullet]}


def generate_dynamic_ai_bullets(series_id: str, dates: list, values: list, info: dict, user_query: str = None) -> list:
    """Generate dynamic AI-powered bullets using Claude, with static bullets as guidance.

    This function creates contextual, data-aware bullets that:
    1. Reference actual current values and trends
    2. Use static bullet guidance for domain expertise
    3. Are tailored to the user's specific question
    4. Provide timely economic context

    Args:
        series_id: FRED series ID
        dates: List of date strings
        values: List of numeric values
        info: Series metadata dict
        user_query: Optional user's original question for context

    Returns:
        List of 2-3 dynamic bullet strings
    """
    if not ANTHROPIC_API_KEY or not values or len(values) < 2:
        # Fall back to static bullets
        db_info = SERIES_DB.get(series_id, {})
        return db_info.get('bullets', [])

    # Gather data context
    db_info = SERIES_DB.get(series_id, {})
    name = info.get('name', info.get('title', series_id))
    unit = info.get('unit', info.get('units', ''))
    latest = values[-1]
    latest_date = dates[-1]
    data_type = db_info.get('data_type', 'level')
    frequency = db_info.get('frequency', 'monthly')

    # Format date
    try:
        latest_date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
        if frequency == 'quarterly':
            quarter = (latest_date_obj.month - 1) // 3 + 1
            date_str = f"Q{quarter} {latest_date_obj.year}"
        else:
            date_str = latest_date_obj.strftime('%B %Y')
    except:
        date_str = latest_date

    # Calculate trend and changes
    trend_info = ""
    if len(values) >= 13:  # Have at least a year of data
        year_ago = values[-13] if frequency == 'monthly' else values[-5] if frequency == 'quarterly' else values[-2]
        yoy_change = latest - year_ago
        if year_ago != 0:
            yoy_pct = ((latest - year_ago) / abs(year_ago)) * 100
            trend_info = f"Year-over-year change: {yoy_change:+.2f} ({yoy_pct:+.1f}%)"

    # Recent trend (3 months)
    recent_trend = ""
    if len(values) >= 4:
        three_mo_ago = values[-4]
        if three_mo_ago != 0:
            recent_change = ((latest - three_mo_ago) / abs(three_mo_ago)) * 100
            if recent_change > 2:
                recent_trend = "Rising over past 3 months"
            elif recent_change < -2:
                recent_trend = "Falling over past 3 months"
            else:
                recent_trend = "Roughly flat over past 3 months"

    # Historical context
    historical_context = ""
    if len(values) >= 60:  # 5 years of monthly data
        five_yr_high = max(values[-60:])
        five_yr_low = min(values[-60:])
        historical_context = f"5-year range: {five_yr_low:.2f} to {five_yr_high:.2f}"

    # Get static bullet guidance
    static_bullets = db_info.get('bullets', [])
    static_guidance = "\n".join([f"- {b}" for b in static_bullets]) if static_bullets else "No static guidance available."

    # Short description
    short_desc = SHORT_DESCRIPTIONS.get(series_id, "")

    # Check for benchmark context
    benchmark_info = ""
    if 'benchmark' in db_info:
        bench = db_info['benchmark']
        bench_val = bench.get('value')
        if bench_val is not None:
            if latest > bench_val:
                benchmark_info = f"Currently ABOVE the {bench_val} benchmark ({bench.get('text', '')})"
            else:
                benchmark_info = f"Currently BELOW the {bench_val} benchmark ({bench.get('text', '')})"

    # Build the prompt
    prompt = f"""Generate 2-3 insightful bullet points that INTERPRET what this economic data means.

SERIES: {name} ({series_id})
DESCRIPTION: {short_desc}
CURRENT VALUE: {latest:.2f} {unit} as of {date_str}
{trend_info}
{recent_trend}
{historical_context}
{benchmark_info}

STATIC GUIDANCE (domain expertise to inform your analysis):
{static_guidance}

{"USER QUESTION: " + user_query if user_query else ""}

Write 2-3 bullets that:
1. INTERPRET what the trend means in plain language (e.g., "wages rising faster than inflation means workers are gaining purchasing power")
2. Explain the "SO WHAT" - what this means for workers, consumers, businesses, or the economy
3. Note any unusual context (e.g., "excluding the pandemic dip" or "since the Fed started hiking")
4. Reference specific numbers but focus on MEANING not just data description
5. Keep each bullet to 1-2 sentences max

BAD example: "CPI is at 3.2% as of December 2024, up from 2.9% a year ago."
GOOD example: "Inflation has reaccelerated to 3.2%, moving away from the Fed's 2% target—suggesting rate cuts may be delayed."

Format: Return ONLY the bullets as a JSON array of strings, like:
["First bullet here.", "Second bullet here."]"""

    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 400,
            "messages": [{"role": "user", "content": prompt}]
        }

        req = Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urlopen(req, timeout=8) as response:
            result = json.loads(response.read().decode('utf-8'))
            text = result['content'][0]['text']

            # Parse JSON array from response
            if '[' in text and ']' in text:
                start = text.index('[')
                end = text.rindex(']') + 1
                bullets = json.loads(text[start:end])
                if isinstance(bullets, list) and len(bullets) > 0:
                    return bullets[:3]  # Max 3 bullets
    except Exception as e:
        pass  # Fall through to static bullets

    # Fallback to static bullets
    return static_bullets if static_bullets else []


# Session state for caching dynamic bullets
_dynamic_bullet_cache = {}

def get_dynamic_bullets(series_id: str, dates: list, values: list, info: dict, user_query: str = None, use_ai: bool = True) -> list:
    """Get bullets for a chart, using AI if enabled or falling back to static.

    Caches results per session to avoid repeated API calls for same data.
    """
    if not use_ai:
        db_info = SERIES_DB.get(series_id, {})
        return db_info.get('bullets', [])

    # Create cache key from series and latest value
    cache_key = f"{series_id}_{values[-1] if values else 'empty'}_{user_query or ''}"

    if cache_key in _dynamic_bullet_cache:
        return _dynamic_bullet_cache[cache_key]

    bullets = generate_dynamic_ai_bullets(series_id, dates, values, info, user_query)
    _dynamic_bullet_cache[cache_key] = bullets

    # Limit cache size
    if len(_dynamic_bullet_cache) > 100:
        # Remove oldest entries
        keys = list(_dynamic_bullet_cache.keys())
        for k in keys[:50]:
            del _dynamic_bullet_cache[k]

    return bullets


# Alias for backward compatibility
def generate_goldman_style_analysis(series_id: str, dates: list, values: list, info: dict, user_query: str = None, use_dynamic_ai: bool = True) -> dict:
    """Generate chart analysis with optional dynamic AI bullets.

    Args:
        use_dynamic_ai: If True, generates AI-powered contextual bullets.
                       If False, uses basic template approach.
    """
    name = info.get('name', info.get('title', series_id))
    title = name
    if info.get('is_yoy'):
        if 'YoY' not in title and 'Year' not in title:
            title = f"{title} (Year-over-Year Change)"

    if not values or len(values) < 2:
        return {'title': title, 'bullets': []}

    if use_dynamic_ai:
        bullets = get_dynamic_bullets(series_id, dates, values, info, user_query)
    else:
        # Fall back to basic clear analysis
        result = generate_clear_analysis(series_id, dates, values, info)
        bullets = result.get('bullets', [])

    return {'title': title, 'bullets': bullets}


def generate_chart_description(series_id: str, dates: list, values: list, info: dict) -> str:
    """Generate a dynamic one-line description of recent trends for a chart.

    This creates a bullet point describing the recent reading and trend direction,
    with historical context comparing to recent peaks/troughs.

    Args:
        series_id: FRED series ID
        dates: List of date strings
        values: List of numeric values
        info: Series metadata dict

    Returns:
        A single sentence describing the current value, trend, and historical context
    """
    if not values or len(values) < 2:
        return ""

    name = info.get('name', info.get('title', series_id))
    unit = info.get('unit', info.get('units', ''))
    latest = values[-1]
    latest_date = dates[-1]

    # Get database info for data type
    db_info = SERIES_DB.get(series_id, {})
    data_type = db_info.get('data_type', 'level')
    frequency = db_info.get('frequency', 'monthly')

    # Format latest date
    try:
        latest_date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
        if frequency == 'quarterly':
            quarter = (latest_date_obj.month - 1) // 3 + 1
            date_str = f"Q{quarter} {latest_date_obj.year}"
        else:
            date_str = latest_date_obj.strftime('%b %Y')
    except:
        date_str = latest_date

    # Helper to format values consistently
    def format_val(v):
        if data_type in ['rate', 'growth_rate'] or info.get('is_yoy') or info.get('is_mom'):
            return f"{v:.1f}%"
        elif data_type == 'price':
            return f"${v:.2f}"
        elif data_type == 'spread':
            return f"{v:.2f} pp"
        elif 'Thousands' in unit:
            if v >= 1000:
                return f"{v/1000:.1f}M"
            else:
                return f"{v:,.0f}K"
        elif 'Index' in unit or data_type == 'index':
            return f"{v:.1f}"
        else:
            return format_number(v, unit)

    value_str = format_val(latest)

    # Determine trend direction (compare to 3 months ago or 1 quarter)
    trend = ""
    lookback = 3 if frequency == 'monthly' else 1
    if len(values) > lookback:
        prior = values[-(lookback + 1)]
        if prior != 0:
            change_pct = ((latest - prior) / abs(prior)) * 100
            if abs(change_pct) < 1:
                trend = "roughly flat"
            elif change_pct > 5:
                trend = "rising sharply"
            elif change_pct > 0:
                trend = "trending up"
            elif change_pct < -5:
                trend = "falling sharply"
            else:
                trend = "trending down"

    # Calculate historical context (5-year high/low if enough data)
    historical_context = ""
    # Get approximately 5 years of data (60 months or 20 quarters)
    lookback_periods = 60 if frequency == 'monthly' else 20
    if len(values) >= lookback_periods:
        recent_values = values[-lookback_periods:]
        recent_dates = dates[-lookback_periods:]

        five_yr_max = max(recent_values)
        five_yr_min = min(recent_values)
        max_idx = recent_values.index(five_yr_max)
        min_idx = recent_values.index(five_yr_min)

        # Only add context if current value is meaningfully different from peak/trough
        if five_yr_max != 0:
            pct_from_max = ((latest - five_yr_max) / abs(five_yr_max)) * 100
            pct_from_min = ((latest - five_yr_min) / abs(five_yr_min)) * 100 if five_yr_min != 0 else 0

            try:
                max_date_obj = datetime.strptime(recent_dates[max_idx], '%Y-%m-%d')
                min_date_obj = datetime.strptime(recent_dates[min_idx], '%Y-%m-%d')
                max_date_str = max_date_obj.strftime('%b %Y')
                min_date_str = min_date_obj.strftime('%b %Y')
            except:
                max_date_str = recent_dates[max_idx]
                min_date_str = recent_dates[min_idx]

            # If we're down significantly from peak, mention it
            if pct_from_max < -10 and trend in ["trending down", "falling sharply", "roughly flat"]:
                historical_context = f"down from {format_val(five_yr_max)} peak ({max_date_str})"
            # If we're up significantly from trough, mention it
            elif pct_from_min > 10 and trend in ["trending up", "rising sharply", "roughly flat"]:
                historical_context = f"up from {format_val(five_yr_min)} low ({min_date_str})"
            # If near 5-year high (within 5%)
            elif abs(pct_from_max) < 5:
                historical_context = "near 5-year high"
            # If near 5-year low (within 5%)
            elif abs(pct_from_min) < 5:
                historical_context = "near 5-year low"

    # Build description with historical context
    parts = [f"Currently at {value_str} as of {date_str}"]
    if historical_context:
        parts.append(historical_context)
    if trend:
        parts.append(f"{trend} in recent months")

    if len(parts) == 1:
        return parts[0] + "."
    elif len(parts) == 2:
        return f"{parts[0]}, {parts[1]}."
    else:
        return f"{parts[0]} ({parts[1]}), {parts[2]}."


def generate_chart_title(series_id: str, info: dict) -> str:
    """Generate a clear, understandable title for a chart.

    Args:
        series_id: FRED series ID
        info: Series metadata dict

    Returns:
        A user-friendly chart title
    """
    # Check if there's a custom friendly name in SERIES_DB
    db_info = SERIES_DB.get(series_id, {})

    # Use friendly name if available, otherwise use the series name
    name = db_info.get('name', info.get('name', info.get('title', series_id)))

    # Add transformation info to title
    if info.get('is_yoy'):
        if '(YoY' not in name and 'Year-over-Year' not in name:
            name = f"{name} (YoY %)"
    elif info.get('is_mom'):
        if '(MoM' not in name and 'Month-over-Month' not in name:
            name = f"{name} (MoM %)"
    elif info.get('is_avg_annual'):
        name = f"{name} (Annual Average)"

    return name


def fred_request(endpoint: str, params: dict) -> dict:
    """
    Make a request to the FRED API with detailed error handling and caching.

    Caches responses for 15 minutes to reduce API calls.

    Returns dict with response data or {'error': message, 'error_type': type}
    """
    # Check cache first (exclude api_key from cache key for security)
    cache_params = {k: v for k, v in params.items() if k != 'api_key'}
    cache_key = _get_cache_key('fred_request', endpoint, **cache_params)
    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result

    # Make the API request
    params['api_key'] = FRED_API_KEY
    params['file_type'] = 'json'
    url = f"{FRED_BASE}/{endpoint}?{urlencode(params)}"
    try:
        req = Request(url, headers={'User-Agent': 'EconStats/1.0'})
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            # Cache successful responses
            _set_cache(cache_key, result)
            return result
    except HTTPError as e:
        # Distinguish between different HTTP errors for better user messaging
        if e.code == 429:
            # Don't cache rate limit errors - they're temporary
            return {
                'error': 'FRED API rate limit reached. Please wait a moment and try again.',
                'error_type': 'rate_limit',
                'retry_after': e.headers.get('Retry-After', '60')
            }
        elif e.code == 400:
            # Bad request - usually invalid series ID. Cache this to avoid repeated failed requests.
            series_id = params.get('series_id', '')
            result = {
                'error': f'Series {series_id} not found or invalid',
                'error_type': 'invalid_series'
            }
            _set_cache(cache_key, result)
            return result
        elif e.code == 403:
            # Auth error - cache it since it won't change without config changes
            result = {
                'error': 'FRED API access denied. API key may be invalid.',
                'error_type': 'auth_error'
            }
            _set_cache(cache_key, result)
            return result
        elif e.code >= 500:
            # Server errors are temporary - don't cache
            return {
                'error': 'FRED API is temporarily unavailable. Please try again in a moment.',
                'error_type': 'server_error'
            }
        else:
            # Cache other HTTP errors
            result = {
                'error': f'FRED API error: {e.code} - {e.reason}',
                'error_type': 'http_error'
            }
            _set_cache(cache_key, result)
            return result
    except URLError as e:
        # Network errors are temporary - don't cache
        return {
            'error': 'Network error. Please check your internet connection.',
            'error_type': 'network_error'
        }
    except Exception as e:
        # Unknown errors - don't cache as they might be transient
        return {
            'error': f'Unexpected error: {str(e)}',
            'error_type': 'unknown'
        }


def search_series(query: str, limit: int = 5, require_recent: bool = True) -> list:
    """
    Search FRED for series matching the query with caching.

    Caches search results for 15 minutes to reduce API calls.

    Args:
        query: Search terms
        limit: Max results to return
        require_recent: If True, filter out series with no data after 2020

    Returns:
        List of series metadata dictionaries
    """
    # Check cache first
    cache_key = _get_cache_key('search_series', query, limit=limit, require_recent=require_recent)
    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result

    # Request more results than needed so we can filter
    fetch_limit = limit * 3 if require_recent else limit

    # Try popularity-ordered search first
    data = fred_request('series/search', {
        'search_text': query,
        'limit': fetch_limit,
        'order_by': 'popularity',
        'sort_order': 'desc',
        'filter_variable': 'frequency',
        'filter_value': 'Monthly'  # Prefer monthly data
    })
    results = data.get('seriess', [])

    # If no monthly results, try without frequency filter
    if not results:
        data = fred_request('series/search', {
            'search_text': query,
            'limit': fetch_limit,
            'order_by': 'popularity',
            'sort_order': 'desc'
        })
        results = data.get('seriess', [])

    # Filter out stale/discontinued series
    if require_recent and results:
        filtered = []
        for series in results:
            # Check if series has recent data (after 2020)
            observation_end = series.get('observation_end', '')
            if observation_end:
                try:
                    end_year = int(observation_end[:4])
                    if end_year >= 2020:
                        filtered.append(series)
                except (ValueError, IndexError):
                    pass  # Skip series with invalid dates
        results = filtered[:limit] if filtered else results[:limit]
    else:
        results = results[:limit]

    # Cache the processed results
    _set_cache(cache_key, results)
    return results


def reasoning_query_plan(query: str, verbose: bool = False) -> dict:
    """
    AI-first approach: Reason about what an economist needs, then search.

    This is the PRIMARY query path. It asks AI to think like an economist
    about what indicators are needed, then searches FRED for those indicators.

    Pre-computed plans are used as a fast-path backstop, not the main approach.
    """
    if not REASONING_AVAILABLE:
        return {'series': [], 'explanation': '', 'reasoning_failed': True}

    if verbose:
        print(f"  Using economist reasoning for: {query}")

    # Step 1: AI reasons about what's needed (or finds direct mapping)
    reasoning = reason_about_query(query, verbose=verbose)

    # Check if direct series mapping was found (e.g., "What is the Fed funds rate?")
    direct_series = reasoning.get('direct_series', [])
    if direct_series:
        if verbose:
            print(f"  Direct series: {direct_series}")
        # For direct mappings, use unit-based compatibility check
        # can_combine_series checks if all series share compatible units (rates, percentages, indexes)
        can_combine, combine_reason = can_combine_series(direct_series)
        should_combine = can_combine and len(direct_series) <= 4
        if verbose and can_combine:
            print(f"    Auto-combine: {combine_reason}")

        # Look up rich explanation from pre-computed plans if available
        explanation = reasoning.get('reasoning', '')
        query_lower = query.lower().strip().rstrip('?')
        # Try to find a matching pre-computed plan for better explanation
        for plan_key in [query_lower, query_lower.replace('what is the ', '').replace('what are the ', '')]:
            if plan_key in QUERY_PLANS:
                plan_explanation = QUERY_PLANS[plan_key].get('explanation', '')
                if plan_explanation and len(plan_explanation) > len(explanation):
                    explanation = plan_explanation
                break

        return {
            'series': direct_series[:4],
            'explanation': explanation,
            'used_reasoning': True,
            'used_direct_mapping': True,
            'combine_chart': should_combine,
            'show_yoy': False,
        }

    search_terms = reasoning.get('search_terms', [])
    indicators = reasoning.get('indicators', [])

    if not search_terms and not indicators:
        # P0 FIX: Fallback to pre-computed plans before returning empty
        # This fixes the 60% failure rate when Gemini is unavailable
        precomputed = find_query_plan(query)
        if precomputed:
            base_series = precomputed.get('series', [])[:4]
            can_combine, _ = can_combine_series(base_series)
            return {
                'series': base_series,
                'explanation': precomputed.get('explanation', ''),
                'used_reasoning': False,
                'used_precomputed_fallback': True,
                'combine_chart': precomputed.get('combine_chart', can_combine),
                'show_yoy': precomputed.get('show_yoy', False),
            }
        return {'series': [], 'explanation': reasoning.get('reasoning', ''), 'reasoning_failed': True}

    # Step 2: Search FRED for each indicator concept
    found_series = []
    series_info = []

    # Extract concept keywords for relevance checking
    def is_relevant_series(title: str, concept: str, search_term: str) -> bool:
        """Check if series title is relevant to the concept we're looking for."""
        title_lower = title.lower()
        concept_lower = concept.lower()
        term_lower = search_term.lower()

        # Title should contain at least one word from concept or search term
        concept_words = [w for w in concept_lower.split() if len(w) > 3]
        term_words = [w for w in term_lower.split() if len(w) > 3]

        return any(w in title_lower for w in concept_words + term_words)

    for indicator in indicators[:4]:  # Max 4 indicators
        terms = indicator.get('search_terms', [])
        concept = indicator.get('concept', '')

        for term in terms[:2]:  # Try up to 2 search terms per indicator
            results = search_series(term, limit=5, require_recent=True)  # Get more to filter
            for r in results:
                sid = r['id']
                title = r.get('title', sid)

                # Skip if already found or not relevant to the concept
                if sid in found_series:
                    continue
                if not is_relevant_series(title, concept, term):
                    if verbose:
                        print(f"    Skipping {sid} - not relevant to '{concept}'")
                    continue

                found_series.append(sid)
                series_info.append({
                    'id': sid,
                    'title': title,
                    'concept': concept,
                    'why': indicator.get('why', '')
                })
                if verbose:
                    print(f"    Found {sid}: {title} for '{concept}'")
                break  # Found one for this indicator, move on

            if any(s.get('concept') == concept for s in series_info):
                break  # Already found series for this concept

    # Limit to 4 series
    found_series = found_series[:4]

    # Build explanation from reasoning
    explanation = reasoning.get('reasoning', '')
    if indicators:
        indicator_names = [i.get('concept', '') for i in indicators if i.get('concept')]
        if indicator_names:
            explanation = f"To answer this, looking at: {', '.join(indicator_names)}. {explanation}"

    # Determine if series should be combined on one chart
    # Combine for: comparison queries, or when showing closely related series
    query_lower = query.lower()
    
    # Comparison detection - explicit keywords like "vs", "compare"
    # Note: " and " is NOT included here - it doesn't force combining with mixed units
    explicit_comparison_keywords = [
        'vs', 'versus', 'compare', 'comparing', 'comparison',
        'relative to', 'against', 'between',
    ]
    is_explicit_comparison = any(kw in query_lower for kw in explicit_comparison_keywords)

    # Also detect implicit comparisons: queries with exactly 2 related concepts
    # e.g., "wages inflation" or "unemployment job openings"
    has_two_indicators = len(found_series) == 2

    # Auto-detect: check if series have compatible units for combining
    units_compatible, compatibility_reason = can_combine_series(found_series)
    if verbose and units_compatible:
        print(f"    Auto-combine: {compatibility_reason}")

    # Combine when:
    # - Explicit comparison (vs, compare) - even with mixed units
    # - Units are compatible (all rates, all %, all indexes)
    # - Two related indicators with compatible units
    should_combine = (
        is_explicit_comparison or
        units_compatible or
        (has_two_indicators and units_compatible)
    ) and len(found_series) <= 4

    return {
        'series': found_series,
        'explanation': explanation,
        'reasoning': reasoning,
        'series_info': series_info,
        'used_reasoning': True,
        'combine_chart': should_combine,
        'show_yoy': False,
        'is_comparison': is_comparison,
    }


def hybrid_query_plan(query: str, verbose: bool = False) -> dict:
    """
    Hybrid approach: Combine RAG catalog search + FRED API search.

    This gives the best of both worlds:
    - RAG provides high-quality curated series for known topics
    - FRED search finds niche/specific series not in the catalog
    - Validation filters out garbage from both sources

    Args:
        query: User's question
        verbose: Whether to print progress

    Returns:
        Query plan dict with series, explanation, etc.
    """
    all_series = []
    all_series_info = []  # For validation
    sources = {'rag': [], 'fred': []}

    # Step 1: Get RAG results (from curated catalog)
    if RAG_AVAILABLE:
        try:
            rag_result = rag_query_plan(query, verbose=verbose)
            rag_series = rag_result.get('series', [])
            sources['rag'] = rag_series
            for sid in rag_series:
                if sid not in all_series:
                    all_series.append(sid)
            if verbose:
                print(f"  RAG found: {rag_series}")
        except Exception as e:
            if verbose:
                print(f"  RAG error: {e}")
            rag_result = {}
    else:
        rag_result = {}

    # Step 2: Also search FRED API directly for additional series
    # Extract key terms from query for targeted search
    search_terms = _extract_search_terms(query)
    if verbose:
        print(f"  FRED search terms: {search_terms}")

    # Extract key topic nouns for relevance checking (exclude generic terms)
    generic_terms = {'rate', 'rates', 'current', 'effective', 'does', 'affect', 'economy',
                     'economic', 'data', 'index', 'level', 'growth', 'change', 'trend'}
    topic_words = [w.lower().strip('?.,!\'') for w in query.split()
                   if len(w) > 3 and w.lower().strip('?.,!\'') not in generic_terms]

    for term in search_terms[:2]:  # Limit to 2 searches
        try:
            fred_results = search_series(term, limit=4, require_recent=True)
            for r in fred_results:
                sid = r['id']
                title = r.get('title', sid)
                title_lower = title.lower()

                # Strict relevance: title must contain at least one TOPIC word (not just generic terms)
                # This prevents "effective tariff rate" from matching "Federal Funds Effective Rate"
                is_relevant = any(word in title_lower for word in topic_words)

                if is_relevant and sid not in all_series:
                    all_series.append(sid)
                    all_series_info.append({'id': sid, 'title': title})
                    sources['fred'].append(sid)
                    if verbose:
                        print(f"    FRED found: {sid} - {title}")
        except Exception as e:
            if verbose:
                print(f"  FRED search error: {e}")

    # Step 3: Validate combined results (if we have enough and ensemble is available)
    if ENSEMBLE_AVAILABLE and len(all_series) > 2:
        # Get info for RAG series too
        for sid in sources['rag']:
            if not any(s['id'] == sid for s in all_series_info):
                try:
                    info = get_series_info(sid)
                    all_series_info.append({'id': sid, 'title': info.get('title', sid)})
                except:
                    all_series_info.append({'id': sid, 'title': sid})

        if verbose:
            print(f"  Validating {len(all_series_info)} series...")

        validation = validate_series_relevance(query, all_series_info, verbose=verbose)
        valid_ids = validation.get('valid_series', all_series)

        if valid_ids:
            # Keep only validated series, preserve order
            all_series = [s for s in all_series if s in valid_ids]
            if verbose:
                rejected = validation.get('rejected_series', [])
                if rejected:
                    print(f"  Rejected: {[r.get('id') for r in rejected]}")
        else:
            # Validation rejected ALL series - no relevant data found
            all_series = []
            if verbose:
                print(f"  All series rejected - no relevant data for query")

    # Handle case where no relevant series were found
    if not all_series:
        return {
            'series': [],
            'explanation': f"I couldn't find FRED data specifically about '{query}'. "
                          "FRED primarily covers macroeconomic indicators (employment, inflation, GDP, etc.). "
                          "Try a broader query like 'restaurant employment', 'food prices', or 'small business trends'.",
            'show_yoy': False,
            'show_mom': False,
            'show_avg_annual': False,
            'combine_chart': False,
            'is_followup': False,
            'add_to_previous': False,
            'keep_previous_series': False,
            'search_terms': [],
            'no_data_available': True,
            'hybrid_sources': sources,
        }

    # Limit to 4 series max
    all_series = all_series[:4]

    # Check unit compatibility for auto-combining
    # This catches cases like "treasury yields" where all series are rates
    units_compatible, compatibility_reason = can_combine_series(all_series)

    # Check for comparison keywords in query
    # Explicit comparisons (vs, compare) should combine even with mixed units
    # Implicit " and " should only combine if units are compatible
    query_lower = query.lower()
    explicit_comparison_keywords = ['vs', 'versus', 'compare', 'comparing', 'comparison',
                                    'relative to', 'against', 'between']
    is_explicit_comparison = any(kw in query_lower for kw in explicit_comparison_keywords)
    has_and = ' and ' in query_lower

    # Combine if:
    # - Units are compatible (safe to combine), OR
    # - Explicit comparison requested (user wants them together even with mixed units), OR
    # - RAG recommends it
    # Note: " and " alone doesn't force combining - only combines if units are compatible
    should_combine = (
        units_compatible or
        is_explicit_comparison or
        rag_result.get('combine_chart', False)
    )

    if verbose and units_compatible:
        print(f"  Auto-combine: {compatibility_reason}")

    # Build result, preferring RAG's explanation if available
    result = {
        'series': all_series,
        'explanation': rag_result.get('explanation', f'Data for: {query}'),
        'show_yoy': rag_result.get('show_yoy', False),
        'show_mom': False,
        'show_avg_annual': False,
        'combine_chart': should_combine,
        'is_followup': False,
        'add_to_previous': False,
        'keep_previous_series': False,
        'search_terms': [],  # Already searched
        'hybrid_sources': sources,
    }

    return result


def _extract_search_terms(query: str) -> list:
    """Extract meaningful search terms from a query for FRED API search."""
    # Remove common words - including generic economic terms that cause false matches
    stop_words = {'how', 'are', 'is', 'the', 'what', 'doing', 'for', 'in', 'of', 'and', 'a', 'an', 'to',
                  'rate', 'rates', 'current', 'effective', 'does', 'affect', 'economy', 'economic'}
    words = [w.lower().strip('?.,!\'') for w in query.split()]
    meaningful = [w for w in words if w not in stop_words and len(w) > 2]

    # Build search terms - prioritize specific topic nouns
    terms = []

    # Each key noun as its own search (most specific first)
    for word in meaningful[:3]:
        if word not in terms:
            terms.append(word)

    # Full phrase (minus stop words) as fallback
    if meaningful and len(meaningful) > 1:
        phrase = ' '.join(meaningful)
        if phrase not in terms:
            terms.append(phrase)

    return terms[:3]


def calculate_derived_series(
    series_data: dict,
    formula: str,
    name: str = "Derived Series",
    unit: str = ""
) -> tuple:
    """
    Calculate a derived series from multiple input series using pandas.

    Args:
        series_data: Dict mapping series_id -> (dates, values) tuples
        formula: Pandas-compatible formula string, e.g., "A001RX1Q020SBEA / IMPGS * 100"
        name: Display name for the derived series
        unit: Unit label for the derived series

    Returns:
        Tuple of (dates, values, info_dict) for the derived series,
        or (None, None, None) if calculation fails

    Examples:
        # Effective tariff rate
        calculate_derived_series(data, "A001RX1Q020SBEA / IMPGS * 100", "Effective Tariff Rate", "%")

        # Yield curve spread
        calculate_derived_series(data, "DGS10 - DGS2", "10Y-2Y Spread", "Percentage Points")

        # Real GDP per capita (hypothetical)
        calculate_derived_series(data, "GDPC1 / POP * 1000", "Real GDP per Capita", "$ Thousands")
    """
    import re

    if not series_data or not formula:
        return None, None, None

    try:
        # Build a DataFrame with all series, aligned by date
        dfs = []
        for series_id, (dates, values) in series_data.items():
            if dates and values:
                df = pd.DataFrame({
                    'date': pd.to_datetime(dates),
                    series_id: values
                }).set_index('date')
                dfs.append(df)

        if len(dfs) < 2:
            return None, None, None

        # Join all series on date (outer join to keep all dates, then we'll dropna)
        combined = dfs[0]
        for df in dfs[1:]:
            combined = combined.join(df, how='outer')

        # Drop rows with missing values (dates where not all series have data)
        combined = combined.dropna()

        if combined.empty:
            return None, None, None

        # Validate formula only contains expected series IDs and safe operations
        # Extract series IDs from formula
        formula_series = re.findall(r'[A-Z][A-Z0-9_]+', formula)
        for sid in formula_series:
            if sid not in combined.columns:
                # Series referenced in formula but not in data
                return None, None, None

        # Calculate the derived series using pandas eval (safe evaluation)
        # Only allows pandas operations, not arbitrary Python code
        result = combined.eval(formula)

        # Convert back to lists
        dates = result.index.strftime('%Y-%m-%d').tolist()
        values = result.tolist()

        info = {
            'name': name,
            'unit': unit,
            'is_derived': True,
            'formula': formula,
            'source_series': list(series_data.keys()),
        }

        return dates, values, info

    except Exception as e:
        # Log error but don't crash
        print(f"Error calculating derived series: {e}")
        return None, None, None


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_series_info(series_id: str) -> dict:
    """Get metadata for a series. Cached for 1 hour to reduce API calls."""
    data = fred_request('series', {'series_id': series_id})
    series_list = data.get('seriess', [])
    return series_list[0] if series_list else {}


@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def _fetch_observations_cached(series_id: str, start_date: str = None) -> dict:
    """Cached FRED API call for observations. Returns raw API response."""
    params = {'series_id': series_id, 'limit': 10000, 'sort_order': 'asc'}
    if start_date:
        params['observation_start'] = start_date
    return fred_request('series/observations', params)


def get_observations(series_id: str, years: int = None) -> tuple:
    """Get observations for a series. Uses caching to reduce API calls."""
    # Calculate start date for cache key
    start_date = None
    if years:
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime('%Y-%m-%d')

    # Get info from our database first, then FRED API
    info = dict(SERIES_DB.get(series_id, {}))
    if not info:
        fred_info = get_series_info(series_id)
        if fred_info:
            info = {
                'name': fred_info.get('title', series_id),
                'unit': fred_info.get('units', ''),
                'source': fred_info.get('source', 'FRED'),
                'sa': fred_info.get('seasonal_adjustment_short') == 'SA',
                'bullets': [
                    fred_info.get('notes', f'FRED series {series_id}')[:200],
                    f"Source: {fred_info.get('source', 'FRED')}. {fred_info.get('seasonal_adjustment', '')}"
                ]
            }

    if not info:
        return [], [], {'error': f'Series {series_id} not found'}

    # Use cached API call
    data = _fetch_observations_cached(series_id, start_date)
    if 'error' in data:
        return [], [], {'error': data['error']}

    observations = data.get('observations', [])
    dates, values = [], []
    for obs in observations:
        try:
            val = float(obs['value'])
            dates.append(obs['date'])
            values.append(val)
        except (ValueError, KeyError):
            continue

    return dates, values, info


def fetch_series_data(series_id: str, years: int = None) -> tuple:
    """
    Unified data fetcher that routes to the appropriate source.

    Routes based on series ID prefix:
    - zillow_* -> Zillow API
    - eia_* -> EIA API
    - av_* -> Alpha Vantage API
    - DBnomics series (from DBNOMICS catalog) -> DBnomics API
    - Otherwise -> FRED API

    Returns: (dates, values, info) tuple
    """
    # Route to Zillow
    if series_id.startswith('zillow_') and ZILLOW_AVAILABLE:
        return get_zillow_series(series_id)

    # Route to EIA
    if series_id.startswith('eia_') and EIA_AVAILABLE:
        return get_eia_series(series_id)

    # Route to Alpha Vantage
    if series_id.startswith('av_') and ALPHAVANTAGE_AVAILABLE:
        return get_alphavantage_series(series_id)

    # Route to DBnomics (for international series)
    if DBNOMICS_AVAILABLE:
        from agents.dbnomics import INTERNATIONAL_SERIES
        if series_id in INTERNATIONAL_SERIES:
            return get_observations_dbnomics(series_id)

    # Default to FRED
    return get_observations(series_id, years)


def fetch_single_series(series_id: str, years: int) -> dict:
    """
    Fetch a single series and return structured result for parallel processing.

    Returns dict with:
    - series_id: The series identifier
    - dates: List of date strings
    - values: List of numeric values
    - info: Metadata dict
    - success: Boolean indicating if fetch succeeded
    """
    try:
        dates, values, info = fetch_series_data(series_id, years)
        return {
            'series_id': series_id,
            'dates': dates,
            'values': values,
            'info': info,
            'success': bool(dates and values)
        }
    except Exception as e:
        # Return empty result on failure
        return {
            'series_id': series_id,
            'dates': [],
            'values': [],
            'info': {},
            'success': False,
            'error': str(e)
        }


def calculate_yoy(dates: list, values: list) -> tuple:
    """Calculate year-over-year percent change.

    Handles both monthly and quarterly data by detecting frequency
    and looking back ~365 days for the comparison value.
    """
    if len(dates) < 2:
        return dates, values

    # Detect frequency by looking at date gaps
    date_objs = [datetime.strptime(d, '%Y-%m-%d') for d in dates[:min(5, len(dates))]]
    if len(date_objs) >= 2:
        avg_gap = sum((date_objs[i+1] - date_objs[i]).days for i in range(len(date_objs)-1)) / (len(date_objs)-1)
        # Monthly: ~30 days gap, need 12 observations
        # Quarterly: ~90 days gap, need 4 observations
        # Weekly: ~7 days gap, need 52 observations
        if avg_gap > 60:  # Quarterly
            min_obs = 4
        elif avg_gap > 20:  # Monthly
            min_obs = 12
        else:  # Weekly
            min_obs = 52
    else:
        min_obs = 12  # Default to monthly

    if len(dates) < min_obs + 1:
        return dates, values

    date_to_value = dict(zip(dates, values))
    yoy_dates, yoy_values = [], []

    # Start from the point where we have enough history for YoY comparison
    for i, date_str in enumerate(dates[min_obs:], min_obs):
        date = datetime.strptime(date_str, '%Y-%m-%d')
        # Look for a value from approximately one year ago (allow 31-day window for date matching)
        for offset in range(31):
            check = (date - timedelta(days=365 + offset)).strftime('%Y-%m-%d')
            if check in date_to_value and date_to_value[check] != 0:
                yoy = ((values[i] - date_to_value[check]) / date_to_value[check]) * 100
                yoy_dates.append(date_str)
                yoy_values.append(yoy)
                break

    return yoy_dates, yoy_values


def calculate_mom(dates: list, values: list) -> tuple:
    """Calculate month-over-month percent change."""
    if len(dates) < 2:
        return dates, values

    mom_dates, mom_values = [], []

    for i in range(1, len(dates)):
        if values[i - 1] != 0:
            mom = ((values[i] - values[i - 1]) / abs(values[i - 1])) * 100
            mom_dates.append(dates[i])
            mom_values.append(mom)

    return mom_dates, mom_values


def calculate_avg_annual(dates: list, values: list) -> tuple:
    """Calculate average annual values."""
    if not dates or not values:
        return dates, values

    # Group by year
    yearly_data = {}
    for date_str, value in zip(dates, values):
        year = date_str[:4]
        if year not in yearly_data:
            yearly_data[year] = []
        yearly_data[year].append(value)

    # Calculate averages
    avg_dates, avg_values = [], []
    for year in sorted(yearly_data.keys()):
        vals = yearly_data[year]
        avg = sum(vals) / len(vals)
        # Use mid-year date for plotting
        avg_dates.append(f"{year}-07-01")
        avg_values.append(avg)

    return avg_dates, avg_values


def find_local_series(query: str) -> dict:
    """Find series from local query map using fuzzy matching."""
    q = query.lower().strip()

    # Score each query map entry
    best_match = None
    best_score = 0

    for key, config in QUERY_MAP.items():
        score = 0
        key_words = set(key.split())
        query_words = set(q.split())

        # Exact phrase match
        if key in q:
            score = 100 + len(key)
        # All key words present
        elif key_words.issubset(query_words):
            score = 50 + len(key_words) * 10
        # Partial word match
        else:
            matching_words = key_words.intersection(query_words)
            if matching_words:
                score = len(matching_words) * 10

        if score > best_score:
            best_score = score
            best_match = config

    return best_match if best_score >= 10 else None


def add_recession_shapes(fig, min_date: str, max_date: str):
    """Add recession shading to a plotly figure."""
    # Convert to datetime for proper date comparison
    min_dt = datetime.strptime(min_date, '%Y-%m-%d')
    max_dt = datetime.strptime(max_date, '%Y-%m-%d')

    for rec in RECESSIONS:
        rec_start = datetime.strptime(rec['start'], '%Y-%m-%d')
        rec_end = datetime.strptime(rec['end'], '%Y-%m-%d')

        if rec_end >= min_dt and rec_start <= max_dt:
            x0 = max(rec['start'], min_date)
            x1 = min(rec['end'], max_date)
            fig.add_vrect(
                x0=x0, x1=x1,
                fillcolor="rgba(169, 169, 169, 0.25)",
                layer="below",
                line_width=0,
            )


def add_comparison_period_shapes(fig, temporal_intent, min_date: str, max_date: str):
    """
    Add visual highlighting for temporal comparison periods.

    For comparison queries like "How does current inflation compare to the 1970s?",
    this highlights both the reference period (1970s) and the current/primary period.

    Args:
        fig: Plotly figure to add shapes to
        temporal_intent: TemporalIntent object with period information
        min_date: Start of chart data range
        max_date: End of chart data range
    """
    if not temporal_intent or not temporal_intent.is_comparison:
        return

    # Reference period highlighting (historical period being compared to)
    reference_period = temporal_intent.reference_period
    if reference_period:
        ref_start = reference_period.get('start')
        ref_end = reference_period.get('end')
        ref_label = reference_period.get('label', 'Reference')

        if ref_start or ref_end:
            # Use chart date range bounds if period extends beyond
            x0 = ref_start if ref_start and ref_start >= min_date else min_date
            x1 = ref_end if ref_end and ref_end <= max_date else (ref_end or max_date)

            # Only draw if period overlaps with chart range
            if x0 <= max_date and (not ref_end or ref_end >= min_date):
                # Light blue shading for reference period
                fig.add_vrect(
                    x0=x0, x1=x1,
                    fillcolor="rgba(66, 133, 244, 0.15)",  # Google Blue, light
                    layer="below",
                    line_width=1,
                    line_color="rgba(66, 133, 244, 0.5)",
                    annotation_text=ref_label,
                    annotation_position="top left",
                    annotation_font=dict(size=9, color="rgba(66, 133, 244, 0.8)"),
                )

    # Primary (current) period highlighting - only if explicitly defined
    # Usually we just compare to current/recent so no need to highlight
    primary_period = temporal_intent.primary_period
    if primary_period and primary_period.get('start'):
        prim_start = primary_period.get('start')
        prim_end = primary_period.get('end') or max_date
        prim_label = primary_period.get('label', 'Current')

        # Light green shading for primary/current period
        if prim_start and prim_start <= max_date:
            x0 = prim_start if prim_start >= min_date else min_date
            x1 = prim_end if prim_end <= max_date else max_date

            fig.add_vrect(
                x0=x0, x1=x1,
                fillcolor="rgba(52, 168, 83, 0.1)",  # Google Green, very light
                layer="below",
                line_width=1,
                line_color="rgba(52, 168, 83, 0.4)",
                annotation_text=prim_label,
                annotation_position="top right",
                annotation_font=dict(size=9, color="rgba(52, 168, 83, 0.8)"),
            )


def add_direct_labels(fig, series_data: list, colors: list):
    """Add direct labels at end of lines (NYT style) instead of legend."""
    for i, (series_id, dates, values, info) in enumerate(series_data):
        if not dates or not values:
            continue
        name = info.get('name', info.get('title', series_id))
        # Truncate long names
        if len(name) > 25:
            name = name[:22] + '...'

        # Add annotation at the last data point
        fig.add_annotation(
            x=dates[-1],
            y=values[-1],
            text=f"  {name}",
            showarrow=False,
            xanchor='left',
            font=dict(
                size=10,
                color=colors[i % len(colors)],
            ),
            bgcolor='rgba(255,255,255,0.8)',
        )


# Key economic events for chart annotations
ECONOMIC_EVENTS = [
    # Fed Policy Changes
    {'date': '2022-03-17', 'label': 'Fed hikes begin', 'type': 'fed'},
    {'date': '2020-03-15', 'label': 'Emergency cut to 0%', 'type': 'fed'},
    {'date': '2019-07-31', 'label': 'Fed cuts rates', 'type': 'fed'},
    {'date': '2015-12-16', 'label': 'First hike since 2008', 'type': 'fed'},
    {'date': '2008-12-16', 'label': 'Fed cuts to zero', 'type': 'fed'},

    # Major Crises & Peaks
    {'date': '2022-06-01', 'label': 'Inflation peaks 9.1%', 'type': 'crisis'},
    {'date': '2020-04-01', 'label': 'Unemployment hits 14.7%', 'type': 'crisis'},
    {'date': '2020-03-11', 'label': 'COVID pandemic', 'type': 'crisis'},
    {'date': '2023-03-10', 'label': 'SVB collapse', 'type': 'crisis'},
    {'date': '2008-09-15', 'label': 'Lehman collapse', 'type': 'crisis'},

    # Policy Milestones
    {'date': '2017-12-22', 'label': 'Tax Cuts Act', 'type': 'policy'},
    {'date': '2021-03-11', 'label': 'ARP stimulus', 'type': 'policy'},
]


def add_event_annotations(fig, min_date: str, max_date: str, event_types: list = None, max_annotations: int = 2):
    """Add key economic event annotations to a chart.

    Limits to max_annotations to avoid cluttering the chart, and staggers
    positions if events are close together.
    """
    min_dt = datetime.strptime(min_date, '%Y-%m-%d')
    max_dt = datetime.strptime(max_date, '%Y-%m-%d')

    # Collect eligible events
    eligible_events = []
    for event in ECONOMIC_EVENTS:
        event_dt = datetime.strptime(event['date'], '%Y-%m-%d')

        # Only show if within date range
        if not (min_dt <= event_dt <= max_dt):
            continue

        # Filter by event type if specified
        if event_types and event['type'] not in event_types:
            continue

        eligible_events.append((event_dt, event))

    # Sort by date (most recent first) and limit to max_annotations
    eligible_events.sort(key=lambda x: x[0], reverse=True)
    eligible_events = eligible_events[:max_annotations]

    # Add annotations with staggered y-positions if close together
    y_offsets = [-25, -45, -65]  # Stagger vertically
    for idx, (event_dt, event) in enumerate(eligible_events):
        fig.add_annotation(
            x=event['date'],
            y=1.0,
            yref='paper',
            text=event['label'],
            showarrow=True,
            arrowhead=2,
            arrowsize=0.8,
            arrowwidth=1,
            arrowcolor='#999',
            ax=0,
            ay=y_offsets[idx % len(y_offsets)],
            font=dict(size=9, color='#666'),
            bgcolor='rgba(255,255,255,0.9)',
            borderpad=2,
        )


def create_chart(series_data: list, combine: bool = False, chart_type: str = 'line', temporal_intent=None) -> go.Figure:
    """Create a Plotly chart with recession shading and optional comparison period highlighting.

    Args:
        series_data: List of (series_id, dates, values, info) tuples
        combine: Whether to combine all series on one chart
        chart_type: 'line', 'bar', or 'area'
        temporal_intent: Optional TemporalIntent for comparison period highlighting
    """
    # Okabe-Ito colorblind-safe palette
    colors = ['#0072B2', '#E69F00', '#009E73', '#CC79A7', '#56B4E9', '#D55E00']

    all_dates = []
    for _, dates, _, _ in series_data:
        all_dates.extend(dates)
    if not all_dates:
        return go.Figure()
    min_date, max_date = min(all_dates), max(all_dates)

    if combine or len(series_data) == 1:
        fig = go.Figure()
        for i, (series_id, dates, values, info) in enumerate(series_data):
            full_name = info.get('name', info.get('title', series_id))
            # Include series ID in legend - no truncation for full readability
            name = f"{full_name} ({series_id})"

            if chart_type == 'bar':
                fig.add_trace(go.Bar(
                    x=dates, y=values,
                    name=name,
                    marker_color=colors[i % len(colors)],
                    hovertemplate=f"<b>{name}</b><br>%{{x|%b %Y}}<br>%{{y:,.2f}}<extra></extra>"
                ))
            elif chart_type == 'area':
                # Convert hex to rgba for fill
                hex_color = colors[i % len(colors)]
                r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
                fill_color = f'rgba({r}, {g}, {b}, 0.3)'
                fig.add_trace(go.Scatter(
                    x=dates, y=values, mode='lines',
                    name=name,
                    fill='tozeroy',
                    line=dict(color=hex_color, width=2),
                    fillcolor=fill_color,
                    hovertemplate=f"<b>{name}</b><br>%{{x|%b %Y}}<br>%{{y:,.2f}}<extra></extra>"
                ))
            else:  # line (default)
                fig.add_trace(go.Scatter(
                    x=dates, y=values, mode='lines',
                    name=name,
                    line=dict(color=colors[i % len(colors)], width=2),
                    hovertemplate=f"<b>{name}</b><br>%{{x|%b %Y}}<br>%{{y:,.2f}}<extra></extra>"
                ))

        add_recession_shapes(fig, min_date, max_date)

        # Add comparison period highlighting if this is a temporal comparison query
        if temporal_intent:
            add_comparison_period_shapes(fig, temporal_intent, min_date, max_date)

        # Use direct labels (NYT style) for 2-4 series, legend otherwise
        use_direct_labels = 2 <= len(series_data) <= 4 and chart_type == 'line'
        if use_direct_labels:
            add_direct_labels(fig, series_data, colors)

        # Event annotations removed - they cluttered the charts

        unit = series_data[0][3].get('unit', series_data[0][3].get('units', ''))
        # Build source annotation text
        sources = set(info.get('source', 'FRED') for _, _, _, info in series_data)
        series_ids = [sid for sid, _, _, _ in series_data]
        source_text = f"Source: {', '.join(sources)} | {' | '.join(series_ids)}"

        fig.update_layout(
            template='plotly_white',
            hovermode='x unified',
            showlegend=len(series_data) > 1 and not use_direct_labels,
            legend=dict(
                orientation='h',
                yanchor='top',
                y=-0.15,
                xanchor='center',
                x=0.5,
                font=dict(size=11),
                bgcolor='rgba(255,255,255,0.8)',
            ),
            margin=dict(l=60, r=150 if use_direct_labels else 20, t=20, b=80),
            yaxis_title=unit[:30] if len(unit) > 30 else unit,
            xaxis=dict(
                tickformat='%Y',
                gridcolor='#e5e5e5',
                type='date',
                rangeslider=dict(visible=True, thickness=0.05),
            ),
            yaxis=dict(gridcolor='#e5e5e5'),
            height=320,
            annotations=[
                dict(
                    text=source_text,
                    xref='paper', yref='paper',
                    x=0, y=-0.32,
                    showarrow=False,
                    font=dict(size=9, color='#78716c'),
                    xanchor='left',
                )
            ]
        )
    else:
        fig = make_subplots(
            rows=len(series_data), cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
        )

        for i, (series_id, dates, values, info) in enumerate(series_data):
            name = info.get('name', info.get('title', series_id))
            unit = info.get('unit', info.get('units', ''))

            if chart_type == 'bar':
                trace = go.Bar(
                    x=dates, y=values,
                    name=name[:40],
                    marker_color=colors[i % len(colors)],
                    hovertemplate=f"<b>{name[:40]}</b><br>%{{x|%b %Y}}<br>%{{y:,.2f}}<extra></extra>"
                )
            elif chart_type == 'area':
                hex_color = colors[i % len(colors)]
                r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
                fill_color = f'rgba({r}, {g}, {b}, 0.3)'
                trace = go.Scatter(
                    x=dates, y=values, mode='lines',
                    name=name[:40],
                    fill='tozeroy',
                    line=dict(color=hex_color, width=2),
                    fillcolor=fill_color,
                    hovertemplate=f"<b>{name[:40]}</b><br>%{{x|%b %Y}}<br>%{{y:,.2f}}<extra></extra>"
                )
            else:  # line
                trace = go.Scatter(
                    x=dates, y=values, mode='lines',
                    name=name[:40],
                    line=dict(color=colors[i % len(colors)], width=2),
                    hovertemplate=f"<b>{name[:40]}</b><br>%{{x|%b %Y}}<br>%{{y:,.2f}}<extra></extra>"
                )

            fig.add_trace(trace, row=i + 1, col=1)
            fig.update_yaxes(title_text=unit[:20] if len(unit) > 20 else unit, row=i + 1, col=1)

        for i in range(len(series_data)):
            for rec in RECESSIONS:
                if rec['end'] >= min_date and rec['start'] <= max_date:
                    x0 = max(rec['start'], min_date)
                    x1 = min(rec['end'], max_date)
                    fig.add_vrect(
                        x0=x0, x1=x1,
                        fillcolor="rgba(169, 169, 169, 0.25)",
                        layer="below",
                        line_width=0,
                        row=i + 1, col=1
                    )

            # Add comparison period highlighting for each subplot
            if temporal_intent and temporal_intent.is_comparison:
                reference_period = temporal_intent.reference_period
                if reference_period:
                    ref_start = reference_period.get('start')
                    ref_end = reference_period.get('end')
                    if ref_start or ref_end:
                        x0 = ref_start if ref_start and ref_start >= min_date else min_date
                        x1 = ref_end if ref_end and ref_end <= max_date else (ref_end or max_date)
                        if x0 <= max_date and (not ref_end or ref_end >= min_date):
                            fig.add_vrect(
                                x0=x0, x1=x1,
                                fillcolor="rgba(66, 133, 244, 0.15)",
                                layer="below",
                                line_width=1,
                                line_color="rgba(66, 133, 244, 0.5)",
                                row=i + 1, col=1
                            )

        fig.update_layout(
            template='plotly_white',
            height=280 * len(series_data),
            showlegend=False,
            margin=dict(l=60, r=20, t=20, b=40),
        )

    # Add range slider for zoom control
    fig.update_xaxes(tickformat='%Y', tickangle=-45, type='date')

    # Only use row/col for subplots (when not combined and multiple series)
    if not combine and len(series_data) > 1:
        # Subplots - add slider to bottom chart only
        fig.update_xaxes(
            rangeslider=dict(visible=True, thickness=0.05),
            row=len(series_data), col=1
        )
    else:
        # Single chart or combined - no row/col needed
        fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.05))

    return fig


def format_number(n, unit=''):
    """Format number for display, accounting for unit multipliers."""
    if n is None or (isinstance(n, float) and (n != n)):
        return 'N/A'

    # Adjust for units that are already in thousands/millions/billions
    display_n = n
    unit_lower = unit.lower() if unit else ''
    if 'thousands' in unit_lower:
        display_n = n * 1000  # Convert to actual number
    elif 'millions' in unit_lower:
        display_n = n * 1e6
    elif 'billions' in unit_lower:
        display_n = n * 1e9

    if abs(display_n) >= 1e12:
        return f"{display_n / 1e12:.2f} trillion"
    if abs(display_n) >= 1e9:
        return f"{display_n / 1e9:.2f} billion"
    if abs(display_n) >= 1e6:
        return f"{display_n / 1e6:.2f} million"
    if abs(display_n) >= 1e3:
        return f"{display_n:,.0f}"
    if abs(display_n) < 10:
        return f"{display_n:.2f}"
    return f"{display_n:.1f}"


def summary_to_bullets(text):
    """Convert summary paragraph to HTML bullet list, one sentence per bullet."""
    import re
    if not text:
        return ""

    # Split on sentence endings (. ! ?) followed by space or end of string
    # But be careful with abbreviations like "U.S." or numbers like "3.5%"
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.strip())

    # Filter out empty sentences and clean up
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= 1:
        # If only one sentence, just return as paragraph
        return f"<p>{text}</p>"

    # Build bullet list
    bullets = "".join(f"<li>{s}</li>" for s in sentences)
    return f"<ul>{bullets}</ul>"


def main():
    # Clean up expired cache entries to prevent memory bloat
    _clear_expired_cache()

    st.set_page_config(page_title="EconStats", page_icon="", layout="wide")

    st.markdown("""
    <style>
    /* Prevent button text wrapping */
    .stButton button {
        white-space: nowrap !important;
    }

    /* Hide sidebar entirely and broken collapse buttons */
    section[data-testid="stSidebar"],
    button[kind="header"],
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    [data-testid="baseButton-header"],
    .stAppDeployButton,
    header[data-testid="stHeader"] button,
    .st-emotion-cache-1dp5vir,
    .st-emotion-cache-eczf16,
    .st-emotion-cache-h4xjwg {
        display: none !important;
    }

    /* Financial Dashboard Theme - Inter font, professional colors */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background: #FAF9F6;
        color: #1e293b !important;
    }
    .stApp p, .stApp span, .stApp div, .stApp li, .stApp label {
        color: #1e293b;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
        color: #0f172a !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        font-weight: 600 !important;
    }

    /* Wide layout content control - use more of the page */
    .stApp .main .block-container {
        max-width: 1100px !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    @media (min-width: 1400px) {
        .stApp .main .block-container {
            max-width: 1200px !important;
        }
    }

    /* Tight spacing for chat mode */
    .stApp [data-testid="stVerticalBlock"] > div { gap: 0 !important; margin: 0 !important; padding: 0 !important; }
    .stApp [data-testid="stVerticalBlockBorderWrapper"] { padding: 0 !important; margin: 0 !important; }
    .stApp hr { margin: 2px 0 !important; border-color: #e7e5e4 !important; }
    .stApp h3 { margin-top: 0 !important; margin-bottom: 2px !important; font-size: 1rem !important; }
    .stApp ul { margin-top: 0 !important; margin-bottom: 2px !important; }
    .stApp li { margin-bottom: 1px !important; font-size: 0.88rem !important; line-height: 1.35 !important; }
    .stApp p { margin-bottom: 1px !important; }
    /* Reduce column gaps */
    [data-testid="stHorizontalBlock"] { gap: 0.5rem !important; }
    /* Chat message spacing */
    [data-testid="stChatMessage"] { padding: 0 !important; margin: 0 !important; }
    /* Plotly chart margins */
    .stPlotlyChart { margin: 0 !important; padding: 0 !important; }
    [data-testid="stPlotlyChart"] { margin-bottom: 0 !important; }
    .js-plotly-plot { margin-bottom: 0 !important; }
    /* Reduce but don't eliminate top padding */
    .stApp .main > div { padding-top: 2rem !important; }
    /* Metric labels - don't truncate */
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] > div,
    [data-testid="stMetricLabel"] > div > div,
    [data-testid="stMetricLabel"] p,
    [data-testid="stMetricLabel"] span {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        font-size: 0.6rem !important;
        line-height: 1.15 !important;
        max-width: none !important;
        width: auto !important;
    }
    [data-testid="stMetric"] {
        min-height: auto !important;
    }
    /* Hide anchor links next to headings */
    .stApp a[href^="#"] { display: none !important; }
    h3 a, h2 a, h1 a { display: none !important; }
    h1 {
        font-weight: 700 !important;
        font-style: normal !important;
        text-align: center;
        font-size: 2.5rem !important;
        letter-spacing: -0.5px;
    }
    .subtitle { text-align: center; color: #64748b; margin-top: -5px; margin-bottom: 20px; font-size: 1rem; font-weight: 400; }

    /* Summary Section - tight spacing */
    .summary-callout {
        background: transparent;
        padding: 0 0 8px 0;
        margin-bottom: 8px;
    }
    .summary-callout h3 { color: #292524 !important; margin: 0 0 6px 0; font-size: 1rem; font-weight: 600; }
    .summary-callout p { color: #44403c !important; margin: 0; font-size: 0.9rem; line-height: 1.5; font-weight: 400; }
    .summary-callout ul { margin: 0 0 4px 0; padding-left: 18px; list-style-type: disc; }
    .summary-callout li { color: #44403c; font-size: 0.9rem; line-height: 1.45; margin-bottom: 3px; padding-left: 2px; }
    .summary-callout li::marker { color: #D4A574; }

    /* Premium Economist Analysis Box */
    .economist-analysis {
        background: linear-gradient(135deg, #fefce8 0%, #fef3c7 100%);
        border: 1px solid #fcd34d;
        border-radius: 8px;
        padding: 16px;
        margin: 16px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .economist-analysis .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .economist-analysis .title {
        color: #92400e;
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .economist-analysis .confidence-high { background: #dcfce7; color: #166534; }
    .economist-analysis .confidence-medium { background: #fef3c7; color: #92400e; }
    .economist-analysis .confidence-low { background: #fee2e2; color: #991b1b; }
    .economist-analysis .key-insight {
        background: #FEF3C7;
        border-left: 4px solid #F59E0B;
        padding: 12px;
        margin: 12px 0;
        border-radius: 4px;
    }
    .economist-analysis .risks { color: #DC2626; }
    .economist-analysis .opportunities { color: #059669; }

    /* Chat mode - Modern conversational UI styling */

    /* Hide empty chat messages until content loads - prevents janky empty card flash */
    [data-testid="stChatMessage"]:empty,
    [data-testid="stChatMessage"]:has(> div:empty:only-child) {
        opacity: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
    }

    /* Smooth fade-in for chat messages when content loads */
    [data-testid="stChatMessage"] {
        background: #FFFDFB !important;
        border: 1px solid #e7e5e4 !important;
        border-radius: 4px 20px 20px 20px !important;
        padding: 20px 24px !important;
        margin: 12px 0 24px 0 !important;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04) !important;
        position: relative !important;
        animation: fadeInCard 0.3s ease-out !important;
    }

    @keyframes fadeInCard {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Skeleton loading shimmer for metrics during load */
    .skeleton-loading {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
        min-height: 80px;
    }
    @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }

    /* Status container - clean, professional look */
    [data-testid="stStatusWidget"] {
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        background: #FFFDFB !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    }
    [data-testid="stStatusWidget"] summary {
        font-size: 0.9rem !important;
        color: #475569 !important;
        padding: 12px 16px !important;
    }
    [data-testid="stStatusWidget"] summary span {
        font-weight: 500 !important;
    }
    /* Hide expanded details by default for cleaner look */
    [data-testid="stStatusWidget"][open] > div:last-child {
        padding: 8px 16px 12px 16px !important;
        font-size: 0.8rem !important;
        color: #64748b !important;
        border-top: 1px solid #f1f5f9 !important;
    }

    /* Subtle spinner styling - less jarring during loading */
    [data-testid="stSpinner"] {
        animation: fadeInSpinner 0.2s ease-out;
    }
    [data-testid="stSpinner"] > div {
        font-size: 0.85rem !important;
        color: #64748b !important;
    }
    @keyframes fadeInSpinner {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    /* Hide the default avatar icon */
    [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {
        display: none !important;
    }

    /* Add label via CSS pseudo-element */
    [data-testid="stChatMessage"]::before {
        content: "EconStats";
        position: absolute;
        top: -10px;
        left: 16px;
        background: #FAF9F6;
        padding: 2px 10px;
        font-size: 0.7rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-radius: 8px;
        z-index: 1;
    }

    /* Style horizontal rules within chat message */
    [data-testid="stChatMessage"] hr {
        border: none !important;
        border-top: 1px solid #f1f0ef !important;
        margin: 16px 0 !important;
    }

    /* Metrics within chat message - subtle styling */
    [data-testid="stChatMessage"] [data-testid="stMetric"] {
        background: #f8f7f6 !important;
        border: 1px solid #f1f0ef !important;
    }

    /* User query display in chat history - styled bubble, right-aligned */
    .chat-user-query {
        display: inline-block;
        background: linear-gradient(135deg, #D4A574 0%, #c4956a 100%);
        color: #FFFDFB;
        padding: 12px 18px;
        border-radius: 20px 20px 4px 20px;
        font-size: 0.95rem;
        font-weight: 500;
        margin: 20px 0 12px 0;
        max-width: 85%;
        box-shadow: 0 2px 8px rgba(212, 165, 116, 0.15);
        float: right;
        clear: both;
    }

    /* Assistant response container - clean card style */
    .chat-assistant-response {
        background: #FFFDFB;
        border: 1px solid #e7e5e4;
        border-radius: 4px 20px 20px 20px;
        padding: 24px 24px 20px 24px;
        margin: 12px 0 24px 0;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
        clear: both;
        position: relative;
    }

    /* Subtle label for assistant responses */
    .chat-assistant-response::before {
        content: "EconStats";
        position: absolute;
        top: -10px;
        left: 16px;
        background: #FAF9F6;
        padding: 2px 10px;
        font-size: 0.7rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-radius: 8px;
    }

    /* Style horizontal rules within chat response */
    .chat-assistant-response hr {
        border: none;
        border-top: 1px solid #f1f0ef;
        margin: 16px 0;
    }

    /* Metrics within response - subtle styling */
    .chat-assistant-response [data-testid="stMetric"] {
        background: #f8f7f6 !important;
        border: 1px solid #f1f0ef !important;
    }

    /* Smooth transition for chat mode entry */
    .chat-container {
        animation: fadeInUp 0.3s ease-out;
    }
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Clearfix for float-based layout */
    .chat-clearfix::after {
        content: "";
        display: table;
        clear: both;
    }

    /* Chat follow-up input - coral/terracotta border */
    [data-testid="stTextInput"][data-baseweb] input[aria-label="Follow-up"],
    div:has(> [data-testid="stTextInput"]) + div [data-testid="stTextInput"] input {
        background: #FAF9F6 !important;
        border: 1.5px solid #D4A574 !important;
        border-radius: 16px !important;
        padding: 16px 20px !important;
        font-size: 1rem !important;
    }
    /* Target chat input specifically via key pattern */
    [data-testid="stTextInput"]:last-of-type > div > div {
        background: #FAF9F6 !important;
        border: 1.5px solid #D4A574 !important;
        border-radius: 16px !important;
    }
    [data-testid="stTextInput"]:last-of-type input {
        background: transparent !important;
        border: none !important;
        padding: 14px 18px !important;
    }
    /* Suggestion pills */
    .suggestion-pill {
        display: inline-block;
        background: #f3f4f6;
        border: 1px solid #e5e7eb;
        border-radius: 20px;
        padding: 8px 16px;
        margin: 4px;
        font-size: 0.9rem;
        color: #374151;
        cursor: pointer;
    }
    .suggestion-pill:hover {
        background: #e5e7eb;
        border-color: #d1d5db;
    }

    /* Dashboard Cards - tight spacing */
    .metric-card {
        background: #FFFDFB;
        border: 1px solid #e7e5e4;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
    }
    .metric-label { font-size: 0.7rem; color: #78716c; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
    .metric-value { font-size: 1.4rem; font-weight: 700; color: #292524; }
    .metric-delta-up { font-size: 0.75rem; color: #16a34a; font-weight: 500; }
    .metric-delta-down { font-size: 0.75rem; color: #dc2626; font-weight: 500; }

    /* Streamlit metric overrides - tight spacing */
    [data-testid="stMetric"] {
        background: #FFFDFB;
        border: 1px solid #e7e5e4;
        border-radius: 8px;
        padding: 10px 14px;
    }
    [data-testid="stMetricLabel"] { font-size: 0.7rem !important; color: #78716c !important; text-transform: uppercase; letter-spacing: 0.5px; }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; font-weight: 700 !important; color: #292524 !important; }
    [data-testid="stMetricDelta"] svg { display: none; }
    [data-testid="stMetricDelta"] > div { font-weight: 500 !important; font-size: 0.75rem !important; }

    /* Chart sections - tight spacing */
    .chart-section {
        background: #FFFDFB;
        border: 1px solid #e7e5e4;
        border-radius: 10px;
        margin-bottom: 12px;
        overflow: hidden;
        padding: 12px 16px;
    }
    .chart-section h3 { margin-top: 0; margin-bottom: 6px; font-size: 1rem; color: #292524; font-weight: 600; }
    .chart-section ul { margin: 0 0 8px 0; padding-left: 18px; }
    .chart-section li, .chart-section p { color: #44403c; font-size: 0.85rem; line-height: 1.45; margin-bottom: 3px; }
    .chart-header { padding: 10px 14px; border-bottom: 1px solid #e7e5e4; }
    .chart-title { font-size: 0.95rem; color: #292524; margin-bottom: 4px; font-weight: 600; }
    .chart-bullets { color: #57534e; font-size: 0.85rem; margin-left: 14px; line-height: 1.4; }
    .chart-bullets li { margin-bottom: 3px; }
    .source-line {
        padding: 6px 12px;
        border-top: 1px solid #e7e5e4;
        font-size: 0.7rem;
        color: #78716c;
        background: #FAF9F6;
        font-family: 'Inter', monospace;
        margin-top: 8px;
    }

    /* AI Insight box - warm theme */
    .ai-explanation {
        color: #292524;
        padding: 20px 24px;
        background: #FAF9F6;
        border: 1px solid #e7e5e4;
        border-left: 4px solid #D4A574;
        border-radius: 0 12px 12px 0;
        margin-bottom: 20px;
        font-size: 1rem;
        line-height: 1.7;
        font-weight: 400;
        font-style: normal !important;
    }

    /* Query display - search card style */
    .query-card {
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
        padding: 14px 20px;
        border-radius: 12px;
        border-left: 4px solid #3b82f6;
        font-size: 1.1rem;
        font-weight: 600;
        color: #0f172a;
        margin-bottom: 16px;
    }

    /* Hide empty Streamlit containers */
    .stMarkdown:empty, div[data-testid="stVerticalBlock"]:empty { display: none !important; }
    div[data-testid="stForm"] { border: none !important; padding: 0 !important; }

    /* Status colors */
    .highlight { font-weight: 600; color: #2563eb; }
    .up { color: #16a34a; font-weight: 600; }
    .down { color: #dc2626; font-weight: 600; }
    .caution { color: #d97706; font-weight: 600; }
    /* Hide chat message avatars */
    .stChatMessage [data-testid="chatAvatarIcon-assistant"],
    .stChatMessage [data-testid="chatAvatarIcon-user"],
    .stChatMessage img[alt="assistant avatar"],
    .stChatMessage img[alt="user avatar"],
    [data-testid="stChatMessageAvatarAssistant"],
    [data-testid="stChatMessageAvatarUser"] { display: none !important; }

    /* Category pill buttons */
    .stButton button[kind="primary"],
    .stButton button[data-testid="baseButton-primary"],
    button[kind="primary"],
    button.st-emotion-cache-primary,
    .stFormSubmitButton button {
        color: #ffffff !important;
        background-color: #2563eb !important;
        border: none !important;
        border-radius: 25px !important;
    }
    .stButton button[kind="primary"]:hover,
    .stButton button[data-testid="baseButton-primary"]:hover,
    button[kind="primary"]:hover,
    .stFormSubmitButton button:hover {
        color: #ffffff !important;
        background-color: #1d4ed8 !important;
    }
    /* Category pill buttons - tight spacing, no overflow */
    .stButton button:not([kind="primary"]) {
        color: #57534e !important;
        background-color: #FAF9F6 !important;
        border: 1px solid #d6d3d1 !important;
        border-radius: 8px !important;
        padding: 0.4rem 0.8rem !important;
        font-size: 0.8rem !important;
        transition: all 0.15s ease !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        max-width: 100% !important;
    }
    .stButton button:not([kind="primary"]):hover {
        border-color: #D4A574 !important;
        color: #78716c !important;
        background-color: #FAF9F6 !important;
        transform: none !important;
        box-shadow: none !important;
    }

    /* Example queries section */
    .examples-header {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #6b7280;
        margin: 0.5rem 0 0.5rem 0;
        font-weight: 600;
        font-style: normal !important;
        text-align: center;
    }

    /* Example query buttons */
    .examples-section + div .stButton button,
    div[data-testid="column"] .stButton button[key^="example"] {
        background: #f8fafc !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        color: #475569 !important;
        text-align: left !important;
        font-style: normal !important;
        padding: 0.8rem 1rem !important;
    }
    .examples-section + div .stButton button:hover,
    div[data-testid="column"] .stButton button[key^="example"]:hover {
        background: #eff6ff !important;
        border-color: #bfdbfe !important;
        color: #1e40af !important;
    }

    /* Helper text under search */
    .helper-text {
        text-align: center;
        color: #6b7280;
        font-size: 0.85rem;
        margin: 0.25rem 0 0.25rem 0;
        font-style: normal !important;
    }

    /* Search bar - warm theme */
    .search-wrapper {
        margin: 16px 0 8px 0;
        border-radius: 16px;
        overflow: hidden;
        background: #FFFDFB;
        border: 1px solid #e7e5e4;
    }
    div[data-testid="stTextInput"] input {
        background: #FFFDFB !important;
        border: none !important;
        border-radius: 16px !important;
        font-size: 1rem !important;
        padding: 1.1rem 1.5rem !important;
        box-shadow: none !important;
        transition: none !important;
        text-align: center !important;
        color: #292524 !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        text-align: left !important;
    }
    div[data-testid="stTextInput"] input::placeholder {
        color: #a8a29e !important;
        text-align: center !important;
    }
    /* Hide Streamlit's default input wrapper styling */
    div[data-testid="stTextInput"] > div {
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }
    div[data-testid="stTextInput"] label {
        display: none !important;
    }

    /* Mobile responsive styles */
    @media (max-width: 768px) {
        .narrative-box { padding: 15px; }
        .chart-header { padding: 12px 15px; }
        .chart-title { font-size: 1rem; }
        .chart-bullets { font-size: 0.9rem; margin-left: 15px; }
        .source-line { padding: 8px 15px; font-size: 0.8rem; }
        h1 { font-size: 2.5rem !important; }
        .subtitle { font-size: 0.95rem; }
        /* Prevent horizontal scroll */
        .stApp { overflow-x: hidden; }
        /* Search bar on mobile */
        .search-wrapper { margin: 15px 0 10px 0; }
        div[data-testid="stTextInput"] input {
            font-size: 16px !important;  /* Prevents iOS zoom */
            padding: 1rem 1.25rem !important;
            border-radius: 12px !important;
        }
        /* Category pill buttons on mobile */
        .stButton button {
            min-height: 44px !important;
            font-size: 0.85rem !important;
            padding: 0.5rem 1rem !important;
        }
        /* Examples section on mobile */
        .examples-section { padding: 1rem; }
        .example-query { font-size: 0.85rem; padding: 0.7rem 0.9rem; }
        /* Hide sidebar on mobile */
        section[data-testid="stSidebar"] { display: none; }
    }
    /* Very small screens */
    @media (max-width: 480px) {
        h1 { font-size: 2rem !important; }
        .subtitle { font-size: 0.85rem; margin-bottom: 10px !important; }
    }
    </style>
    """, unsafe_allow_html=True)

    # About section in sidebar
    # Use session state for query persistence and follow-ups
    if 'last_query' not in st.session_state:
        st.session_state.last_query = ''
    if 'last_series' not in st.session_state:
        st.session_state.last_series = []
    if 'last_series_names' not in st.session_state:
        st.session_state.last_series_names = []
    if 'last_series_data' not in st.session_state:
        st.session_state.last_series_data = []
    if 'last_explanation' not in st.session_state:
        st.session_state.last_explanation = ''
    if 'last_chart_type' not in st.session_state:
        st.session_state.last_chart_type = 'line'
    if 'last_combine' not in st.session_state:
        st.session_state.last_combine = False
    # Chat mode toggle - starts as search bar, can switch to chat for follow-ups
    if 'chat_mode' not in st.session_state:
        st.session_state.chat_mode = False
    # Chat history for conversation format
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    # Ensemble mode - use Claude + Gemini + GPT for better query plans
    if 'ensemble_mode' not in st.session_state:
        st.session_state.ensemble_mode = ENSEMBLE_AVAILABLE  # Default on if available
    # RAG mode - use semantic search + LLM selection (recommended)
    if 'rag_mode' not in st.session_state:
        st.session_state.rag_mode = RAG_AVAILABLE  # Default on if available (takes priority)

    # Default timeframe - 8 years provides good context without burying recent trends
    # Users can say "show all data" or "full history" for complete historical view
    DEFAULT_YEARS = 8
    years = DEFAULT_YEARS

    # Handle pending query from button clicks
    query = None
    if 'pending_query' in st.session_state and st.session_state.pending_query:
        query = st.session_state.pending_query
        st.session_state.pending_query = None

    # Check for query in URL params (for permalinks)
    # URL format: ?q=unemployment+rate
    url_params = st.query_params
    if 'q' in url_params and not query and not st.session_state.last_query:
        query = url_params['q']
        # Clear the URL param after reading (so refresh doesn't re-run)
        # st.query_params.clear()  # Uncomment to clear after first load

    # UI Mode: Search Bar (default) or Chat Mode (for follow-ups)
    if not st.session_state.chat_mode:
        # LANDING PAGE MODE - Text only
        st.markdown("<h1 style='text-align: center; margin-bottom: 0; margin-top: 0;'>EconStats<span style='color: #64748b; font-weight: 400;'>.org</span></h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; margin-top: 0; margin-bottom: 10px;'>U.S. Economic Data with Context</p>", unsafe_allow_html=True)

        # Quick search buttons in a single compact row
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
        with col1:
            if st.button("Jobs", width='stretch', key="btn_jobs"):
                st.session_state.pending_query = "job market"
                st.rerun()
        with col2:
            if st.button("Inflation", width='stretch', key="btn_inflation"):
                st.session_state.pending_query = "inflation"
                st.rerun()
        with col3:
            if st.button("GDP", width='stretch', key="btn_gdp"):
                st.session_state.pending_query = "gdp growth"
                st.rerun()
        with col4:
            if st.button("Rates", width='stretch', key="btn_rates"):
                st.session_state.pending_query = "interest rates"
                st.rerun()
        with col5:
            if st.button("Recession", width='stretch', key="btn_recession"):
                st.session_state.pending_query = "are we in a recession"
                st.rerun()

        # Featured Dashboards section
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 0.85rem; margin: 20px 0 10px 0; font-weight: 500;'>Featured Dashboards</p>", unsafe_allow_html=True)

        dash_col1, dash_col2, dash_col3 = st.columns(3)
        with dash_col1:
            if st.button("Leading Indicators", key="dash_leading", use_container_width=True):
                st.session_state.pending_query = "leading indicators dashboard"
                st.rerun()
            if st.button("Reindustrializing America?", key="dash_mfg", use_container_width=True):
                st.session_state.pending_query = "is America reindustrializing? manufacturing jobs and industrial production"
                st.rerun()
        with dash_col2:
            if st.button("Health of the Economy", key="dash_health", use_container_width=True):
                st.session_state.pending_query = "how is the economy doing overall"
                st.rerun()
            if st.button("AI's Impact on Jobs", key="dash_ai", use_container_width=True):
                st.session_state.pending_query = "AI impact on jobs and labor market"
                st.rerun()
        with dash_col3:
            if st.button("America's Finances", key="dash_debt", use_container_width=True):
                st.session_state.pending_query = "federal debt deficit and interest payments"
                st.rerun()
            if st.button("Tariffs & Trade", key="dash_tariffs", use_container_width=True):
                st.session_state.pending_query = "tariffs and trade balance"
                st.rerun()

        # SEARCH BAR MODE - single clean input field (no button needed, Enter submits)
        st.markdown('<div class="search-wrapper">', unsafe_allow_html=True)
        text_query = st.text_input(
            "Search",
            placeholder="Ask about the economy... (press Enter)",
            label_visibility="collapsed",
            key="search_input"
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # Helper text - more concise
        st.markdown('<p class="helper-text">Ask in plain English. We\'ll pull the data and explain what it means.</p>', unsafe_allow_html=True)

        # Example queries section - only show when no results yet
        if not st.session_state.last_query:
            st.markdown('<p class="examples-header">Try these questions</p>', unsafe_allow_html=True)

            # Simple list of example queries
            example_queries = [
                "How is the economy?",
                "Are wages keeping up with inflation?",
                "Is the labor market cooling off?",
                "How tight is the job market right now?",
                "Is rent inflation coming down yet?",
                "Compare the job market to pre-pandemic"
            ]

            # Two-column grid
            cols = st.columns(2)
            for i, eq in enumerate(example_queries):
                with cols[i % 2]:
                    if st.button(eq, key=f"example_{i}", use_container_width=True):
                        st.session_state.pending_query = eq
                        st.rerun()

        if not query:
            query = text_query
    else:
        # CHAT MODE - conversational interface
        # Compact header with back button
        col_back, col_title = st.columns([1, 4])
        with col_back:
            if st.button("← Back", key="home_btn", type="secondary"):
                st.session_state.chat_mode = False
                st.session_state.messages = []
                st.session_state.last_query = ''
                st.session_state.last_series = []
                st.session_state.last_series_data = []
                st.session_state.last_explanation = ''
                st.rerun()
        with col_title:
            st.markdown("<span style='font-size: 1.3rem; font-weight: 600; color: #292524;'>EconStats</span>", unsafe_allow_html=True)

        # Wrap conversation in animated container for smooth transition
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)

        # Render conversation history with full charts
        for msg_idx, msg in enumerate(st.session_state.messages):
            if msg["role"] == "user":
                # User query bubble - styled and right-aligned
                st.markdown(f'<div class="chat-clearfix"><div class="chat-user-query">{msg["content"]}</div></div>', unsafe_allow_html=True)
            else:
                # Assistant message with summary and charts - Dashboard layout
                with st.chat_message("assistant"):
                    # Key metrics row FIRST (above summary)
                    if msg.get("series_data"):
                        series_data = msg["series_data"]
                        metric_cols = st.columns(min(len(series_data), 4))
                        for idx, (sid, d, v, i) in enumerate(series_data[:4]):
                            if v and len(v) > 0:
                                latest_val = v[-1]
                                name = i.get('name', sid)
                                unit = i.get('unit', '')

                                # Check if this is a percentage/rate series
                                is_rate_series = ('percent' in unit.lower() or '%' in unit or
                                                  'rate' in name.lower() or i.get('is_yoy'))

                                # Check if this is a payroll change series (already a flow, not a stock)
                                is_payroll_change = i.get('is_payroll_change', False)

                                # Calculate delta if we have enough data
                                delta = None
                                delta_color = "normal"
                                if len(v) >= 13:  # YoY comparison
                                    prev_val = v[-13]
                                    if is_payroll_change:
                                        # For job changes, show absolute comparison (not % of %)
                                        # e.g., "vs 111K Dec 2024" instead of "-84.5% YoY"
                                        if prev_val >= 1000:
                                            delta = f"vs {prev_val/1000:.0f}K yr ago"
                                        elif prev_val >= 0:
                                            delta = f"vs {prev_val:.0f}K yr ago"
                                        else:
                                            delta = f"vs {prev_val:.0f}K yr ago"
                                    elif is_rate_series:
                                        # For rates/percentages, show pp change (not % of %)
                                        pp_change = latest_val - prev_val
                                        delta = f"{pp_change:+.1f} pp YoY"
                                    elif prev_val != 0:
                                        # For levels, show % change
                                        pct_change = ((latest_val - prev_val) / abs(prev_val)) * 100
                                        delta = f"{pct_change:+.1f}% YoY"
                                    # For unemployment, down is good
                                    if 'unemployment' in name.lower() or 'jobless' in name.lower():
                                        delta_color = "inverse"

                                with metric_cols[idx % len(metric_cols)]:
                                    # Format value based on type, accounting for unit multipliers
                                    unit_lower = unit.lower()
                                    display_val = latest_val
                                    # Convert to actual number if unit indicates thousands/millions
                                    if 'thousands' in unit_lower:
                                        display_val = latest_val * 1000
                                    elif 'millions' in unit_lower:
                                        display_val = latest_val * 1e6
                                    elif 'billions' in unit_lower:
                                        display_val = latest_val * 1e9

                                    if 'percent' in unit_lower or '%' in unit:
                                        val_str = f"{latest_val:.2f}%"
                                    elif display_val >= 1e9:
                                        val_str = f"{display_val/1e9:.1f}B"
                                    elif display_val >= 1e6:
                                        val_str = f"{display_val/1e6:.1f}M"
                                    elif display_val >= 1000:
                                        val_str = f"{display_val/1000:.1f}K"
                                    else:
                                        val_str = f"{display_val:,.2f}"
                                    st.metric(label=name, value=val_str, delta=delta, delta_color=delta_color)

                    # =================================================================
                    # RAILWAY-STYLE MINIMAL LAYOUT
                    # Single narrative - no redundancy between explanation and analysis
                    # =================================================================

                    # Show EITHER premium analysis OR basic explanation (not both)
                    has_premium_analysis = msg.get("premium_analysis_html") and PREMIUM_ANALYSIS_AVAILABLE

                    if has_premium_analysis:
                        # Premium analysis is richer - show it as the main content
                        analysis_html = msg["premium_analysis_html"]
                        st.markdown(f"""<div style='margin: 8px 0 16px 0;'>{analysis_html}</div>""", unsafe_allow_html=True)
                    elif msg.get("explanation"):
                        # Fallback to basic explanation if no premium analysis
                        explanation_text = msg['explanation']
                        st.markdown(f"""<div style='font-size: 0.95rem; line-height: 1.7; color: #1f2937; margin: 8px 0 16px 0;'>{explanation_text}</div>""", unsafe_allow_html=True)

                    # Coverage disclaimer - shown when we're displaying proxy data
                    if msg.get("coverage_disclaimer"):
                        disclaimer = msg["coverage_disclaimer"]
                        st.markdown(f"""<div style='background: #fef3c7; border-left: 3px solid #f59e0b; padding: 8px 12px; margin: 8px 0 16px 0; font-size: 0.85rem; color: #92400e; border-radius: 0 4px 4px 0;'>
                            <strong>Note:</strong> {disclaimer}
                        </div>""", unsafe_allow_html=True)

                    # Recession Dashboard (keep for recession queries - this IS the answer)
                    if msg.get("recession_scorecard") and RECESSION_SCORECARD_AVAILABLE:
                        scorecard = msg["recession_scorecard"]
                        scorecard_html = format_scorecard_for_display(scorecard)
                        st.markdown(scorecard_html, unsafe_allow_html=True)

                    # Prediction Markets Box (forward-looking market expectations)
                    if msg.get("polymarket_html"):
                        st.markdown(msg["polymarket_html"], unsafe_allow_html=True)

                    # Render charts from stored series_data
                    if msg.get("series_data"):
                        chart_type = msg.get("chart_type", "line")
                        combine = msg.get("combine", False)
                        chart_groups = msg.get("chart_groups")
                        raw_series_data = msg.get("raw_series_data", {})
                        series_data = msg["series_data"]

                        # Use chart_groups if available (for proper combining)
                        if chart_groups and len(chart_groups) > 0:
                            for group_idx, group in enumerate(chart_groups):
                                group_series_ids = group.get('series', [])
                                group_show_yoy = group.get('show_yoy', False)
                                group_normalize = group.get('normalize', False)
                                group_title = group.get('title', '')

                                # Get data for this group
                                group_data = []
                                for sid in group_series_ids:
                                    if sid in raw_series_data:
                                        entry = raw_series_data[sid]
                                        # Handle both old 2-tuple and new 4-tuple formats
                                        if isinstance(entry, tuple) and len(entry) == 4:
                                            group_data.append(entry)
                                        else:
                                            # Fall through to series_data fallback
                                            for s_id, d, v, i in series_data:
                                                if s_id == sid:
                                                    group_data.append((s_id, d, v, i))
                                                    break
                                    else:
                                        # Fallback to series_data
                                        for s_id, d, v, i in series_data:
                                            if s_id == sid:
                                                group_data.append((s_id, d, v, i))
                                                break

                                if not group_data:
                                    continue

                                # Apply YoY transformation if requested
                                if group_show_yoy:
                                    transformed = []
                                    for sid, dates_g, values_g, info_g in group_data:
                                        new_dates, new_values = calculate_yoy(dates_g, values_g)
                                        new_info = dict(info_g)
                                        new_info['is_yoy'] = True
                                        new_info['unit'] = 'YoY % Change'
                                        transformed.append((sid, new_dates, new_values, new_info))
                                    group_data = transformed

                                # Apply normalize transformation
                                if group_normalize and len(group_data) > 0:
                                    start_dates = [dates_g[0] for sid, dates_g, values_g, info_g in group_data if dates_g]
                                    common_start = max(start_dates) if start_dates else None
                                    norm_data = []
                                    for sid, dates_g, values_g, info_g in group_data:
                                        if values_g and len(values_g) > 0 and dates_g:
                                            start_idx = 0
                                            for i, d in enumerate(dates_g):
                                                if d >= common_start:
                                                    start_idx = i
                                                    break
                                            trimmed_dates = dates_g[start_idx:]
                                            trimmed_values = values_g[start_idx:]
                                            if trimmed_values and trimmed_values[0] != 0:
                                                base_value = trimmed_values[0]
                                                indexed_values = [(v / base_value) * 100 for v in trimmed_values]
                                                new_info = dict(info_g)
                                                new_info['unit'] = 'Index (Start = 100)'
                                                norm_data.append((sid, trimmed_dates, indexed_values, new_info))
                                    group_data = norm_data if norm_data else group_data

                                # Vertical layout: title, bullets, chart, source
                                st.markdown("---")

                                # Title
                                if group_title:
                                    st.markdown(f"### {group_title}")
                                else:
                                    title_parts = [info.get('name', sid) for sid, _, _, info in group_data]
                                    st.markdown(f"### {' vs '.join(title_parts)}")

                                # Bullets for each series in group
                                msg_query = msg.get('content', '')
                                all_bullets = []
                                for sid, d, v, i in group_data:
                                    analysis = generate_goldman_style_analysis(sid, d, v, i, user_query=msg_query)
                                    bullets = analysis.get('bullets', [])
                                    all_bullets.extend(bullets[:2])
                                for bullet in all_bullets[:3]:
                                    if bullet and bullet.strip():
                                        st.markdown(f"- {bullet}")

                                # Chart (full width)
                                fig = create_chart(group_data, combine=len(group_data) > 1, chart_type=chart_type)
                                st.plotly_chart(fig, width='stretch', key=f"hist_chart_{msg_idx}_group_{group_idx}")

                        elif combine and len(series_data) > 1:
                            # Vertical layout: title, bullets, chart
                            st.markdown("---")

                            # Title
                            title_parts = [info.get('name', sid) for sid, _, _, info in series_data]
                            st.markdown(f"### {' vs '.join(title_parts)}")

                            # Bullets
                            msg_query = msg.get('content', '')
                            all_bullets = []
                            for sid, d, v, i in series_data:
                                analysis = generate_goldman_style_analysis(sid, d, v, i, user_query=msg_query)
                                bullets = analysis.get('bullets', [])
                                all_bullets.extend(bullets[:2])
                            for bullet in all_bullets[:3]:
                                if bullet and bullet.strip():
                                    st.markdown(f"- {bullet}")

                            # Chart (full width)
                            fig = create_chart(series_data, combine=True, chart_type=chart_type)
                            st.plotly_chart(fig, width='stretch', key=f"hist_chart_{msg_idx}_combined")

                        else:
                            # Individual charts - vertical layout
                            msg_query = msg.get('content', '')
                            for series_idx, (series_id, dates, values, info) in enumerate(series_data):
                                if not values:
                                    continue

                                analysis = generate_goldman_style_analysis(series_id, dates, values, info, user_query=msg_query)
                                chart_title = analysis.get('title', info.get('name', series_id))
                                bullets = analysis.get('bullets', [])

                                st.markdown("---")

                                # Title
                                st.markdown(f"### {chart_title}")

                                # Bullets
                                if bullets:
                                    for bullet in bullets[:3]:
                                        if bullet and bullet.strip():
                                            st.markdown(f"- {bullet}")

                                # Chart (full width)
                                fig = create_chart([(series_id, dates, values, info)], combine=False, chart_type=chart_type)
                                st.plotly_chart(fig, width='stretch', key=f"hist_chart_{msg_idx}_{series_id}")

        # Close chat container
        st.markdown('</div>', unsafe_allow_html=True)

        # Follow-up section at bottom (Railway-style "Continue exploring")
        if not query and st.session_state.messages:
            # Generate context-specific follow-ups based on what's currently displayed
            last_series = st.session_state.last_series if st.session_state.last_series else []
            last_series_str = str(last_series).upper()
            last_query = st.session_state.last_query or ""

            # Default follow-ups
            followup1 = ("What's driving these trends?", f"What's driving {last_query}?")
            followup2 = ("How does this compare to pre-pandemic levels?", f"compare {last_query} to pre-pandemic")

            # Context-specific follow-ups based on WHAT DATA IS SHOWN
            if any(s in last_series_str for s in ['UNRATE', 'PAYEMS', 'LNS', 'EMPL']):
                followup1 = ("What sectors are driving job growth?", "job growth by sector")
                followup2 = ("How does this compare to pre-pandemic employment?", "employment vs pre-covid")
            elif any(s in last_series_str for s in ['CPI', 'PCE', 'INFLATION']):
                followup1 = ("What's driving the difference between core and headline inflation?", "core vs headline inflation breakdown")
                followup2 = ("How do current inflation levels compare to pre-pandemic trends?", "inflation vs pre-pandemic")
            elif any(s in last_series_str for s in ['GDP', 'A191']):
                followup1 = ("What components are contributing to GDP growth?", "GDP by component")
                followup2 = ("How does growth compare to other major economies?", "US vs Eurozone GDP growth")
            elif any(s in last_series_str for s in ['MORTGAGE', 'HOUST', 'PERMIT', 'CSUSHPINSA']):
                followup1 = ("How has housing affordability changed?", "housing affordability over time")
                followup2 = ("How do home prices compare to income growth?", "home prices vs income")

            # "Continue exploring" section - Railway style
            st.markdown("""<hr style='border: none; border-top: 1px solid #e5e7eb; margin: 24px 0 16px 0;'>""", unsafe_allow_html=True)
            st.markdown("""<div style='color: #6b7280; font-size: 0.85rem; margin-bottom: 12px;'>Continue exploring:</div>""", unsafe_allow_html=True)

            # Clickable suggestion cards
            col1, col2 = st.columns(2)
            with col1:
                if st.button(followup1[0], key="followup_1", use_container_width=True):
                    st.session_state.pending_query = followup1[1]
                    st.rerun()
            with col2:
                if st.button(followup2[0], key="followup_2", use_container_width=True):
                    st.session_state.pending_query = followup2[1]
                    st.rerun()

            # Follow-up input
            chat_query = st.text_input(
                "Follow-up",
                placeholder="Ask a follow-up question...",
                label_visibility="collapsed",
                key="chat_followup_input"
            )
            if chat_query:
                st.session_state.pending_query = chat_query
                st.rerun()

    if query:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": query})

        # Only show chat bubble in chat mode - use styled bubble
        if st.session_state.chat_mode:
            st.markdown(f'<div class="chat-clearfix"><div class="chat-user-query">{query}</div></div>', unsafe_allow_html=True)

        # Use a simple status placeholder (st.status has rendering bugs)
        class SimpleStatus:
            def __init__(self, label):
                self.placeholder = st.empty()
                self.placeholder.markdown(f"<div style='color: #6b7280; font-size: 0.9rem; padding: 8px 0;'>⏳ {label}</div>", unsafe_allow_html=True)
            def update(self, label=None, state=None, expanded=None):
                if state == "complete":
                    self.placeholder.empty()
                elif label:
                    self.placeholder.markdown(f"<div style='color: #6b7280; font-size: 0.9rem; padding: 8px 0;'>⏳ {label}</div>", unsafe_allow_html=True)
        status_container = SimpleStatus("Analyzing your question...")

        # Build context from previous query for follow-up detection
        previous_context = None
        if st.session_state.last_query and st.session_state.last_series:
            previous_context = {
                'query': st.session_state.last_query,
                'series': st.session_state.last_series,
                'series_names': st.session_state.last_series_names
            }

        # TEMPORAL INTENT DETECTION - Detect COMPARE vs FILTER vs CURRENT
        # This MUST happen before data selection to avoid filtering away comparison data
        temporal_intent = None
        if TEMPORAL_INTENT_AVAILABLE:
            temporal_intent = detect_temporal_intent(query)
            # Store in session for later use
            st.session_state['current_temporal_intent'] = temporal_intent

        # =================================================================
        # QUERY UNDERSTANDING - "Thinking First" Layer
        # =================================================================
        # This is the NEW first step: deeply analyze query intent BEFORE
        # any routing decisions. Uses Gemini to understand:
        # - What is the user really asking?
        # - What entities are mentioned (demographics, regions, sectors)?
        # - What type of query is this (factual, analytical, comparison)?
        # - What data sources should we use?
        # - What pitfalls should we avoid?
        #
        # The understanding then guides all downstream routing decisions.
        # =================================================================
        query_understanding = None
        routing_recommendation = None
        if QUERY_UNDERSTANDING_AVAILABLE:
            status_container.update(label="Understanding your question...")
            query_understanding = understand_query(query, verbose=False)
            routing_recommendation = get_routing_recommendation(query_understanding)

            # Store understanding in session for debugging/logging
            st.session_state['query_understanding'] = query_understanding
            st.session_state['routing_recommendation'] = routing_recommendation

            # Log key insights from understanding
            if query_understanding:
                intent = query_understanding.get('intent', {})
                entities = query_understanding.get('entities', {})

                # Use understanding to enhance subsequent routing
                # (e.g., if demographic-specific, we'll filter results later)

        # Check for comparison queries FIRST
        # Two types of comparisons:
        # 1. DOMESTIC comparisons (Black unemployment vs overall, inflation vs wages)
        #    - All data from FRED, no DBnomics needed
        # 2. INTERNATIONAL comparisons (US vs Eurozone, etc.)
        #    - Data from FRED + DBnomics
        # ENHANCED by query understanding - use its is_comparison flag
        comparison_route = None

        # Use query understanding to guide comparison detection
        understanding_says_comparison = (
            routing_recommendation and routing_recommendation.get('use_comparison_router', False)
        )
        understanding_says_international = (
            routing_recommendation and routing_recommendation.get('use_international_data', False)
        )

        # Check for comparisons - domestic comparisons don't need DBnomics
        if QUERY_ROUTER_AVAILABLE:
            # Always run the smart router to detect both domestic and international comparisons
            comparison_route = smart_route_query(query)

            if comparison_route.get('is_comparison') or understanding_says_comparison:
                # Build a combined plan from the routing result
                fred_series = comparison_route.get('series_to_fetch', {}).get('fred', [])
                dbnomics_series = comparison_route.get('series_to_fetch', {}).get('dbnomics', [])

                # For domestic comparisons, we only have FRED series
                is_domestic = comparison_route.get('is_domestic_comparison', False)

                # Only proceed if we have series to fetch
                # For international comparisons, we need DBnomics available
                if is_domestic or (dbnomics_series and DBNOMICS_AVAILABLE) or (fred_series and not dbnomics_series):
                    precomputed_plan = {
                        'series': fred_series,  # FRED series fetched normally
                        'dbnomics_series': dbnomics_series,  # DBnomics series fetched separately
                        'explanation': comparison_route.get('explanation', ''),
                        'source': 'comparison',
                        'is_comparison': True,
                        'is_domestic_comparison': is_domestic,
                        # Pass through combine_chart and show_yoy from domestic comparisons
                        'combine_chart': comparison_route.get('combine_chart', True),
                        'show_yoy': comparison_route.get('show_yoy', False),
                        'units_compatible': comparison_route.get('units_compatible', True),
                    }
                else:
                    comparison_route = None  # International comparison but DBnomics not available
            else:
                comparison_route = None  # Not a comparison, continue normal flow

        # First check DIRECT MAPPINGS (most precise - curated query->series)
        # These are exact matches for specific queries like "rent inflation", "black unemployment"
        # Direct mappings take precedence over fuzzy precomputed plan matching
        from core.economist_reasoning import check_direct_mapping
        direct_series = check_direct_mapping(query)
        direct_mapping_plan = None
        if direct_series and not comparison_route:
            # Build a plan from the direct mapping
            direct_mapping_plan = {
                'series': direct_series[:4],
                'explanation': '',
                'used_direct_mapping': True,
                'combine_chart': len(direct_series) > 1 and len(direct_series) <= 3,
            }
            # Try to get rich explanation from precomputed plans
            query_lower = query.lower().strip().rstrip('?')
            for plan_key in [query_lower,
                           query_lower.replace('is ', '').replace('are ', '').replace('what is the ', '').replace('what are the ', '').strip()]:
                if plan_key in QUERY_PLANS:
                    direct_mapping_plan['explanation'] = QUERY_PLANS[plan_key].get('explanation', '')
                    break

        # Check if this is a "how is X doing?" health check query
        # These get routed to curated multi-dimensional indicator sets
        health_check_plan = None
        if HEALTH_CHECK_AVAILABLE and not comparison_route and not direct_mapping_plan:
            health_route = route_health_check_query(query)
            if health_route and health_route.get('is_health_check'):
                # Build a plan from the health check routing
                health_check_plan = {
                    'series': health_route['series'],
                    'show_yoy_series': [
                        sid for sid, show_yoy in zip(health_route['series'], health_route['show_yoy'])
                        if show_yoy
                    ],
                    'explanation': health_route['explanation'],
                    'entity_name': health_route['entity_name'],
                    'source': 'health_check',
                }

        # Then check pre-computed query plans (fuzzy matching for typos)
        # Only if no direct mapping or health check was found
        precomputed_plan = None
        if not comparison_route and not direct_mapping_plan and not health_check_plan:
            precomputed_plan = find_query_plan(query)

            # Check stock market queries if no precomputed plan found
            if not precomputed_plan and STOCKS_AVAILABLE:
                market_plan = find_market_plan(query)
                if market_plan:
                    precomputed_plan = market_plan
                    # Mark source for debugging
                    precomputed_plan['source'] = 'stocks'

            # Check international queries (DBnomics: IMF, Eurostat, ECB, etc.)
            if not precomputed_plan and DBNOMICS_AVAILABLE:
                intl_plan = find_international_plan(query)
                if intl_plan:
                    precomputed_plan = intl_plan
                    precomputed_plan['source'] = 'dbnomics'

        # Check if this looks like a follow-up command (transformation, time range, etc.)
        local_parsed = parse_followup_command(query, st.session_state.last_series) if previous_context else None

        # Check if this is a "how is X doing?" style query that needs multi-dimensional answers
        holistic = is_holistic_query(query)

        # ROUTING LOGIC:
        # 1. Has pre-computed plan -> use it as base
        #    - For holistic queries: augment with hybrid (RAG + FRED search)
        #    - For specific queries: use as-is (instant)
        # 2. No pre-computed plan -> Hybrid (RAG + FRED search)
        #
        # All paths use the same high-quality pipeline:
        # - Merge series from multiple sources
        # - Dedupe
        # - Validate relevance

        if direct_mapping_plan and not local_parsed:
            # Found a direct mapping - use it (highest priority, most precise)
            interpretation = direct_mapping_plan.copy()
            interpretation['used_precomputed'] = False
            interpretation['used_direct_mapping'] = True
            # Include query understanding for downstream validation/enhancement
            interpretation['query_understanding'] = query_understanding
            interpretation['routing_recommendation'] = routing_recommendation

        elif health_check_plan and not local_parsed:
            # Found a health check route - use curated multi-dimensional indicators
            # This handles "how is X doing?" queries with the RIGHT data
            interpretation = health_check_plan.copy()
            interpretation['used_precomputed'] = False
            interpretation['used_health_check'] = True
            interpretation['query_understanding'] = query_understanding
            interpretation['routing_recommendation'] = routing_recommendation

            # Check coverage and add disclaimer if showing proxy data
            if COVERAGE_CHECK_AVAILABLE:
                coverage_result = check_query_coverage(query, search_fred=False)
                if coverage_result.get('message'):
                    interpretation['coverage_disclaimer'] = coverage_result['message']
                    interpretation['coverage_level'] = coverage_result['coverage']

        elif precomputed_plan and not local_parsed:
            # Found a pre-computed plan - use it as the base
            # ENHANCED: Use query understanding to filter/validate series
            base_series = precomputed_plan.get('series', [])
            hybrid_sources = {'precomputed': base_series, 'rag': [], 'fred': []}

            # Use query understanding to filter series that don't match query intent
            # This prevents wrong demographic data (e.g., women's data for Black workers)
            if query_understanding:
                entities = query_understanding.get('entities', {})
                detected_demographics = entities.get('demographics', [])
                pitfalls = query_understanding.get('pitfalls', [])

                # If query is demographic-specific, filter out wrong demographics
                if detected_demographics:
                    # Build list of series to exclude based on pitfalls
                    # Pitfalls often say "Don't use UNRATE for Black workers" etc.
                    filtered_series = []
                    for sid in base_series:
                        # Check if this series should be excluded
                        exclude = False
                        for pitfall in pitfalls:
                            if sid in pitfall:
                                exclude = True
                                break
                        if not exclude:
                            filtered_series.append(sid)

                    # Only use filtered list if we still have series
                    if filtered_series:
                        base_series = filtered_series
                        hybrid_sources['precomputed'] = base_series

            # For holistic queries, augment with hybrid search (RAG + FRED)
            # BUT: If precomputed plan has 3+ series, it's comprehensive enough - don't augment
            # This prevents irrelevant FRED search results from polluting curated plans
            plan_is_comprehensive = len(base_series) >= 3
            should_augment = holistic and RAG_AVAILABLE and not plan_is_comprehensive

            if should_augment:
                status_container.update(label="Finding relevant indicators...")
                # Run hybrid search to find complementary series
                hybrid_result = hybrid_query_plan(query, verbose=False)
                hybrid_series = hybrid_result.get('series', [])
                hybrid_sources['rag'] = hybrid_result.get('hybrid_sources', {}).get('rag', [])
                hybrid_sources['fred'] = hybrid_result.get('hybrid_sources', {}).get('fred', [])

                # Merge: precomputed first, then hybrid additions (no duplicates)
                all_series = base_series.copy()
                for sid in hybrid_series:
                    if sid not in all_series:
                        all_series.append(sid)

                # Limit to 4 series
                all_series = all_series[:4]
            else:
                all_series = base_series

            # Determine combine_chart: use plan value, or check unit compatibility as fallback
            plan_combine = precomputed_plan.get('combine_chart')
            if plan_combine is None:
                # Plan doesn't specify - use smart defaults
                if precomputed_plan.get('is_comparison'):
                    plan_combine = True
                else:
                    # Check if series have compatible units (all rates, all %, etc.)
                    units_ok, _ = can_combine_series(all_series)
                    plan_combine = units_ok

            interpretation = {
                'series': all_series,
                'explanation': precomputed_plan.get('explanation', f'Showing data for: {query}'),
                'show_yoy': precomputed_plan.get('show_yoy', False),
                'show_yoy_series': precomputed_plan.get('show_yoy_series', []),
                'combine_chart': plan_combine,
                'show_mom': False,
                'show_avg_annual': False,
                'is_followup': False,
                'add_to_previous': False,
                'keep_previous_series': False,
                'search_terms': [],  # Already searched via hybrid
                'used_precomputed': True,
                'used_hybrid': holistic and RAG_AVAILABLE,
                'hybrid_sources': hybrid_sources,
                'show_payroll_changes': precomputed_plan.get('show_payroll_changes', False),
                'chart_groups': precomputed_plan.get('chart_groups', None),
                'derived': precomputed_plan.get('derived', None),  # Formula for calculated series
                # Comparison query support - pass through DBnomics series
                'source': precomputed_plan.get('source', 'fred'),
                'is_comparison': precomputed_plan.get('is_comparison', False),
                'dbnomics_series': precomputed_plan.get('dbnomics_series', []),
                # ENHANCED: Include query understanding for downstream use
                'query_understanding': query_understanding,
                'routing_recommendation': routing_recommendation,
            }
        elif local_parsed:
            # Try local parser for common follow-up commands (no API call needed)
            # For follow-ups, inherit combine setting or check unit compatibility
            local_combine = local_parsed.get('combine_chart')
            if local_combine is None:
                local_series = local_parsed.get('series', [])
                if local_series:
                    units_ok, _ = can_combine_series(local_series)
                    local_combine = units_ok
                else:
                    local_combine = False

            interpretation = {
                'series': local_parsed.get('series', []),
                'explanation': local_parsed.get('explanation', ''),
                'show_yoy': local_parsed.get('show_yoy', False),
                'show_mom': local_parsed.get('show_mom', False),
                'show_avg_annual': local_parsed.get('show_avg_annual', False),
                'combine_chart': local_combine,
                'is_followup': local_parsed.get('is_followup', True),
                'add_to_previous': local_parsed.get('add_to_previous', False),
                'keep_previous_series': local_parsed.get('keep_previous_series', False),
                'search_terms': [],
                'used_precomputed': False,
                'used_local_parser': True,
                'years_override': local_parsed.get('years_override'),
                'chart_type': local_parsed.get('chart_type'),
                'normalize': local_parsed.get('normalize', False),
                'pct_change_from_start': local_parsed.get('pct_change_from_start', False),
                'filter_end_date': local_parsed.get('filter_end_date'),
                'filter_start_date': local_parsed.get('filter_start_date'),
            }
        else:
            # PRIMARY PATH: Use economist reasoning (AI thinks about what's needed)
            # This asks AI to reason like an economist, then searches for indicators
            # NOW ENHANCED with query understanding from the "thinking first" layer
            if REASONING_AVAILABLE:
                status_container.update(label="Analyzing your question...")
                interpretation = reasoning_query_plan(query, verbose=False)

                # If reasoning found series, use them
                if interpretation.get('series'):
                    interpretation['used_reasoning'] = True
                    interpretation['used_precomputed'] = False

                    # Enhance with query understanding metadata if available
                    if query_understanding:
                        interpretation['query_understanding'] = query_understanding
                        # Add pitfalls as warnings for downstream validation
                        pitfalls = query_understanding.get('pitfalls', [])
                        if pitfalls:
                            interpretation['understanding_pitfalls'] = pitfalls
                else:
                    # Reasoning failed - fall back to hybrid search
                    interpretation = None

            # FALLBACK: Hybrid RAG + FRED search
            if not REASONING_AVAILABLE or not interpretation or not interpretation.get('series'):
                if RAG_AVAILABLE:
                    status_container.update(label="Searching economic data...")
                    interpretation = hybrid_query_plan(query, verbose=False)
                    interpretation['used_rag'] = True
                    interpretation['used_hybrid'] = True
                elif ENSEMBLE_AVAILABLE:
                    status_container.update(label="Analyzing with AI...")
                    interpretation = call_ensemble_for_app(
                        query, ECONOMIST_PROMPT_BASE,
                        previous_context=previous_context,
                        use_few_shot=True, verbose=False
                    )
                    interpretation['used_ensemble'] = True
                else:
                    status_container.update(label="Analyzing...")
                    interpretation = call_claude(query, previous_context)
                interpretation['used_precomputed'] = False

        # QA Validation Layer: Check query-series alignment
        series_for_validation = interpretation.get('series', [])
        validation_result = validate_query_series_alignment(query, series_for_validation)

        # DEMOGRAPHIC FILTERING: Use query understanding to filter irrelevant series
        # This prevents returning women's data for Black workers queries, etc.
        if routing_recommendation and routing_recommendation.get('require_demographic_filter'):
            demographic_filter = routing_recommendation.get('demographic_filter', [])
            pitfalls = routing_recommendation.get('pitfalls', [])

            # Log the demographic requirements
            if demographic_filter:
                print(f"[QueryUnderstanding] Demographic filter: {demographic_filter}")
                print(f"[QueryUnderstanding] Pitfalls: {pitfalls[:2]}")

            # Store understanding metadata in interpretation for later use
            interpretation['query_understanding'] = query_understanding
            interpretation['routing_recommendation'] = routing_recommendation

        # Log query resolution for analysis
        source = 'precomputed' if interpretation.get('used_precomputed') else (
            'local_followup' if interpretation.get('used_local_parser') else (
                'reasoning' if interpretation.get('used_reasoning') else (
                    'rag' if interpretation.get('used_rag') else (
                        'ensemble' if interpretation.get('used_ensemble') else 'claude'
                    )
                )
            )
        )
        # Get reasoning indicators if available
        reasoning_info = interpretation.get('reasoning', {})
        reasoning_indicators = [i.get('concept') for i in reasoning_info.get('indicators', [])] if reasoning_info else None

        log_query_resolution(
            query=query,
            source=source,
            series=series_for_validation,
            validation=validation_result,
            explanation=interpretation.get('explanation', ''),
            reasoning_indicators=reasoning_indicators,
            is_comparison=interpretation.get('is_comparison', False),
            sources=interpretation.get('hybrid_sources', {}),
        )

        ai_explanation = interpretation.get('explanation', '')
        series_to_fetch = list(interpretation.get('series', []))  # Copy the list

        # Handle case where hybrid search found no relevant data
        if interpretation.get('no_data_available'):
            st.warning("No data available for this specific query")
            st.info(ai_explanation)  # Shows guidance about what to try instead
            log_query(query, [], "no_relevant_data")
            st.stop()

        combine = interpretation.get('combine_chart', False)

        # Handle show_yoy - can be boolean OR array like [False, False, True]
        show_yoy_config = interpretation.get('show_yoy', False)
        if isinstance(show_yoy_config, list):
            # Array-style: map True values to their corresponding series IDs
            show_yoy = False  # Don't apply globally
            show_yoy_series = [series_to_fetch[i] for i, apply_yoy in enumerate(show_yoy_config)
                              if apply_yoy and i < len(series_to_fetch)]
        else:
            show_yoy = show_yoy_config
            show_yoy_series = interpretation.get('show_yoy_series', [])  # Specific series to apply YoY to
        show_mom = interpretation.get('show_mom', False)
        show_avg_annual = interpretation.get('show_avg_annual', False)
        show_payroll_changes = interpretation.get('show_payroll_changes', False)
        is_followup = interpretation.get('is_followup', False)
        add_to_previous = interpretation.get('add_to_previous', False)
        keep_previous_series = interpretation.get('keep_previous_series', False)

        # Handle years override from follow-up commands (e.g., "show last 5 years")
        if 'years_override' in interpretation and interpretation['years_override'] is not None:
            years = interpretation['years_override']
        elif 'years_override' in interpretation and interpretation['years_override'] is None:
            years = None  # Show all data
        else:
            # No explicit override - use smart defaults based on query type
            # Historical queries get more years; most queries use focused 8-year view
            years = get_smart_date_range(query, DEFAULT_YEARS)

        # Handle chart type from follow-up commands (e.g., "bar chart")
        chart_type = interpretation.get('chart_type', 'line')

        # Handle normalize from follow-up commands (e.g., "normalize", "index to 100")
        normalize = interpretation.get('normalize', False)

        # Handle percent change from start (cumulative change)
        pct_change_from_start = interpretation.get('pct_change_from_start', False)

        # Handle chart groups (multiple charts with different series/transformations)
        chart_groups = interpretation.get('chart_groups', None)

        # Handle date filtering - INTENT-AWARE
        # For COMPARE intents: Keep ALL data (don't filter)
        # For FILTER intents: Apply date filter from intent
        # For CURRENT intents: No filter
        is_temporal_comparison = False

        if temporal_intent and TEMPORAL_INTENT_AVAILABLE:
            if temporal_intent.is_comparison:
                # COMPARISON QUERY: Keep all data for comparison
                # DO NOT apply filter_end_date - we need both periods!
                is_temporal_comparison = True
                interpretation['is_temporal_comparison'] = True
                interpretation['temporal_intent'] = temporal_intent
                # Clear any filter dates that might be set
                interpretation.pop('filter_end_date', None)
                interpretation.pop('filter_start_date', None)
            elif temporal_intent.intent_type == "filter":
                # FILTER QUERY: Apply date filter
                if temporal_intent.filter_start:
                    interpretation['filter_start_date'] = temporal_intent.filter_start
                if temporal_intent.filter_end:
                    interpretation['filter_end_date'] = temporal_intent.filter_end
                interpretation['temporal_focus'] = temporal_intent.explanation
        else:
            # Fallback to legacy temporal filter for non-intent queries
            temporal_filter = extract_temporal_filter(query)
            if temporal_filter and not interpretation.get('filter_end_date') and not interpretation.get('filter_start_date'):
                interpretation['filter_end_date'] = temporal_filter.get('filter_end_date')
                interpretation['filter_start_date'] = temporal_filter.get('filter_start_date')
                interpretation['temporal_focus'] = temporal_filter.get('temporal_focus')
                if temporal_filter.get('years_override'):
                    years = temporal_filter['years_override']
                if temporal_filter.get('explanation'):
                    ai_explanation = f"{ai_explanation} {temporal_filter['explanation']}" if ai_explanation else temporal_filter['explanation']

        filter_end_date = interpretation.get('filter_end_date') if not is_temporal_comparison else None
        filter_start_date = interpretation.get('filter_start_date') if not is_temporal_comparison else None

        # Handle follow-up that keeps/adds to previous series
        if is_followup and (keep_previous_series or add_to_previous):
            if keep_previous_series and not series_to_fetch:
                # Just apply transformation to previous series
                series_to_fetch = st.session_state.last_series.copy()
            elif add_to_previous:
                # Add new series to previous ones
                previous_series = st.session_state.last_series.copy()
                for sid in previous_series:
                    if sid not in series_to_fetch:
                        series_to_fetch.insert(0, sid)

        # If Claude provided search_terms, ALWAYS search FRED (even if we have some series)
        search_terms = interpretation.get('search_terms', [])
        if search_terms:
            status_container.update(label="Searching for data...")
            for term in search_terms[:3]:
                results = search_series(term, limit=5)  # Get more, then filter
                for r in results:
                    # Relevance check: series title should relate to search term
                    title = r.get('title', '').lower()
                    term_words = term.lower().split()
                    # At least one significant word from search term should appear in title
                    # (ignore common words like "the", "for", "and")
                    significant_words = [w for w in term_words if len(w) > 3]
                    is_relevant = any(word in title for word in significant_words) if significant_words else True

                    if is_relevant and r['id'] not in series_to_fetch and len(series_to_fetch) < 4:
                        series_to_fetch.append(r['id'])
                        # Add explanation if we found something via search
                        if not ai_explanation:
                            ai_explanation = f"Found relevant series for '{term}'"

        # Only use local fallback if Claude completely failed AND no search terms worked
        if not series_to_fetch:
            local_match = find_local_series(query)
            if local_match:
                series_to_fetch = local_match['series']
                combine = local_match.get('combine', False)
                ai_explanation = f"Showing common indicators for: {query}"

        # Last resort: direct FRED search with the raw query
        if not series_to_fetch:
            status_container.update(label="Searching for data...")
            results = search_series(query, limit=4)
            for r in results:
                series_to_fetch.append(r['id'])
            if series_to_fetch:
                ai_explanation = f"Search results for: {query}"

        if not series_to_fetch:
            st.warning("Could not find relevant economic data for this query")

            # Provide context-specific suggestions
            suggestions = []
            query_lower = query.lower()

            # Check for common query issues
            if len(query.split()) < 2:
                suggestions.append("• Try adding more context: 'unemployment rate' instead of 'unemployment'")

            # Industry-specific queries
            if any(word in query_lower for word in ['restaurant', 'hotel', 'travel', 'tourism']):
                suggestions.append("• Try: 'leisure hospitality employment' or 'food services jobs'")
            elif any(word in query_lower for word in ['tech', 'software', 'silicon']):
                suggestions.append("• Try: 'information sector employment' or 'computer systems wages'")
            elif any(word in query_lower for word in ['bank', 'finance', 'wall street']):
                suggestions.append("• Try: 'financial sector employment' or 'bank lending'")

            # Demographic queries
            if any(word in query_lower for word in ['black', 'hispanic', 'asian', 'women', 'men']):
                suggestions.append("• For demographics, try: 'Black unemployment rate' or 'women labor force participation'")

            # General suggestions
            suggestions.append("• Popular queries: 'unemployment', 'inflation', 'GDP growth', 'housing market', 'job growth'")

            st.info("**Suggestions:**\n" + "\n".join(suggestions))
            log_query(query, [], "no_results")
            st.stop()

        # Geographic scope detection - search FRED for state-specific series
        geo_scope = detect_geographic_scope(query)
        if geo_scope['type'] == 'state':
            state_name = geo_scope['name']
            status_container.update(label=f"Searching for {state_name.title()} data...")
            # Search FRED for state-specific series
            state_search_terms = [
                f"{state_name} unemployment",
                f"{state_name} employment",
                f"{state_name} GDP",
            ]
            state_series = []
            for term in state_search_terms:
                try:
                    results = search_series(term, limit=2, require_recent=True)
                    for r in results:
                        sid = r['id']
                        title = r.get('title', '').lower()
                        # Verify it's actually state-specific (contains state name)
                        if state_name in title and sid not in state_series:
                            state_series.append(sid)
                except:
                    pass

            if state_series:
                # Found state-specific data - use it instead
                series_to_fetch = state_series[:4]
                st.success(f"📍 Found {state_name.title()}-specific data from FRED!")
                interpretation['geographic_override'] = True
                interpretation['state'] = state_name
            else:
                # No state data found - fall back to national with warning
                st.info(f"📍 No {state_name.title()}-specific series found. Showing national indicators as context.")

        # Validate series relevance - filter out irrelevant/overly broad series
        # ALWAYS validate, including pre-computed plans, to catch:
        # - Stale plans that no longer match the query
        # - Fuzzy-matched plans that don't fit the actual query
        # - Demographic/industry mismatches from plan file errors
        needs_validation = (
            ENSEMBLE_AVAILABLE and
            len(series_to_fetch) > 1
        )
        if needs_validation:
            status_container.update(label="Validating data relevance...")
            # Get series info for validation
            series_info_list = []
            for sid in series_to_fetch[:6]:  # Check up to 6 series
                try:
                    info = get_series_info(sid)
                    series_info_list.append({
                        'id': sid,
                        'title': info.get('title', sid)
                    })
                except:
                    series_info_list.append({'id': sid, 'title': sid})

            validation = validate_series_relevance(query, series_info_list, verbose=False)
            valid_ids = validation.get('valid_series', series_to_fetch)

            # Only use validation if it kept at least one series
            if valid_ids:
                # Preserve order, only keep validated series
                series_to_fetch = [s for s in series_to_fetch if s in valid_ids]
                interpretation['validation_result'] = validation

        # Log the query for analytics
        source = "precomputed" if interpretation.get('used_precomputed') else "claude"
        log_query(query, series_to_fetch[:4], source)

        # Fetch data
        series_data = []
        raw_series_data = {}  # Store raw data for chart_groups (4-tuple: sid, dates, values, info)
        derived_raw_data = {}  # Store raw data for derived calculations (2-tuple: dates, values)
        series_names_fetched = []
        derived_config = interpretation.get('derived', None)  # Formula for calculated series
        data_source = interpretation.get('source', 'fred')
        is_comparison = interpretation.get('is_comparison', False)

        # For comparison queries, also fetch DBnomics series
        dbnomics_series_to_fetch = interpretation.get('dbnomics_series', []) if is_comparison else []

        status_msg = "Fetching data..." if is_comparison else (
            "Fetching data from DBnomics..." if data_source == 'dbnomics' else "Fetching data..."
        )
        status_container.update(label=status_msg)

        # Combine all series to fetch (FRED + DBnomics for comparisons)
        all_series_to_fetch = []
        series_source_map = {}  # Track which source each series comes from

        for sid in series_to_fetch[:4]:
            all_series_to_fetch.append(sid)
            series_source_map[sid] = 'dbnomics' if data_source == 'dbnomics' else 'fred'

        for sid in dbnomics_series_to_fetch[:2]:  # Limit DBnomics to 2 for comparisons
            if sid not in all_series_to_fetch:
                all_series_to_fetch.append(sid)
                series_source_map[sid] = 'dbnomics'

        # Fetch all series data in parallel using ThreadPoolExecutor
        # This significantly speeds up queries that return multiple series
        fetch_results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all fetch tasks
            future_to_series = {
                executor.submit(fetch_single_series, series_id, years): series_id
                for series_id in all_series_to_fetch[:4]
            }

            # Collect results as they complete
            for future in as_completed(future_to_series):
                try:
                    result = future.result()
                    fetch_results.append(result)
                except Exception as e:
                    series_id = future_to_series[future]
                    # Log error but continue with other series
                    fetch_results.append({
                        'series_id': series_id,
                        'dates': [],
                        'values': [],
                        'info': {},
                        'success': False,
                        'error': str(e)
                    })

        # Track failed series for better user messaging
        failed_series = []
        for result in fetch_results:
            if not result['success']:
                failed_series.append({
                    'series_id': result['series_id'],
                    'error': result.get('error', 'Unknown error')
                })

        # Report failed series to user if some failed but others succeeded
        if failed_series and len(failed_series) < len(fetch_results):
            failed_ids = [f['series_id'] for f in failed_series]
            # Check if errors are due to rate limiting
            rate_limit_errors = [f for f in failed_series if 'rate limit' in f['error'].lower()]
            if rate_limit_errors:
                st.warning(f"FRED API rate limit reached. Showing partial results. Please wait a moment before making another query.")
            else:
                # Show which series failed (but only if it's a small number)
                if len(failed_series) <= 2:
                    st.warning(f"Could not fetch: {', '.join(failed_ids)}. These series may be discontinued or temporarily unavailable. Showing other requested data.")

        # Process fetched results sequentially (transformations depend on series-specific logic)
        for result in fetch_results:
            if not result['success']:
                continue

            series_id = result['series_id']
            dates = result['dates']
            values = result['values']
            info = result['info']

            if dates and values:
                # Recency check: silently skip series if latest observation is more than 1 year old
                try:
                    latest_date = datetime.strptime(dates[-1], '%Y-%m-%d')
                    days_stale = (datetime.now() - latest_date).days
                    if days_stale > 365:
                        continue  # Skip stale data silently
                except (ValueError, IndexError):
                    pass  # If we can't parse the date, proceed anyway

                # Apply date filter if specified (e.g., pre-covid filter, specific year)
                if filter_end_date or filter_start_date:
                    filtered_dates, filtered_values = [], []
                    for d, v in zip(dates, values):
                        if filter_start_date and d < filter_start_date:
                            continue
                        if filter_end_date and d > filter_end_date:
                            continue
                        filtered_dates.append(d)
                        filtered_values.append(v)
                    dates, values = filtered_dates, filtered_values
                    if not dates:
                        continue  # Skip series if no data in range

                db_info = SERIES_DB.get(series_id, {})
                series_name = info.get('name', info.get('title', series_id))
                series_names_fetched.append(series_name)

                # Store raw data for chart_groups (4-tuple) and derived calculations (2-tuple)
                raw_series_data[series_id] = (series_id, list(dates), list(values), dict(info))
                derived_raw_data[series_id] = (dates, values)

                # Apply transformations based on user request or series config
                if show_payroll_changes and series_id == 'PAYEMS' and len(dates) > 1:
                    # Special handling for payrolls: show monthly job changes (not percent)
                    change_dates = dates[1:]  # Skip first date
                    change_values = [values[i] - values[i-1] for i in range(1, len(values))]
                    info_copy = dict(info)
                    info_copy['name'] = 'Monthly Job Change'
                    info_copy['unit'] = 'Thousands of Jobs'
                    info_copy['is_payroll_change'] = True
                    # Store original data for side-by-side display
                    info_copy['original_dates'] = dates
                    info_copy['original_values'] = values
                    info_copy['original_name'] = 'Total Nonfarm Payrolls'
                    series_data.append((series_id, change_dates, change_values, info_copy))
                elif show_mom and len(dates) > 1:
                    # User requested month-over-month - but NEVER for rates or employment counts!
                    data_type = db_info.get('data_type', 'level')
                    if data_type in ['rate', 'spread', 'growth_rate']:
                        # Rates are already percentages - showing MoM % is nonsense
                        # Just show the raw rate instead
                        series_data.append((series_id, dates, values, info))
                    elif db_info.get('show_absolute_change', False):
                        # Employment counts like PAYEMS - NEVER show as %, show raw data
                        series_data.append((series_id, dates, values, info))
                    else:
                        mom_dates, mom_values = calculate_mom(dates, values)
                        if mom_dates:
                            info_copy = dict(info)
                            info_copy['name'] = series_name + ' (MoM %)'
                            info_copy['unit'] = '% Change MoM'
                            info_copy['is_mom'] = True
                            series_data.append((series_id, mom_dates, mom_values, info_copy))
                        else:
                            series_data.append((series_id, dates, values, info))
                elif show_avg_annual:
                    # User requested average annual
                    avg_dates, avg_values = calculate_avg_annual(dates, values)
                    if avg_dates:
                        info_copy = dict(info)
                        info_copy['name'] = series_name + ' (Annual Avg)'
                        info_copy['unit'] = info.get('unit', info.get('units', '')) + ' (Annual Average)'
                        info_copy['is_avg_annual'] = True
                        series_data.append((series_id, avg_dates, avg_values, info_copy))
                    else:
                        series_data.append((series_id, dates, values, info))
                elif (show_yoy or series_id in show_yoy_series) and len(dates) > 12:
                    # User explicitly requested YoY (all or specific series) - but skip for certain types
                    data_type = db_info.get('data_type', 'level')
                    if data_type in ['rate', 'spread', 'growth_rate']:
                        # Don't apply YoY to rates - show raw data instead
                        series_data.append((series_id, dates, values, info))
                    elif db_info.get('show_absolute_change', False):
                        # Employment counts like PAYEMS - NEVER show as %, show raw data
                        series_data.append((series_id, dates, values, info))
                    else:
                        yoy_dates, yoy_values = calculate_yoy(dates, values)
                        if yoy_dates:
                            info_copy = dict(info)
                            info_copy['name'] = series_name + ' (YoY %)'
                            info_copy['unit'] = '% Change YoY'
                            info_copy['is_yoy'] = True
                            series_data.append((series_id, yoy_dates, yoy_values, info_copy))
                        else:
                            series_data.append((series_id, dates, values, info))
                elif db_info.get('show_yoy') and len(dates) > 12:
                    # Series default is to show YoY (like CPI) - but skip for certain types
                    data_type = db_info.get('data_type', 'level')
                    if data_type in ['rate', 'spread', 'growth_rate']:
                        # Don't apply YoY to rates - show raw data instead
                        series_data.append((series_id, dates, values, info))
                    elif db_info.get('show_absolute_change', False):
                        # Employment counts like PAYEMS - NEVER show as %, show raw data
                        series_data.append((series_id, dates, values, info))
                    else:
                        yoy_dates, yoy_values = calculate_yoy(dates, values)
                        if yoy_dates:
                            info_copy = dict(info)
                            info_copy['name'] = db_info.get('yoy_name', series_name + ' (YoY %)')
                            info_copy['unit'] = db_info.get('yoy_unit', '% Change YoY')
                            info_copy['is_yoy'] = True
                            series_data.append((series_id, yoy_dates, yoy_values, info_copy))
                        else:
                            series_data.append((series_id, dates, values, info))
                else:
                    series_data.append((series_id, dates, values, info))

        # Calculate derived series if formula specified (e.g., effective tariff rate = customs/imports*100)
        if derived_config and derived_raw_data:
            formula = derived_config.get('formula', '')
            derived_name = derived_config.get('name', 'Calculated Value')
            derived_unit = derived_config.get('unit', '')

            if formula:
                derived_dates, derived_values, derived_info = calculate_derived_series(
                    derived_raw_data, formula, derived_name, derived_unit
                )
                if derived_dates and derived_values:
                    # Add derived series as the PRIMARY series (first in list)
                    # Keep component series for context if show_components is True
                    if derived_config.get('show_components', False):
                        # Insert derived at beginning, keep component series
                        series_data.insert(0, ('DERIVED', derived_dates, derived_values, derived_info))
                    else:
                        # Replace component series with derived series only
                        series_data = [('DERIVED', derived_dates, derived_values, derived_info)]

        if not series_data:
            # Provide helpful guidance instead of generic error
            # Build context-specific guidance first to determine the error message
            guidance_parts = []
            error_reason = None

            # Check if ALL series failed to fetch
            if failed_series and len(failed_series) == len(all_series_to_fetch):
                # All series failed - show which ones and why
                rate_limit_errors = [f for f in failed_series if 'rate limit' in f['error'].lower()]
                invalid_series_errors = [f for f in failed_series if 'not found' in f['error'].lower() or 'invalid' in f['error'].lower()]

                if rate_limit_errors:
                    error_reason = "FRED API rate limit reached"
                    st.error(f"Unable to fetch data: {error_reason}")
                    guidance_parts.append("• The FRED API has temporarily rate-limited requests.")
                    guidance_parts.append("• Please wait 60 seconds and try again.")
                    guidance_parts.append("• Tip: Rate limits reset every minute, so you can retry shortly.")
                elif invalid_series_errors:
                    error_reason = "Requested series not found"
                    st.error(f"Unable to fetch data: {error_reason}")
                    failed_ids = [f['series_id'] for f in invalid_series_errors]
                    guidance_parts.append(f"• Series not found in FRED: {', '.join(failed_ids[:3])}")
                    guidance_parts.append("• These series may have been discontinued or renamed.")
                    # Suggest alternatives based on query
                    query_lower = query.lower()
                    if 'unemployment' in query_lower:
                        guidance_parts.append("• Try: 'unemployment rate' or 'jobless claims'")
                    elif 'inflation' in query_lower or 'price' in query_lower:
                        guidance_parts.append("• Try: 'inflation rate' or 'CPI'")
                    elif 'gdp' in query_lower or 'growth' in query_lower:
                        guidance_parts.append("• Try: 'GDP growth' or 'economic growth'")
                    else:
                        guidance_parts.append("• Try a broader query like 'unemployment', 'inflation', or 'GDP growth'")
                else:
                    error_reason = "Data fetch failed"
                    st.error(f"Unable to fetch data: {error_reason}")
                    guidance_parts.append("• All requested series failed to load.")
                    guidance_parts.append("• This may be a temporary FRED API issue.")
                    guidance_parts.append("• Please try again in a moment.")
            else:
                # Some data was fetched but filtered out
                st.error("No data available for this query")

                # Check if date filtering removed all data
                if filter_start_date or filter_end_date:
                    date_range = ""
                    if filter_start_date and filter_end_date:
                        date_range = f"between {filter_start_date} and {filter_end_date}"
                    elif filter_start_date:
                        date_range = f"after {filter_start_date}"
                    elif filter_end_date:
                        date_range = f"before {filter_end_date}"
                guidance_parts.append(f"• The date filter ({date_range}) may have excluded all data. Try a broader time range.")

            # Check if it was a niche query
            niche_keywords = ['food truck', 'solar', 'crypto', 'nft', 'startup', 'gig economy', 'streaming']
            query_lower = query.lower()
            if any(kw in query_lower for kw in niche_keywords):
                guidance_parts.append("• FRED focuses on broad macroeconomic indicators and may not have data for niche industries.")
                guidance_parts.append("• Try broader queries like 'restaurant employment', 'energy sector', or 'technology industry'.")

                # Check if series IDs were valid
                if series_to_fetch:
                    guidance_parts.append(f"• Attempted to fetch: {', '.join(series_to_fetch[:4])}")
                    guidance_parts.append("• These series may be discontinued, have delayed releases, or be temporarily unavailable.")

            # General suggestions if nothing else was added
            if not guidance_parts:
                guidance_parts.append("• FRED may be temporarily unavailable. Try again in a moment.")
                guidance_parts.append("• Try a broader economic query like 'unemployment', 'inflation', or 'GDP growth'.")

            st.info("**Suggestions:**\n" + "\n".join(guidance_parts))
            st.stop()

        # Apply normalization if requested (index all series to 100 at start)
        if normalize and series_data:
            normalized_data = []
            for series_id, dates, values, info in series_data:
                if values and len(values) > 0:
                    base_value = values[0]
                    if base_value != 0:
                        normalized_values = [v / base_value * 100 for v in values]
                        info_copy = info.copy()
                        info_copy['is_normalized'] = True
                        info_copy['unit'] = 'Index (start = 100)'
                        normalized_data.append((series_id, dates, normalized_values, info_copy))
                    else:
                        normalized_data.append((series_id, dates, values, info))
                else:
                    normalized_data.append((series_id, dates, values, info))
            series_data = normalized_data

        # Apply percent change from start if requested
        if pct_change_from_start and series_data:
            pct_data = []
            for series_id, dates, values, info in series_data:
                if values and len(values) > 0:
                    base_value = values[0]
                    if base_value != 0:
                        pct_values = [(v - base_value) / base_value * 100 for v in values]
                        info_copy = info.copy()
                        info_copy['is_pct_change'] = True
                        info_copy['unit'] = '% change from start'
                        pct_data.append((series_id, dates, pct_values, info_copy))
                    else:
                        pct_data.append((series_id, dates, values, info))
                else:
                    pct_data.append((series_id, dates, values, info))
            series_data = pct_data

        # AI-driven presentation validation: determine stock vs flow vs rate for proper display
        # Only apply if user hasn't explicitly requested a transformation (YoY, MoM, normalize, etc.)
        # and if we have ensemble capability
        user_requested_transform = show_yoy or show_mom or normalize or pct_change_from_start or show_avg_annual
        if ENSEMBLE_AVAILABLE and series_data and not user_requested_transform:
            status_container.update(label="Formatting data...")
            # Build series info for the validator
            series_info_for_validation = []
            for sid, dates_v, values_v, info_v in series_data:
                # Skip if already transformed (payroll changes, etc.)
                if info_v.get('is_payroll_change') or info_v.get('is_yoy') or info_v.get('is_mom'):
                    continue
                series_info_for_validation.append({
                    'id': sid,
                    'title': info_v.get('name', info_v.get('title', sid)),
                    'units': info_v.get('unit', info_v.get('units', 'unknown'))
                })

            if series_info_for_validation:
                presentation_config = validate_presentation(query, series_info_for_validation, verbose=False)

                # Apply transformations based on AI recommendations
                transformed_data = []
                for sid, dates_v, values_v, info_v in series_data:
                    config = presentation_config.get(sid, {})
                    display_as = config.get('display_as', 'level')
                    category = config.get('category', 'unknown')

                    # Store the presentation metadata
                    info_copy = dict(info_v)
                    info_copy['presentation_category'] = category
                    info_copy['presentation_display_as'] = display_as

                    # Check if this series should NEVER be shown as percentage change
                    series_db_info = SERIES_DB.get(sid, {})
                    force_absolute = series_db_info.get('show_absolute_change', False)

                    # Apply transformation if AI determined this is a STOCK that should show changes
                    if display_as == 'mom_change' and len(values_v) > 1 and not info_v.get('is_payroll_change'):
                        if force_absolute:
                            # PAYEMS etc - show absolute monthly change, not percent
                            change_dates = dates_v[1:]
                            change_values = [values_v[i] - values_v[i-1] for i in range(1, len(values_v))]
                            info_copy['name'] = 'Monthly Job Change'
                            info_copy['unit'] = 'Thousands of Jobs'
                            info_copy['is_payroll_change'] = True
                            info_copy['original_values'] = values_v
                            info_copy['original_dates'] = dates_v
                            transformed_data.append((sid, change_dates, change_values, info_copy))
                        else:
                            # Convert stock to month-over-month change
                            change_dates = dates_v[1:]
                            change_values = [values_v[i] - values_v[i-1] for i in range(1, len(values_v))]
                            info_copy['name'] = info_v.get('name', sid) + ' (Monthly Change)'
                            info_copy['unit'] = 'Change from Prior Month'
                            info_copy['is_stock_to_change'] = True
                            info_copy['original_values'] = values_v
                            info_copy['original_dates'] = dates_v
                            transformed_data.append((sid, change_dates, change_values, info_copy))
                    elif display_as == 'yoy_change' and len(values_v) > 12:
                        if force_absolute:
                            # PAYEMS etc - NEVER show as YoY %, show monthly job change instead
                            change_dates = dates_v[1:]
                            change_values = [values_v[i] - values_v[i-1] for i in range(1, len(values_v))]
                            info_copy['name'] = 'Monthly Job Change'
                            info_copy['unit'] = 'Thousands of Jobs'
                            info_copy['is_payroll_change'] = True
                            info_copy['original_values'] = values_v
                            info_copy['original_dates'] = dates_v
                            transformed_data.append((sid, change_dates, change_values, info_copy))
                        else:
                            # Convert stock to year-over-year change
                            yoy_dates, yoy_values = calculate_yoy(dates_v, values_v)
                            if yoy_dates:
                                info_copy['name'] = info_v.get('name', sid) + ' (YoY %)'
                                info_copy['unit'] = '% Change YoY'
                                info_copy['is_yoy'] = True
                                transformed_data.append((sid, yoy_dates, yoy_values, info_copy))
                            else:
                                transformed_data.append((sid, dates_v, values_v, info_copy))
                    else:
                        # Level display is appropriate (flows, rates)
                        transformed_data.append((sid, dates_v, values_v, info_copy))

                series_data = transformed_data

        # Check data freshness - warn if data is more than 45 days old
        # Call economist reviewer agent for ALL queries to ensure quality explanations
        if series_data:
            status_container.update(label="Generating insights...")

            # TEMPORAL COMPARISON: Generate comparison-specific narrative
            comparison_metrics = None
            if is_temporal_comparison and TEMPORAL_INTENT_AVAILABLE and temporal_intent:
                try:
                    # Convert series_data to SeriesData format for comparison
                    from core.data_fetcher import SeriesData
                    series_data_dict = {}
                    for sid, dates_v, values_v, info_v in series_data:
                        series_data_dict[sid] = SeriesData(
                            id=sid,
                            name=info_v.get('name', info_v.get('title', sid)),
                            dates=list(dates_v),
                            values=list(values_v),
                            source=info_v.get('source', 'fred'),
                            units=info_v.get('units', info_v.get('unit', '')),
                        )

                    # Compute comparison metrics
                    comparison_metrics = compute_comparison_metrics(series_data_dict, temporal_intent)

                    if comparison_metrics:
                        # Build MultiPeriodData for narrative generation
                        multi_period_data = MultiPeriodData(
                            full_data=series_data_dict,
                            comparison_metrics=comparison_metrics,
                            reference_label=temporal_intent.reference_label,
                            intent=temporal_intent
                        )

                        # Generate comparison-focused narrative
                        comparison_narrative = generate_comparison_narrative(
                            temporal_intent, multi_period_data, query
                        )

                        # Prepend comparison narrative to AI explanation
                        if comparison_narrative:
                            ai_explanation = comparison_narrative
                except Exception as e:
                    print(f"[TemporalIntent] Error generating comparison narrative: {e}")
                    # Fall back to standard narrative generation

            # Standard narrative generation (or if comparison failed)
            if not (is_temporal_comparison and comparison_metrics):
                # Use ensemble for descriptions if enabled
                if ENSEMBLE_AVAILABLE and st.session_state.get('ensemble_mode', False):
                    # Build data summary for ensemble
                    data_summary = _build_data_summary_for_ensemble(series_data)
                    ai_explanation = generate_ensemble_description(
                        query, data_summary, ai_explanation, verbose=False
                    )
                else:
                    ai_explanation = call_economist_reviewer(query, series_data, ai_explanation)

        # Fetch relevant Polymarket predictions for forward-looking context
        polymarket_predictions = []
        polymarket_html = None
        if POLYMARKET_AVAILABLE:
            try:
                polymarket_predictions = find_relevant_predictions(query)[:4]  # Top 4 relevant
                if polymarket_predictions:
                    polymarket_html = format_predictions_box(polymarket_predictions, query)
            except Exception as e:
                print(f"[Polymarket] Error fetching predictions: {e}")

        # Fetch Fed SEP projections if query is about forecasts/outlook
        sep_data = None
        if SEP_AVAILABLE:
            try:
                sep_data = get_sep_for_query(query)
            except Exception as e:
                print(f"[SEP] Error fetching projections: {e}")

        # Generate contextual narratives based on query topic
        housing_narrative = None
        energy_narrative = None
        market_narrative = None
        query_lower = query.lower()

        # Housing narrative for rent/home/mortgage queries
        if ZILLOW_AVAILABLE and any(kw in query_lower for kw in ['rent', 'housing', 'home', 'mortgage', 'real estate', 'shelter', 'zhvi', 'zori']):
            try:
                # Get latest Zillow data for narrative
                _, rent_yoy_values, _ = get_zillow_series('zillow_rent_yoy')
                _, home_yoy_values, _ = get_zillow_series('zillow_home_value_yoy')
                _, rent_values, _ = get_zillow_series('zillow_zori_national')
                _, home_values, _ = get_zillow_series('zillow_zhvi_national')

                rent_yoy = rent_yoy_values[-1] if rent_yoy_values else None
                home_value_yoy = home_yoy_values[-1] if home_yoy_values else None
                rent_value = rent_values[-1] if rent_values else None
                home_value = home_values[-1] if home_values else None

                housing_narrative = synthesize_housing_narrative(
                    rent_value=rent_value,
                    rent_yoy=rent_yoy,
                    home_value=home_value,
                    home_value_yoy=home_value_yoy,
                )
            except Exception as e:
                print(f"[Zillow] Error generating narrative: {e}")

        # Energy narrative for oil/gas/energy queries
        if EIA_AVAILABLE and any(kw in query_lower for kw in ['oil', 'gas', 'gasoline', 'energy', 'crude', 'petroleum', 'fuel', 'natural gas']):
            try:
                # Get latest EIA data for narrative
                _, wti_values, _ = get_eia_series('eia_wti_crude')
                _, gas_values, _ = get_eia_series('eia_gasoline_retail')
                _, natgas_values, _ = get_eia_series('eia_natural_gas_henry_hub')

                wti_price = wti_values[-1] if wti_values else None
                gasoline_price = gas_values[-1] if gas_values else None
                natgas_price = natgas_values[-1] if natgas_values else None

                energy_narrative = synthesize_energy_narrative(
                    wti_price=wti_price,
                    gasoline_price=gasoline_price,
                    natgas_price=natgas_price,
                )
            except Exception as e:
                print(f"[EIA] Error generating narrative: {e}")

        # Market narrative for stock/bond/treasury/market queries
        if ALPHAVANTAGE_AVAILABLE and any(kw in query_lower for kw in ['stock', 'market', 'treasury', 'yield', 'bond', 's&p', 'nasdaq', 'dow', 'vix', 'equity']):
            try:
                # Get latest market data for narrative
                _, spy_values, _ = get_alphavantage_series('av_spy')
                _, treasury_10y_values, _ = get_alphavantage_series('av_treasury_10y')
                _, treasury_2y_values, _ = get_alphavantage_series('av_treasury_2y')

                # Calculate YTD change for S&P
                spy_change_pct = None
                if spy_values and len(spy_values) > 20:
                    start_idx = max(0, len(spy_values) - 252)
                    spy_change_pct = ((spy_values[-1] / spy_values[start_idx]) - 1) * 100

                treasury_10y = treasury_10y_values[-1] if treasury_10y_values else None
                treasury_2y = treasury_2y_values[-1] if treasury_2y_values else None

                market_narrative = synthesize_market_narrative(
                    spy_change_pct=spy_change_pct,
                    treasury_10y=treasury_10y,
                    treasury_2y=treasury_2y,
                )
            except Exception as e:
                print(f"[AlphaVantage] Error generating narrative: {e}")

        # Historical analogues for recession/Fed/macro queries
        historical_context = None
        if ANALOGUES_AVAILABLE and any(kw in query_lower for kw in ['recession', 'soft landing', 'hard landing', 'fed policy', 'monetary policy', 'downturn', 'economic outlook', 'where are we headed', 'what happens next']):
            try:
                # Build current conditions fingerprint from available data
                # These would ideally come from the data we just fetched
                current_conditions = {
                    "inflation": 2.7,  # Default to recent values
                    "unemployment": 4.2,
                    "fed_stance": "easing",  # Fed started cutting Sept 2024
                    "gdp_growth": 2.5,
                    "yield_spread": 20,  # 10Y-2Y spread
                }

                # Try to extract actual values from series_data if available
                for sid, dates, values, info in series_data:
                    if values:
                        if 'CPI' in sid.upper() or 'CPIAUCSL' in sid:
                            current_conditions["inflation"] = values[-1]
                        elif 'UNRATE' in sid.upper() or 'unemployment' in info.get('name', '').lower():
                            current_conditions["unemployment"] = values[-1]
                        elif 'FEDFUNDS' in sid.upper():
                            # If Fed funds rising, tightening; if falling, easing
                            if len(values) >= 2:
                                if values[-1] > values[-2]:
                                    current_conditions["fed_stance"] = "tightening"
                                elif values[-1] < values[-2]:
                                    current_conditions["fed_stance"] = "easing"
                        elif 'T10Y2Y' in sid.upper():
                            current_conditions["yield_spread"] = values[-1] * 100  # Convert to bp

                historical_context = get_analogue_summary(current_conditions, top_n=2)
            except Exception as e:
                print(f"[Analogues] Error generating historical context: {e}")

        # Recession scorecard for recession-related queries
        recession_scorecard = None
        if RECESSION_SCORECARD_AVAILABLE and is_recession_query(query):
            try:
                # Fetch recession indicator data from FRED
                # SAHMREALTIME - Sahm Rule
                sahm_dates, sahm_values, _ = get_observations('SAHMREALTIME', years=2)
                sahm_value = sahm_values[-1] if sahm_values else None
                sahm_prev = sahm_values[-2] if len(sahm_values) >= 2 else None

                # T10Y2Y - Yield curve spread
                yc_dates, yc_values, _ = get_observations('T10Y2Y', years=2)
                yield_curve_value = yc_values[-1] if yc_values else None
                yield_curve_prev = yc_values[-2] if len(yc_values) >= 2 else None

                # UMCSENT - Consumer sentiment
                sent_dates, sent_values, _ = get_observations('UMCSENT', years=2)
                sentiment_value = sent_values[-1] if sent_values else None
                sentiment_prev = sent_values[-2] if len(sent_values) >= 2 else None

                # ICSA - Initial jobless claims (use 4-week moving average)
                claims_dates, claims_values, _ = get_observations('ICSA', years=2)
                # Calculate 4-week moving average for claims
                if claims_values and len(claims_values) >= 4:
                    claims_value = sum(claims_values[-4:]) / 4
                    claims_prev = sum(claims_values[-8:-4]) / 4 if len(claims_values) >= 8 else None
                else:
                    claims_value = claims_values[-1] if claims_values else None
                    claims_prev = None

                # USSLIND - Conference Board Leading Economic Index (MoM % change)
                lei_dates, lei_values, _ = get_observations('USSLIND', years=2)
                if lei_values and len(lei_values) >= 2:
                    # LEI is an index, calculate MoM % change
                    lei_value = ((lei_values[-1] - lei_values[-2]) / lei_values[-2]) * 100
                    lei_prev = ((lei_values[-2] - lei_values[-3]) / lei_values[-3]) * 100 if len(lei_values) >= 3 else None
                else:
                    lei_value = None
                    lei_prev = None

                # NAPM - ISM Manufacturing PMI
                pmi_dates, pmi_values, _ = get_observations('NAPM', years=2)
                pmi_value = pmi_values[-1] if pmi_values else None
                pmi_prev = pmi_values[-2] if len(pmi_values) >= 2 else None

                # BAMLH0A0HYM2 - High Yield Credit Spread
                spread_dates, spread_values, _ = get_observations('BAMLH0A0HYM2', years=2)
                credit_spread_value = spread_values[-1] if spread_values else None
                credit_spread_prev = spread_values[-2] if len(spread_values) >= 2 else None

                # Get Polymarket recession odds
                polymarket_odds = None
                if POLYMARKET_AVAILABLE:
                    try:
                        from agents.polymarket import get_recession_odds
                        recession_data = get_recession_odds()
                        if recession_data:
                            polymarket_odds = recession_data.get('probability', 0) * 100
                    except Exception as e:
                        print(f"[Recession Scorecard] Error fetching Polymarket odds: {e}")

                # Build the scorecard with all leading indicators
                recession_scorecard = build_recession_scorecard(
                    sahm_value=sahm_value,
                    yield_curve_value=yield_curve_value,
                    sentiment_value=sentiment_value,
                    claims_value=claims_value,
                    lei_value=lei_value,
                    pmi_value=pmi_value,
                    credit_spread_value=credit_spread_value,
                    polymarket_odds=polymarket_odds,
                    sahm_prev=sahm_prev,
                    yield_curve_prev=yield_curve_prev,
                    sentiment_prev=sentiment_prev,
                    claims_prev=claims_prev,
                    lei_prev=lei_prev,
                    pmi_prev=pmi_prev,
                    credit_spread_prev=credit_spread_prev,
                )
            except Exception as e:
                print(f"[Recession Scorecard] Error building scorecard: {e}")

        # Generate premium economist analysis for deeper insights
        premium_analysis = None
        premium_analysis_html = None
        if PREMIUM_ANALYSIS_AVAILABLE and series_data:
            try:
                # Get news context if available
                news_ctx = ""
                if NEWS_CONTEXT_AVAILABLE:
                    try:
                        news_ctx = get_economic_context(query)
                    except Exception:
                        pass

                # Generate premium analysis
                analysis_obj, _, analysis_html = get_premium_analysis(
                    query=query,
                    series_data=series_data,
                    news_context=news_ctx,
                )
                premium_analysis = analysis_obj
                premium_analysis_html = analysis_html
                print(f"[PremiumAnalysis] Generated analysis with confidence: {analysis_obj.confidence}")
            except Exception as e:
                print(f"[PremiumAnalysis] Error generating analysis: {e}")

        # Store ALL context atomically for follow-up queries (prevents race conditions)
        st.session_state.last_query = query
        st.session_state.last_series = series_to_fetch[:4]
        st.session_state.last_series_names = series_names_fetched
        st.session_state.last_series_data = series_data
        st.session_state.last_chart_type = chart_type
        st.session_state.last_combine = combine
        st.session_state.last_explanation = ai_explanation

        # Store assistant message for chat history (with all data needed to re-render charts)
        st.session_state.messages.append({
            "role": "assistant",
            "content": query,  # The query this responds to
            "explanation": ai_explanation,
            "series_data": series_data,
            "raw_series_data": raw_series_data,  # For chart_groups re-rendering
            "chart_type": chart_type,
            "combine": combine,
            "chart_groups": chart_groups,  # Store chart groups for proper re-rendering
            "series_names": series_names_fetched,
            "polymarket": polymarket_predictions,  # Prediction market data
            "polymarket_html": polymarket_html,  # Pre-formatted HTML box for display
            "sep": sep_data,  # Fed SEP projections
            "housing_narrative": housing_narrative,  # Zillow housing context
            "energy_narrative": energy_narrative,  # EIA energy context
            "market_narrative": market_narrative,  # Alpha Vantage market context
            "historical_context": historical_context,  # Historical analogues (1994, 2008, etc.)
            "recession_scorecard": recession_scorecard,  # Recession dashboard for recession queries
            "premium_analysis": premium_analysis,  # Premium economist analysis
            "premium_analysis_html": premium_analysis_html,  # Pre-formatted HTML for display
            "coverage_disclaimer": interpretation.get('coverage_disclaimer'),  # Proxy data warning
        })

        # Mark processing as complete and activate chat mode
        status_container.update(label="Done!", state="complete", expanded=False)
        st.session_state.chat_mode = True
        st.rerun()

        # Display response in chat message format (legacy - kept for fallback)
        with st.chat_message("assistant"):
            # Summary callout at top - prominent dashboard style
            has_narrative_content = ai_explanation or any(values for _, _, values, _ in series_data)
            if has_narrative_content:
                # Railway-style: flowing prose without box/label
                if ai_explanation:
                    st.markdown(f"""<div style='font-size: 0.95rem; line-height: 1.7; color: #1f2937; margin: 8px 0 16px 0;'>{ai_explanation}</div>""", unsafe_allow_html=True)

                # Key metrics row using st.metric
                if series_data:
                    metric_cols = st.columns(min(len(series_data), 4))
                    for idx, (sid, d, v, i) in enumerate(series_data[:4]):
                        if v and len(v) > 0:
                            latest_val = v[-1]
                            name = i.get('name', sid)[:25]
                            unit = i.get('unit', '')

                            # Check if this is a payroll change series
                            is_payroll_change = i.get('is_payroll_change', False)
                            is_rate_series = ('percent' in unit.lower() or '%' in unit or
                                              'rate' in name.lower() or i.get('is_yoy'))

                            # Calculate delta if we have enough data
                            delta = None
                            delta_color = "normal"
                            if len(v) >= 13:  # YoY comparison
                                prev_val = v[-13]
                                if is_payroll_change:
                                    # For job changes, show absolute comparison
                                    if prev_val >= 1000:
                                        delta = f"vs {prev_val/1000:.0f}K yr ago"
                                    else:
                                        delta = f"vs {prev_val:.0f}K yr ago"
                                elif is_rate_series:
                                    # For rates/percentages, show pp change
                                    pp_change = latest_val - prev_val
                                    delta = f"{pp_change:+.1f} pp YoY"
                                elif prev_val != 0:
                                    pct_change = ((latest_val - prev_val) / abs(prev_val)) * 100
                                    delta = f"{pct_change:+.1f}% YoY"
                                # For rates like unemployment, down is good
                                if 'unemployment' in name.lower() or 'jobless' in name.lower():
                                    delta_color = "inverse"

                            with metric_cols[idx % len(metric_cols)]:
                                # Format value based on type, accounting for unit multipliers
                                unit_lower = unit.lower()
                                display_val = latest_val
                                # Convert to actual number if unit indicates thousands/millions
                                if 'thousands' in unit_lower:
                                    display_val = latest_val * 1000
                                elif 'millions' in unit_lower:
                                    display_val = latest_val * 1e6
                                elif 'billions' in unit_lower:
                                    display_val = latest_val * 1e9

                                if 'percent' in unit_lower or '%' in unit:
                                    val_str = f"{latest_val:.2f}%"
                                elif display_val >= 1e9:
                                    val_str = f"{display_val/1e9:.1f}B"
                                elif display_val >= 1e6:
                                    val_str = f"{display_val/1e6:.1f}M"
                                elif display_val >= 1000:
                                    val_str = f"{display_val/1000:.1f}K"
                                else:
                                    val_str = f"{display_val:,.2f}"
                                st.metric(label=name, value=val_str, delta=delta, delta_color=delta_color)

        for series_id, dates, values, info in series_data:
            if not values:
                continue

            name = info.get('name', info.get('title', series_id))
            unit = info.get('unit', info.get('units', ''))
            latest = values[-1]

            # Get data type info from SERIES_DB
            db_info = SERIES_DB.get(series_id, {})
            data_type = db_info.get('data_type', 'level')
            frequency = db_info.get('frequency', 'monthly')

            # Format the latest date based on frequency
            latest_date_obj = datetime.strptime(dates[-1], '%Y-%m-%d')
            if frequency == 'quarterly':
                quarter = (latest_date_obj.month - 1) // 3 + 1
                latest_date_str = f"Q{quarter} {latest_date_obj.year}"
            else:
                latest_date_str = latest_date_obj.strftime('%b %Y')

            # SPECIAL HANDLING: Payrolls - BLS-style presentation
            if series_id == 'PAYEMS' and info.get('is_payroll_change') and len(values) >= 3:
                # Values are already monthly changes (in thousands)
                monthly_changes = values

                # Latest month change
                latest_change = monthly_changes[-1] if monthly_changes else 0

                # Prior month change (for month-over-month comparison)
                prior_change = monthly_changes[-2] if len(monthly_changes) >= 2 else 0

                # 12-month trailing average (BLS standard comparison)
                # Use prior 12 months, excluding current month
                prior_12mo = monthly_changes[-13:-1] if len(monthly_changes) >= 13 else monthly_changes[:-1]
                avg_12mo = sum(prior_12mo) / len(prior_12mo) if prior_12mo else 0

                # Format change numbers (data is in thousands, display as full number: 256 -> +256,000)
                def format_job_change(val):
                    full_val = val * 1000  # Convert from thousands to actual
                    return f"{full_val:+,.0f}"

                # Build BLS-style narrative
                sentences = []

                # Headline: "Total nonfarm payroll employment rose by 256,000 in December"
                if latest_change >= 0:
                    verb = "rose" if latest_change > 50 else "edged up" if latest_change > 0 else "was unchanged"
                else:
                    verb = "fell" if latest_change < -50 else "edged down"

                sentences.append(f"<span class='highlight'>Nonfarm payrolls {verb} by {format_job_change(latest_change)}</span> in {latest_date_str}.")

                # Month-over-month comparison
                if prior_change != 0:
                    mom_diff = latest_change - prior_change
                    if abs(mom_diff) < 10:
                        mom_desc = "little changed from"
                    elif mom_diff > 0:
                        mom_desc = "up from"
                    else:
                        mom_desc = "down from"
                    sentences.append(f"This is {mom_desc} {format_job_change(prior_change)} the prior month.")

                # 12-month average comparison
                if avg_12mo != 0:
                    sentences.append(f"The 12-month average is {format_job_change(avg_12mo)}/month.")

                # Benchmark context: compare to breakeven job growth
                change_benchmark = db_info.get('change_benchmark')
                if change_benchmark:
                    breakeven_low = change_benchmark.get('breakeven_low', 100)
                    breakeven_high = change_benchmark.get('breakeven_high', 150)
                    if latest_change < breakeven_low:
                        sentences.append(f"This is below the {breakeven_low:,}-{breakeven_high:,}/month economists estimate is needed to keep pace with population growth.")
                    elif latest_change > breakeven_high * 1.5:
                        sentences.append(f"This is well above the {breakeven_low:,}-{breakeven_high:,}/month needed to keep pace with population growth.")

                narrative = f"<p>{' '.join(sentences)}</p>"
                st.markdown(narrative, unsafe_allow_html=True)
                continue  # Skip the normal narrative for PAYEMS

            # Build context-aware description based on data type
            if data_type == 'growth_rate':
                value_desc = f"<strong>{latest:.1f}%</strong> (annualized quarterly rate)"
            elif data_type == 'rate':
                value_desc = f"<strong>{latest:.1f}%</strong>"
            elif data_type == 'index' and info.get('is_yoy'):
                value_desc = f"<strong>{latest:.1f}%</strong> year-over-year"
            elif info.get('is_yoy') or info.get('is_mom'):
                value_desc = f"<strong>{latest:.1f}%</strong>"
            elif data_type == 'spread':
                value_desc = f"<strong>{latest:.2f} percentage points</strong>"
            elif data_type == 'price':
                value_desc = f"<strong>${latest:.2f}</strong>"
            else:
                value_desc = f"<strong>{format_number(latest, unit)}</strong>"

            # Build prose narrative with full sentences
            sentences = []

            # Sentence 1: Current value
            sentences.append(f"<span class='highlight'>{name}</span> is {value_desc} as of {latest_date_str}.")

            # Sentence 1b: Benchmark context (if available)
            benchmark = db_info.get('benchmark')
            if benchmark:
                bench_val = benchmark.get('value')
                bench_text = benchmark.get('text', '')
                applies_to_yoy = benchmark.get('applies_to_yoy', False)
                comparison_type = benchmark.get('comparison', 'above')

                # Only apply benchmark if it's relevant (YoY benchmarks only for YoY data)
                if applies_to_yoy and info.get('is_yoy') and bench_val is not None:
                    diff = latest - bench_val
                    if comparison_type == 'above' and diff > 0.2:
                        sentences.append(f"This is above the Fed's {bench_val}% target ({diff:+.1f} pp).")
                    elif comparison_type == 'above' and diff < -0.2:
                        sentences.append(f"This is below the Fed's {bench_val}% target ({diff:+.1f} pp).")
                elif not applies_to_yoy and data_type == 'rate' and bench_val is not None:
                    # For rates like unemployment
                    diff = latest - bench_val
                    if comparison_type == 'above' and diff > 0.3:
                        sentences.append(f"This is above what economists generally estimate as full employment (~{bench_val}%).")
                    elif comparison_type == 'above' and diff < -0.3:
                        sentences.append(f"This is below typical estimates of full employment (~{bench_val}%), indicating a tight labor market.")
                elif data_type == 'growth_rate' and benchmark.get('ranges'):
                    # For GDP growth rate - describe where in the range we are
                    ranges = benchmark.get('ranges')
                    for low, high, desc in ranges:
                        if low <= latest < high:
                            if latest < 0:
                                sentences.append(f"Negative growth indicates economic contraction.")
                            else:
                                sentences.append(f"This is considered {desc} (trend growth is ~{bench_val}%).")
                            break

            # Sentence 2: Recent trend description (what's happening)
            show_abs = db_info.get('show_absolute_change', False)
            trend_desc = describe_recent_trend(dates, values, data_type, frequency, show_absolute_change=show_abs)
            if trend_desc:
                sentences.append(trend_desc)

            # Sentence 3: Year-over-year comparison with actual values
            try:
                target_date = latest_date_obj - timedelta(days=365)
                year_ago_idx = None
                for i, d in enumerate(dates):
                    d_obj = datetime.strptime(d, '%Y-%m-%d')
                    if d_obj >= target_date - timedelta(days=45) and d_obj <= target_date + timedelta(days=45):
                        year_ago_idx = i
                        break
                if year_ago_idx is not None:
                    year_ago_val = values[year_ago_idx]
                    year_ago_date = datetime.strptime(dates[year_ago_idx], '%Y-%m-%d').strftime('%b %Y')
                    if data_type in ['rate', 'spread', 'growth_rate'] or info.get('is_yoy') or info.get('is_mom'):
                        change = latest - year_ago_val
                        direction = 'up' if change >= 0 else 'down'
                        css_class = 'up' if change >= 0 else 'down'
                        sentences.append(f"That's <span class='{css_class}'>{direction} {abs(change):.1f} percentage points</span> from a year ago ({year_ago_val:.1f}% in {year_ago_date}).")
                    elif db_info.get('show_absolute_change', False):
                        # Employment counts like PAYEMS - show absolute change, not percent
                        change = latest - year_ago_val
                        direction = 'up' if change >= 0 else 'down'
                        css_class = 'up' if change >= 0 else 'down'
                        # Format as full number (data is in thousands, so multiply by 1000)
                        full_change = abs(change) * 1000
                        if full_change >= 1000000:
                            change_str = f"{full_change/1000000:.1f} million jobs"
                        else:
                            change_str = f"{full_change:,.0f} jobs"
                        sentences.append(f"That's <span class='{css_class}'>{change_str} {direction}</span> from a year ago.")
                    elif year_ago_val != 0:
                        pct = ((latest - year_ago_val) / abs(year_ago_val)) * 100
                        direction = 'up' if pct >= 0 else 'down'
                        css_class = 'up' if pct >= 0 else 'down'
                        if data_type == 'price':
                            sentences.append(f"That's <span class='{css_class}'>{direction} {abs(pct):.1f}%</span> from a year ago (${year_ago_val:.2f} in {year_ago_date}).")
                        else:
                            sentences.append(f"That's <span class='{css_class}'>{direction} {abs(pct):.1f}%</span> from a year ago ({format_number(year_ago_val, unit)} in {year_ago_date}).")
            except:
                pass

            # Sentence 3: Pre-COVID comparison (Dec 2019/Jan 2020) for seasonally adjusted data
            # Use late 2019/early 2020 as the baseline - before any pandemic impact
            if db_info.get('sa', False):
                try:
                    # Find the last data point before March 2020 (when pandemic hit US)
                    # This handles quarterly data (finds Q4 2019 or Q1 2020) and monthly data (finds Jan/Feb 2020)
                    pre_covid_candidates = [(i, d) for i, d in enumerate(dates) if d < '2020-03-01' and d >= '2019-10-01']
                    if pre_covid_candidates:
                        covid_idx = pre_covid_candidates[-1][0]  # Get the most recent pre-pandemic point
                        pre_covid = values[covid_idx]
                        pre_covid_date = dates[covid_idx]
                        # Format the date nicely
                        try:
                            dt = datetime.strptime(pre_covid_date[:10], '%Y-%m-%d')
                            date_label = dt.strftime('%b %Y')  # e.g., "Jan 2020" or "Dec 2019"
                        except:
                            date_label = "pre-pandemic"
                    else:
                        raise StopIteration

                    # Skip this comparison for growth rates - it's confusing to compare YoY% to a specific month's YoY%
                    if data_type == 'growth_rate':
                        pass  # Don't show this comparison for growth rates
                    elif data_type in ['rate', 'spread']:
                        diff = latest - pre_covid
                        if abs(diff) >= 0.2:
                            if diff > 0.2:
                                sentences.append(f"This is {abs(diff):.1f} pp above the {pre_covid:.1f}% level from {date_label}, before the pandemic.")
                            elif diff < -0.2:
                                sentences.append(f"This is {abs(diff):.1f} pp below the {pre_covid:.1f}% level from {date_label}, before the pandemic.")
                    elif db_info.get('show_absolute_change', False):
                        # Employment counts like PAYEMS - show absolute change
                        diff = latest - pre_covid
                        if abs(diff) >= 100:  # Only mention if significant (100K+)
                            direction = "above" if diff > 0 else "below"
                            # Format as full number (data is in thousands, so multiply by 1000)
                            full_diff = abs(diff) * 1000
                            if full_diff >= 1000000:
                                diff_str = f"{full_diff/1000000:.1f} million jobs"
                            else:
                                diff_str = f"{full_diff:,.0f} jobs"
                            sentences.append(f"Employment is {diff_str} {direction} the pre-pandemic level ({date_label}).")
                    elif pre_covid != 0:
                        pct_diff = ((latest - pre_covid) / abs(pre_covid)) * 100
                        if abs(pct_diff) >= 3:
                            if pct_diff > 3:
                                if data_type == 'price':
                                    sentences.append(f"This is {pct_diff:.0f}% above the ${pre_covid:.2f} level from {date_label}, before the pandemic.")
                                else:
                                    sentences.append(f"This is {pct_diff:.0f}% above the {format_number(pre_covid, unit)} level from {date_label}, before the pandemic.")
                            elif pct_diff < -3:
                                if data_type == 'price':
                                    sentences.append(f"This is {abs(pct_diff):.0f}% below the ${pre_covid:.2f} level from {date_label}, before the pandemic.")
                                else:
                                    sentences.append(f"This is {abs(pct_diff):.0f}% below the {format_number(pre_covid, unit)} level from {date_label}, before the pandemic.")
                except (StopIteration, IndexError):
                    pass

            # Sentence 4: Historical context (trend, highs/lows)
            smart_context = generate_narrative_context(dates, values, data_type, db_info)
            context_sentence_parts = []

            # Trend
            if 'trend' in smart_context:
                context_sentence_parts.append(f"has been {smart_context['trend']}")

            # Historical position
            if 'at_high' in smart_context:
                context_sentence_parts.append(f"is at a {smart_context['at_high']}")
            elif 'near_high' in smart_context:
                context_sentence_parts.append(f"is {smart_context['near_high']}")
            elif 'at_low' in smart_context:
                context_sentence_parts.append(f"is at a {smart_context['at_low']}")
            elif 'near_low' in smart_context:
                context_sentence_parts.append(f"is {smart_context['near_low']}")

            # vs 2019 average
            if 'vs_2019' in smart_context:
                context_sentence_parts.append(f"is {smart_context['vs_2019']}")

            if context_sentence_parts:
                # Join with "and" for readability
                if len(context_sentence_parts) == 1:
                    sentences.append(f"The current reading {context_sentence_parts[0]}.")
                elif len(context_sentence_parts) == 2:
                    sentences.append(f"The current reading {context_sentence_parts[0]} and {context_sentence_parts[1]}.")
                else:
                    sentences.append(f"The current reading {', '.join(context_sentence_parts[:-1])}, and {context_sentence_parts[-1]}.")

            narrative = f"<p>{' '.join(sentences)}</p>"
            st.markdown(narrative, unsafe_allow_html=True)

        if has_narrative_content:
            st.markdown("</div>", unsafe_allow_html=True)

        # Chart Groups handling - allows multiple charts with different series/transformations
        if chart_groups and len(chart_groups) > 0:
            # Use raw_series_data (untransformed) for chart groups
            series_lookup = raw_series_data

            for group_idx, group in enumerate(chart_groups):
                group_series_ids = group.get('series', [])
                group_show_yoy = group.get('show_yoy', False)
                group_pct_from_start = group.get('pct_change_from_start', False)
                group_title = group.get('title', '')

                # Filter to series in this group
                group_data = []
                for sid in group_series_ids:
                    if sid in series_lookup:
                        group_data.append(series_lookup[sid])
                    else:
                        # Need to fetch this series
                        dates_g, values_g, info_g = get_observations(sid, years)
                        if dates_g and values_g:
                            group_data.append((sid, dates_g, values_g, info_g))

                if not group_data:
                    continue

                # Apply YoY transformation if requested for this group
                if group_show_yoy:
                    transformed = []
                    for sid, dates_g, values_g, info_g in group_data:
                        new_dates, new_values = calculate_yoy(dates_g, values_g)
                        new_info = dict(info_g)
                        new_info['is_yoy'] = True
                        new_info['unit'] = 'YoY % Change'
                        transformed.append((sid, new_dates, new_values, new_info))
                    group_data = transformed

                # Apply normalize transformation (index to 100 at common start date)
                group_normalize = group.get('normalize', False)
                if group_normalize and len(group_data) > 0:
                    # Find the latest start date among all series (so all have data)
                    start_dates = [dates_g[0] for sid, dates_g, values_g, info_g in group_data if dates_g]
                    common_start = max(start_dates) if start_dates else None

                    norm_data = []
                    for sid, dates_g, values_g, info_g in group_data:
                        if values_g and len(values_g) > 0 and dates_g:
                            # Find index of common start date (or closest date after)
                            start_idx = 0
                            for i, d in enumerate(dates_g):
                                if d >= common_start:
                                    start_idx = i
                                    break

                            # Trim to common start and index to 100
                            trimmed_dates = dates_g[start_idx:]
                            trimmed_values = values_g[start_idx:]

                            if trimmed_values and trimmed_values[0] != 0:
                                base_value = trimmed_values[0]
                                indexed_values = [(v / base_value) * 100 for v in trimmed_values]
                                new_info = dict(info_g)
                                new_info['unit'] = 'Index (Start = 100)'
                                new_info['is_normalized'] = True
                                norm_data.append((sid, trimmed_dates, indexed_values, new_info))
                    group_data = norm_data if norm_data else group_data

                # Apply pct_change_from_start transformation if requested
                elif group_pct_from_start:
                    pct_data = []
                    for sid, dates_g, values_g, info_g in group_data:
                        if values_g and len(values_g) > 0:
                            base_value = values_g[0]
                            if base_value != 0:
                                pct_values = [((v - base_value) / base_value) * 100 for v in values_g]
                                new_info = dict(info_g)
                                new_info['unit'] = '% Change from Start'
                                new_info['is_pct_from_start'] = True
                                pct_data.append((sid, dates_g, pct_values, new_info))
                    group_data = pct_data if pct_data else group_data

                # Render the chart for this group
                st.markdown("<div class='chart-section'>", unsafe_allow_html=True)

                # Generate chart title
                if group_title:
                    chart_title = group_title
                else:
                    chart_title = ' vs '.join([generate_chart_title(sid, info)[:40] for sid, _, _, info in group_data])

                # Title
                st.markdown(f"### {chart_title}")

                # Bullets - each as a separate line
                all_bullets = []
                for sid, d, v, i in group_data:
                    analysis = generate_goldman_style_analysis(sid, d, v, i, user_query=query)
                    bullets = analysis.get('bullets', [])
                    all_bullets.extend(bullets[:2])
                if all_bullets:
                    for bullet in all_bullets[:3]:  # Limit to 3 bullets
                        if bullet and bullet.strip():
                            st.markdown(f"- {bullet}")

                # Chart - pass temporal_intent for comparison period highlighting
                combine_group = len(group_data) > 1
                fig = create_chart(group_data, combine=combine_group, chart_type=chart_type, temporal_intent=temporal_intent)
                st.plotly_chart(fig, width='stretch')
                st.markdown("</div>", unsafe_allow_html=True)

        # Regular Charts (when not using chart_groups)
        elif combine and len(series_data) > 1:
            st.markdown("<div class='chart-section'>", unsafe_allow_html=True)

            # Generate dynamic chart title and descriptions
            chart_title = ' vs '.join([generate_chart_title(sid, info)[:40] for sid, _, _, info in series_data])

            # Title
            st.markdown(f"### {chart_title}")

            # Bullets - each as a separate line
            all_bullets = []
            for sid, d, v, i in series_data:
                analysis = generate_goldman_style_analysis(sid, d, v, i, user_query=query)
                bullets = analysis.get('bullets', [])
                all_bullets.extend(bullets[:2])
            if all_bullets:
                for bullet in all_bullets[:3]:  # Limit to 3 bullets
                    if bullet and bullet.strip():
                        st.markdown(f"- {bullet}")

            # Chart (source is built into the chart)
            # Pass temporal_intent for comparison period highlighting
            fig = create_chart(series_data, combine=True, chart_type=chart_type, temporal_intent=temporal_intent)
            st.plotly_chart(fig, width='stretch')
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            for series_id, dates, values, info in series_data:
                db_info = SERIES_DB.get(series_id, {})
                name = info.get('name', info.get('title', series_id))
                source = db_info.get('source', info.get('source', 'FRED'))
                unit = info.get('unit', info.get('units', ''))
                bullets = db_info.get('bullets', [f'FRED series: {series_id}', f"Unit: {unit}" if unit else ''])
                # Filter out empty bullets
                bullets = [b for b in bullets if b and b.strip()]
                sa_note = "Seasonally adjusted." if db_info.get('sa', False) else "Not seasonally adjusted."
                transform_note = ""
                if info.get('is_yoy'):
                    transform_note = " Showing year-over-year percent change."
                elif info.get('is_mom'):
                    transform_note = " Showing month-over-month percent change."
                elif info.get('is_avg_annual'):
                    transform_note = " Showing annual averages."

                st.markdown("<div class='chart-section'>", unsafe_allow_html=True)

                # Special side-by-side layout for payroll changes
                if info.get('is_payroll_change') and info.get('original_dates'):
                    # Generate Goldman-style analysis for monthly job changes
                    goldman_analysis = generate_goldman_style_analysis(series_id, dates, values, info, user_query=query)
                    payroll_title = goldman_analysis.get('title', 'Nonfarm Payrolls')
                    payroll_bullets = goldman_analysis.get('bullets', [])

                    st.markdown(f"**{payroll_title}**")
                    for bullet in payroll_bullets:
                        if bullet and bullet.strip():
                            st.markdown(f"- {bullet}")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**Monthly Job Change**")
                        # Limit to last 5 years to avoid COVID crash dominating scale
                        recent_count = min(60, len(dates))
                        recent_dates = dates[-recent_count:]
                        recent_values = values[-recent_count:]
                        fig_bar = create_chart([(series_id, recent_dates, recent_values, info)], combine=False, chart_type='bar')
                        fig_bar.update_layout(
                            height=350,
                            margin=dict(l=50, r=20, t=30, b=50),
                            yaxis_title='Thousands'
                        )
                        st.plotly_chart(fig_bar, width='stretch')

                    with col2:
                        st.markdown("**Total Nonfarm Payrolls**")
                        orig_info = dict(info)
                        orig_info['name'] = info.get('original_name', 'Total Nonfarm Payrolls')
                        orig_info['unit'] = 'Thousands of Persons'
                        fig_line = create_chart(
                            [(series_id, info['original_dates'], info['original_values'], orig_info)],
                            combine=False, chart_type='line'
                        )
                        fig_line.update_layout(
                            height=350,
                            margin=dict(l=50, r=20, t=30, b=50),
                            yaxis_title='Thousands'
                        )
                        st.plotly_chart(fig_line, width='stretch')
                else:
                    # Generate dynamic AI-powered bullets based on current data and user query
                    goldman_analysis = generate_goldman_style_analysis(series_id, dates, values, info, user_query=query)
                    chart_title = goldman_analysis.get('title', info.get('name', series_id))
                    goldman_bullets = goldman_analysis.get('bullets', [])

                    # Title
                    st.markdown(f"### {chart_title}")

                    # Bullets - each as a separate line
                    if goldman_bullets:
                        valid_bullets = [b for b in goldman_bullets[:3] if b and b.strip()]
                        for bullet in valid_bullets:
                            st.markdown(f"- {bullet}")

                    # Chart (source is built into the chart)
                    # Pass temporal_intent for comparison period highlighting
                    fig = create_chart([(series_id, dates, values, info)], combine=False, chart_type=chart_type, temporal_intent=temporal_intent)
                    st.plotly_chart(fig, width='stretch')

                st.markdown("</div>", unsafe_allow_html=True)

        # Download button
        all_data = {}
        for series_id, dates, values, info in series_data:
            name = info.get('name', info.get('title', series_id))
            for d, v in zip(dates, values):
                if d not in all_data:
                    all_data[d] = {'Date': d}
                all_data[d][name] = v

        df = pd.DataFrame(list(all_data.values())).sort_values('Date')
        csv = df.to_csv(index=False)

        # Action buttons row
        btn_col1, btn_col2 = st.columns([1, 3])
        with btn_col1:
            st.download_button("Download CSV", csv, "econstats_data.csv", "text/csv")

        # Debug info expander
        with st.expander("🔧 Debug Info", expanded=False):
            # Settings toggles
            if RAG_AVAILABLE:
                st.session_state.rag_mode = st.checkbox(
                    "RAG Mode (Semantic Search + LLM) - Recommended",
                    value=st.session_state.get('rag_mode', True),
                    help="Use semantic search to find relevant series, then LLM selects best ones"
                )
            if ENSEMBLE_AVAILABLE:
                st.session_state.ensemble_mode = st.checkbox(
                    "🧠 Ensemble Mode (Claude + Gemini + GPT)",
                    value=st.session_state.get('ensemble_mode', False),
                    help="Use multiple AI models (only if RAG is off)",
                    disabled=st.session_state.get('rag_mode', False)
                )

            # Query interpretation method
            if interpretation.get('used_precomputed'):
                if interpretation.get('used_hybrid'):
                    sources = interpretation.get('hybrid_sources', {})
                    st.write("**Method:** Pre-computed + Hybrid Augmentation")
                    st.write(f"  - Pre-computed: {sources.get('precomputed', [])}")
                    st.write(f"  - From RAG: {sources.get('rag', [])}")
                    st.write(f"  - From FRED: {sources.get('fred', [])}")
                else:
                    st.write("**Method:** Pre-computed query plan (instant)")
            elif interpretation.get('used_local_parser'):
                st.write("**Method:** Local follow-up parser (instant)")
            elif interpretation.get('used_rag'):
                if interpretation.get('used_hybrid'):
                    sources = interpretation.get('hybrid_sources', {})
                    st.write("**Method:** Hybrid (RAG Catalog + FRED Search)")
                    st.write(f"  - From RAG: {sources.get('rag', [])}")
                    st.write(f"  - From FRED: {sources.get('fred', [])}")
                else:
                    st.write("**Method:** RAG (Semantic Search + GPT Selection)")
            elif interpretation.get('used_ensemble'):
                st.write("**Method:** AI Ensemble (Claude + Gemini + GPT)")
                # Show ensemble metadata if available
                ensemble_meta = interpretation.get('ensemble_metadata', {})
                if ensemble_meta:
                    st.write(f"  - Winner: {ensemble_meta.get('winner', 'N/A')}")
                    st.write(f"  - Claude suggested: {ensemble_meta.get('claude_series', [])}")
                    st.write(f"  - Gemini suggested: {ensemble_meta.get('gemini_series', [])}")
            else:
                st.write("**Method:** Claude AI interpretation")

            st.write(f"**Series fetched:** {', '.join(series_to_fetch)}")

            # Show validation results if any
            validation_result = interpretation.get('validation_result')
            if validation_result:
                rejected = validation_result.get('rejected_series', [])
                if rejected:
                    st.write(f"**Rejected (irrelevant):** {', '.join([r.get('id', '?') for r in rejected])}")
                    for r in rejected:
                        st.write(f"  - {r.get('id')}: {r.get('reason', 'No reason given')}")

            st.write(f"**Chart type:** {chart_type}")
            st.write(f"**Combine charts:** {combine}")

            transforms = []
            if show_yoy:
                transforms.append("Year-over-Year")
            if show_mom:
                transforms.append("Month-over-Month")
            if show_avg_annual:
                transforms.append("Annual Average")
            if normalize:
                transforms.append("Normalized to 100")
            if pct_change_from_start:
                transforms.append("% Change from Start")
            st.write(f"**Transformations:** {', '.join(transforms) if transforms else 'None'}")

            st.write(f"**Time period:** {years} years")

            if is_followup:
                st.write("**Follow-up query:** Yes")

        # Feedback section
        st.markdown("---")
        st.markdown("**Was this helpful?**")

        # Initialize feedback state for this query
        feedback_key = f"feedback_{hash(query)}"
        if feedback_key not in st.session_state:
            st.session_state[feedback_key] = {'voted': False, 'vote': None}

        col1, col2, col3 = st.columns([1, 1, 4])

        with col1:
            if st.button("👍 Yes", key=f"upvote_{hash(query)}", disabled=st.session_state[feedback_key]['voted']):
                st.session_state[feedback_key]['voted'] = True
                st.session_state[feedback_key]['vote'] = 'upvote'
                save_feedback(query, series_to_fetch, 'upvote')
                st.success("Thanks!")

        with col2:
            if st.button("👎 No", key=f"downvote_{hash(query)}", disabled=st.session_state[feedback_key]['voted']):
                st.session_state[feedback_key]['voted'] = True
                st.session_state[feedback_key]['vote'] = 'downvote'
                st.session_state[feedback_key]['show_comment'] = True

        # Show comment box if downvoted
        if st.session_state[feedback_key].get('show_comment') and not st.session_state[feedback_key].get('comment_submitted'):
            comment = st.text_area(
                "What could be better?",
                placeholder="e.g., Wrong data series, missing context, confusing presentation...",
                key=f"comment_{hash(query)}"
            )
            if st.button("Submit Feedback", key=f"submit_{hash(query)}"):
                save_feedback(query, series_to_fetch, 'downvote', comment)
                st.session_state[feedback_key]['comment_submitted'] = True
                st.success("Thanks for your feedback!")

        if st.session_state[feedback_key].get('comment_submitted'):
            st.info("Feedback submitted. Thank you!")

    elif not query and st.session_state.last_series_data and not st.session_state.chat_mode:
        # Display cached results from previous query (only in non-chat mode)
        # In chat mode, the chat history already renders everything
        series_data = st.session_state.last_series_data
        ai_explanation = st.session_state.last_explanation
        chart_type = st.session_state.last_chart_type
        combine = st.session_state.last_combine

        # Show previous query context
        st.markdown(f"<p style='color: #666; font-size: 0.9em;'>Showing results for: <strong>{st.session_state.last_query}</strong></p>", unsafe_allow_html=True)

        # Narrative summary
        st.markdown("<div class='narrative-box'>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0'>Summary</h3>", unsafe_allow_html=True)
        if ai_explanation:
            st.markdown(f"<div class='ai-explanation'>{ai_explanation}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Charts
        if combine and len(series_data) > 1:
            fig = create_chart(series_data, combine=True, chart_type=chart_type)
            st.plotly_chart(fig, width='stretch')
        else:
            for series_id, dates, values, info in series_data:
                fig = create_chart([(series_id, dates, values, info)], combine=False, chart_type=chart_type)
                st.plotly_chart(fig, width='stretch')

    # Footer - About section
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #64748b; font-size: 0.85rem; padding: 15px 0;">
        <strong>About EconStats</strong><br>
        Government economic data is free—but too hard for most people to access and understand.
        EconStats uses AI to help anyone draw insights directly from the numbers.<br><br>
        Contact <a href="mailto:waldman1@stanford.edu" style="color: #3b82f6;">waldman1@stanford.edu</a> with feedback or ideas.
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
