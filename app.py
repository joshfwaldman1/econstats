#!/usr/bin/env python3
"""
EconStats - Streamlit Economic Data Dashboard
Ask questions in plain English and get charts of economic data from FRED.
Incorporates economist intuitions for proper data selection and presentation.
"""

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
            'gdp': ['A191RL1Q225SBEA'],
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
            'oil': ['DCOILWTICO'],
            'oil prices': ['DCOILWTICO'],
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

# Import pre-computed query plans (314 common queries)
try:
    from query_plans import QUERY_PLANS
except ImportError:
    QUERY_PLANS = {}

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
        import gspread
        from google.oauth2.service_account import Credentials

        if not hasattr(st, 'secrets') or 'gcp_service_account' not in st.secrets:
            return True  # Logged to console, that's enough

        creds_dict = dict(st.secrets['gcp_service_account'])
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)

        sheet_url = st.secrets.get('FEEDBACK_SHEET_URL', '')
        if sheet_url:
            sheet = client.open_by_url(sheet_url).sheet1
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


def generate_narrative_context(dates: list, values: list, data_type: str = 'level') -> dict:
    """
    Generate smart narrative context from time series data.
    Returns factual comparisons without prescriptive claims.
    """
    if not dates or not values or len(values) < 2:
        return {}

    context = {}
    latest = values[-1]
    latest_date = dates[-1]
    current_year = datetime.now().year

    try:
        # Helper: calculate average for a given year
        def year_average(year):
            year_vals = [v for d, v in zip(dates, values)
                        if d.startswith(str(year))]
            return sum(year_vals) / len(year_vals) if year_vals else None

        # 1. Compare to 2019 average (pre-COVID baseline)
        avg_2019 = year_average(2019)
        if avg_2019 is not None:
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
        prior_year = current_year - 1
        # Only use prior year if we have enough data from current year (at least 2 months in)
        latest_date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
        if latest_date_obj.year == current_year and latest_date_obj.month >= 3:
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

        if recent_values:
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

    # Employment - Household Survey (CPS)
    'UNRATE': {
        'name': 'Unemployment Rate (U-3)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'frequency': 'monthly',
        'data_type': 'rate',
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
        'yoy_unit': 'Percent Change (Year-over-Year)',
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
        'yoy_unit': 'Percent Change (Year-over-Year)',
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
        'yoy_unit': 'Percent Change (Year-over-Year)',
        'bullets': [
            'Housing costs (rent and owners\' equivalent rent) make up roughly one-third of the CPI basket—the largest single component. When shelter inflation surges, it pulls overall inflation higher and is felt acutely by household budgets.',
            'Critical caveat: CPI shelter lags actual market rents by approximately 12 months due to how the BLS measures it (surveying existing leases that turn over slowly). This means market rent declines won\'t show up in CPI shelter for many months. Economists watching for inflation to ease look at private rent indexes like Zillow or Apartment List for leading signals.'
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
        'yoy_unit': 'Percent Change (Year-over-Year)',
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
        'yoy_unit': 'Percent Change (Year-over-Year)',
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
        'name': 'Real GDP Growth Rate',
        'unit': 'Percent Change (Quarterly, Annualized)',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'frequency': 'quarterly',
        'data_type': 'growth_rate',
        'bullets': [
            'This measures how fast the economy is expanding or contracting, expressed as an annualized rate (what growth would be if the quarterly pace continued for a full year). It\'s the headline GDP number reported in the news.',
            'Historical context: Trend U.S. growth is around 2% annually. Growth above 3% is considered robust; above 4% is a boom. Negative growth signals contraction. Consumer spending drives roughly 70% of GDP, so consumer health is paramount. Note: GDP is released in three estimates (advance, second, third) and can be significantly revised.'
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

    # Housing
    'CSUSHPINSA': {
        'name': 'S&P/Case-Shiller National Home Price Index',
        'unit': 'Index Jan 2000=100',
        'source': 'S&P Dow Jones Indices LLC',
        'sa': False,
        'frequency': 'monthly',
        'data_type': 'index',
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
    # Economy overview - show the big picture
    'economy': {'series': ['A191RL1Q225SBEA', 'UNRATE', 'CPIAUCSL'], 'combine': False},
    'how is the economy': {'series': ['A191RL1Q225SBEA', 'UNRATE', 'CPIAUCSL'], 'combine': False},
    'economic overview': {'series': ['A191RL1Q225SBEA', 'UNRATE', 'CPIAUCSL'], 'combine': False},
    'recession': {'series': ['A191RL1Q225SBEA', 'UNRATE', 'T10Y2Y'], 'combine': False},

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

    # GDP
    'gdp': {'series': ['GDPC1'], 'combine': False},
    'gdp growth': {'series': ['A191RL1Q225SBEA'], 'combine': False},
    'economic growth': {'series': ['A191RL1Q225SBEA'], 'combine': False},

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
    'oil': {'series': ['DCOILWTICO'], 'combine': False},
    'oil prices': {'series': ['DCOILWTICO'], 'combine': False},
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
1. START SIMPLE: Return 1-2 series for simple questions, max 3-4 for complex ones.
2. USE SEASONALLY ADJUSTED DATA by default.
3. For topics you don't know exact series for, provide SPECIFIC search terms that would find them in FRED.

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
- GDPC1 = Real GDP
- A191RL1Q225SBEA = Real GDP growth rate
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

## RESPONSE FORMAT
Return JSON only:
{
  "series": ["SERIES_ID1", "SERIES_ID2"],
  "search_terms": ["specific search term 1", "specific search term 2"],
  "explanation": "Brief explanation of why these series answer the question",
  "show_yoy": false,
  "combine_chart": false
}

CRITICAL: If you're not 100% sure of exact series IDs, ALWAYS include search_terms. It's better to search than guess wrong.

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
        'model': 'claude-sonnet-4-20250514',
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
        latest = values[-1]
        latest_date = dates[-1]

        # Calculate some basic stats
        if len(values) >= 12:
            year_ago_val = values[-12] if len(values) >= 12 else values[0]
            yoy_change = latest - year_ago_val
        else:
            yoy_change = None

        # Get min/max in recent period
        recent_vals = values[-60:] if len(values) >= 60 else values  # Last 5 years
        recent_min = min(recent_vals)
        recent_max = max(recent_vals)

        summary = {
            'series_id': series_id,
            'name': name,
            'latest_value': round(latest, 2),
            'latest_date': latest_date,
            'yoy_change': round(yoy_change, 2) if yoy_change else None,
            'recent_5yr_min': round(recent_min, 2),
            'recent_5yr_max': round(recent_max, 2),
        }
        data_summary.append(summary)

    prompt = f"""You are an expert economist reviewing data for a user query. Your job is to write a clear, insightful 2-3 sentence explanation.

USER QUERY: {query}

DATA SUMMARY:
{json.dumps(data_summary, indent=2)}

INITIAL EXPLANATION: {original_explanation}

Write an improved explanation that:
1. States the current values clearly with proper formatting
2. Provides meaningful context (is this high/low historically? trending up/down?)
3. Answers the user's actual question directly
4. Avoids jargon - write for a general audience
5. Is factual and objective - no speculation or predictions

Keep it to 2-3 concise sentences. Do not use bullet points. Just return the explanation text, nothing else."""

    url = 'https://api.anthropic.com/v1/messages'
    payload = {
        'model': 'claude-sonnet-4-20250514',
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
    for rec in RECESSIONS:
        if rec['end'] >= min_date and rec['start'] <= max_date:
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
            xaxis=dict(tickformat='%Y', gridcolor='#e5e5e5'),
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

    fig.update_xaxes(tickformat='%Y', tickangle=-45)
    return fig


def format_number(n):
    """Format number for display."""
    if n is None or (isinstance(n, float) and (n != n)):
        return 'N/A'
    if abs(n) >= 1e12:
        return f"{n / 1e12:.2f} trillion"
    if abs(n) >= 1e9:
        return f"{n / 1e9:.2f} billion"
    if abs(n) >= 1e6:
        return f"{n / 1e6:.2f} million"
    if abs(n) >= 1e3:
        return f"{n:,.1f}"
    if abs(n) < 10:
        return f"{n:.2f}"
    return f"{n:.1f}"


def main():
    st.set_page_config(page_title="EconStats", page_icon="", layout="centered")

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+Pro:wght@400;600&display=swap');
    .stApp { font-family: 'Source Serif Pro', Georgia, serif; background-color: #fafafa; }
    h1 { font-weight: 400 !important; text-align: center; }
    .subtitle { text-align: center; color: #666; margin-top: -15px; margin-bottom: 20px; }
    .header-divider { border-bottom: 1px solid #ddd; margin-bottom: 25px; padding-bottom: 15px; }
    .narrative-box { background: #fff; border: 1px solid #e0e0e0; padding: 20px 25px; border-radius: 4px; margin-bottom: 20px; }
    .narrative-box p { color: #333; line-height: 1.7; margin-bottom: 10px; }
    .highlight { font-weight: 600; }
    .up { color: #228b22; }
    .down { color: #cc0000; }
    .chart-section { background: #fff; border: 1px solid #e0e0e0; border-radius: 4px; margin-bottom: 20px; overflow: hidden; }
    .chart-header { padding: 15px 20px; border-bottom: 1px solid #e0e0e0; }
    .chart-title { font-size: 1.1rem; color: #333; margin-bottom: 10px; }
    .chart-bullets { color: #555; font-size: 0.95rem; margin-left: 20px; }
    .chart-bullets li { margin-bottom: 4px; }
    .source-line { padding: 10px 20px; border-top: 1px solid #e0e0e0; font-size: 0.85rem; color: #666; background: #fafafa; }
    .ai-explanation { font-style: italic; color: #444; padding: 10px 15px; background: #f8f8f8; border-left: 3px solid #0066cc; margin-bottom: 15px; }
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

    # Quick search buttons - single compact row
    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1, 1])
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
    with col6:
        time_period = st.selectbox("Timeframe", list(TIME_PERIODS.keys()), index=3, label_visibility="collapsed")
        years = TIME_PERIODS[time_period]

    # Search input
    has_previous_query = st.session_state.last_query and len(st.session_state.last_query) > 0
    placeholder = "Ask a follow-up..." if has_previous_query else "Ask about the economy (e.g., inflation, jobs, GDP)"

    # Use session state to preserve query across reruns
    if 'search_query' not in st.session_state:
        st.session_state.search_query = ""

    query = st.text_input("Search", placeholder=placeholder, label_visibility="collapsed", key="search_input")
    search_clicked = st.button("Search", type="primary", use_container_width=True)

    # Handle pending query from button clicks
    if 'pending_query' in st.session_state and st.session_state.pending_query:
        query = st.session_state.pending_query
        search_clicked = True
        st.session_state.pending_query = None

    if query and search_clicked:
        # Build context from previous query for follow-up detection
        previous_context = None
        if st.session_state.last_query and st.session_state.last_series:
            previous_context = {
                'query': st.session_state.last_query,
                'series': st.session_state.last_series,
                'series_names': st.session_state.last_series_names
            }

        # First check pre-computed query plans (fast, no API call needed)
        query_lower = query.lower().strip()
        precomputed_plan = QUERY_PLANS.get(query_lower)

        if precomputed_plan and not previous_context:
            # Use pre-computed plan - instant response!
            interpretation = {
                'series': precomputed_plan.get('series', []),
                'explanation': precomputed_plan.get('explanation', f'Showing data for: {query}'),
                'show_yoy': precomputed_plan.get('show_yoy', False),
                'combine_chart': precomputed_plan.get('combine_chart', False),
                'show_mom': False,
                'show_avg_annual': False,
                'is_followup': False,
                'add_to_previous': False,
                'keep_previous_series': False,
                'search_terms': [],
                'used_precomputed': True
            }
        elif previous_context and (local_parsed := parse_followup_command(query, st.session_state.last_series)):
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
            }
        else:
            # Fall back to Claude for unknown queries or follow-ups
            with st.spinner("Analyzing your question with AI economist..."):
                interpretation = call_claude(query, previous_context)
            interpretation['used_precomputed'] = False

        ai_explanation = interpretation.get('explanation', '')
        series_to_fetch = list(interpretation.get('series', []))  # Copy the list
        combine = interpretation.get('combine_chart', False)
        show_yoy = interpretation.get('show_yoy', False)
        show_mom = interpretation.get('show_mom', False)
        show_avg_annual = interpretation.get('show_avg_annual', False)
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
            st.stop()

        # Fetch data
        series_data = []
        series_names_fetched = []
        with st.spinner("Fetching data from FRED..."):
            for series_id in series_to_fetch[:4]:
                dates, values, info = get_observations(series_id, years)
                if dates and values:
                    db_info = SERIES_DB.get(series_id, {})
                    series_name = info.get('name', info.get('title', series_id))
                    series_names_fetched.append(series_name)

                    # Apply transformations based on user request or series config
                    if show_mom and len(dates) > 1:
                        # User requested month-over-month
                        mom_dates, mom_values = calculate_mom(dates, values)
                        if mom_dates:
                            info_copy = dict(info)
                            info_copy['name'] = series_name + ' (MoM %)'
                            info_copy['unit'] = 'Percent Change (Month-over-Month)'
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
                    elif show_yoy and len(dates) > 12:
                        # User explicitly requested YoY
                        yoy_dates, yoy_values = calculate_yoy(dates, values)
                        if yoy_dates:
                            info_copy = dict(info)
                            info_copy['name'] = series_name + ' (YoY %)'
                            info_copy['unit'] = 'Percent Change (Year-over-Year)'
                            info_copy['is_yoy'] = True
                            series_data.append((series_id, yoy_dates, yoy_values, info_copy))
                        else:
                            series_data.append((series_id, dates, values, info))
                    elif db_info.get('show_yoy') and len(dates) > 12:
                        # Series default is to show YoY (like CPI)
                        yoy_dates, yoy_values = calculate_yoy(dates, values)
                        if yoy_dates:
                            info_copy = dict(info)
                            info_copy['name'] = db_info.get('yoy_name', series_name + ' (YoY %)')
                            info_copy['unit'] = db_info.get('yoy_unit', 'Percent Change (Year-over-Year)')
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

        # Store context for follow-up queries
        st.session_state.last_query = query
        st.session_state.last_series = series_to_fetch[:4]
        st.session_state.last_series_names = series_names_fetched
        st.session_state.last_series_data = series_data
        st.session_state.last_chart_type = chart_type
        st.session_state.last_combine = combine

        # Call economist reviewer agent to improve explanation (only for non-precomputed queries)
        used_precomputed = interpretation.get('used_precomputed', False)
        used_local_parser = interpretation.get('used_local_parser', False)
        if not used_precomputed and not used_local_parser and series_data:
            with st.spinner("Economist reviewing analysis..."):
                ai_explanation = call_economist_reviewer(query, series_data, ai_explanation)

        # Save explanation to session state
        st.session_state.last_explanation = ai_explanation

        # Narrative summary
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
                value_desc = f"<strong>{format_number(latest)}</strong>"

            # Build prose narrative with full sentences
            sentences = []

            # Sentence 1: Current value
            sentences.append(f"<span class='highlight'>{name}</span> is {value_desc} as of {latest_date_str}.")

            # Sentence 2: Year-over-year comparison with actual values
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
                    elif year_ago_val != 0:
                        pct = ((latest - year_ago_val) / abs(year_ago_val)) * 100
                        direction = 'up' if pct >= 0 else 'down'
                        css_class = 'up' if pct >= 0 else 'down'
                        if data_type == 'price':
                            sentences.append(f"That's <span class='{css_class}'>{direction} {abs(pct):.1f}%</span> from a year ago (${year_ago_val:.2f} in {year_ago_date}).")
                        else:
                            sentences.append(f"That's <span class='{css_class}'>{direction} {abs(pct):.1f}%</span> from a year ago ({format_number(year_ago_val)} in {year_ago_date}).")
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
                    elif pre_covid != 0:
                        pct_diff = ((latest - pre_covid) / abs(pre_covid)) * 100
                        if abs(pct_diff) >= 3:
                            if pct_diff > 3:
                                if data_type == 'price':
                                    sentences.append(f"This is {pct_diff:.0f}% above the ${pre_covid:.2f} level from February 2020, just before the pandemic.")
                                else:
                                    sentences.append(f"This is {pct_diff:.0f}% above the {format_number(pre_covid)} level from February 2020, just before the pandemic.")
                            elif pct_diff < -3:
                                if data_type == 'price':
                                    sentences.append(f"This is {abs(pct_diff):.0f}% below the ${pre_covid:.2f} level from February 2020, just before the pandemic.")
                                else:
                                    sentences.append(f"This is {abs(pct_diff):.0f}% below the {format_number(pre_covid)} level from February 2020, just before the pandemic.")
                except (StopIteration, IndexError):
                    pass

            # Sentence 4: Historical context (trend, highs/lows)
            smart_context = generate_narrative_context(dates, values, data_type)
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

        st.markdown("</div>", unsafe_allow_html=True)

        # Charts
        if combine and len(series_data) > 1:
            db_info = SERIES_DB.get(series_data[0][0], {})
            bullets = db_info.get('bullets', ['', ''])

            st.markdown("<div class='chart-section'>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='chart-header'>
                <div class='chart-title'>{' vs '.join([info.get('name', info.get('title', sid))[:40] for sid, _, _, info in series_data])}</div>
                <ul class='chart-bullets'>
                    <li>{bullets[0]}</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

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
                bullets = db_info.get('bullets', [f'FRED series: {series_id}', f"Unit: {info.get('unit', info.get('units', ''))}"])
                sa_note = "Seasonally adjusted." if db_info.get('sa', False) else "Not seasonally adjusted."
                transform_note = ""
                if info.get('is_yoy'):
                    transform_note = " Showing year-over-year percent change."
                elif info.get('is_mom'):
                    transform_note = " Showing month-over-month percent change."
                elif info.get('is_avg_annual'):
                    transform_note = " Showing annual averages."

                st.markdown("<div class='chart-section'>", unsafe_allow_html=True)
                st.markdown(f"""
                <div class='chart-header'>
                    <div class='chart-title'>{name}</div>
                    <ul class='chart-bullets'>
                        <li>{bullets[0]}</li>
                        <li>{bullets[1]}</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

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
        st.download_button("Download CSV", csv, "econstats_data.csv", "text/csv")

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

    elif not query:
        st.markdown("""
        <div class='narrative-box'>
        <h3 style='margin-top:0'>Welcome to EconStats</h3>
        <p>Ask questions about the economy in plain English:</p>
        <ul style='color: #555; line-height: 1.8;'>
            <li>"How is the economy doing?"</li>
            <li>"How is the job market?"</li>
            <li>"What is inflation?"</li>
        </ul>
        <p style='color: #666; font-size: 0.9rem; margin-top: 15px;'>Data from FRED (Federal Reserve Economic Data).</p>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
