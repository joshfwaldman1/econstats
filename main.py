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

# =============================================================================
# ADVANCED AGENT MODULES (ported from Streamlit)
# =============================================================================

# Query Understanding - deep semantic analysis of user intent
try:
    from agents.query_understanding import understand_query, get_routing_recommendation, validate_series_for_query
    QUERY_UNDERSTANDING_AVAILABLE = True
except Exception as e:
    print(f"Query understanding not available: {e}")
    QUERY_UNDERSTANDING_AVAILABLE = False

# Query Router - handles comparisons and multi-region queries
try:
    from agents.query_router import smart_route_query, is_comparison_query, route_comparison_query
    QUERY_ROUTER_AVAILABLE = True
except Exception as e:
    print(f"Query router not available: {e}")
    QUERY_ROUTER_AVAILABLE = False

# Series RAG - embedding-based series retrieval
try:
    from agents.series_rag import rag_query_plan, retrieve_relevant_series
    RAG_AVAILABLE = True
except Exception as e:
    print(f"Series RAG not available: {e}")
    RAG_AVAILABLE = False

# Stocks module - market queries
try:
    from agents.stocks import find_market_plan, is_market_query, MARKET_SERIES
    STOCKS_AVAILABLE = True
except Exception as e:
    print(f"Stocks module not available: {e}")
    STOCKS_AVAILABLE = False

# Fed SEP - Federal Reserve projections
try:
    from agents.fed_sep import is_fed_related_query, is_sep_query, get_fed_guidance_for_query, get_sep_data, get_current_fed_funds_rate
    FED_SEP_AVAILABLE = True
except Exception as e:
    print(f"Fed SEP not available: {e}")
    FED_SEP_AVAILABLE = False

# Judgment Layer - interpretive queries with web search
try:
    from agents.judgment_layer import is_judgment_query, process_judgment_query
    JUDGMENT_AVAILABLE = True
except Exception as e:
    print(f"Judgment layer not available: {e}")
    JUDGMENT_AVAILABLE = False

# Agent Ensemble - multi-model query planning
try:
    from agents.agent_ensemble import call_ensemble_for_app, generate_ensemble_description
    ENSEMBLE_AVAILABLE = True
except Exception as e:
    print(f"Agent ensemble not available: {e}")
    ENSEMBLE_AVAILABLE = False

# Startup diagnostics
print("=" * 60)
print("EconStats FastAPI Starting Up")
print("=" * 60)
print(f"FRED_API_KEY: {'SET' if FRED_API_KEY else 'NOT SET'}")
print(f"ANTHROPIC_API_KEY: {'SET' if ANTHROPIC_API_KEY else 'NOT SET'}")
print(f"GOOGLE_API_KEY: {'SET' if GOOGLE_API_KEY else 'NOT SET'}")
print(f"ALPHAVANTAGE_API_KEY: {'SET' if ALPHAVANTAGE_API_KEY else 'NOT SET'}")
print("-" * 60)
print("Data Sources:")
print(f"  ALPHAVANTAGE: {ALPHAVANTAGE_AVAILABLE}")
print(f"  SHILLER: {SHILLER_AVAILABLE}")
print(f"  POLYMARKET: {POLYMARKET_AVAILABLE}")
print(f"  RECESSION_SCORECARD: {RECESSION_SCORECARD_AVAILABLE}")
print(f"  ZILLOW: {ZILLOW_AVAILABLE}")
print(f"  EIA: {EIA_AVAILABLE}")
print(f"  DBNOMICS: {DBNOMICS_AVAILABLE}")
print(f"  HEALTH_CHECK: {HEALTH_CHECK_AVAILABLE}")
print("-" * 60)
print("Agent Modules:")
print(f"  QUERY_UNDERSTANDING: {QUERY_UNDERSTANDING_AVAILABLE}")
print(f"  QUERY_ROUTER: {QUERY_ROUTER_AVAILABLE}")
print(f"  RAG: {RAG_AVAILABLE}")
print(f"  STOCKS: {STOCKS_AVAILABLE}")
print(f"  FED_SEP: {FED_SEP_AVAILABLE}")
print(f"  JUDGMENT: {JUDGMENT_AVAILABLE}")
print(f"  ENSEMBLE: {ENSEMBLE_AVAILABLE}")
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

    # Trade Overview - show balance, imports, and exports together
    'trade': {'series': ['BOPGSTB', 'IMPGS', 'EXPGS'], 'combine': False, 'show_yoy': False},
    'trade balance': {'series': ['BOPGSTB', 'IMPGS', 'EXPGS'], 'combine': False, 'show_yoy': False},
    'trade deficit': {'series': ['BOPGSTB', 'IMPGS', 'EXPGS'], 'combine': False, 'show_yoy': False},
    'trade surplus': {'series': ['BOPGSTB', 'IMPGS', 'EXPGS'], 'combine': False, 'show_yoy': False},
    'imports': {'series': ['IMPGS', 'BOPGSTB'], 'combine': False, 'show_yoy': False},
    'exports': {'series': ['EXPGS', 'BOPGSTB'], 'combine': False, 'show_yoy': False},
    'imports and exports': {'series': ['IMPGS', 'EXPGS', 'BOPGSTB'], 'combine': False, 'show_yoy': False},

    # Trade by Category - Goods vs Services
    'goods trade': {'series': ['BOPGTB', 'IMGION', 'EXGION'], 'combine': False, 'show_yoy': False},
    'services trade': {'series': ['BOPSTB', 'BOPSTXSVCS', 'BOPSTMSVCS'], 'combine': False, 'show_yoy': False},
    'trade by category': {'series': ['BOPGTB', 'BOPSTB', 'BOPGSTB'], 'combine': False, 'show_yoy': False},

    # China Trade (bilateral)
    'china': {'series': ['IMPCH', 'EXPCH', 'BOPGTB'], 'combine': False, 'show_yoy': False},
    'china trade': {'series': ['IMPCH', 'EXPCH', 'BOPGTB'], 'combine': False, 'show_yoy': False},
    'trade with china': {'series': ['IMPCH', 'EXPCH', 'BOPGTB'], 'combine': False, 'show_yoy': False},
    'us china trade': {'series': ['IMPCH', 'EXPCH', 'BOPGTB'], 'combine': False, 'show_yoy': False},
    'imports from china': {'series': ['IMPCH'], 'combine': False, 'show_yoy': False},
    'exports to china': {'series': ['EXPCH'], 'combine': False, 'show_yoy': False},

    # Mexico Trade
    'mexico trade': {'series': ['IMPMX', 'EXPMX', 'BOPGTB'], 'combine': False, 'show_yoy': False},
    'trade with mexico': {'series': ['IMPMX', 'EXPMX', 'BOPGTB'], 'combine': False, 'show_yoy': False},
    'imports from mexico': {'series': ['IMPMX'], 'combine': False, 'show_yoy': False},
    'exports to mexico': {'series': ['EXPMX'], 'combine': False, 'show_yoy': False},

    # Canada Trade
    'canada trade': {'series': ['IMPCA', 'EXPCA', 'BOPGTB'], 'combine': False, 'show_yoy': False},
    'trade with canada': {'series': ['IMPCA', 'EXPCA', 'BOPGTB'], 'combine': False, 'show_yoy': False},
    'imports from canada': {'series': ['IMPCA'], 'combine': False, 'show_yoy': False},
    'exports to canada': {'series': ['EXPCA'], 'combine': False, 'show_yoy': False},

    # Japan Trade
    'japan trade': {'series': ['IMPJP', 'EXPJP', 'BOPGTB'], 'combine': False, 'show_yoy': False},
    'trade with japan': {'series': ['IMPJP', 'EXPJP', 'BOPGTB'], 'combine': False, 'show_yoy': False},

    # EU Trade
    'eu trade': {'series': ['IMPEU', 'EXPEU', 'BOPGTB'], 'combine': False, 'show_yoy': False},
    'trade with europe': {'series': ['IMPEU', 'EXPEU', 'BOPGTB'], 'combine': False, 'show_yoy': False},
    'trade with eu': {'series': ['IMPEU', 'EXPEU', 'BOPGTB'], 'combine': False, 'show_yoy': False},

    # Major Trading Partners Overview
    'trading partners': {'series': ['IMPCH', 'IMPMX', 'IMPCA', 'IMPEU'], 'combine': False, 'show_yoy': False},
    'top trading partners': {'series': ['IMPCH', 'IMPMX', 'IMPCA', 'IMPEU'], 'combine': False, 'show_yoy': False},

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


# =============================================================================
# TEMPORAL FILTERING - Extract date ranges from queries
# =============================================================================

def extract_temporal_filter(query: str) -> dict:
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
    if match := re.search(r'\b(?:in|during|for|from)?\s*((?:19|20)\d{2})\b', q):
        year = int(match.group(1))
        if 1950 <= year <= current_year:
            return {
                'temporal_focus': f'{year}',
                'filter_start_date': f'{year}-01-01',
                'filter_end_date': f'{year}-12-31',
                'years_override': max(2, current_year - year + 2),
                'explanation': f'Showing data for {year}.',
            }
        elif year > current_year:
            return {
                'temporal_focus': f'{year} (future)',
                'invalid_temporal': True,
                'explanation': f'Note: {year} is in the future. Showing latest available data.',
            }

    # === Year range ===
    if match := re.search(r'\b(?:from|between)\s*((?:19|20)\d{2})\s*(?:to|and|-)\s*((?:19|20)\d{2})\b', q):
        start_year = int(match.group(1))
        end_year = int(match.group(2))
        if start_year > end_year:
            start_year, end_year = end_year, start_year
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
    if re.search(r'\blast\s+year\b', q):
        last_year = current_year - 1
        return {
            'temporal_focus': f'{last_year}',
            'filter_start_date': f'{last_year}-01-01',
            'filter_end_date': f'{last_year}-12-31',
            'years_override': 3,
            'explanation': f'Showing data for {last_year}.',
        }

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
    if re.search(r'\b(pre[\s-]?(covid|pandemic|2020)|before\s+(covid|pandemic|the\s+pandemic|2020))\b', q):
        return {
            'temporal_focus': 'pre-COVID',
            'filter_end_date': '2020-02-29',
            'years_override': current_year - 2017 + 1,
            'explanation': 'Showing pre-COVID data (through February 2020).',
        }

    if re.search(r'\b(during\s+(covid|pandemic|the\s+pandemic)|covid\s+era|pandemic\s+period)\b', q):
        return {
            'temporal_focus': 'COVID period',
            'filter_start_date': '2020-03-01',
            'filter_end_date': '2021-12-31',
            'years_override': 5,
            'explanation': 'Showing COVID pandemic period (March 2020 - December 2021).',
        }

    if re.search(r'\b(post[\s-]?(covid|pandemic)|after\s+(covid|pandemic|the\s+pandemic)|recovery\s+period)\b', q):
        return {
            'temporal_focus': 'post-COVID',
            'filter_start_date': '2022-01-01',
            'years_override': 4,
            'explanation': 'Showing post-COVID recovery period (2022 onward).',
        }

    if re.search(r'\b(great\s+recession|during\s+(?:the\s+)?recession|2008\s+(?:recession|crisis)|financial\s+crisis)\b', q):
        return {
            'temporal_focus': 'Great Recession',
            'filter_start_date': '2007-12-01',
            'filter_end_date': '2009-06-30',
            'years_override': current_year - 2007 + 1,
            'explanation': 'Showing Great Recession period (December 2007 - June 2009).',
        }

    return None


def get_smart_date_range(query: str, default_years: int = 8) -> int:
    """
    Determine smart date range based on query content.
    Queries about historical events need more data; most queries benefit from focused recent data.
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

    return default_years


# =============================================================================
# GEOGRAPHIC SCOPE DETECTION
# =============================================================================

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
    'west virginia', 'wisconsin', 'wyoming'
}

US_REGIONS = {'midwest', 'northeast', 'south', 'west', 'pacific', 'mountain', 'southeast', 'southwest'}


def detect_geographic_scope(query: str) -> dict:
    """
    Detect if query asks about a specific state or region.
    Returns dict with type ('national', 'state', 'region') and name.
    """
    query_lower = query.lower()

    for state in US_STATES:
        if state in query_lower:
            if state == 'georgia' and 'country' in query_lower:
                continue
            return {'type': 'state', 'name': state}

    for region in US_REGIONS:
        if region in query_lower:
            return {'type': 'region', 'name': region}

    return {'type': 'national', 'name': 'US'}


# =============================================================================
# ECONOMIC EVENTS - For chart annotations
# =============================================================================

ECONOMIC_EVENTS = [
    # Fed Policy Changes
    {'date': '2022-03-17', 'label': 'Fed hikes begin', 'type': 'fed'},
    {'date': '2020-03-15', 'label': 'Emergency cut to 0%', 'type': 'fed'},
    {'date': '2019-07-31', 'label': 'Fed cuts rates', 'type': 'fed'},
    {'date': '2015-12-16', 'label': 'First hike since 2008', 'type': 'fed'},
    {'date': '2008-12-16', 'label': 'Fed cuts to zero', 'type': 'fed'},
    {'date': '2024-09-18', 'label': 'Fed starts cutting', 'type': 'fed'},

    # Major Crises & Peaks
    {'date': '2022-06-01', 'label': 'Inflation peaks 9.1%', 'type': 'crisis'},
    {'date': '2020-04-01', 'label': 'Unemployment hits 14.7%', 'type': 'crisis'},
    {'date': '2020-03-11', 'label': 'COVID pandemic', 'type': 'crisis'},
    {'date': '2023-03-10', 'label': 'SVB collapse', 'type': 'crisis'},
    {'date': '2008-09-15', 'label': 'Lehman collapse', 'type': 'crisis'},

    # Policy Milestones
    {'date': '2017-12-22', 'label': 'Tax Cuts Act', 'type': 'policy'},
    {'date': '2021-03-11', 'label': 'ARP stimulus', 'type': 'policy'},
    {'date': '2022-08-16', 'label': 'IRA signed', 'type': 'policy'},
]


# =============================================================================
# DYNAMIC AI BULLETS - AI-generated chart insights
# =============================================================================

_dynamic_bullet_cache = {}


def generate_dynamic_ai_bullets(series_id: str, dates: list, values: list, info: dict, user_query: str = None) -> list:
    """Generate dynamic AI-powered bullets using Claude.

    Creates contextual, data-aware bullets that:
    1. Reference actual current values and trends
    2. Are tailored to the user's specific question
    3. Provide timely economic context
    """
    if not ANTHROPIC_API_KEY or not values or len(values) < 2:
        db_info = SERIES_DB.get(series_id, {})
        return db_info.get('bullets', [])

    db_info = SERIES_DB.get(series_id, {})
    name = info.get('name', info.get('title', series_id))
    unit = info.get('unit', info.get('units', ''))
    latest = values[-1]
    latest_date = dates[-1]
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

    # Calculate trends
    trend_info = ""
    if len(values) >= 13:
        year_ago = values[-13] if frequency == 'monthly' else values[-5] if frequency == 'quarterly' else values[-2]
        yoy_change = latest - year_ago
        if year_ago != 0:
            yoy_pct = ((latest - year_ago) / abs(year_ago)) * 100
            trend_info = f"Year-over-year change: {yoy_change:+.2f} ({yoy_pct:+.1f}%)"

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

    historical_context = ""
    if len(values) >= 60:
        five_yr_high = max(values[-60:])
        five_yr_low = min(values[-60:])
        historical_context = f"5-year range: {five_yr_low:.2f} to {five_yr_high:.2f}"

    static_bullets = db_info.get('bullets', [])
    static_guidance = "\n".join([f"- {b}" for b in static_bullets]) if static_bullets else ""

    prompt = f"""Generate 2 insightful bullet points that INTERPRET what this economic data means.

SERIES: {name} ({series_id})
CURRENT VALUE: {latest:.2f} {unit} as of {date_str}
{trend_info}
{recent_trend}
{historical_context}

{f"DOMAIN CONTEXT: {static_guidance}" if static_guidance else ""}
{f"USER QUESTION: {user_query}" if user_query else ""}

Write 2 bullets that:
1. INTERPRET what the trend means (e.g., "wages rising faster than inflation means workers gaining purchasing power")
2. Explain the "SO WHAT" - what this means for workers, consumers, or the economy
3. Keep each bullet to 1 sentence max

Format: Return ONLY a JSON array of strings, like: ["First bullet.", "Second bullet."]"""

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text

        if '[' in text and ']' in text:
            start = text.index('[')
            end = text.rindex(']') + 1
            bullets = json.loads(text[start:end])
            if isinstance(bullets, list) and len(bullets) > 0:
                return bullets[:2]
    except Exception as e:
        print(f"[DynamicBullets] Error: {e}")

    return static_bullets[:2] if static_bullets else []


def get_dynamic_bullets(series_id: str, dates: list, values: list, info: dict, user_query: str = None, use_ai: bool = True) -> list:
    """Get bullets for a chart, using AI if enabled or falling back to static. Caches results."""
    if not use_ai:
        db_info = SERIES_DB.get(series_id, {})
        return db_info.get('bullets', [])

    cache_key = f"{series_id}_{values[-1] if values else 'empty'}_{user_query or ''}"

    if cache_key in _dynamic_bullet_cache:
        return _dynamic_bullet_cache[cache_key]

    bullets = generate_dynamic_ai_bullets(series_id, dates, values, info, user_query)
    _dynamic_bullet_cache[cache_key] = bullets

    if len(_dynamic_bullet_cache) > 100:
        keys = list(_dynamic_bullet_cache.keys())
        for k in keys[:50]:
            del _dynamic_bullet_cache[k]

    return bullets


# =============================================================================
# DERIVED SERIES CALCULATIONS
# =============================================================================

def calculate_derived_series(series_data: dict, formula: str, name: str = "Derived Series", unit: str = "") -> tuple:
    """
    Calculate a derived series from multiple input series using pandas.

    Args:
        series_data: Dict mapping series_id -> (dates, values) tuples
        formula: Pandas-compatible formula string, e.g., "B235RC1Q027SBEA / IMPGS * 100"
        name: Display name for the derived series
        unit: Unit label for the derived series

    Returns:
        Tuple of (dates, values, info_dict) for the derived series,
        or (None, None, None) if calculation fails
    """
    import re
    try:
        import pandas as pd
    except ImportError:
        print("[DerivedSeries] pandas not available")
        return None, None, None

    if not series_data or not formula:
        return None, None, None

    try:
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

        combined = dfs[0]
        for df in dfs[1:]:
            combined = combined.join(df, how='outer')

        combined = combined.dropna()

        if combined.empty:
            return None, None, None

        formula_series = re.findall(r'[A-Z][A-Z0-9_]+', formula)
        for sid in formula_series:
            if sid not in combined.columns:
                return None, None, None

        result = combined.eval(formula)

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
        print(f"[DerivedSeries] Error: {e}")
        return None, None, None


# =============================================================================
# ECONOMIST REVIEWER - Second-pass AI review of explanations
# =============================================================================

def call_economist_reviewer(query: str, series_data: list, original_summary: str) -> str:
    """Call a second Claude agent to review and improve the explanation.

    This agent sees actual data values to explain not just WHAT is happening but WHY.
    """
    if not ANTHROPIC_API_KEY or not series_data:
        return original_summary

    # Build data summary for the reviewer
    data_summary = []
    for series_id, dates, values, info in series_data:
        if not values:
            continue
        name = info.get('name', info.get('title', series_id))
        unit = info.get('unit', info.get('units', ''))
        latest = values[-1]
        latest_date = dates[-1]

        yoy_change = None
        if len(values) >= 12:
            yoy_change = latest - values[-12]

        recent_vals = values[-60:] if len(values) >= 60 else values

        summary = {
            'name': name,
            'latest_value': round(latest, 2),
            'latest_date': latest_date,
            'unit': unit,
            'yoy_change': round(yoy_change, 2) if yoy_change else None,
            'recent_min': round(min(recent_vals), 2),
            'recent_max': round(max(recent_vals), 2),
        }

        if yoy_change is not None:
            if yoy_change > 0.01:
                summary['yoy_direction'] = 'UP from year ago'
            elif yoy_change < -0.01:
                summary['yoy_direction'] = 'DOWN from year ago'
            else:
                summary['yoy_direction'] = 'UNCHANGED from year ago'

        data_summary.append(summary)

    if not data_summary:
        return original_summary

    prompt = f"""You are reviewing an economic data explanation. Improve it to be clearer and more insightful.

USER'S QUESTION: "{query}"

ACTUAL DATA:
{json.dumps(data_summary, indent=2)}

ORIGINAL EXPLANATION:
{original_summary}

Improve the explanation to:
1. Reference specific numbers from the data
2. Explain what the trends MEAN (not just describe them)
3. Connect to broader economic context
4. Keep it concise (2-3 sentences max)
5. Use plain language, avoid jargon

Return ONLY the improved explanation, no preamble."""

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        improved = response.content[0].text.strip()
        if len(improved) > 50:  # Sanity check
            return improved
    except Exception as e:
        print(f"[EconomistReviewer] Error: {e}")

    return original_summary


def classify_query_intent(query: str, available_topics: list) -> dict:
    """Use LLM to understand query intent AND how to display data.

    This runs FIRST to intelligently route queries based on semantic understanding.
    Returns dict with 'topic' and 'show_yoy' recommendation.
    """
    if not ANTHROPIC_API_KEY:
        return None

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        # Group topics by category for better LLM understanding
        topics_str = ", ".join(sorted(set(available_topics))[:150])

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": f"""You route economic data queries. Pick the best topic AND decide how to display data.

Question: "{query}"

Available topics: {topics_str}

DISPLAY RULES (show_yoy):
- RATES (unemployment %, interest rates, P/E ratios, CAPE ratio) → show_yoy: false (already meaningful)
- INDEXES (CPI, home price index) → show_yoy: true (raw index meaningless, show inflation rate)
- LEVELS (GDP dollars, employment count, stock prices) → show_yoy: false usually (actual value matters)
- GROWTH questions ("how fast", "growth rate") → show_yoy: true

Reply in format: topic_name|show_yoy
Examples: "inflation|true" or "cape ratio|false" or "unemployment|false" or "none|false" """
            }]
        )

        result = response.content[0].text.strip().lower()
        print(f"[Intent] Query '{query}' -> '{result}'")

        # Parse response
        if "|" in result:
            parts = result.split("|")
            topic = parts[0].strip()
            show_yoy = parts[1].strip() == "true" if len(parts) > 1 else None
        else:
            topic = result.strip()
            show_yoy = None

        if topic != "none" and topic in [t.lower() for t in available_topics]:
            # Find the original casing
            for t in available_topics:
                if t.lower() == topic:
                    return {"topic": t, "show_yoy": show_yoy}
        return None

    except Exception as e:
        print(f"[Intent] Classification error: {e}")
        return None


def find_query_plan(query: str):
    """Find matching query plan using LLM-FIRST routing architecture.

    This is the master router that:
    1. Understands query intent via LLM FIRST
    2. Routes to specialized modules based on query type
    3. Falls back to pattern matching for simple queries

    Priority order:
    1. Fed SEP queries (Fed projections, rate decisions)
    2. Market queries (stocks, indices)
    3. Comparison queries (US vs Europe, demographics)
    4. Quick exact match (common queries)
    5. LLM deep understanding + RAG (complex queries)
    6. Fuzzy match (typos)
    7. Agentic search (last resort)
    """
    normalized = normalize_query(query)
    original_lower = query.lower().strip()

    # Get all available plans
    intl_plans = INTERNATIONAL_QUERY_PLANS if DBNOMICS_AVAILABLE else {}
    all_plans = {}
    all_plans.update(QUERY_MAP)
    all_plans.update(intl_plans)
    all_plans.update(QUERY_PLANS)

    # =================================================================
    # STEP 1: FED SEP QUERIES (takes priority - real-time Fed data)
    # =================================================================
    if FED_SEP_AVAILABLE and is_fed_related_query(query):
        print(f"[Router] Fed-related query detected: '{query}'")
        fed_guidance = get_fed_guidance_for_query(query)
        if fed_guidance:
            print(f"[Router] Using Fed SEP guidance")
            return {
                'series': fed_guidance.get('series', ['FEDFUNDS']),
                'show_yoy': False,
                'fed_guidance': fed_guidance,  # Pass through for display
            }

    # =================================================================
    # STEP 2: MARKET QUERIES (stocks, indices)
    # =================================================================
    if STOCKS_AVAILABLE and is_market_query(query):
        print(f"[Router] Market query detected: '{query}'")
        market_plan = find_market_plan(query)
        if market_plan:
            print(f"[Router] Using market plan: {market_plan.get('series', [])}")
            return market_plan

    # =================================================================
    # STEP 3: COMPARISON QUERIES (US vs Europe, demographics)
    # =================================================================
    if QUERY_ROUTER_AVAILABLE and is_comparison_query(query):
        print(f"[Router] Comparison query detected: '{query}'")
        comparison_plan = route_comparison_query(query)
        if comparison_plan:
            print(f"[Router] Using comparison plan: {comparison_plan.get('series', [])}")
            return comparison_plan

    # =================================================================
    # STEP 4: FAST PATH - Exact match (common single-word queries)
    # =================================================================
    if original_lower in all_plans:
        print(f"[Router] Exact match: '{original_lower}'")
        return all_plans[original_lower]
    if normalized in all_plans:
        print(f"[Router] Normalized match: '{normalized}'")
        return all_plans[normalized]

    # =================================================================
    # STEP 5: LLM DEEP UNDERSTANDING (complex/novel queries)
    # Use query_understanding module if available, else our simpler classifier
    # =================================================================
    understanding = None
    if QUERY_UNDERSTANDING_AVAILABLE:
        try:
            understanding = understand_query(query)
            if understanding:
                print(f"[Router] Query understanding: {understanding.get('query_type', 'unknown')}")

                # Get routing recommendation from understanding
                routing = get_routing_recommendation(understanding)
                if routing and routing.get('suggested_topic'):
                    topic = routing['suggested_topic']
                    if topic in all_plans:
                        plan = all_plans[topic].copy()
                        if routing.get('show_yoy') is not None:
                            plan['show_yoy'] = routing['show_yoy']
                        print(f"[Router] Understanding routed to '{topic}'")
                        return plan
        except Exception as e:
            print(f"[Router] Query understanding error: {e}")

    # Try RAG-based retrieval for complex queries
    if RAG_AVAILABLE and not understanding:
        try:
            rag_plan = rag_query_plan(query)
            if rag_plan and rag_plan.get('series'):
                print(f"[Router] RAG found series: {rag_plan.get('series', [])[:3]}")
                return rag_plan
        except Exception as e:
            print(f"[Router] RAG error: {e}")

    # Simpler LLM classification as fallback
    all_topics = list(all_plans.keys())
    classification = classify_query_intent(query, all_topics)

    if classification and classification.get("topic") in all_plans:
        topic = classification["topic"]
        plan = all_plans[topic].copy()

        if classification.get("show_yoy") is not None:
            print(f"[Router] LLM classified '{query}' -> '{topic}' with show_yoy={classification['show_yoy']}")
            plan["show_yoy"] = classification["show_yoy"]
        else:
            print(f"[Router] LLM classified '{query}' -> '{topic}'")

        return plan

    # =================================================================
    # STEP 6: FUZZY MATCH (catches typos, close variations)
    # =================================================================
    import difflib
    matches = difflib.get_close_matches(normalized, all_topics, n=1, cutoff=0.7)
    if matches:
        print(f"[Router] Fuzzy matched '{normalized}' -> '{matches[0]}'")
        return all_plans[matches[0]]

    print(f"[Router] No match found for '{query}'")
    return None


def is_judgment_needed(query: str) -> bool:
    """Check if query needs interpretive judgment (not just facts)."""
    if JUDGMENT_AVAILABLE:
        return is_judgment_query(query)
    return False


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
   - Employment, GDP, inflation, interest rates, international data, TRADE DATA
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

6. **Trade Data** - FRED has comprehensive US trade data:
   BALANCES:
   - BOPGSTB: Total Trade Balance (goods + services) - THE KEY METRIC
   - BOPGTB: Goods Trade Balance only
   - BOPSTB: Services Trade Balance only

   TOTALS:
   - IMPGS: Total Imports (goods + services)
   - EXPGS: Total Exports (goods + services)

   BY COUNTRY - IMPORTS:
   - IMPCH: Imports from China (largest source)
   - IMPMX: Imports from Mexico
   - IMPCA: Imports from Canada
   - IMPJP: Imports from Japan
   - IMPEU: Imports from EU

   BY COUNTRY - EXPORTS:
   - EXPCH: Exports to China
   - EXPMX: Exports to Mexico
   - EXPCA: Exports to Canada
   - EXPJP: Exports to Japan
   - EXPEU: Exports to EU

WORKFLOW:
1. Call search_fred to find FRED series (if needed)
2. Call select_series with your chosen series - can include zillow_*, av_*, eia_* IDs directly!

SEARCH TIPS for FRED:
- Rent/housing costs: "CPI rent" or "shelter" (CUSR0000SEHA, CUSR0000SAH1)
- Home prices: "case shiller" (CSUSHPINSA) - OR use zillow_zhvi_national for real-time
- Wages: "average hourly earnings"
- Manufacturing: "industrial production"
- Trade: Use the specific series above - don't search, just use them directly!

CRITICAL - show_yoy rules:
- show_yoy=True for price INDEXES (CPI, home prices, rent CPI) - raw index values are meaningless
- show_yoy=True for LEVELS (GDP dollars, employment counts, production indexes)
- show_yoy=False for RATES (unemployment %, interest rates, inflation rates that are already %)
- show_yoy=False for TRADE BALANCES and flows ($ billions - already meaningful)
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


def format_chart_data(series_data: list, payems_show_level: bool = False, user_query: str = None, use_dynamic_bullets: bool = True) -> list:
    """Format series data for Plotly.js on the frontend.

    Args:
        series_data: List of (series_id, dates, values, info) tuples
        payems_show_level: If True, show PAYEMS as total employment level instead of monthly changes
        user_query: Optional user query for contextual dynamic bullets
        use_dynamic_bullets: If True, generate AI-powered contextual bullets
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

        # Generate dynamic AI bullets if enabled, otherwise use static
        if use_dynamic_bullets and ANTHROPIC_API_KEY:
            bullets = get_dynamic_bullets(sid, dates, values, info, user_query, use_ai=True)
        else:
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

        # =================================================================
        # TEMPORAL FILTERING: Extract date ranges from query
        # =================================================================
        temporal_filter = extract_temporal_filter(query)
        years_override = None
        if temporal_filter:
            years_override = temporal_filter.get('years_override')
            print(f"[Temporal] Detected: {temporal_filter.get('temporal_focus', 'none')} -> years={years_override}")

        # Smart date range based on query content
        if not years_override:
            years_override = get_smart_date_range(query, default_years=8)

        # Detect geographic scope (for future regional support)
        geo_scope = detect_geographic_scope(query)
        if geo_scope['type'] != 'national':
            print(f"[Geographic] Detected {geo_scope['type']}: {geo_scope['name']}")

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
        # ROUTE 5: Fed SEP (Federal Reserve Projections)
        # =================================================================
        fed_sep_html = None
        if FED_SEP_AVAILABLE and is_fed_related_query(query):
            try:
                fed_data = get_sep_data()
                fed_rate = get_current_fed_funds_rate()

                if fed_data and fed_rate:
                    current_rate = fed_rate.get('current_rate', 'N/A')
                    rate_decision = fed_rate.get('last_decision', '')
                    projections = fed_data.get('projections', {})

                    # Build Fed SEP display box
                    fed_sep_html = f"""
                    <div class="bg-white rounded-2xl border border-slate-200 shadow-sm mb-6 overflow-hidden">
                        <div class="px-6 py-4 border-b border-slate-100">
                            <div class="flex items-center justify-between">
                                <div>
                                    <h3 class="font-semibold text-slate-900">Federal Reserve Outlook</h3>
                                    <p class="text-sm text-slate-500">FOMC Summary of Economic Projections</p>
                                </div>
                                <span class="px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">{rate_decision}</span>
                            </div>
                        </div>
                        <div class="grid grid-cols-4 gap-4 text-center px-6 py-4">
                            <div>
                                <p class="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Fed Funds Rate</p>
                                <p class="text-2xl font-bold text-slate-900">{current_rate}</p>
                                <p class="text-xs text-slate-400">Current Target</p>
                            </div>
                            <div>
                                <p class="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">GDP Growth</p>
                                <p class="text-2xl font-bold text-emerald-600">{projections.get('gdp_2024', 'N/A')}</p>
                                <p class="text-xs text-slate-400">2024 Median</p>
                            </div>
                            <div>
                                <p class="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Unemployment</p>
                                <p class="text-2xl font-bold text-blue-600">{projections.get('unemployment_2024', 'N/A')}</p>
                                <p class="text-xs text-slate-400">2024 Median</p>
                            </div>
                            <div>
                                <p class="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Core PCE</p>
                                <p class="text-2xl font-bold text-amber-600">{projections.get('core_pce_2024', 'N/A')}</p>
                                <p class="text-xs text-slate-400">2024 Median</p>
                            </div>
                        </div>
                        <div class="px-6 py-3 bg-slate-50 border-t border-slate-100">
                            <p class="text-sm text-slate-600">Source: Federal Reserve FOMC Summary of Economic Projections</p>
                        </div>
                    </div>
                    """
                    print(f"[FedSEP] Added Fed projections box, rate: {current_rate}")
            except Exception as e:
                print(f"[FedSEP] Error: {e}")

        # Track if this is a judgment query (needs interpretive context)
        judgment_context = None
        if JUDGMENT_AVAILABLE and is_judgment_query(query):
            print(f"[Judgment] Query requires interpretive context: '{query}'")

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

        # =================================================================
        # JUDGMENT LAYER: Add interpretive context for judgment queries
        # =================================================================
        if JUDGMENT_AVAILABLE and is_judgment_query(query):
            try:
                # Get the series IDs we're displaying
                displayed_series = [sd[0] for sd in series_data]
                judgment_result = process_judgment_query(
                    query=query,
                    series_ids=displayed_series,
                    data_summary=summary
                )
                if judgment_result:
                    # Enhance summary with judgment context
                    summary = judgment_result
                    print(f"[Judgment] Enhanced summary with interpretive context")
            except Exception as e:
                print(f"[Judgment] Error processing: {e}")

        # =================================================================
        # ECONOMIST REVIEWER: Second-pass review for quality
        # =================================================================
        if ANTHROPIC_API_KEY and series_data and len(summary) < 500:
            try:
                improved_summary = call_economist_reviewer(query, series_data, summary)
                if improved_summary and improved_summary != summary:
                    summary = improved_summary
                    print(f"[EconomistReviewer] Enhanced summary")
            except Exception as e:
                print(f"[EconomistReviewer] Error: {e}")

        # Format for frontend with dynamic AI bullets
        charts = format_chart_data(series_data, payems_show_level=payems_show_level, user_query=query, use_dynamic_bullets=True)

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
            "fed_sep_html": fed_sep_html,
            # Temporal context
            "temporal_context": temporal_filter.get('explanation') if temporal_filter else None,
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
