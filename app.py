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
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# LangGraph deep analysis agent (optional - requires langchain/langgraph dependencies)
try:
    from langgraph_agent import run_query as run_deep_analysis
    DEEP_ANALYSIS_AVAILABLE = True
except Exception:
    # Catch all errors (ImportError, KeyError, etc.) - Deep Analysis is optional
    DEEP_ANALYSIS_AVAILABLE = False
    run_deep_analysis = None


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
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': years,
            'explanation': f'Showing last {years} years.',
        }

    # "since YYYY"
    elif match := re.search(r'\bsince\s+(\d{4})\b', q):
        start_year = int(match.group(1))
        years = datetime.now().year - start_year + 1
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': years,
            'explanation': f'Showing data since {start_year}.',
        }

    # "all data" / "all time"
    elif re.search(r'\b(all\s+(available\s+)?(data|time|history)|full\s+history)\b', q):
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': None,  # None means all
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
        # Show data from 2017-2020 (3 years before COVID)
        # Calculate years from 2017 to now to fetch enough data, then filter
        years_from_2017 = datetime.now().year - 2017 + 1
        result = {
            'is_followup': True,
            'keep_previous_series': True,
            'years_override': years_from_2017,
            'filter_end_date': '2020-02-29',  # Pre-COVID cutoff
            'explanation': 'Showing pre-COVID data (through February 2020).',
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
            'rates': ['FEDFUNDS'],
            'interest rates': ['FEDFUNDS'],
            '10 year': ['DGS10'],
            '2 year': ['DGS2'],
            'yield curve': ['T10Y2Y'],
            'mortgage': ['MORTGAGE30US'],
            'mortgage rates': ['MORTGAGE30US'],
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

def find_query_plan(query: str, threshold: float = 0.85) -> dict | None:
    """
    Find the best matching query plan using normalization and fuzzy matching.
    Returns the plan dict if found, None otherwise.
    """
    if not QUERY_PLANS:
        return None

    # Normalize the input query
    normalized = normalize_query(query)
    original_lower = query.lower().strip()

    # 1. Exact match on original (fastest)
    if original_lower in QUERY_PLANS:
        return QUERY_PLANS[original_lower]

    # 2. Exact match on normalized
    if normalized in QUERY_PLANS:
        return QUERY_PLANS[normalized]

    # 3. Check synonyms - some plans have a "synonyms" list for alternate names
    for plan_key, plan in QUERY_PLANS.items():
        synonyms = plan.get('synonyms', [])
        if original_lower in synonyms or normalized in synonyms:
            return plan
        # Also check if query is a fuzzy match to any synonym
        for syn in synonyms:
            if difflib.SequenceMatcher(None, normalized, syn).ratio() > 0.85:
                return plan

    # 4. Fuzzy match - find closest query in plans
    all_queries = list(QUERY_PLANS.keys())

    # Try matching against normalized query
    matches = difflib.get_close_matches(normalized, all_queries, n=1, cutoff=threshold)
    if matches:
        return QUERY_PLANS[matches[0]]

    # Try matching against original (for cases like typos)
    matches = difflib.get_close_matches(original_lower, all_queries, n=1, cutoff=threshold)
    if matches:
        return QUERY_PLANS[matches[0]]

    # 5. Word-based matching for longer queries
    # If query contains key economic terms, try to match those
    key_terms = ['inflation', 'unemployment', 'gdp', 'jobs', 'rates', 'housing',
                 'wages', 'recession', 'fed', 'cpi', 'pce', 'payrolls']
    for term in key_terms:
        if term in normalized:
            # Find all plans containing this term
            term_matches = [q for q in all_queries if term in q]
            if term_matches:
                # Find best match among these
                best = difflib.get_close_matches(normalized, term_matches, n=1, cutoff=0.5)
                if best:
                    return QUERY_PLANS[best[0]]
                # If still no fuzzy match, return the simplest one (shortest)
                term_matches.sort(key=len)
                return QUERY_PLANS[term_matches[0]]

    return None

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
            'breakeven_low': 100,  # in thousands
            'breakeven_high': 150,
            'text': "Economists generally estimate the economy needs 100,000-150,000 new jobs per month to keep pace with population growth.",
        },
        'bullets': [
            'The single most important monthly indicator of labor market health. This is the "jobs number" that moves markets on the first Friday of each month. It counts every worker on a U.S. business payroll outside of farming.',
            'Context matters: The economy needs roughly 100,000-150,000 new jobs per month just to absorb population growth. Gains above 200,000 signal robust hiring; below 100,000 suggests softening. During recessions, this figure turns sharply negative—the economy lost 800,000+ jobs monthly at the depths of the 2008-09 crisis.'
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
}

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
1. BE COMPREHENSIVE: When there are multiple relevant charts, include ALL of them (up to 4). Do NOT be lazy and just pick one. For example, GDP should show: annual growth, quarterly growth, core GDP, and GDPNow.
2. USE SEASONALLY ADJUSTED DATA by default.
3. For topics you don't know exact series for, provide SPECIFIC search terms that would find them in FRED.
4. Each series you include should tell a different part of the story - don't include redundant series.
5. EVERY CHART MUST HAVE AN EXPLANATORY BULLET - each series needs a clear explanation of what it shows and why it matters.

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

## CRITICAL RULE FOR DEMOGRAPHIC QUESTIONS
When asked about a specific demographic group (women, men, Black workers, Hispanic workers, etc.), NEVER use aggregate series like PAYEMS (total nonfarm payrolls) or UNRATE (overall unemployment). These tell you nothing about that specific group. Instead, use the demographic-specific series listed above. For example:
- "How are women doing?" → Use LNS14000002, LNS12300062, LNS11300002 (women-specific series)
- "Black unemployment" → Use LNS14000006 (Black unemployment rate)
- Do NOT mix in PAYEMS or other aggregate measures that don't break down by demographic.

## FOR UNKNOWN TOPICS
If the user asks about something not listed above (e.g., "semiconductor production", "restaurant sales", "California unemployment", "auto manufacturing"), provide search_terms like:
- "semiconductor production index"
- "restaurant sales receipts"
- "California unemployment rate"
- "motor vehicle manufacturing employment"

FRED's search API will find the right series.

## COMBINE_CHART RULES
Only set combine_chart=true when ALL of these are true:
- Series share the same units (e.g., both are rates, both are indexes)
- Scales are comparable (e.g., both 0-10%, not one 0-5% and another 0-100%)
- Visual comparison adds insight (comparing them on one chart tells a story)
Otherwise use separate charts (combine_chart=false).

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


def call_economist_reviewer(query: str, series_data: list, original_explanation: str) -> str:
    """Call a second Claude agent to review and improve the explanation.

    This agent sees the actual data values and can write smarter, more contextual narratives.

    Args:
        query: The user's original question
        series_data: List of (series_id, dates, values, info) tuples with actual data
        original_explanation: The initial explanation from the first agent

    Returns:
        Improved explanation string
    """
    if not ANTHROPIC_API_KEY or not series_data:
        return original_explanation

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

        # Add job growth stats for payroll data
        if monthly_change is not None:
            summary['monthly_job_change'] = round(monthly_change, 1)
        if avg_3mo_change is not None:
            summary['avg_monthly_change_3mo'] = round(avg_3mo_change, 1)
        if avg_12mo_change is not None:
            summary['avg_monthly_change_12mo'] = round(avg_12mo_change, 1)

        data_summary.append(summary)

    prompt = f"""You are an expert economist reviewing data for a user query. Your job is to write a clear, insightful summary explanation.

USER QUERY: {query}

DATA SUMMARY:
{json.dumps(data_summary, indent=2)}

INITIAL EXPLANATION: {original_explanation}

Write an improved explanation that:
1. States the current values clearly with proper formatting (IMPORTANT: if unit is "Thousands of Persons", convert to millions - e.g., 1764.6 thousands = 1.76 million)
2. Provides meaningful context (is this high/low historically? trending up/down?)
3. Answers the user's actual question directly
4. Avoids jargon - write for a general audience
5. Be fact-based. You CAN characterize things as "strong", "weak", "cooling", etc. - but only if the data supports it. If signals are mixed (e.g., slowing job growth but still-low unemployment), acknowledge the mixed picture honestly rather than cherry-picking one narrative.
6. For employment/payroll data: Focus on job GROWTH, not total levels. If monthly_job_change, avg_monthly_change_3mo, and avg_monthly_change_12mo are provided, mention: (a) the latest month's job gain/loss, (b) the 3-month average, and (c) the 12-month average. These are in thousands, so 150.0 = 150,000 jobs. Context: The economy needs ~100-150K jobs/month to keep up with population growth. If the 3-month average is negative or well below the 12-month average, that's a cooling signal worth noting.
7. IMPORTANT: EVERY CHART MUST HAVE AN EXPLANATORY BULLET. If multiple series are shown, provide a bullet point for EACH one explaining what it measures and why it matters. Don't just focus on one chart - acknowledge all the data being presented.

CRITICAL DATE RULE: You MUST use the exact dates from the "latest_date" field in the DATA SUMMARY above. Do NOT guess or hallucinate dates. If the data says "2025-12-01", write "December 2025". NEVER write a different year than what the data shows.

CRITICAL: Do NOT start with meta-commentary like "I notice the data..." or "The data provided shows..." or "Looking at the data...". Just answer the question directly using the data. Start with the answer, not with observations about what data you have.

Keep it to 4-6 concise sentences if multiple series are shown. Do not use bullet points. Just return the explanation text, nothing else."""

    url = 'https://api.anthropic.com/v1/messages'
    payload = {
        'model': 'claude-opus-4-5-20251101',
        'max_tokens': 300,
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
            return improved if improved else original_explanation
    except Exception as e:
        return original_explanation


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
    """Make a request to the FRED API."""
    params['api_key'] = FRED_API_KEY
    params['file_type'] = 'json'
    url = f"{FRED_BASE}/{endpoint}?{urlencode(params)}"
    try:
        req = Request(url, headers={'User-Agent': 'EconStats/1.0'})
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e)}


def search_series(query: str, limit: int = 5) -> list:
    """Search FRED for series matching the query."""
    # Try popularity-ordered search first
    data = fred_request('series/search', {
        'search_text': query,
        'limit': limit,
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
            'limit': limit,
            'order_by': 'popularity',
            'sort_order': 'desc'
        })
        results = data.get('seriess', [])

    return results


def get_series_info(series_id: str) -> dict:
    """Get metadata for a series."""
    data = fred_request('series', {'series_id': series_id})
    series_list = data.get('seriess', [])
    return series_list[0] if series_list else {}


def get_observations(series_id: str, years: int = None) -> tuple:
    """Get observations for a series."""
    params = {'series_id': series_id, 'limit': 10000, 'sort_order': 'asc'}
    if years:
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime('%Y-%m-%d')
        params['observation_start'] = start_date

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

    data = fred_request('series/observations', params)
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


def calculate_yoy(dates: list, values: list) -> tuple:
    """Calculate year-over-year percent change."""
    if len(dates) < 13:
        return dates, values

    date_to_value = dict(zip(dates, values))
    yoy_dates, yoy_values = [], []

    for i, date_str in enumerate(dates[12:], 12):
        date = datetime.strptime(date_str, '%Y-%m-%d')
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


def create_chart(series_data: list, combine: bool = False, chart_type: str = 'line') -> go.Figure:
    """Create a Plotly chart with recession shading.

    Args:
        series_data: List of (series_id, dates, values, info) tuples
        combine: Whether to combine all series on one chart
        chart_type: 'line', 'bar', or 'area'
    """
    colors = ['#0066cc', '#cc3300', '#009933', '#9933cc']

    all_dates = []
    for _, dates, _, _ in series_data:
        all_dates.extend(dates)
    if not all_dates:
        return go.Figure()
    min_date, max_date = min(all_dates), max(all_dates)

    if combine or len(series_data) == 1:
        fig = go.Figure()
        for i, (series_id, dates, values, info) in enumerate(series_data):
            name = info.get('name', info.get('title', series_id))
            if len(name) > 50:
                name = name[:47] + "..."

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

        unit = series_data[0][3].get('unit', series_data[0][3].get('units', ''))
        fig.update_layout(
            template='plotly_white',
            hovermode='x unified',
            showlegend=len(series_data) > 1,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            margin=dict(l=60, r=20, t=20, b=60),
            yaxis_title=unit[:30] if len(unit) > 30 else unit,
            xaxis=dict(
                tickformat='%Y',
                gridcolor='#e5e5e5',
                type='date',
                rangeslider=dict(visible=True, thickness=0.05),
            ),
            yaxis=dict(gridcolor='#e5e5e5'),
            height=350,
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


def main():
    st.set_page_config(page_title="EconStats", page_icon="", layout="centered")

    st.markdown("""
    <style>
    /* Color palette: Primary #2563eb, Secondary #4B5563, Accent #22C55E, Warning #F59E0B */
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+Pro:ital,wght@0,400;0,600;1,400&display=swap');
    .stApp {
        font-family: 'Source Serif Pro', Georgia, serif;
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
        color: #1a1a2e !important;
        min-height: 100vh;
    }
    .stApp p, .stApp span, .stApp div, .stApp li, .stApp label { color: #1a1a2e; }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: #1a1a2e !important; }
    h1 {
        font-weight: 300 !important;
        font-style: italic !important;
        text-align: center;
        font-size: 3.5rem !important;
        letter-spacing: -1px;
    }
    .subtitle { text-align: center; color: #555; margin-top: -10px; margin-bottom: 20px; font-size: 1.1rem; }
    .header-divider { border-bottom: 1px solid #e5e7eb; margin-bottom: 25px; padding-bottom: 15px; }
    .narrative-box { background: #fff; border: 1px solid #e5e7eb; padding: 20px 25px; border-radius: 6px; margin-bottom: 20px; }
    .narrative-box p { color: #1f2937; line-height: 1.7; margin-bottom: 10px; }
    .narrative-box:empty { display: none; }
    /* Hide empty Streamlit containers */
    .stMarkdown:empty, div[data-testid="stVerticalBlock"]:empty { display: none !important; }
    div[data-testid="stForm"] { border: none !important; padding: 0 !important; }
    .highlight { font-weight: 600; color: #1F4FD8; }
    .up { color: #22C55E; font-weight: 600; }
    .down { color: #DC2626; font-weight: 600; }
    .caution { color: #F59E0B; font-weight: 600; }
    .chart-section { background: #fff; border: 1px solid #e5e7eb; border-radius: 6px; margin-bottom: 20px; overflow: hidden; }
    .chart-header { padding: 15px 20px; border-bottom: 1px solid #e5e7eb; }
    .chart-title { font-size: 1.1rem; color: #111827; margin-bottom: 10px; font-weight: 600; }
    .chart-bullets { color: #4B5563; font-size: 0.95rem; margin-left: 20px; }
    .chart-bullets li { margin-bottom: 4px; }
    .source-line { padding: 10px 20px; border-top: 1px solid #e5e7eb; font-size: 0.85rem; color: #6B7280; background: #f9fafb; }
    .ai-explanation { font-style: italic; color: #374151; padding: 10px 15px; background: #f0f7ff; border-left: 3px solid #1F4FD8; margin-bottom: 15px; }
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
    /* Category pill buttons - default state */
    .stButton button:not([kind="primary"]) {
        color: #344054 !important;
        background-color: white !important;
        border: 1.5px solid #d0d5dd !important;
        border-radius: 25px !important;
        padding: 0.6rem 1.5rem !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
    }
    .stButton button:not([kind="primary"]):hover {
        border-color: #2563eb !important;
        color: #2563eb !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15) !important;
        background-color: white !important;
    }

    /* Example queries section */
    .examples-header {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #6b7280;
        margin: 1.5rem 0 0.75rem 0;
        font-weight: 600;
        font-style: normal !important;
        text-align: center;
    }
    .example-query {
        padding: 0.8rem 1rem;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.15s ease;
        font-size: 0.9rem;
        color: #475569;
        margin-bottom: 0.5rem;
    }
    .example-query:hover {
        background: #eff6ff;
        border-color: #bfdbfe;
        color: #1e40af;
    }
    /* Example query buttons - override pill style */
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
        transform: none !important;
        box-shadow: none !important;
    }

    /* Helper text under search */
    .helper-text {
        text-align: center;
        color: #6b7280;
        font-size: 0.9rem;
        margin-top: 0.5rem;
        font-style: normal !important;
    }

    /* Search bar - clean box design matching mockup */
    .search-wrapper {
        margin: 20px 0 10px 0;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border-radius: 12px;
        overflow: hidden;
        background: white;
    }
    div[data-testid="stTextInput"] input {
        background: #ffffff !important;
        border: none !important;
        border-radius: 12px !important;
        font-size: 1rem !important;
        padding: 1.1rem 1.5rem !important;
        box-shadow: none !important;
        transition: none !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }
    div[data-testid="stTextInput"] input::placeholder {
        color: #9ca3af !important;
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

    st.markdown("<h1 style='margin-bottom: 0;'>EconStats</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle' style='margin-bottom: 10px;'>U.S. Economic Data with Context</p>", unsafe_allow_html=True)

    # About section in sidebar
    with st.sidebar:
        st.markdown("### About EconStats.org")
        st.markdown("""
        Government economic data is free—but too hard for most people to access and understand.
        EconStats uses AI to change that, helping anyone draw insights directly from the numbers.

        We're starting with FRED's API and working to add more data sources: productivity
        statistics buried in the back pages of the BLS website, prices of specific consumer
        items, consumer credit data, and beyond.

        **This is just the beginning.**

        Contact [waldman1@stanford.edu](mailto:waldman1@stanford.edu) with feedback or ideas.
        """)

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

    # Quick search buttons - single compact row
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
    with col1:
        if st.button("Jobs", use_container_width=True, key="btn_jobs"):
            st.session_state.pending_query = "job market"
    with col2:
        if st.button("Inflation", use_container_width=True, key="btn_inflation"):
            st.session_state.pending_query = "inflation"
    with col3:
        if st.button("GDP", use_container_width=True, key="btn_gdp"):
            st.session_state.pending_query = "gdp growth"
    with col4:
        if st.button("Rates", use_container_width=True, key="btn_rates"):
            st.session_state.pending_query = "interest rates"
    with col5:
        if st.button("Recession?", use_container_width=True, key="btn_recession"):
            st.session_state.pending_query = "are we in a recession"

    # Default timeframe - show all available data for full historical context
    years = None

    # Handle pending query from button clicks
    query = None
    if 'pending_query' in st.session_state and st.session_state.pending_query:
        query = st.session_state.pending_query
        st.session_state.pending_query = None

    # UI Mode: Search Bar (default) or Chat Mode (for follow-ups)
    if not st.session_state.chat_mode:
        # SEARCH BAR MODE - single clean input field (no button needed, Enter submits)
        st.markdown('<div class="search-wrapper">', unsafe_allow_html=True)
        text_query = st.text_input(
            "Search",
            placeholder="Ask about the economy... (press Enter)",
            label_visibility="collapsed",
            key="search_input"
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # Helper text
        st.markdown('<p class="helper-text">Ask questions in plain English — we\'ll pull the latest economic data and explain what it means.</p>', unsafe_allow_html=True)

        # Example queries section - only show when no results yet
        if not st.session_state.last_query:
            st.markdown('<p class="examples-header">Try these questions</p>', unsafe_allow_html=True)

            # Example query buttons in a grid
            example_queries = [
                "How is the economy?",
                "Are wages keeping up with inflation?",
                "Is the labor market cooling off?",
                "How tight is the job market right now?",
                "Is rent inflation coming down yet?",
                "Compare the job market to pre-pandemic"
            ]
            cols = st.columns(2)
            for i, eq in enumerate(example_queries):
                with cols[i % 2]:
                    if st.button(eq, key=f"example_{i}", use_container_width=True):
                        st.session_state.pending_query = eq
                        st.rerun()

        if not query:
            query = text_query
    else:
        # CHAT MODE - for follow-up questions
        # Show chat history
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                if msg["role"] == "user":
                    st.write(msg["content"])
                else:
                    if msg.get("explanation"):
                        st.markdown(f"**{msg['explanation']}**")

        # Chat input at the bottom
        if not query:
            query = st.chat_input("Ask a follow-up question...")

        # Option to exit chat mode
        if st.button("← New Search", key="exit_chat"):
            st.session_state.chat_mode = False
            st.session_state.messages = []
            st.session_state.last_query = ''
            st.session_state.last_series = []
            st.rerun()

    if query:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": query})

        # Only show chat bubble in chat mode
        if st.session_state.chat_mode:
            with st.chat_message("user"):
                st.write(query)

        # Build context from previous query for follow-up detection
        previous_context = None
        if st.session_state.last_query and st.session_state.last_series:
            previous_context = {
                'query': st.session_state.last_query,
                'series': st.session_state.last_series,
                'series_names': st.session_state.last_series_names
            }

        # First check pre-computed query plans (fast, no API call needed)
        # Uses smart matching: normalization + fuzzy matching for typos
        precomputed_plan = find_query_plan(query)

        # Check if this looks like a follow-up command (transformation, time range, etc.)
        local_parsed = parse_followup_command(query, st.session_state.last_series) if previous_context else None

        if precomputed_plan and not local_parsed:
            # Use pre-computed plan - instant response! (even if there's previous context)
            interpretation = {
                'series': precomputed_plan.get('series', []),
                'explanation': precomputed_plan.get('explanation', f'Showing data for: {query}'),
                'show_yoy': precomputed_plan.get('show_yoy', False),
                'show_yoy_series': precomputed_plan.get('show_yoy_series', []),
                'combine_chart': precomputed_plan.get('combine_chart', False),
                'show_mom': False,
                'show_avg_annual': False,
                'is_followup': False,
                'add_to_previous': False,
                'keep_previous_series': False,
                'search_terms': [],
                'used_precomputed': True,
                'show_payroll_changes': precomputed_plan.get('show_payroll_changes', False),
                'chart_groups': precomputed_plan.get('chart_groups', None),
            }
        elif local_parsed:
            # Try local parser for common follow-up commands (no API call needed)
            interpretation = {
                'series': local_parsed.get('series', []),
                'explanation': local_parsed.get('explanation', ''),
                'show_yoy': local_parsed.get('show_yoy', False),
                'show_mom': local_parsed.get('show_mom', False),
                'show_avg_annual': local_parsed.get('show_avg_annual', False),
                'combine_chart': local_parsed.get('combine_chart', False),
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
            }
        else:
            # Fall back to Claude for unknown queries or follow-ups
            with st.spinner("Analyzing your question with AI economist..."):
                interpretation = call_claude(query, previous_context)
            interpretation['used_precomputed'] = False

        ai_explanation = interpretation.get('explanation', '')
        series_to_fetch = list(interpretation.get('series', []))  # Copy the list
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

        # Handle chart type from follow-up commands (e.g., "bar chart")
        chart_type = interpretation.get('chart_type', 'line')

        # Handle normalize from follow-up commands (e.g., "normalize", "index to 100")
        normalize = interpretation.get('normalize', False)

        # Handle percent change from start (cumulative change)
        pct_change_from_start = interpretation.get('pct_change_from_start', False)

        # Handle chart groups (multiple charts with different series/transformations)
        chart_groups = interpretation.get('chart_groups', None)

        # Handle date filtering (e.g., pre-covid filter)
        filter_end_date = interpretation.get('filter_end_date')

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
            with st.spinner(f"Searching FRED for: {', '.join(search_terms[:2])}..."):
                for term in search_terms[:3]:
                    results = search_series(term, limit=3)
                    for r in results:
                        if r['id'] not in series_to_fetch and len(series_to_fetch) < 4:
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
            with st.spinner(f"Searching FRED directly for: {query}..."):
                results = search_series(query, limit=4)
                for r in results:
                    series_to_fetch.append(r['id'])
                if series_to_fetch:
                    ai_explanation = f"Search results for: {query}"

        if not series_to_fetch:
            st.warning("Could not find relevant economic data. Try rephrasing your question or being more specific.")
            log_query(query, [], "no_results")
            st.stop()

        # Log the query for analytics
        source = "precomputed" if interpretation.get('used_precomputed') else "claude"
        log_query(query, series_to_fetch[:4], source)

        # Fetch data
        series_data = []
        raw_series_data = {}  # Store raw data for chart_groups
        series_names_fetched = []
        with st.spinner("Fetching data from FRED..."):
            for series_id in series_to_fetch[:4]:
                dates, values, info = get_observations(series_id, years)
                if dates and values:
                    # Apply date filter if specified (e.g., pre-covid filter)
                    if filter_end_date:
                        filtered_dates, filtered_values = [], []
                        for d, v in zip(dates, values):
                            if d <= filter_end_date:
                                filtered_dates.append(d)
                                filtered_values.append(v)
                        dates, values = filtered_dates, filtered_values
                        if not dates:
                            continue  # Skip series if no data in range

                    db_info = SERIES_DB.get(series_id, {})
                    series_name = info.get('name', info.get('title', series_id))
                    series_names_fetched.append(series_name)

                    # Store raw data for chart_groups (before any transformations)
                    if chart_groups:
                        raw_series_data[series_id] = (series_id, list(dates), list(values), dict(info))

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

        if not series_data:
            st.error("No data available for the requested series.")
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

        # Call economist reviewer agent for ALL queries to ensure quality explanations
        if series_data:
            with st.spinner("Economist reviewing analysis..."):
                ai_explanation = call_economist_reviewer(query, series_data, ai_explanation)

        # Store ALL context atomically for follow-up queries (prevents race conditions)
        st.session_state.last_query = query
        st.session_state.last_series = series_to_fetch[:4]
        st.session_state.last_series_names = series_names_fetched
        st.session_state.last_series_data = series_data
        st.session_state.last_chart_type = chart_type
        st.session_state.last_combine = combine
        st.session_state.last_explanation = ai_explanation

        # Display response in chat message format
        with st.chat_message("assistant"):
            # Narrative summary - only render if there's content
            has_narrative_content = ai_explanation or any(values for _, _, values, _ in series_data)
            if has_narrative_content:
                st.markdown("<div class='narrative-box'>", unsafe_allow_html=True)
                st.markdown("<h3 style='margin-top:0'>Summary</h3>", unsafe_allow_html=True)

                if ai_explanation:
                    st.markdown(f"<div class='ai-explanation'>{ai_explanation}</div>", unsafe_allow_html=True)

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

            # Sentence 3: Pre-COVID comparison (Feb 2020) for seasonally adjusted data
            if db_info.get('sa', False):
                try:
                    covid_idx = next(i for i, d in enumerate(dates) if d >= '2020-02-01')
                    pre_covid = values[covid_idx]
                    if data_type in ['rate', 'spread', 'growth_rate']:
                        diff = latest - pre_covid
                        if abs(diff) >= 0.2:
                            if diff > 0.2:
                                sentences.append(f"This is {abs(diff):.1f} pp above the {pre_covid:.1f}% level from February 2020, just before the pandemic.")
                            elif diff < -0.2:
                                sentences.append(f"This is {abs(diff):.1f} pp below the {pre_covid:.1f}% level from February 2020, just before the pandemic.")
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
                            sentences.append(f"Employment is {diff_str} {direction} the pre-pandemic level (Feb 2020).")
                    elif pre_covid != 0:
                        pct_diff = ((latest - pre_covid) / abs(pre_covid)) * 100
                        if abs(pct_diff) >= 3:
                            if pct_diff > 3:
                                if data_type == 'price':
                                    sentences.append(f"This is {pct_diff:.0f}% above the ${pre_covid:.2f} level from February 2020, just before the pandemic.")
                                else:
                                    sentences.append(f"This is {pct_diff:.0f}% above the {format_number(pre_covid, unit)} level from February 2020, just before the pandemic.")
                            elif pct_diff < -3:
                                if data_type == 'price':
                                    sentences.append(f"This is {abs(pct_diff):.0f}% below the ${pre_covid:.2f} level from February 2020, just before the pandemic.")
                                else:
                                    sentences.append(f"This is {abs(pct_diff):.0f}% below the {format_number(pre_covid, unit)} level from February 2020, just before the pandemic.")
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

                # Render title using native Streamlit (more reliable)
                st.markdown(f"**{chart_title}**")

                # Generate bullets for each series
                for sid, d, v, i in group_data:
                    desc = generate_chart_description(sid, d, v, i)
                    if desc:
                        series_name = generate_chart_title(sid, i)[:30]
                        st.markdown(f"- **{series_name}:** {desc}")

                # Always combine for groups with multiple series
                combine_group = len(group_data) > 1
                fig = create_chart(group_data, combine=combine_group, chart_type=chart_type)
                st.plotly_chart(fig, use_container_width=True)

                source = group_data[0][3].get('source', 'FRED') if group_data else 'FRED'
                transform_note = ""
                if group_show_yoy:
                    transform_note = " Showing year-over-year percent change."
                elif group_pct_from_start:
                    transform_note = " Indexed to start of period."
                st.markdown(f"<div class='source-line'>Source: {source}.{transform_note} Shaded areas indicate U.S. recessions (NBER).</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

        # Regular Charts (when not using chart_groups)
        elif combine and len(series_data) > 1:
            st.markdown("<div class='chart-section'>", unsafe_allow_html=True)

            # Generate dynamic chart title and descriptions
            chart_title = ' vs '.join([generate_chart_title(sid, info)[:40] for sid, _, _, info in series_data])

            # Render title using native Streamlit (more reliable)
            st.markdown(f"**{chart_title}**")

            # Generate bullet points for each series
            for sid, d, v, i in series_data:
                desc = generate_chart_description(sid, d, v, i)
                if desc:
                    series_name = generate_chart_title(sid, i)[:30]
                    st.markdown(f"- **{series_name}:** {desc}")

            fig = create_chart(series_data, combine=True, chart_type=chart_type)
            st.plotly_chart(fig, use_container_width=True)

            source = series_data[0][3].get('source', 'FRED')
            st.markdown(f"<div class='source-line'>Source: {source}. Shaded areas indicate U.S. recessions (NBER).</div>", unsafe_allow_html=True)
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
                    # Show both monthly changes (bar) and total level (line) side by side
                    payroll_bullets = [
                        "Monthly change in thousands of jobs. The economy typically needs 100-150K new jobs/month to absorb population growth.",
                        "Total employment level in thousands. This is the headline 'jobs number' from the BLS Employment Situation report."
                    ]
                    payroll_bullets_html = ''.join([f'<li>{b}</li>' for b in payroll_bullets])
                    st.markdown(f"""
                    <div class='chart-header'>
                        <div class='chart-title'>Nonfarm Payrolls</div>
                        <ul class='chart-bullets'>{payroll_bullets_html}</ul>
                    </div>
                    """, unsafe_allow_html=True)

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
                        st.plotly_chart(fig_bar, use_container_width=True)

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
                        st.plotly_chart(fig_line, use_container_width=True)
                else:
                    # Generate dynamic chart title and description
                    chart_title = generate_chart_title(series_id, info)
                    chart_desc = generate_chart_description(series_id, dates, values, info)

                    # Get educational bullet from SERIES_DB if available
                    static_bullets = db_info.get('bullets', [])
                    educational_bullet = static_bullets[0] if static_bullets else None

                    # Render title using native Streamlit (more reliable)
                    st.markdown(f"**{chart_title}**")

                    # Combine dynamic trend + educational context as bullet list
                    bullet_items = []
                    if chart_desc:
                        bullet_items.append(f"**Current:** {chart_desc}")
                    if educational_bullet and educational_bullet.strip():
                        edu_text = educational_bullet[:300] + "..." if len(educational_bullet) > 300 else educational_bullet
                        bullet_items.append(edu_text)

                    if bullet_items:
                        for bullet in bullet_items:
                            st.markdown(f"- {bullet}")

                    fig = create_chart([(series_id, dates, values, info)], combine=False, chart_type=chart_type)
                    st.plotly_chart(fig, use_container_width=True)

                st.markdown(f"<div class='source-line'>Source: {source}. {sa_note}{transform_note} Shaded areas indicate U.S. recessions (NBER).</div>", unsafe_allow_html=True)
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
            # Query interpretation method
            if interpretation.get('used_precomputed'):
                st.write("**Method:** Pre-computed query plan (instant)")
            elif interpretation.get('used_local_parser'):
                st.write("**Method:** Local follow-up parser (instant)")
            else:
                st.write("**Method:** Claude AI interpretation")

            st.write(f"**Series fetched:** {', '.join(series_to_fetch)}")
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

        # Follow-up suggestions
        st.markdown("---")
        st.markdown("**Try a follow-up:**")
        suggestions = []
        if len(series_data) > 1:
            suggestions.append('"combine" - overlay on one chart')
            suggestions.append('"normalize" - index to 100 for comparison')
        suggestions.append('"year over year" - show % change')
        suggestions.append('"last 5 years" - zoom to recent data')
        suggestions.append('"add unemployment" - add another series')
        suggestions.append('"bar chart" - switch visualization')
        st.markdown('<span style="color: #666; font-size: 0.9em;">' + ' &bull; '.join(suggestions[:4]) + '</span>', unsafe_allow_html=True)

        # Inline follow-up input (auto-pivot to chat experience)
        followup_query = st.text_input(
            "Follow-up",
            placeholder="Type a follow-up: 'last 5 years', 'add unemployment', 'year over year'...",
            label_visibility="collapsed",
            key="followup_input"
        )
        if followup_query:
            st.session_state.chat_mode = True
            st.session_state.pending_query = followup_query
            st.rerun()

        # Deep Analysis section (only show if dependencies are available)
        if DEEP_ANALYSIS_AVAILABLE:
            st.markdown("---")
            deep_analysis_key = f"deep_analysis_{hash(query)}"
            if deep_analysis_key not in st.session_state:
                st.session_state[deep_analysis_key] = {'running': False, 'result': None}

            col_deep1, col_deep2 = st.columns([2, 4])
            with col_deep1:
                if st.button("🔬 Deep Analysis", key=f"deep_btn_{hash(query)}",
                            disabled=st.session_state[deep_analysis_key]['running']):
                    st.session_state[deep_analysis_key]['running'] = True
                    st.rerun()

            with col_deep2:
                st.markdown("<span style='color: #666; font-size: 0.85em;'>Get multi-step AI analysis with real-time data</span>", unsafe_allow_html=True)

            # Run deep analysis if triggered
            if st.session_state[deep_analysis_key]['running'] and not st.session_state[deep_analysis_key]['result']:
                with st.spinner("🔬 Running deep analysis... (fetching data, analyzing trends)"):
                    try:
                        analysis_result = run_deep_analysis(query, verbose=False)
                        st.session_state[deep_analysis_key]['result'] = analysis_result
                        st.session_state[deep_analysis_key]['running'] = False
                        st.rerun()
                    except Exception as e:
                        st.session_state[deep_analysis_key]['result'] = f"Analysis failed: {str(e)}"
                        st.session_state[deep_analysis_key]['running'] = False

            # Display deep analysis result
            if st.session_state[deep_analysis_key]['result']:
                st.markdown("### 🔬 Deep Analysis")
                st.markdown(f"<div style='background-color: #f8f9fa; padding: 1rem; border-radius: 8px; border-left: 4px solid #667eea;'>{st.session_state[deep_analysis_key]['result']}</div>", unsafe_allow_html=True)

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

    elif not query and st.session_state.last_series_data:
        # Display cached results from previous query
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
            st.plotly_chart(fig, use_container_width=True)
        else:
            for series_id, dates, values, info in series_data:
                fig = create_chart([(series_id, dates, values, info)], combine=False, chart_type=chart_type)
                st.plotly_chart(fig, use_container_width=True)

        # Follow-up suggestions
        st.markdown("---")
        st.markdown("**Try a follow-up:**")
        suggestions = ['"year over year"', '"last 5 years"', '"add unemployment"', '"bar chart"']
        st.markdown('<span style="color: #666; font-size: 0.9em;">' + ' &bull; '.join(suggestions) + '</span>', unsafe_allow_html=True)

        # Inline follow-up input for cached results
        cached_followup = st.text_input(
            "Follow-up",
            placeholder="Type a follow-up: 'last 5 years', 'add unemployment', 'year over year'...",
            label_visibility="collapsed",
            key="cached_followup_input"
        )
        if cached_followup:
            st.session_state.chat_mode = True
            st.session_state.pending_query = cached_followup
            st.rerun()


if __name__ == "__main__":
    main()
