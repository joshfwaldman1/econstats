"""
EconStats - FastAPI + HTMX + Tailwind version
A clean, modern frontend for economic data exploration.

Now with full data source integration:
- FRED (primary economic data)
- Alpha Vantage (stocks, forex, P/E ratios)
- Shiller CAPE (valuation/bubble analysis)
- Polymarket (prediction markets)
- Zillow (housing data)
- EIA (energy data)
- DBnomics (international data)
"""

import os
import json
import httpx
import subprocess
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from anthropic import Anthropic

# Initialize
app = FastAPI(title="EconStats")
templates = Jinja2Templates(directory="templates")

# Get last git commit timestamp at startup
def get_last_update_time():
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%cd', '--date=format:%b %d, %Y %H:%M UTC'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None

LAST_UPDATED = get_last_update_time()
templates.env.globals['last_updated'] = LAST_UPDATED

# API Keys
FRED_API_KEY = os.environ.get('FRED_API_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
ALPHAVANTAGE_API_KEY = os.environ.get('ALPHAVANTAGE_API_KEY')

# =============================================================================
# IMPORT DATA SOURCE MODULES
# =============================================================================

# Alpha Vantage (stocks, forex, P/E ratios)
try:
    from agents.alphavantage import get_alphavantage_series, ALPHAVANTAGE_SERIES
    ALPHAVANTAGE_AVAILABLE = True
except Exception as e:
    print(f"Alpha Vantage not available: {e}")
    ALPHAVANTAGE_AVAILABLE = False

# Shiller CAPE (valuation/bubble analysis)
try:
    from agents.shiller import get_cape_series, get_current_cape, get_bubble_comparison_data, is_valuation_query
    SHILLER_AVAILABLE = True
except Exception as e:
    print(f"Shiller CAPE not available: {e}")
    SHILLER_AVAILABLE = False

# Polymarket (prediction markets)
try:
    from agents.polymarket import find_relevant_predictions, format_predictions_box
    POLYMARKET_AVAILABLE = True
except Exception as e:
    print(f"Polymarket not available: {e}")
    POLYMARKET_AVAILABLE = False

# Recession scorecard
try:
    from agents.recession_scorecard import is_recession_query, build_recession_scorecard, format_scorecard_for_display
    RECESSION_SCORECARD_AVAILABLE = True
except Exception as e:
    print(f"Recession scorecard not available: {e}")
    RECESSION_SCORECARD_AVAILABLE = False

# Zillow (housing data)
try:
    from agents.zillow import get_zillow_series, ZILLOW_SERIES
    ZILLOW_AVAILABLE = True
except Exception as e:
    print(f"Zillow not available: {e}")
    ZILLOW_AVAILABLE = False

# EIA (energy data)
try:
    from agents.eia import get_eia_series, EIA_SERIES
    EIA_AVAILABLE = True
except Exception as e:
    print(f"EIA not available: {e}")
    EIA_AVAILABLE = False

# DBnomics (international data)
try:
    from agents.dbnomics import get_observations_dbnomics, INTERNATIONAL_SERIES, INTERNATIONAL_QUERY_PLANS
    DBNOMICS_AVAILABLE = True
except Exception as e:
    print(f"DBnomics not available: {e}")
    DBNOMICS_AVAILABLE = False

# Health check indicators (megacap, labor market, etc.)
try:
    from core.health_check_indicators import is_health_check_query, detect_health_check_entity, get_health_check_config
    HEALTH_CHECK_AVAILABLE = True
except Exception as e:
    print(f"Health check not available: {e}")
    HEALTH_CHECK_AVAILABLE = False

# Startup diagnostics
print("=" * 60)
print("EconStats FastAPI Starting Up")
print("=" * 60)
print(f"FRED_API_KEY: {'SET' if FRED_API_KEY else 'NOT SET'}")
print(f"ANTHROPIC_API_KEY: {'SET' if ANTHROPIC_API_KEY else 'NOT SET'}")
print(f"GOOGLE_API_KEY: {'SET' if GOOGLE_API_KEY else 'NOT SET'}")
print(f"ALPHAVANTAGE_API_KEY: {'SET' if ALPHAVANTAGE_API_KEY else 'NOT SET'}")
print("-" * 60)
print(f"ALPHAVANTAGE_AVAILABLE: {ALPHAVANTAGE_AVAILABLE}")
print(f"SHILLER_AVAILABLE: {SHILLER_AVAILABLE}")
print(f"POLYMARKET_AVAILABLE: {POLYMARKET_AVAILABLE}")
print(f"RECESSION_SCORECARD_AVAILABLE: {RECESSION_SCORECARD_AVAILABLE}")
print(f"ZILLOW_AVAILABLE: {ZILLOW_AVAILABLE}")
print(f"EIA_AVAILABLE: {EIA_AVAILABLE}")
print(f"DBNOMICS_AVAILABLE: {DBNOMICS_AVAILABLE}")
print(f"HEALTH_CHECK_AVAILABLE: {HEALTH_CHECK_AVAILABLE}")
print("=" * 60)

# Load query plans from existing JSON files
def load_query_plans():
    plans = {}
    plan_files = [
        'agents/plans_economy_overview.json',
        'agents/plans_inflation.json',
        'agents/plans_employment.json',
        'agents/plans_gdp.json',
        'agents/plans_housing.json',
        'agents/plans_fed_rates.json',
        'agents/plans_consumer.json',
        'agents/plans_demographics.json',
        'agents/plans_trade_markets.json',
    ]
    for pf in plan_files:
        if os.path.exists(pf):
            with open(pf) as f:
                plans.update(json.load(f))
    return plans

QUERY_PLANS = load_query_plans()

# NBER Recession dates (for chart shading)
RECESSIONS = [
    ('1948-11-01', '1949-10-01'),
    ('1953-07-01', '1954-05-01'),
    ('1957-08-01', '1958-04-01'),
    ('1960-04-01', '1961-02-01'),
    ('1969-12-01', '1970-11-01'),
    ('1973-11-01', '1975-03-01'),
    ('1980-01-01', '1980-07-01'),
    ('1981-07-01', '1982-11-01'),
    ('1990-07-01', '1991-03-01'),
    ('2001-03-01', '2001-11-01'),
    ('2007-12-01', '2009-06-01'),
    ('2020-02-01', '2020-04-01'),
]

# Series metadata with educational bullets and data_type for YoY safety
SERIES_DB = {
    'PAYEMS': {
        'name': 'Nonfarm Payrolls', 'unit': 'Thousands of Persons', 'show_yoy': False, 'sa': True,
        'source': 'U.S. Bureau of Labor Statistics',
        'data_type': 'level',  # Employment count - show absolute changes, not %
        'show_absolute_change': True,
        'bullets': [
            'The single most important monthly indicator of labor market health—this is the "jobs number" that moves markets on the first Friday of each month.',
            'Context: The economy now needs only 50-75K new jobs/month to keep pace with slowing population growth. Gains above 150K signal robust hiring; below 50K suggests softening.'
        ]
    },
    'UNRATE': {
        'name': 'Unemployment Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': True,
        'source': 'U.S. Bureau of Labor Statistics',
        'data_type': 'rate',  # Already a rate - never apply YoY
        'bullets': [
            'The headline unemployment rate—the share of Americans actively looking for work but unable to find it.',
            'Rates below 4% are historically rare and signal a tight labor market. The rate peaked at 10% in 2009 and briefly hit 14.7% in April 2020.'
        ]
    },
    'A191RO1Q156NBEA': {
        'name': 'Real GDP Growth', 'unit': 'Percent Change', 'show_yoy': False, 'sa': True,
        'source': 'U.S. Bureau of Economic Analysis',
        'data_type': 'growth_rate',  # Already a growth rate - never apply YoY
        'bullets': [
            'The broadest measure of economic output—real GDP growth shows how fast the economy is expanding or contracting.',
            'Healthy growth is typically 2-3% annually. Two consecutive quarters of negative growth is one common definition of recession.'
        ]
    },
    'CPIAUCSL': {
        'name': 'Consumer Price Index', 'unit': 'Index 1982-84=100', 'show_yoy': True, 'sa': True,
        'source': 'U.S. Bureau of Labor Statistics',
        'data_type': 'index',  # Index - convert to YoY %
        'yoy_name': 'CPI Inflation Rate (Headline)',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'CPI measures the average change in prices paid by urban consumers for a basket of goods and services.',
            'The Fed targets 2% annual inflation. Above 3% raises concerns; sustained rates above 5% typically prompt aggressive Fed action.'
        ]
    },
    'FEDFUNDS': {
        'name': 'Federal Funds Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': False,
        'source': 'Board of Governors of the Federal Reserve System',
        'data_type': 'rate',  # Already a rate
        'bullets': [
            'The Fed\'s primary tool for monetary policy—the rate banks charge each other for overnight loans.',
            'When the Fed raises rates, borrowing becomes more expensive throughout the economy, slowing growth and inflation.'
        ]
    },
    'DGS10': {
        'name': '10-Year Treasury Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': False,
        'source': 'Board of Governors of the Federal Reserve System',
        'data_type': 'rate',
        'bullets': [
            'The benchmark "risk-free" rate that influences mortgages, corporate bonds, and stock valuations.',
            'Higher 10-year yields mean higher borrowing costs across the economy and typically pressure stock prices.'
        ]
    },
    'DGS2': {
        'name': '2-Year Treasury Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': False,
        'source': 'Board of Governors of the Federal Reserve System',
        'data_type': 'rate',
        'bullets': [
            'Reflects market expectations for Fed policy over the next two years.',
            'When the 2-year exceeds the 10-year (yield curve inversion), it has historically preceded recessions.'
        ]
    },
    'MORTGAGE30US': {
        'name': '30-Year Mortgage Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': False,
        'source': 'Freddie Mac',
        'data_type': 'rate',
        'bullets': [
            'The rate on a conventional 30-year fixed mortgage—the primary driver of housing affordability.',
            'Each 1% increase in rates reduces buying power by roughly 10%. Rates below 4% are historically low; above 7% is restrictive.'
        ]
    },
    'SAHMREALTIME': {
        'name': 'Sahm Rule Recession Indicator', 'unit': 'Percentage Points', 'show_yoy': False, 'sa': True,
        'source': 'Federal Reserve Bank of St. Louis', 'benchmark': 0.5,
        'data_type': 'spread',  # Spread - never apply YoY
        'bullets': [
            'Created by economist Claudia Sahm—signals recession when the 3-month average unemployment rate rises 0.5 points above its 12-month low.',
            'Has correctly identified every U.S. recession since 1970 with no false positives.'
        ]
    },
    'T10Y2Y': {
        'name': 'Treasury Yield Spread (10Y-2Y)', 'unit': 'Percent', 'show_yoy': False, 'sa': False,
        'source': 'Federal Reserve Bank of St. Louis',
        'data_type': 'spread',  # Spread - never apply YoY
        'bullets': [
            'The difference between 10-year and 2-year Treasury yields—a key recession indicator.',
            'When negative (inverted), it has preceded every recession since the 1970s, typically by 12-18 months.'
        ]
    },
    'ICSA': {
        'name': 'Initial Jobless Claims', 'unit': 'Number', 'show_yoy': False, 'sa': True,
        'source': 'U.S. Employment and Training Administration',
        'data_type': 'level',
        'bullets': [
            'Weekly count of new unemployment insurance filings—the most timely indicator of labor market stress.',
            'Claims below 250K indicate a healthy labor market. Sustained readings above 300K suggest deterioration.'
        ]
    },
    'CIVPART': {
        'name': 'Labor Force Participation Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': True,
        'source': 'U.S. Bureau of Labor Statistics',
        'data_type': 'rate',  # Already a rate
        'bullets': [
            'Share of the adult population either working or actively seeking work.',
            'Has declined from 67% in 2000 due to aging demographics, rising disability, and more students pursuing education.'
        ]
    },
    'U6RATE': {
        'name': 'U-6 Unemployment Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': True,
        'source': 'U.S. Bureau of Labor Statistics',
        'data_type': 'rate',
        'bullets': [
            'The broadest measure of unemployment—includes discouraged workers and those working part-time for economic reasons.',
            'Typically runs 3-4 percentage points higher than the headline U-3 rate.'
        ]
    },
    'PCEPILFE': {
        'name': 'Core PCE Inflation', 'unit': 'Index', 'show_yoy': True, 'sa': True,
        'source': 'U.S. Bureau of Economic Analysis',
        'data_type': 'index',  # Index - convert to YoY %
        'yoy_name': 'Core PCE Inflation Rate',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'The Federal Reserve\'s preferred inflation measure—excludes volatile food and energy prices.',
            'The Fed explicitly targets 2% core PCE inflation over time.'
        ]
    },
    'PCEPI': {
        'name': 'PCE Inflation', 'unit': 'Index', 'show_yoy': True, 'sa': True,
        'source': 'U.S. Bureau of Economic Analysis',
        'data_type': 'index',
        'yoy_name': 'PCE Inflation Rate',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'Personal Consumption Expenditures price index—broader than CPI and the Fed\'s official inflation gauge.',
            'Tends to run slightly lower than CPI because it accounts for consumers substituting cheaper goods.'
        ]
    },
    'RSAFS': {
        'name': 'Retail Sales', 'unit': 'Millions of Dollars', 'show_yoy': True, 'sa': True,
        'source': 'U.S. Census Bureau',
        'data_type': 'level',
        'bullets': [
            'Total receipts at retail stores—a direct measure of consumer spending, which drives ~70% of GDP.',
            'Closely watched for signs of consumer strength or pullback.'
        ]
    },
    'PSAVERT': {
        'name': 'Personal Savings Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': True,
        'source': 'U.S. Bureau of Economic Analysis',
        'data_type': 'rate',
        'bullets': [
            'The share of disposable income that households save rather than spend.',
            'Spiked to 33% during COVID stimulus; rates below 4% suggest consumers may be stretched.'
        ]
    },
    'UMCSENT': {
        'name': 'Consumer Sentiment', 'unit': 'Index 1966:Q1=100', 'show_yoy': False, 'sa': False,
        'source': 'University of Michigan',
        'data_type': 'index',
        'bullets': [
            'Survey-based measure of how consumers feel about their finances and the economy.',
            'Readings above 90 indicate optimism; below 70 suggests pessimism. Can lead changes in spending behavior.'
        ]
    },
    'GDPNOW': {
        'name': 'GDPNow Estimate', 'unit': 'Percent', 'show_yoy': False, 'sa': True,
        'source': 'Federal Reserve Bank of Atlanta',
        'data_type': 'growth_rate',  # Already a growth rate
        'bullets': [
            'Real-time estimate of current-quarter GDP growth based on incoming economic data.',
            'Updates frequently as new data releases and provides the most current read on economic momentum.'
        ]
    },
    'CPILFESL': {
        'name': 'Core CPI', 'unit': 'Index 1982-84=100', 'show_yoy': True, 'sa': True,
        'source': 'U.S. Bureau of Labor Statistics',
        'data_type': 'index',
        'yoy_name': 'Core CPI Inflation Rate',
        'yoy_unit': '% Change YoY',
        'bullets': [
            'CPI excluding food and energy—shows underlying inflation trends without volatile components.',
            'Markets and policymakers watch core inflation to gauge persistent price pressures.'
        ]
    },
    'MANEMP': {
        'name': 'Manufacturing Employment', 'unit': 'Thousands of Persons', 'show_yoy': False, 'sa': True,
        'source': 'U.S. Bureau of Labor Statistics',
        'data_type': 'level',
        'bullets': [
            'Total jobs in the manufacturing sector—a key indicator of industrial strength.',
            'Has declined from 19 million in 1979 to around 13 million today due to automation and offshoring.'
        ]
    },
    # Additional series for complete coverage
    'LNS12300060': {
        'name': 'Prime-Age Employment-Population Ratio', 'unit': 'Percent', 'show_yoy': False, 'sa': True,
        'source': 'U.S. Bureau of Labor Statistics',
        'data_type': 'rate',
        'bullets': [
            'Share of Americans aged 25-54 who are employed—avoids distortions from retiring boomers and students.',
            'Many economists consider this the single best measure of labor market health.'
        ]
    },
    'A191RL1Q225SBEA': {
        'name': 'Real GDP Growth Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': True,
        'source': 'U.S. Bureau of Economic Analysis',
        'data_type': 'growth_rate',
        'bullets': [
            'Quarterly annualized real GDP growth rate.',
            'Shows the pace of economic expansion or contraction.'
        ]
    },
}


# Query mappings with economist intuitions - MUST match app.py for consistency
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
    'rent inflation': {'series': ['CUSR0000SAH1'], 'show_yoy': True, 'combine': False},
    'shelter': {'series': ['CUSR0000SAH1'], 'show_yoy': True, 'combine': False},
    'rents': {'series': ['CUSR0000SEHA', 'CUSR0000SAH1'], 'show_yoy': True, 'combine': True},
    'rent': {'series': ['CUSR0000SEHA', 'CUSR0000SAH1'], 'show_yoy': True, 'combine': True},
    'how have rents changed': {'series': ['CUSR0000SEHA', 'CUSR0000SAH1'], 'show_yoy': True, 'combine': True},
    'rental prices': {'series': ['CUSR0000SEHA', 'CUSR0000SAH1'], 'show_yoy': True, 'combine': True},

    # GDP - Annual (YoY), quarterly, core GDP, and GDPNow
    # GDP queries - use only quarterly for main view (JSON plans have full breakdown with chart_groups)
    'gdp': {'series': ['A191RL1Q225SBEA', 'PB0000031Q225SBEA', 'GDPNOW'], 'combine': False},
    'gdp growth': {'series': ['A191RL1Q225SBEA', 'PB0000031Q225SBEA', 'GDPNOW'], 'combine': False},
    'economic growth': {'series': ['A191RL1Q225SBEA', 'PB0000031Q225SBEA', 'GDPNOW'], 'combine': False},
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

    # International comparisons - FRED has this data!
    'us vs europe': {'series': ['A191RL1Q225SBEA', 'CLVMNACSCAB1GQEA19', 'UNRATE', 'LRHUTTTTEZM156S'], 'show_yoy': False, 'combine': False},
    'us vs eurozone': {'series': ['A191RL1Q225SBEA', 'CLVMNACSCAB1GQEA19', 'UNRATE', 'LRHUTTTTEZM156S'], 'show_yoy': False, 'combine': False},
    'us v europe': {'series': ['A191RL1Q225SBEA', 'CLVMNACSCAB1GQEA19', 'UNRATE', 'LRHUTTTTEZM156S'], 'show_yoy': False, 'combine': False},
    'us v eurozone': {'series': ['A191RL1Q225SBEA', 'CLVMNACSCAB1GQEA19', 'UNRATE', 'LRHUTTTTEZM156S'], 'show_yoy': False, 'combine': False},
    'europe economy': {'series': ['CLVMNACSCAB1GQEA19', 'LRHUTTTTEZM156S', 'EA19CPALTT01GYM'], 'show_yoy': False, 'combine': False},
    'eurozone economy': {'series': ['CLVMNACSCAB1GQEA19', 'LRHUTTTTEZM156S', 'EA19CPALTT01GYM'], 'show_yoy': False, 'combine': False},
    'eurozone': {'series': ['CLVMNACSCAB1GQEA19', 'LRHUTTTTEZM156S', 'EA19CPALTT01GYM'], 'show_yoy': False, 'combine': False},
    'europe': {'series': ['CLVMNACSCAB1GQEA19', 'LRHUTTTTEZM156S', 'EA19CPALTT01GYM'], 'show_yoy': False, 'combine': False},
}


def normalize_query(query: str) -> str:
    """Normalize query for matching."""
    import re
    q = query.lower().strip()

    # Normalize "v." and "versus" to "vs"
    q = re.sub(r'\bv\.?\s+', 'vs ', q)
    q = re.sub(r'\bversus\b', 'vs', q)
    # Normalize "europe's" to "europe"
    q = re.sub(r"europe's", 'europe', q)

    fillers = [
        r'^what is\s+', r'^what are\s+', r'^show me\s+', r'^show\s+',
        r'^tell me about\s+', r'^how is\s+', r'^how are\s+', r'^how has\s+', r'^how have\s+',
        r'^what\'s\s+', r'^whats\s+', r'^give me\s+',
        r'\s+changed\s*$', r'\s+doing\s*$', r'\s+looking\s*$', r'\s+trending\s*$',
        r'\s+economy\s*$',  # "us vs europe economy" -> "us vs europe"
        r'\?$', r'\.+$', r'\s+the\s+', r'^the\s+'
    ]
    for filler in fillers:
        q = re.sub(filler, ' ', q)
    q = ' '.join(q.split()).strip()
    return q


def classify_query_intent(query: str, available_topics: list) -> str:
    """Use LLM to understand what topic the user is asking about.

    This is a fast, cheap call that routes queries intelligently.
    Returns the best matching topic from available_topics, or None.
    """
    if not ANTHROPIC_API_KEY:
        return None

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        # Create a condensed list of topics (sample if too many)
        topics_str = ", ".join(available_topics[:100])

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": f"""Given the user's economic/financial data question, pick the single best matching topic from this list.

Question: "{query}"

Available topics: {topics_str}

Note: We have data from FRED (economic), Zillow (housing/rent), stock market, energy prices, and more.

Reply with ONLY the exact topic name that best matches, or "none" if nothing fits. No explanation."""
            }]
        )

        result = response.content[0].text.strip().lower()
        print(f"[Intent] Query '{query}' -> classified as '{result}'")

        if result != "none" and result in [t.lower() for t in available_topics]:
            # Find the original casing
            for topic in available_topics:
                if topic.lower() == result:
                    return topic
        return None

    except Exception as e:
        print(f"[Intent] Classification error: {e}")
        return None


def find_query_plan(query: str):
    """Find matching query plan.

    Priority order:
    1. Exact match in QUERY_PLANS, QUERY_MAP, or INTERNATIONAL_QUERY_PLANS
    2. Normalized match
    3. Fuzzy match
    4. LLM intent classification (if no match found)
    """
    normalized = normalize_query(query)
    original_lower = query.lower().strip()

    # Get international plans if available
    intl_plans = INTERNATIONAL_QUERY_PLANS if DBNOMICS_AVAILABLE else {}

    # PRIORITY 1: Check JSON query plans first (richer series)
    if original_lower in QUERY_PLANS:
        return QUERY_PLANS[original_lower]
    if normalized in QUERY_PLANS:
        return QUERY_PLANS[normalized]

    # Check international plans (Europe, UK, China, etc.)
    if original_lower in intl_plans:
        print(f"[International] Matched '{original_lower}' to international plan")
        return intl_plans[original_lower]
    if normalized in intl_plans:
        print(f"[International] Matched '{normalized}' to international plan")
        return intl_plans[normalized]

    # PRIORITY 2: Check QUERY_MAP as fallback
    if original_lower in QUERY_MAP:
        return QUERY_MAP[original_lower]
    if normalized in QUERY_MAP:
        return QUERY_MAP[normalized]

    # PRIORITY 3: Fuzzy match on all plan sources
    import difflib

    # Fuzzy match on QUERY_PLANS
    matches = difflib.get_close_matches(normalized, list(QUERY_PLANS.keys()), n=1, cutoff=0.8)
    if matches:
        return QUERY_PLANS[matches[0]]

    # Fuzzy match on international plans
    if intl_plans:
        matches = difflib.get_close_matches(normalized, list(intl_plans.keys()), n=1, cutoff=0.7)
        if matches:
            print(f"[International] Fuzzy matched '{normalized}' to '{matches[0]}'")
            return intl_plans[matches[0]]

    # Fuzzy match on QUERY_MAP
    matches = difflib.get_close_matches(normalized, list(QUERY_MAP.keys()), n=1, cutoff=0.7)
    if matches:
        return QUERY_MAP[matches[0]]

    # PRIORITY 4: LLM intent classification
    # Combine all available topics from all sources
    all_topics = list(QUERY_PLANS.keys()) + list(QUERY_MAP.keys()) + list(intl_plans.keys())
    classified_topic = classify_query_intent(query, all_topics)

    if classified_topic:
        if classified_topic in QUERY_PLANS:
            print(f"[Intent] Routed to QUERY_PLANS['{classified_topic}']")
            return QUERY_PLANS[classified_topic]
        elif classified_topic in intl_plans:
            print(f"[Intent] Routed to international plan '{classified_topic}'")
            return intl_plans[classified_topic]
        elif classified_topic in QUERY_MAP:
            print(f"[Intent] Routed to QUERY_MAP['{classified_topic}']")
            return QUERY_MAP[classified_topic]

    return None


def search_fred(query: str, limit: int = 10) -> list:
    """Search FRED for series matching a query."""
    url = "https://api.stlouisfed.org/fred/series/search"
    params = {
        'search_text': query,
        'api_key': FRED_API_KEY,
        'file_type': 'json',
        'limit': limit,
        'order_by': 'popularity',
        'sort_order': 'desc',
    }
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
            data = resp.json()

        results = []
        for s in data.get('seriess', []):
            results.append({
                'series_id': s['id'],
                'title': s['title'],
                'frequency': s.get('frequency', 'Unknown'),
                'units': s.get('units', ''),
                'seasonal_adjustment': s.get('seasonal_adjustment_short', ''),
                'popularity': s.get('popularity', 0),
            })
        return results
    except Exception as e:
        print(f"FRED search error: {e}")
        return []


def get_series_via_claude(query: str) -> dict:
    """Use Claude with tools to find relevant FRED series for unusual queries.

    Returns a dict like a query plan: {'series': [...], 'show_yoy': ..., 'explanation': ...}
    """
    if not ANTHROPIC_API_KEY:
        print("WARNING: ANTHROPIC_API_KEY not set - agentic search disabled")
        return None

    print(f"Agentic search starting for: {query}")

    # Define the tools Claude can use
    tools = [
        {
            "name": "search_fred",
            "description": "Search the FRED database for economic data series. Returns a list of matching series with IDs, titles, and metadata. Use this to find relevant series for the user's question.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search terms (e.g., 'manufacturing employment', 'oil prices', 'auto sales')"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "select_series",
            "description": "After searching, call this to select 1-4 series to display to the user. Pick the most relevant, popular, and recently-updated series.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "series_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of FRED series IDs to display (1-4 series)"
                    },
                    "display_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Short, clear display names for each series (e.g., 'Norway GDP', 'Norway Unemployment Rate', 'Norway Inflation'). Must match order of series_ids."
                    },
                    "show_yoy": {
                        "type": "boolean",
                        "description": "Whether to show year-over-year change. True for indexes/levels, False for rates/percentages."
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Brief explanation of why you chose these series and what they show."
                    }
                },
                "required": ["series_ids", "display_names", "show_yoy", "explanation"]
            }
        }
    ]

    system_prompt = """You are an economist assistant helping users find economic and financial data.

AVAILABLE DATA SOURCES (not just FRED!):
1. **FRED** - Federal Reserve Economic Data (search_fred tool)
   - Employment, GDP, inflation, interest rates, international data
   - Use series IDs like: UNRATE, PAYEMS, CPIAUCSL, FEDFUNDS, GDP

2. **Zillow** - Real-time housing data (use series IDs starting with "zillow_")
   - zillow_zhvi_national: National home values (~$360K)
   - zillow_home_value_yoy: Home price YoY change
   - zillow_zori_national: National asking rents (~$2,100/mo)
   - zillow_rent_yoy: Rent YoY change (LEADS CPI rent by 12 months!)

3. **Alpha Vantage** - Stock market data (use series IDs starting with "av_")
   - av_SPY, av_QQQ, av_AAPL, av_MSFT, etc. (any ticker)
   - For "how are stocks doing" or company-specific queries

4. **Shiller CAPE** - Stock market valuation
   - For bubble/valuation queries, the system auto-includes CAPE ratio

5. **EIA** - Energy data (use series IDs starting with "eia_")
   - eia_gasoline_price: Retail gas prices
   - eia_crude_oil: Crude oil prices

WORKFLOW:
1. Call search_fred to find FRED series (if needed)
2. Call select_series with your chosen series - can include zillow_*, av_*, eia_* IDs directly!

SEARCH TIPS for FRED:
- Rent/housing costs: "CPI rent" or "shelter" (CUSR0000SEHA, CUSR0000SAH1)
- Home prices: "case shiller" (CSUSHPINSA) - OR use zillow_zhvi_national for real-time
- Wages: "average hourly earnings"
- Manufacturing: "industrial production"

CRITICAL - show_yoy rules:
- show_yoy=True for price INDEXES (CPI, home prices, rent CPI) - raw index values are meaningless
- show_yoy=True for LEVELS (GDP dollars, employment counts, production indexes)
- show_yoy=False for RATES (unemployment %, interest rates, inflation rates that are already %)
- When showing Zillow YoY series (zillow_rent_yoy, zillow_home_value_yoy), show_yoy=False (already YoY)

CRITICAL - display_names: Keep short but precise. Include country for international data."""

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        messages = [{"role": "user", "content": f"Find relevant economic data for: {query}"}]

        # First API call - Claude will likely call search_fred
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        # Process tool calls in a loop (max 5 iterations)
        for iteration in range(5):
            print(f"  Iteration {iteration + 1}, stop_reason: {response.stop_reason}")

            if response.stop_reason == "end_turn":
                print("  Claude ended without tool call")
                # Check if there's text content we can use
                for block in response.content:
                    if hasattr(block, 'text'):
                        print(f"  Claude said: {block.text[:200]}...")
                break

            # Find tool use blocks
            tool_uses = [block for block in response.content if block.type == "tool_use"]
            if not tool_uses:
                print("  No tool calls found in response")
                break

            print(f"  Tool calls: {[t.name for t in tool_uses]}")

            # Process each tool call
            tool_results = []
            final_result = None

            for tool_use in tool_uses:
                if tool_use.name == "search_fred":
                    # Execute FRED search
                    search_query = tool_use.input.get("query", query)
                    print(f"  Searching FRED for: {search_query}")
                    results = search_fred(search_query)
                    print(f"  FRED returned {len(results)} results")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(results[:10])  # Limit results
                    })

                elif tool_use.name == "select_series":
                    # Claude has made its selection - we're done
                    selected = tool_use.input.get("series_ids", [])[:4]
                    display_names = tool_use.input.get("display_names", [])[:4]
                    print(f"  Claude selected series: {selected}")
                    print(f"  Display names: {display_names}")
                    final_result = {
                        "series": selected,
                        "display_names": display_names,
                        "show_yoy": tool_use.input.get("show_yoy", False),
                        "explanation": tool_use.input.get("explanation", ""),
                        "agentic": True  # Flag that this came from agentic search
                    }
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": "Selection recorded."
                    })

            if final_result:
                return final_result

            # Continue conversation with tool results
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                tools=tools,
                messages=messages
            )

        print("  Loop exhausted - Claude never called select_series")
        return None

    except Exception as e:
        import traceback
        print(f"Claude agentic search error: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return None


def get_fred_data(series_id: str, years: int = None) -> tuple:
    """Fetch data from FRED API."""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        'series_id': series_id,
        'api_key': FRED_API_KEY,
        'file_type': 'json',
        'sort_order': 'asc',
    }

    if years:
        start = datetime.now() - timedelta(days=years * 365)
        params['observation_start'] = start.strftime('%Y-%m-%d')

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
            data = resp.json()

        observations = data.get('observations', [])
        dates = []
        values = []
        for obs in observations:
            if obs['value'] != '.':
                dates.append(obs['date'])
                values.append(float(obs['value']))

        # Get series info
        info_url = "https://api.stlouisfed.org/fred/series"
        info_params = {'series_id': series_id, 'api_key': FRED_API_KEY, 'file_type': 'json'}
        with httpx.Client(timeout=10) as client:
            info_resp = client.get(info_url, params=info_params)
            info_data = info_resp.json()

        info = info_data.get('seriess', [{}])[0]
        db_info = SERIES_DB.get(series_id, {})
        info['name'] = db_info.get('name', info.get('title', series_id))
        info['unit'] = db_info.get('unit', info.get('units', ''))
        # Keep FRED notes for AI context (already in info from API response)

        return dates, values, info
    except Exception as e:
        print(f"FRED error for {series_id}: {e}")
        return [], [], {}


def fetch_series_data(series_id: str, years: int = 5) -> tuple:
    """
    Unified data fetcher - routes to appropriate data source based on series prefix.

    Supports:
    - av_* -> Alpha Vantage (stocks, forex, treasuries)
    - zillow_* -> Zillow (housing data)
    - eia_* -> EIA (energy data)
    - shiller_cape -> Shiller CAPE ratio
    - International series -> DBnomics
    - Everything else -> FRED

    Returns: (dates, values, info) tuple
    """
    # Alpha Vantage series
    if series_id.startswith('av_') and ALPHAVANTAGE_AVAILABLE:
        try:
            return get_alphavantage_series(series_id)
        except Exception as e:
            print(f"Alpha Vantage error for {series_id}: {e}")
            return [], [], {}

    # Shiller CAPE
    if series_id == 'shiller_cape' and SHILLER_AVAILABLE:
        try:
            cape_data = get_cape_series()
            return cape_data['dates'], cape_data['values'], cape_data['info']
        except Exception as e:
            print(f"Shiller error: {e}")
            return [], [], {}

    # Zillow series
    if series_id.startswith('zillow_') and ZILLOW_AVAILABLE:
        try:
            return get_zillow_series(series_id)
        except Exception as e:
            print(f"Zillow error for {series_id}: {e}")
            return [], [], {}

    # EIA series
    if series_id.startswith('eia_') and EIA_AVAILABLE:
        try:
            return get_eia_series(series_id)
        except Exception as e:
            print(f"EIA error for {series_id}: {e}")
            return [], [], {}

    # DBnomics (international) series
    if DBNOMICS_AVAILABLE:
        try:
            if series_id in INTERNATIONAL_SERIES:
                return get_observations_dbnomics(series_id)
        except Exception as e:
            print(f"DBnomics error for {series_id}: {e}")

    # Default to FRED
    return get_fred_data(series_id, years)


def calculate_yoy(dates: list, values: list) -> tuple:
    """Calculate year-over-year percent change.

    Uses proper month-based comparison (Dec 2025 vs Dec 2024) rather than
    day-based (365 days back), which is how FRED calculates YoY.
    """
    if len(dates) < 2:
        return dates, values

    # Detect frequency by looking at date gaps
    date_objs = [datetime.strptime(d, '%Y-%m-%d') for d in dates[:min(5, len(dates))]]
    if len(date_objs) >= 2:
        avg_gap = sum((date_objs[i+1] - date_objs[i]).days for i in range(len(date_objs)-1)) / (len(date_objs)-1)
        if avg_gap > 60:  # Quarterly
            min_obs = 4
        elif avg_gap > 20:  # Monthly
            min_obs = 12
        else:  # Weekly
            min_obs = 52
    else:
        min_obs = 12

    if len(dates) < min_obs + 1:
        return dates, values

    date_to_value = dict(zip(dates, values))
    yoy_dates, yoy_values = [], []

    for i, date_str in enumerate(dates[min_obs:], min_obs):
        date = datetime.strptime(date_str, '%Y-%m-%d')

        # Calculate exactly 12 months ago (same month, previous year)
        # This matches FRED's YoY calculation method
        try:
            year_ago = date.replace(year=date.year - 1)
            year_ago_str = year_ago.strftime('%Y-%m-%d')
        except ValueError:
            # Handle Feb 29 -> Feb 28 for non-leap years
            year_ago = date.replace(year=date.year - 1, day=28)
            year_ago_str = year_ago.strftime('%Y-%m-%d')

        # Look for exact match first, then try nearby dates (for weekly data)
        found = False
        for check_str in [year_ago_str]:
            if check_str in date_to_value and date_to_value[check_str] != 0:
                base_value = date_to_value[check_str]
                yoy = ((values[i] - base_value) / base_value) * 100
                yoy_dates.append(date_str)
                yoy_values.append(yoy)
                found = True
                break

        # Fallback for weekly data: try nearby dates within 7 days
        if not found and avg_gap < 20:
            for offset in range(1, 8):
                for direction in [1, -1]:
                    check = (year_ago + timedelta(days=offset * direction)).strftime('%Y-%m-%d')
                    if check in date_to_value and date_to_value[check] != 0:
                        base_value = date_to_value[check]
                        yoy = ((values[i] - base_value) / base_value) * 100
                        yoy_dates.append(date_str)
                        yoy_values.append(yoy)
                        found = True
                        break
                if found:
                    break

    return yoy_dates, yoy_values


def get_ai_summary(query: str, series_data: list, conversation_history: list = None) -> dict:
    """Get AI-generated summary, chart descriptions, and follow-up suggestions from Claude."""
    # Build series IDs list for default response
    series_ids = [sid for sid, dates, values, info in series_data if values]

    default_response = {
        "summary": "Economic data loaded successfully.",
        "suggestions": ["How is inflation trending?", "What's the unemployment rate?"],
        "chart_descriptions": {sid: "" for sid in series_ids}
    }

    if not ANTHROPIC_API_KEY:
        return default_response

    # Build RICH context with analytics for better descriptions
    context_parts = []
    for sid, dates, values, info in series_data:
        if values and len(values) > 0:
            latest = values[-1]
            latest_date = dates[-1]
            name = info.get('name', sid)
            unit = info.get('unit', '')

            # Start with basic info
            lines = [f"**{name} ({sid})**: {latest:.2f} {unit} as of {latest_date}"]

            # Add YoY change if enough data
            if len(values) >= 13:
                prev_year = values[-13]
                if prev_year != 0:
                    yoy_change = values[-1] - prev_year
                    yoy_pct = (yoy_change / abs(prev_year)) * 100
                    lines.append(f"  - YoY change: {yoy_change:+.2f} ({yoy_pct:+.1f}%)")

            # Add 3-month change
            if len(values) >= 4:
                three_mo_ago = values[-4]
                if three_mo_ago != 0:
                    three_mo_change = values[-1] - three_mo_ago
                    three_mo_pct = (three_mo_change / abs(three_mo_ago)) * 100
                    trend = "rising" if three_mo_pct > 0.5 else ("falling" if three_mo_pct < -0.5 else "flat")
                    lines.append(f"  - 3-month trend: {trend} ({three_mo_pct:+.1f}%)")

            # Add 52-week high/low (or available data)
            lookback = min(52, len(values))
            if lookback > 12:
                recent_vals = values[-lookback:]
                recent_dates = dates[-lookback:]
                peak_val = max(recent_vals)
                trough_val = min(recent_vals)
                peak_idx = recent_vals.index(peak_val)
                trough_idx = recent_vals.index(trough_val)

                if peak_val != 0:
                    pct_from_peak = ((latest - peak_val) / abs(peak_val)) * 100
                    if abs(pct_from_peak) > 2:  # Only mention if >2% from peak
                        lines.append(f"  - 52-week high: {peak_val:.2f} ({recent_dates[peak_idx]}), currently {pct_from_peak:.1f}% from peak")

                if trough_val != 0:
                    pct_from_trough = ((latest - trough_val) / abs(trough_val)) * 100
                    if pct_from_trough > 2:  # Only mention if notably above trough
                        lines.append(f"  - 52-week low: {trough_val:.2f} ({recent_dates[trough_idx]}), currently {pct_from_trough:+.1f}% above")

            context_parts.append("\n".join(lines))

    context = "\n\n".join(context_parts)

    # Build background info from FRED notes
    background_parts = []
    for sid, dates, values, info in series_data:
        notes = info.get('notes', '')
        if notes:
            name = info.get('name', sid)
            # Truncate very long notes
            if len(notes) > 500:
                notes = notes[:500] + "..."
            background_parts.append(f"**{name} ({sid})**: {notes}")

    background = "\n\n".join(background_parts) if background_parts else ""

    # Build conversation context if this is a follow-up
    conv_context = ""
    if conversation_history:
        conv_parts = []
        for item in conversation_history[-3:]:  # Last 3 exchanges max
            conv_parts.append(f"User: {item.get('query', '')}")
            conv_parts.append(f"Assistant: {item.get('summary', '')}")
        conv_context = "Previous conversation:\n" + "\n".join(conv_parts) + "\n\n"

    # Build chart descriptions format hint
    chart_desc_format = ", ".join([f'"{sid}": "description"' for sid in series_ids])

    prompt = f"""You are an economist assistant helping users explore U.S. economic data.

{conv_context}User asked: "{query}"

Current data:
{context}

{"Background on these indicators (from FRED):" + chr(10) + background if background else ""}

Respond with JSON in exactly this format:
{{
  "summary": "Your 2-3 sentence summary answering their question with specific numbers and context.",
  "chart_descriptions": {{{chart_desc_format}}},
  "suggestions": ["First follow-up question?", "Second follow-up question?"]
}}

Guidelines:
- Summary: Be concise, avoid jargon, use flowing prose (no bullets). Directly answer their question using the analytics provided.
- Chart descriptions: For EACH series, write 1-2 sentences putting the value in meaningful RECENT context:

  CRITICAL RULES FOR CHART DESCRIPTIONS:
  1. NEVER reference ancient base periods for index series. Do NOT say "282 means prices are 2.8x higher than 1982-84." The base period is irrelevant to users.
  2. For index series (CPI, PPI, etc.), focus on CHANGE not level. The absolute index value is meaningless. Describe YoY change, recent trend, or distance from recent peaks.
  3. Put values in context of the past 1-5 years, NOT decades. Compare to: year-ago, recent peaks/troughs, or pre-pandemic if relevant.
  4. For rates (unemployment, interest rates, inflation %), describe the recent trajectory: "has ticked up 0.3pp over 6 months" or "declining from 4.5% to 2.8%".
  5. Lead with what matters: direction and magnitude of recent change, then context.
  6. For JOBS/PAYROLL data (PAYEMS, etc.): NEVER use YoY percentage change. Describe jobs in terms of "X jobs added per month" or "X jobs added over the past year". Jobs are best understood as absolute numbers, not percentages.

  GOOD: "Gas prices are down 8% from a year ago and 15% below their June 2022 peak."
  BAD: "The CPI for gasoline is 282.98, meaning prices are nearly 3x higher than in the 1980s."
  GOOD: "Unemployment has ticked up 0.3pp over the past 6 months but remains historically low."
  BAD: "The unemployment rate is 4.1%."

- Suggestions: Ask specific, relevant follow-ups (e.g., "How does this compare to pre-pandemic levels?" not "What is GDP?")

Return only valid JSON, no other text."""

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(response.content[0].text)
        return {
            "summary": result.get("summary", default_response["summary"]),
            "suggestions": result.get("suggestions", default_response["suggestions"])[:2],
            "chart_descriptions": result.get("chart_descriptions", default_response["chart_descriptions"])
        }
    except Exception as e:
        print(f"Claude error: {e}")
        return default_response


def get_recessions_in_range(min_date: str, max_date: str) -> list:
    """Get recession periods that overlap with the date range."""
    recessions = []
    for start, end in RECESSIONS:
        if end >= min_date and start <= max_date:
            recessions.append({
                'start': max(start, min_date),
                'end': min(end, max_date),
            })
    return recessions


def format_chart_data(series_data: list, payems_show_level: bool = False) -> list:
    """Format series data for Plotly.js on the frontend.

    Args:
        series_data: List of (series_id, dates, values, info) tuples
        payems_show_level: If True, show PAYEMS as total employment level instead of monthly changes
    """
    charts = []

    # Series that are already rates/percentages - show pp change, not % change
    RATE_SERIES = {'UNRATE', 'FEDFUNDS', 'DGS10', 'DGS2', 'MORTGAGE30US', 'T10Y2Y', 'PSAVERT', 'CIVPART', 'U6RATE'}
    # Series that are already growth rates - don't show any YoY (it would be "YoY change in YoY change")
    GROWTH_RATE_SERIES = {'A191RO1Q156NBEA', 'A191RL1Q225SBEA', 'GDPNOW'}
    # Series where data is already YoY transformed - don't double-transform
    ALREADY_YOY_SERIES = set()  # Will be marked by name containing "YoY"

    for sid, dates, values, info in series_data:
        if not values:
            continue

        # Calculate latest value and change
        latest = values[-1]
        latest_date = dates[-1]

        # Determine series type
        name = info.get('name', sid)
        is_already_yoy = 'YoY' in name or 'YoY' in info.get('unit', '')
        is_rate = sid in RATE_SERIES
        is_growth_rate = sid in GROWTH_RATE_SERIES

        # Special handling for PAYEMS - show monthly job gains, not level
        display_value = latest
        display_unit = info.get('unit', '')
        is_job_change = False
        three_mo_avg = None
        yoy_change = None
        yoy_type = 'percent'  # 'percent', 'pp', 'jobs', or None

        # For chart data - may be transformed for PAYEMS
        chart_dates = dates
        chart_values = values

        # Flag for PAYEMS level display (value is in thousands, so 159500 = 159.5M)
        is_payems_level = False

        if sid == 'PAYEMS' and payems_show_level:
            # Show total employment LEVEL (not changes)
            # Used for "total payrolls" / "nonfarm payrolls" queries
            display_value = latest  # Value in thousands (e.g., 159500 = 159.5M)
            display_unit = 'Thousands of Persons'
            is_job_change = False
            is_payems_level = True  # Template needs this to show as millions
            # YoY change in total jobs
            if len(values) >= 13:
                yoy_change = values[-1] - values[-13]
                yoy_type = 'jobs'

        elif sid == 'PAYEMS' and len(values) >= 4:
            # Show 3-month average job gains (more stable than single month)
            # Used for "how is the economy" type queries
            three_mo_avg = (values[-1] - values[-4]) / 3
            mom_change = values[-1] - values[-2]  # Keep single month for reference
            display_value = three_mo_avg  # Headline is 3-mo avg
            display_unit = 'Thousands of Jobs (Monthly Change)'
            is_job_change = True
            # YoY: total jobs added over the year
            if len(values) >= 13:
                yoy_change = values[-1] - values[-13]
                yoy_type = 'jobs'

            # Compute monthly changes for the CHART (not just the headline)
            # This makes the chart show job gains/losses over time
            chart_values = []
            chart_dates = []
            for i in range(1, len(values)):
                chart_values.append(values[i] - values[i-1])
                chart_dates.append(dates[i])

        elif sid == 'PAYEMS' and len(values) >= 2:
            # Fallback if not enough data for 3-mo avg
            mom_change = values[-1] - values[-2]
            three_mo_avg = mom_change
            display_value = mom_change
            display_unit = 'Thousands of Jobs (Monthly Change)'
            is_job_change = True
            if len(values) >= 13:
                yoy_change = values[-1] - values[-13]
                yoy_type = 'jobs'

            # Compute monthly changes for chart
            chart_values = []
            chart_dates = []
            for i in range(1, len(values)):
                chart_values.append(values[i] - values[i-1])
                chart_dates.append(dates[i])

        elif is_already_yoy or is_growth_rate:
            # Already a rate/change - don't show any YoY comparison
            yoy_change = None
            yoy_type = None

        elif is_rate:
            # Show percentage point change, not percent change
            if len(values) >= 13:
                yoy_change = latest - values[-13]  # pp change
                yoy_type = 'pp'

        else:
            # Normal series - show % change YoY
            if len(values) >= 13:
                prev = values[-13]
                if prev != 0:
                    yoy_change = ((latest - prev) / abs(prev)) * 100
                    yoy_type = 'percent'

        # Get recessions for this date range
        recessions = get_recessions_in_range(dates[0], dates[-1]) if dates else []

        # Get source and seasonal adjustment info
        db_info = SERIES_DB.get(sid, {})
        source = db_info.get('source', 'FRED')
        sa = db_info.get('sa', False)
        bullets = db_info.get('bullets', [])

        # Get FRED notes for educational content (fallback if no bullets)
        notes = info.get('notes', '')
        # Clean up notes - take first 2-3 sentences for brevity
        if notes:
            sentences = notes.replace('\n', ' ').split('. ')
            notes = '. '.join(sentences[:3]) + ('.' if len(sentences) > 0 else '')

        # Generate description from bullets or notes
        description = bullets[0] if bullets else (notes if notes else '')

        charts.append({
            'series_id': sid,
            'name': info.get('name', sid),
            'unit': display_unit,
            'dates': chart_dates,
            'values': chart_values,
            'latest': display_value,
            'latest_date': latest_date,
            'yoy_change': yoy_change,
            'yoy_type': yoy_type,  # 'percent', 'pp', 'jobs', or None
            'recessions': recessions,
            'source': source,
            'sa': sa,
            'notes': notes,
            'bullets': bullets,
            'description': description,
            'is_job_change': is_job_change,
            'is_payems_level': is_payems_level,  # PAYEMS level (value in thousands)
            'three_mo_avg': three_mo_avg,
        })

    return charts


# Routes

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Landing page."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "examples": [
            "How is the economy?",
            "What's the unemployment rate?",
            "Is inflation coming down?",
            "Are we in a recession?",
        ]
    })


@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, query: str = Form(...), history: str = Form(default="")):
    """Handle search query - returns HTMX partial with full data source support."""
    import traceback

    try:
        # Parse conversation history from JSON
        conversation_history = []
        if history:
            try:
                conversation_history = json.loads(history)
            except json.JSONDecodeError:
                pass

        # Special data for enhanced responses
        polymarket_html = None
        cape_html = None
        recession_html = None

        # =================================================================
        # ROUTE 1: Health Check Queries (megacap, labor market, etc.)
        # =================================================================
        health_check_handled = False
        if HEALTH_CHECK_AVAILABLE and is_health_check_query(query):
            entity = detect_health_check_entity(query)
            if entity:
                health_config = get_health_check_config(entity)
                if health_config:
                    series_ids = health_config.primary_series[:4]
                    show_yoy = health_config.show_yoy[:4] if health_config.show_yoy else [False] * len(series_ids)
                    payems_show_level = False
                    agentic_search = False
                    agentic_display_names = []
                    fallback_mode = False
                    health_check_handled = True
                    print(f"[HealthCheck] Routed '{query}' to entity '{entity}' with series {series_ids}")

        # =================================================================
        # ROUTE 2: Valuation/Bubble Queries (Shiller CAPE)
        # =================================================================
        if SHILLER_AVAILABLE and is_valuation_query(query):
            try:
                cape_current = get_current_cape()
                cape_value = cape_current['current_value']
                percentile = cape_current['percentile']
                vs_avg = cape_current['vs_average']['premium_pct']
                dot_com_peak = cape_current['comparisons'].get('dot_com_peak', 44.2)
                vs_dot_com = cape_current['comparisons'].get('vs_dot_com_pct', 0)

                color = "#dc2626" if percentile >= 90 else "#f59e0b" if percentile >= 75 else "#3b82f6"
                status = "Extremely Elevated" if percentile >= 90 else "Elevated" if percentile >= 75 else "Above Average"

                # FastAPI UI style - clean white card matching other boxes
                vs_avg_color = "text-red-600" if vs_avg >= 50 else "text-amber-600" if vs_avg >= 25 else "text-slate-900"
                vs_dot_com_color = "text-emerald-600" if vs_dot_com < 0 else "text-red-600"
                cape_html = f"""
                <div class="bg-white rounded-2xl border border-slate-200 shadow-sm mb-6 overflow-hidden">
                    <div class="px-6 py-4 border-b border-slate-100">
                        <div class="flex items-center justify-between">
                            <div>
                                <h3 class="font-semibold text-slate-900">Shiller CAPE Ratio</h3>
                                <p class="text-sm text-slate-500">143 years of valuation history</p>
                            </div>
                            <span class="px-3 py-1 rounded-full text-xs font-semibold text-white" style="background: {color}">{status}</span>
                        </div>
                    </div>
                    <div class="grid grid-cols-4 gap-4 text-center px-6 py-4">
                        <div><p class="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Current</p><p class="text-2xl font-bold text-slate-900">{cape_value:.1f}</p><p class="text-xs text-slate-400">{percentile:.0f}th percentile</p></div>
                        <div><p class="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">vs Average</p><p class="text-2xl font-bold {vs_avg_color}">+{vs_avg:.0f}%</p><p class="text-xs text-slate-400">Avg: 17</p></div>
                        <div><p class="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">vs Dot-Com</p><p class="text-2xl font-bold {vs_dot_com_color}">{vs_dot_com:+.0f}%</p><p class="text-xs text-slate-400">Peak: {dot_com_peak:.1f}</p></div>
                        <div><p class="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">History</p><p class="text-2xl font-bold text-blue-600">143yr</p><p class="text-xs text-slate-400">Since 1881</p></div>
                    </div>
                    <div class="px-6 py-3 bg-slate-50 border-t border-slate-100">
                        <p class="text-sm text-slate-600">{cape_current['interpretation']}</p>
                    </div>
                </div>
                """
                print(f"[CAPE] Current: {cape_value:.1f} ({percentile:.0f}th percentile)")
            except Exception as e:
                print(f"[CAPE] Error: {e}")

        # =================================================================
        # ROUTE 3: Recession Queries (Scorecard)
        # =================================================================
        if RECESSION_SCORECARD_AVAILABLE and is_recession_query(query):
            try:
                # Fetch recession indicators
                sahm_dates, sahm_values, _ = get_fred_data('SAHMREALTIME', years=2)
                yc_dates, yc_values, _ = get_fred_data('T10Y2Y', years=2)
                claims_dates, claims_values, _ = get_fred_data('ICSA', years=2)
                sent_dates, sent_values, _ = get_fred_data('UMCSENT', years=2)

                sahm = sahm_values[-1] if sahm_values else None
                yield_curve = yc_values[-1] if yc_values else None
                claims = sum(claims_values[-4:]) / 4 if claims_values and len(claims_values) >= 4 else None
                sentiment = sent_values[-1] if sent_values else None

                scorecard = build_recession_scorecard(
                    sahm_value=sahm, yield_curve_value=yield_curve,
                    sentiment_value=sentiment, claims_value=claims
                )
                recession_html = format_scorecard_for_display(scorecard)
                print(f"[Recession] Scorecard built - overall risk: {scorecard.get('overall_risk', 'unknown')}")
            except Exception as e:
                print(f"[Recession] Error: {e}")

        # =================================================================
        # ROUTE 4: Polymarket Predictions
        # =================================================================
        if POLYMARKET_AVAILABLE:
            try:
                predictions = find_relevant_predictions(query)[:3]
                if predictions:
                    polymarket_html = format_predictions_box(predictions, query)
                    print(f"[Polymarket] Found {len(predictions)} relevant predictions")
            except Exception as e:
                print(f"[Polymarket] Error: {e}")

        # =================================================================
        # STANDARD ROUTING: Query Plans or Agentic Search
        # =================================================================
        # Check if we already have series from health check routing
        if not health_check_handled:
            plan = find_query_plan(query)
            agentic_search = False
            agentic_display_names = []
            fallback_mode = False

            if plan:
                series_ids = plan.get('series', [])[:4]
                show_yoy = plan.get('show_yoy', False)
                payems_show_level = plan.get('payems_show_level', False)
            else:
                # No pre-defined plan - use Claude to search
                print(f"No plan found for '{query}', trying agentic search...")
                agentic_plan = get_series_via_claude(query)

                if agentic_plan and agentic_plan.get('series'):
                    series_ids = agentic_plan['series'][:4]
                    agentic_display_names = agentic_plan.get('display_names', [])
                    show_yoy = agentic_plan.get('show_yoy', False)
                    payems_show_level = False
                    agentic_search = True
                    print(f"Agentic search found: {series_ids}")
                else:
                    print("Agentic search failed, using default series")
                    series_ids = ['PAYEMS', 'UNRATE', 'A191RO1Q156NBEA', 'CPIAUCSL']
                    show_yoy = [False, False, False, True]
                    payems_show_level = False
                    fallback_mode = True

        # Fetch data using unified fetcher (supports av_*, zillow_*, eia_*, etc.)
        series_data = []
        for i, sid in enumerate(series_ids):
            dates, values, info = fetch_series_data(sid)
            if dates and values:
                # Override name with agentic display name if available
                if agentic_search and i < len(agentic_display_names) and agentic_display_names[i]:
                    info['name'] = agentic_display_names[i]

                # Apply YoY if needed (with type safety guards)
                db_info = SERIES_DB.get(sid, {})
                data_type = db_info.get('data_type', 'level')

                # Determine if YoY should be applied
                apply_yoy = False
                if isinstance(show_yoy, list) and i < len(show_yoy):
                    apply_yoy = show_yoy[i]
                elif isinstance(show_yoy, bool):
                    apply_yoy = show_yoy
                elif db_info.get('show_yoy', False):
                    apply_yoy = True

                # TYPE SAFETY GUARDS - never apply YoY to:
                # 1. Rates (unemployment rate, interest rates) - already percentages
                # 2. Spreads (yield curve) - already differences
                # 3. Growth rates (GDP growth) - already percent changes
                # 4. Series marked show_absolute_change (employment counts)
                if data_type in ('rate', 'spread', 'growth_rate'):
                    apply_yoy = False
                if db_info.get('show_absolute_change', False):
                    apply_yoy = False

                if apply_yoy and len(dates) > 12:
                    dates, values = calculate_yoy(dates, values)
                    # Use custom YoY name/unit if available
                    yoy_name = db_info.get('yoy_name', info.get('name', sid) + ' (YoY %)')
                    yoy_unit = db_info.get('yoy_unit', '% Change YoY')
                    info['name'] = yoy_name
                    info['unit'] = yoy_unit
                    info['is_yoy'] = True

                series_data.append((sid, dates, values, info))

        # Get AI summary and suggestions
        ai_response = get_ai_summary(query, series_data, conversation_history)
        summary = ai_response["summary"]
        suggestions = ai_response["suggestions"]
        chart_descriptions = ai_response.get("chart_descriptions", {})

        # If we fell back to default data, acknowledge we couldn't find specific data
        if fallback_mode:
            summary = f"I wasn't able to find data specifically about \"{query}\" in FRED. Here are some key indicators showing the current state of the U.S. economy: {summary}"

        # Format for frontend
        charts = format_chart_data(series_data, payems_show_level=payems_show_level)

        # Add Claude's descriptions to each chart
        for chart in charts:
            chart['description'] = chart_descriptions.get(chart['series_id'], '')

        # Update conversation history for next request
        new_history = conversation_history + [{"query": query, "summary": summary}]
        # Keep last 5 exchanges
        new_history = new_history[-5:]

        # Check if this is an HTMX request
        is_htmx = request.headers.get("HX-Request") == "true"

        template_context = {
            "request": request,
            "query": query,
            "summary": summary,
            "charts": charts,
            "suggestions": suggestions,
            "history": json.dumps(new_history),
            # Enhanced data boxes
            "polymarket_html": polymarket_html,
            "cape_html": cape_html,
            "recession_html": recession_html,
        }

        if is_htmx:
            return templates.TemplateResponse("partials/results.html", template_context)
        else:
            # Non-HTMX request (e.g., direct form POST) - return full page
            return templates.TemplateResponse("results_full.html", template_context)
    except Exception as e:
        print(f"Search error: {e}")
        print(traceback.format_exc())
        # Return a simple error response
        return HTMLResponse(
            content=f"<div class='p-4 text-red-600'>Error: {str(e)}</div>",
            status_code=500
        )


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    """About page."""
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
