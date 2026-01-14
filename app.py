#!/usr/bin/env python3
"""
EconStats - Streamlit Economic Data Dashboard
Ask questions in plain English and get charts of economic data from FRED.
Incorporates economist intuitions for proper data selection and presentation.
"""

import json
import os
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

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

# Series database with proper economist intuitions
SERIES_DB = {
    # Employment - Establishment Survey (CES)
    'PAYEMS': {
        'name': 'Total Nonfarm Payrolls',
        'unit': 'Thousands of Persons',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'bullets': [
            'THE jobs number. Monthly change is what makes headlines. From the establishment survey (asks employers).',
            'A gain of 150,000+ jobs/month is needed to keep pace with population growth. Above 200,000 = strong hiring.'
        ]
    },
    'CES0500000003': {
        'name': 'Average Hourly Earnings (Private)',
        'unit': 'Dollars per Hour',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'can_inflate_adjust': True,
        'bullets': [
            'What American workers earn per hour. When wages grow faster than inflation, workers gain purchasing power.',
            'The Fed watches wage growth closely: too-fast increases can fuel inflation, but stagnant wages hurt spending.'
        ]
    },

    # Employment - Household Survey (CPS)
    'UNRATE': {
        'name': 'Unemployment Rate (U-3)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'bullets': [
            'The headline unemployment rate. From the household survey (asks people). Below 4% = "full employment."',
            'Only counts people actively looking for work. The broader U-6 measure is typically 3-4 points higher.'
        ]
    },
    'LNS12300060': {
        'name': 'Prime-Age Employment-Population Ratio (25-54)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'bullets': [
            'Many economists consider this THE best measure of labor market health. Avoids distortions from retirees/students.',
            'Shows what % of prime-age Americans (25-54) have jobs. Pre-pandemic peak was 80.4% in early 2020.'
        ]
    },
    'LNS11300000': {
        'name': 'Labor Force Participation Rate',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'bullets': [
            'Share of working-age Americans either employed or actively job-hunting. Peaked at 67% in 2000.',
            'Decline reflects Boomers retiring, more students, and some prime-age workers dropping out.'
        ]
    },
    'LNS11300060': {
        'name': 'Prime-Age Labor Force Participation Rate (25-54)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'bullets': [
            'Participation rate for 25-54 year olds. Removes demographic effects of aging population.',
            'Better than overall participation for tracking whether working-age people are engaged in the labor market.'
        ]
    },

    # JOLTS
    'JTSJOL': {
        'name': 'Job Openings (JOLTS)',
        'unit': 'Thousands',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'bullets': [
            'Counts unfilled job positions. Key indicator of labor demand.',
            'The ratio of job openings to unemployed workers measures labor market "tightness."'
        ]
    },

    # Inflation - CPI
    'CPIAUCSL': {
        'name': 'Consumer Price Index (All Items)',
        'unit': 'Index 1982-84=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'show_yoy': True,
        'yoy_name': 'CPI Inflation Rate (Headline)',
        'yoy_unit': 'Percent Change (Year-over-Year)',
        'bullets': [
            'THE inflation number for most purposes. What consumers actually experience. Used for Social Security adjustments.',
            'At 2%, prices double every 35 years. At 7%, they double in 10 years.'
        ]
    },
    'CPILFESL': {
        'name': 'Core CPI (Less Food & Energy)',
        'unit': 'Index 1982-84=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'show_yoy': True,
        'yoy_name': 'Core CPI Inflation Rate',
        'yoy_unit': 'Percent Change (Year-over-Year)',
        'bullets': [
            'Strips out volatile food and energy to show underlying inflation trend.',
            'Economists prefer core because it\'s "stickier" and harder to reverse once embedded.'
        ]
    },
    'CUSR0000SAH1': {
        'name': 'CPI: Shelter',
        'unit': 'Index 1982-84=100',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'show_yoy': True,
        'yoy_name': 'Shelter Inflation Rate',
        'yoy_unit': 'Percent Change (Year-over-Year)',
        'bullets': [
            'Housing costs are ~1/3 of CPI. When shelter surges, it pushes overall inflation higher.',
            'IMPORTANT: CPI shelter lags market rents by ~12 months due to how it\'s measured.'
        ]
    },

    # Inflation - PCE (Fed's preferred)
    'PCEPI': {
        'name': 'PCE Price Index',
        'unit': 'Index 2017=100',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'show_yoy': True,
        'yoy_name': 'PCE Inflation Rate',
        'yoy_unit': 'Percent Change (Year-over-Year)',
        'bullets': [
            'The Federal Reserve\'s preferred inflation measure. When the Fed says "2% target," this is what they mean.',
            'Typically runs 0.3-0.5 points below CPI because it accounts for consumers switching to cheaper alternatives.'
        ]
    },
    'PCEPILFE': {
        'name': 'Core PCE Price Index',
        'unit': 'Index 2017=100',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'show_yoy': True,
        'yoy_name': 'Core PCE Inflation Rate',
        'yoy_unit': 'Percent Change (Year-over-Year)',
        'bullets': [
            'THE number the Fed watches most closely. The explicit target is 2.0% year-over-year.',
            'When discussing Fed policy or interest rate decisions, this is the inflation measure that matters.'
        ]
    },

    # GDP
    'GDPC1': {
        'name': 'Real Gross Domestic Product',
        'unit': 'Billions of Chained 2017 Dollars',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'bullets': [
            'Total value of everything America produces, adjusted for inflation ("real"). Always use real, not nominal GDP.',
            'Two consecutive quarters of negative growth is the rule-of-thumb for recession (but NBER officially decides).'
        ]
    },
    'A191RL1Q225SBEA': {
        'name': 'Real GDP Growth Rate',
        'unit': 'Percent Change (Quarterly, Annualized)',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'bullets': [
            'How fast the economy is growing. Healthy growth is 2-3% annually. "Annualized" = if pace continued for full year.',
            'Consumer spending drives ~70% of GDP. Released quarterly, revised twice.'
        ]
    },

    # Interest Rates
    'FEDFUNDS': {
        'name': 'Federal Funds Effective Rate',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'bullets': [
            'THE interest rate the Fed controls. All other rates (mortgages, car loans, credit cards) move with it.',
            'Near 0% = emergency stimulus mode. 5%+ = inflation-fighting mode.'
        ]
    },
    'DGS10': {
        'name': '10-Year Treasury Yield',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'bullets': [
            'The benchmark rate for the economy. Mortgage rates and corporate bonds key off this.',
            'Set by market forces (not the Fed directly). Reflects expectations for growth and inflation over 10 years.'
        ]
    },
    'DGS2': {
        'name': '2-Year Treasury Yield',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'bullets': [
            'The market\'s best guess about where the Fed will set rates over the next two years.',
            'When 2-year exceeds 10-year ("inverted yield curve"), recession has historically followed.'
        ]
    },
    'T10Y2Y': {
        'name': '10-Year Minus 2-Year Treasury (Yield Curve)',
        'unit': 'Percent',
        'source': 'Board of Governors of the Federal Reserve System',
        'sa': False,
        'bullets': [
            'Most reliable recession warning signal. Normally positive. When negative ("inverted"), trouble usually follows.',
            'Has preceded every U.S. recession since 1970, typically by 12-18 months.'
        ]
    },
    'MORTGAGE30US': {
        'name': '30-Year Fixed Mortgage Rate',
        'unit': 'Percent',
        'source': 'Freddie Mac',
        'sa': False,
        'bullets': [
            'What homebuyers actually pay. At 3%, a $400K house = $1,686/month. At 7%, same house = $2,661/month.',
            'Roughly equals 10-year Treasury + 1.5-2.5% spread for risk.'
        ]
    },

    # Housing
    'CSUSHPINSA': {
        'name': 'S&P/Case-Shiller National Home Price Index',
        'unit': 'Index Jan 2000=100',
        'source': 'S&P Dow Jones Indices LLC',
        'sa': False,
        'bullets': [
            'The gold standard for home prices. Uses "repeat sales" to track same homes over time. Index 300 = tripled since 2000.',
            'Home equity is the largest source of wealth for most American families. Lags real-time by ~2 months.'
        ]
    },
    'HOUST': {
        'name': 'Housing Starts',
        'unit': 'Thousands of Units (Annual Rate)',
        'source': 'U.S. Census Bureau',
        'sa': True,
        'bullets': [
            'New construction projects breaking ground. Leading indicator—builders only start when confident.',
            'Healthy range: 1.2-1.6 million annually. The U.S. is estimated 3-5 million homes short of demand.'
        ]
    },

    # Consumer
    'UMCSENT': {
        'name': 'University of Michigan Consumer Sentiment',
        'unit': 'Index 1966:Q1=100',
        'source': 'University of Michigan',
        'sa': False,
        'bullets': [
            'How optimistic Americans feel about the economy. Consumer spending is ~70% of GDP, so sentiment matters.',
            'Index ~100 is neutral. Below 70 is deeply pessimistic.'
        ]
    },
    'RSXFS': {
        'name': 'Retail Sales (ex. Food Services)',
        'unit': 'Millions of Dollars',
        'source': 'U.S. Census Bureau',
        'sa': True,
        'can_inflate_adjust': True,
        'bullets': [
            'Monthly pulse of consumer spending at stores and online. Strong sales = confident consumers.',
            'Highly volatile month-to-month. Watch the 3-month trend, not single months.'
        ]
    },

    # Stocks
    'SP500': {
        'name': 'S&P 500 Index',
        'unit': 'Index',
        'source': 'S&P Dow Jones Indices LLC',
        'sa': False,
        'bullets': [
            'The closest thing to "the stock market." 500 largest U.S. companies, ~$40 trillion in wealth.',
            'Long-term average return: ~10% annually (7% after inflation).'
        ]
    },

    # Demographics
    'LNS14000002': {
        'name': 'Unemployment Rate - Women',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'bullets': [
            'Unemployment for women 16+. COVID recession hit women harder initially ("she-cession").',
            'Women\'s unemployment fell below men\'s in 2022 for the first time in decades.'
        ]
    },
    'LNS12300062': {
        'name': 'Prime-Age Employment-Population Ratio - Women (25-54)',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'bullets': [
            'Best measure of women\'s labor market success. Hit all-time high of 75.3% in 2024.',
            'Avoids distortions from students and retirees.'
        ]
    },
    'LNS11300002': {
        'name': 'Labor Force Participation Rate - Women',
        'unit': 'Percent',
        'source': 'U.S. Bureau of Labor Statistics',
        'sa': True,
        'bullets': [
            'Rose from 34% in 1950 to 60% in 2000—one of the most significant economic shifts in history.',
            'U.S. lags other developed countries, partly due to lack of paid family leave.'
        ]
    },

    # Commodities & Trade
    'DCOILWTICO': {
        'name': 'Crude Oil Prices: WTI',
        'unit': 'Dollars per Barrel',
        'source': 'Federal Reserve Bank of St. Louis',
        'sa': False,
        'bullets': [
            'West Texas Intermediate—the U.S. benchmark for oil prices.',
            'Directly affects gas prices, transportation costs, and inflation.'
        ]
    },
    'IMPCH': {
        'name': 'U.S. Imports from China',
        'unit': 'Millions of Dollars',
        'source': 'U.S. Census Bureau',
        'sa': False,
        'bullets': [
            'Total goods imported from China. Reflects trade policy and supply chain shifts.',
            'Note: Some goods may be re-exports (passing through other countries).'
        ]
    },
    'BOPGSTB': {
        'name': 'Trade Balance (Goods & Services)',
        'unit': 'Millions of Dollars',
        'source': 'U.S. Bureau of Economic Analysis',
        'sa': True,
        'bullets': [
            'Exports minus imports. Negative = trade deficit. U.S. has run deficits since the 1970s.',
            'Deficits aren\'t inherently bad—partly reflect strong consumer demand and dollar\'s reserve currency role.'
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
ECONOMIST_PROMPT = """You are an expert economist helping interpret economic data questions for the FRED (Federal Reserve Economic Data) database. Think like Jason Furman or a top policy economist.

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

USER QUESTION: """


def call_claude(query: str) -> dict:
    """Call Claude API to interpret the economic question."""
    if not ANTHROPIC_API_KEY:
        return {
            'series': [],
            'search_terms': [query],
            'explanation': '',
            'show_yoy': False,
            'combine_chart': False
        }

    url = 'https://api.anthropic.com/v1/messages'
    payload = {
        'model': 'claude-sonnet-4-20250514',
        'max_tokens': 1024,
        'messages': [{'role': 'user', 'content': ECONOMIST_PROMPT + query}]
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
            return json.loads(content.strip())
    except Exception as e:
        return {
            'series': [],
            'search_terms': [query],
            'explanation': '',
            'show_yoy': False,
            'combine_chart': False
        }


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


def create_chart(series_data: list, combine: bool = False) -> go.Figure:
    """Create a Plotly chart with recession shading."""
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
            fig.add_trace(
                go.Scatter(
                    x=dates, y=values, mode='lines',
                    name=name[:40],
                    line=dict(color=colors[i % len(colors)], width=2),
                    hovertemplate=f"<b>{name[:40]}</b><br>%{{x|%b %Y}}<br>%{{y:,.2f}}<extra></extra>"
                ),
                row=i + 1, col=1
            )
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

    st.markdown("<h1>EconStats</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>U.S. Economic Data with Context</p>", unsafe_allow_html=True)
    st.markdown("<div class='header-divider'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns([5, 1])
    with col1:
        query = st.text_input(
            "Search",
            placeholder="Ask: How is the economy? What is inflation? Is the labor market tight?",
            label_visibility="collapsed",
        )
    with col2:
        search_clicked = st.button("Search", type="primary", use_container_width=True)

    # Quick search buttons in two rows of 4
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
    quick_items = list(QUICK_SEARCHES.items())

    with col1:
        if st.button("Jobs", use_container_width=True):
            query = "job market"
            search_clicked = True
    with col2:
        if st.button("Inflation", use_container_width=True):
            query = "inflation"
            search_clicked = True
    with col3:
        if st.button("GDP", use_container_width=True):
            query = "gdp growth"
            search_clicked = True
    with col4:
        if st.button("Rates", use_container_width=True):
            query = "interest rates"
            search_clicked = True
    with col5:
        time_period = st.selectbox("Timeframe", list(TIME_PERIODS.keys()), index=3, label_visibility="collapsed")
        years = TIME_PERIODS[time_period]

    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
    with col1:
        if st.button("Housing", use_container_width=True):
            query = "housing"
            search_clicked = True
    with col2:
        if st.button("Women", use_container_width=True):
            query = "women labor"
            search_clicked = True
    with col3:
        if st.button("Oil", use_container_width=True):
            query = "oil prices"
            search_clicked = True
    with col4:
        if st.button("China", use_container_width=True):
            query = "china trade"
            search_clicked = True

    st.markdown("<br>", unsafe_allow_html=True)

    if query and search_clicked:
        # ALWAYS use Claude to interpret the query
        with st.spinner("Analyzing your question with AI economist..."):
            interpretation = call_claude(query)

        ai_explanation = interpretation.get('explanation', '')
        series_to_fetch = list(interpretation.get('series', []))  # Copy the list
        combine = interpretation.get('combine_chart', False)
        show_yoy = interpretation.get('show_yoy', False)

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

        # Debug expander to show what happened
        with st.expander("🔍 Debug: See how this query was interpreted"):
            st.write("**Claude's interpretation:**")
            st.json(interpretation)
            st.write(f"**Series to fetch:** {series_to_fetch}")

        # Fetch data
        series_data = []
        with st.spinner("Fetching data from FRED..."):
            for series_id in series_to_fetch[:4]:
                dates, values, info = get_observations(series_id, years)
                if dates and values:
                    db_info = SERIES_DB.get(series_id, {})
                    if db_info.get('show_yoy') and len(dates) > 12:
                        yoy_dates, yoy_values = calculate_yoy(dates, values)
                        if yoy_dates:
                            info_copy = dict(info)
                            info_copy['name'] = db_info.get('yoy_name', info.get('name', series_id) + ' (YoY %)')
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

        # Narrative summary
        st.markdown("<div class='narrative-box'>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0'>Summary</h3>", unsafe_allow_html=True)

        if ai_explanation:
            st.markdown(f"<div class='ai-explanation'>{ai_explanation}</div>", unsafe_allow_html=True)

        period_text = f"over the past {years} years" if years else "over the available history"

        for series_id, dates, values, info in series_data:
            if not values:
                continue

            name = info.get('name', info.get('title', series_id))
            unit = info.get('unit', info.get('units', ''))
            latest = values[-1]
            first = values[0]
            change = latest - first
            pct_change = (change / abs(first)) * 100 if first != 0 else 0

            direction_class = 'up' if pct_change >= 0 else 'down'
            sign = '+' if pct_change >= 0 else ''

            # Pre-COVID comparison (Feb 2020)
            covid_text = ""
            try:
                covid_idx = next(i for i, d in enumerate(dates) if d >= '2020-02-01')
                pre_covid = values[covid_idx]
                vs_covid = ((latest - pre_covid) / abs(pre_covid)) * 100 if pre_covid != 0 else 0
                covid_class = 'up' if vs_covid >= 0 else 'down'
                covid_sign = '+' if vs_covid >= 0 else ''
                covid_text = f" Compared to Feb 2020 (pre-pandemic): <span class='{covid_class}'>{covid_sign}{vs_covid:.1f}%</span>."
            except (StopIteration, IndexError):
                pass

            latest_date = datetime.strptime(dates[-1], '%Y-%m-%d').strftime('%b %Y')

            narrative = f"""
            <p><span class='highlight'>{name}</span> is at <strong>{format_number(latest)}</strong> {unit} ({latest_date}).
            {period_text.capitalize()}, <span class='{direction_class}'>{sign}{pct_change:.1f}%</span> from {format_number(first)}.{covid_text}</p>
            """
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

            fig = create_chart(series_data, combine=True)
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
                yoy_note = " Showing year-over-year percent change." if info.get('is_yoy') else ""

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

                fig = create_chart([(series_id, dates, values, info)], combine=False)
                st.plotly_chart(fig, use_container_width=True)

                st.markdown(f"<div class='source-line'>Source: {source}. {sa_note}{yoy_note} Shaded areas indicate U.S. recessions (NBER).</div>", unsafe_allow_html=True)
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

    elif not query:
        st.markdown("""
        <div class='narrative-box'>
        <h3 style='margin-top:0'>Welcome to EconStats</h3>
        <p>Ask questions about the economy in plain English:</p>
        <ul style='color: #555; line-height: 1.8;'>
            <li>"How is the economy doing?" → GDP growth, unemployment, inflation</li>
            <li>"How is the job market?" → Nonfarm payrolls + unemployment rate</li>
            <li>"What is inflation?" → CPI headline and core</li>
            <li>"Is the labor market tight?" → Prime-age employment ratio</li>
            <li>"What does the Fed target?" → Core PCE inflation</li>
        </ul>
        <p style='color: #666; font-size: 0.9rem; margin-top: 15px;'>Data from the Federal Reserve Economic Data (FRED). Sources include BLS, BEA, Census Bureau, and others.</p>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
