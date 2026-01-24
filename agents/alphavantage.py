"""
Alpha Vantage data integration for EconStats.

Provides access to financial data including:
- Stock prices (daily, weekly, intraday)
- Economic indicators (GDP, CPI, unemployment, etc.)
- Treasury yields
- Commodities (crude oil, natural gas, etc.)
- Forex rates

API Documentation: https://www.alphavantage.co/documentation/
Free API Key: https://www.alphavantage.co/support/#api-key
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

# API Key from environment
ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "")

# Base URL
ALPHAVANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# =============================================================================
# ALPHA VANTAGE SERIES CATALOG
# =============================================================================

ALPHAVANTAGE_SERIES = {
    # ==========================================================================
    # STOCK INDICES (represented by ETFs that track them)
    # ==========================================================================
    'av_spy': {
        'name': 'S&P 500 (SPY ETF)',
        'description': 'SPDR S&P 500 ETF Trust - tracks the S&P 500 index',
        'function': 'TIME_SERIES_DAILY',
        'symbol': 'SPY',
        'units': 'dollars',
        'frequency': 'daily',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['sp500', 's&p', 'stocks', 'market', 'equity', 'index'],
        'fred_equivalent': 'SP500',
    },
    'av_qqq': {
        'name': 'Nasdaq 100 (QQQ ETF)',
        'description': 'Invesco QQQ Trust - tracks the Nasdaq-100 index',
        'function': 'TIME_SERIES_DAILY',
        'symbol': 'QQQ',
        'units': 'dollars',
        'frequency': 'daily',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['nasdaq', 'tech', 'stocks', 'market', 'equity', 'technology'],
        'fred_equivalent': 'NASDAQCOM',
    },
    'av_dia': {
        'name': 'Dow Jones (DIA ETF)',
        'description': 'SPDR Dow Jones Industrial Average ETF',
        'function': 'TIME_SERIES_DAILY',
        'symbol': 'DIA',
        'units': 'dollars',
        'frequency': 'daily',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['dow', 'djia', 'stocks', 'market', 'equity', 'industrials'],
        'fred_equivalent': 'DJIA',
    },
    'av_iwm': {
        'name': 'Russell 2000 (IWM ETF)',
        'description': 'iShares Russell 2000 ETF - tracks small-cap stocks',
        'function': 'TIME_SERIES_DAILY',
        'symbol': 'IWM',
        'units': 'dollars',
        'frequency': 'daily',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['russell', 'small cap', 'stocks', 'market', 'equity'],
    },
    'av_vix': {
        'name': 'VIX Volatility (VXX)',
        'description': 'iPath Series B S&P 500 VIX Short-Term Futures ETN',
        'function': 'TIME_SERIES_DAILY',
        'symbol': 'VXX',
        'units': 'index',
        'frequency': 'daily',
        'measure_type': 'index',
        'change_type': 'level',
        'keywords': ['vix', 'volatility', 'fear', 'risk', 'market'],
        'fred_equivalent': 'VIXCLS',
    },

    # ==========================================================================
    # ECONOMIC INDICATORS
    # ==========================================================================
    'av_real_gdp': {
        'name': 'Real GDP (Alpha Vantage)',
        'description': 'US Real Gross Domestic Product, quarterly',
        'function': 'REAL_GDP',
        'interval': 'quarterly',
        'units': 'billions of dollars',
        'frequency': 'quarterly',
        'measure_type': 'real',
        'change_type': 'level',
        'keywords': ['gdp', 'growth', 'economy', 'output', 'production'],
        'fred_equivalent': 'GDPC1',
    },
    'av_cpi': {
        'name': 'CPI (Alpha Vantage)',
        'description': 'Consumer Price Index for all urban consumers',
        'function': 'CPI',
        'interval': 'monthly',
        'units': 'index',
        'frequency': 'monthly',
        'measure_type': 'index',
        'change_type': 'level',
        'keywords': ['cpi', 'inflation', 'prices', 'consumer'],
        'fred_equivalent': 'CPIAUCSL',
    },
    'av_inflation': {
        'name': 'Inflation Rate (Alpha Vantage)',
        'description': 'Annual inflation rate based on consumer prices',
        'function': 'INFLATION',
        'units': 'percent',
        'frequency': 'annual',
        'measure_type': 'rate',
        'change_type': 'yoy',
        'keywords': ['inflation', 'prices', 'cost of living'],
    },
    'av_unemployment': {
        'name': 'Unemployment Rate (Alpha Vantage)',
        'description': 'US unemployment rate',
        'function': 'UNEMPLOYMENT',
        'units': 'percent',
        'frequency': 'monthly',
        'measure_type': 'rate',
        'change_type': 'level',
        'keywords': ['unemployment', 'jobs', 'labor', 'jobless'],
        'fred_equivalent': 'UNRATE',
    },
    'av_fed_funds': {
        'name': 'Federal Funds Rate (Alpha Vantage)',
        'description': 'Effective federal funds rate',
        'function': 'FEDERAL_FUNDS_RATE',
        'interval': 'monthly',
        'units': 'percent',
        'frequency': 'monthly',
        'measure_type': 'rate',
        'change_type': 'level',
        'keywords': ['fed', 'interest rate', 'fomc', 'federal reserve', 'rates'],
        'fred_equivalent': 'FEDFUNDS',
    },
    'av_consumer_sentiment': {
        'name': 'Consumer Sentiment (Alpha Vantage)',
        'description': 'University of Michigan Consumer Sentiment Index',
        'function': 'CONSUMER_SENTIMENT',
        'units': 'index',
        'frequency': 'monthly',
        'measure_type': 'index',
        'change_type': 'level',
        'keywords': ['sentiment', 'consumer', 'confidence', 'survey'],
        'fred_equivalent': 'UMCSENT',
    },
    'av_retail_sales': {
        'name': 'Retail Sales (Alpha Vantage)',
        'description': 'US monthly retail sales',
        'function': 'RETAIL_SALES',
        'units': 'millions of dollars',
        'frequency': 'monthly',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['retail', 'sales', 'consumer', 'spending', 'shopping'],
        'fred_equivalent': 'RSXFS',
    },
    'av_nonfarm_payroll': {
        'name': 'Nonfarm Payrolls (Alpha Vantage)',
        'description': 'Total nonfarm employment',
        'function': 'NONFARM_PAYROLL',
        'units': 'thousands of persons',
        'frequency': 'monthly',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['payrolls', 'jobs', 'employment', 'labor', 'jobs report'],
        'fred_equivalent': 'PAYEMS',
    },

    # ==========================================================================
    # TREASURY YIELDS
    # ==========================================================================
    'av_treasury_10y': {
        'name': '10-Year Treasury Yield',
        'description': 'US 10-Year Treasury Bond Yield',
        'function': 'TREASURY_YIELD',
        'interval': 'daily',
        'maturity': '10year',
        'units': 'percent',
        'frequency': 'daily',
        'measure_type': 'rate',
        'change_type': 'level',
        'keywords': ['treasury', 'bond', 'yield', '10 year', 'rates'],
        'fred_equivalent': 'DGS10',
    },
    'av_treasury_2y': {
        'name': '2-Year Treasury Yield',
        'description': 'US 2-Year Treasury Bond Yield',
        'function': 'TREASURY_YIELD',
        'interval': 'daily',
        'maturity': '2year',
        'units': 'percent',
        'frequency': 'daily',
        'measure_type': 'rate',
        'change_type': 'level',
        'keywords': ['treasury', 'bond', 'yield', '2 year', 'rates', 'short term'],
        'fred_equivalent': 'DGS2',
    },
    'av_treasury_30y': {
        'name': '30-Year Treasury Yield',
        'description': 'US 30-Year Treasury Bond Yield',
        'function': 'TREASURY_YIELD',
        'interval': 'daily',
        'maturity': '30year',
        'units': 'percent',
        'frequency': 'daily',
        'measure_type': 'rate',
        'change_type': 'level',
        'keywords': ['treasury', 'bond', 'yield', '30 year', 'rates', 'long term'],
        'fred_equivalent': 'DGS30',
    },
    'av_treasury_3m': {
        'name': '3-Month Treasury Yield',
        'description': 'US 3-Month Treasury Bill Yield',
        'function': 'TREASURY_YIELD',
        'interval': 'daily',
        'maturity': '3month',
        'units': 'percent',
        'frequency': 'daily',
        'measure_type': 'rate',
        'change_type': 'level',
        'keywords': ['treasury', 'bill', 'yield', '3 month', 'rates', 'short term'],
        'fred_equivalent': 'DGS3MO',
    },

    # ==========================================================================
    # COMMODITIES
    # ==========================================================================
    'av_crude_oil': {
        'name': 'WTI Crude Oil',
        'description': 'West Texas Intermediate crude oil price',
        'function': 'WTI',
        'interval': 'daily',
        'units': 'dollars per barrel',
        'frequency': 'daily',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['oil', 'crude', 'wti', 'energy', 'petroleum'],
        'fred_equivalent': 'DCOILWTICO',
    },
    'av_brent': {
        'name': 'Brent Crude Oil',
        'description': 'Brent crude oil price',
        'function': 'BRENT',
        'interval': 'daily',
        'units': 'dollars per barrel',
        'frequency': 'daily',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['oil', 'crude', 'brent', 'energy', 'petroleum', 'europe'],
        'fred_equivalent': 'DCOILBRENTEU',
    },
    'av_natural_gas': {
        'name': 'Natural Gas',
        'description': 'Henry Hub natural gas spot price',
        'function': 'NATURAL_GAS',
        'interval': 'daily',
        'units': 'dollars per MMBtu',
        'frequency': 'daily',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['natural gas', 'gas', 'energy', 'henry hub'],
        'fred_equivalent': 'DHHNGSP',
    },
    'av_gold': {
        'name': 'Gold Price',
        'description': 'Gold spot price per troy ounce',
        'function': 'CURRENCY_EXCHANGE_RATE',
        'from_currency': 'XAU',
        'to_currency': 'USD',
        'is_commodity': True,
        'units': 'dollars per troy ounce',
        'frequency': 'daily',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['gold', 'precious metal', 'commodity', 'safe haven'],
        'fred_equivalent': 'GOLDAMGBD228NLBM',
    },

    # ==========================================================================
    # FOREX
    # ==========================================================================
    'av_eurusd': {
        'name': 'EUR/USD Exchange Rate',
        'description': 'Euro to US Dollar exchange rate',
        'function': 'FX_DAILY',
        'from_symbol': 'EUR',
        'to_symbol': 'USD',
        'units': 'dollars per euro',
        'frequency': 'daily',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['euro', 'dollar', 'forex', 'currency', 'exchange rate'],
        'fred_equivalent': 'DEXUSEU',
    },
    'av_usdjpy': {
        'name': 'USD/JPY Exchange Rate',
        'description': 'US Dollar to Japanese Yen exchange rate',
        'function': 'FX_DAILY',
        'from_symbol': 'USD',
        'to_symbol': 'JPY',
        'units': 'yen per dollar',
        'frequency': 'daily',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['yen', 'dollar', 'forex', 'currency', 'exchange rate', 'japan'],
        'fred_equivalent': 'DEXJPUS',
    },
    'av_gbpusd': {
        'name': 'GBP/USD Exchange Rate',
        'description': 'British Pound to US Dollar exchange rate',
        'function': 'FX_DAILY',
        'from_symbol': 'GBP',
        'to_symbol': 'USD',
        'units': 'dollars per pound',
        'frequency': 'daily',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['pound', 'sterling', 'dollar', 'forex', 'currency', 'uk', 'britain'],
        'fred_equivalent': 'DEXUSUK',
    },
    'av_dollar_index': {
        'name': 'US Dollar Index (UUP ETF)',
        'description': 'Invesco DB US Dollar Index Bullish Fund - tracks USD vs basket',
        'function': 'TIME_SERIES_DAILY',
        'symbol': 'UUP',
        'units': 'index',
        'frequency': 'daily',
        'measure_type': 'index',
        'change_type': 'level',
        'keywords': ['dollar', 'usd', 'dxy', 'currency', 'forex', 'dollar index'],
        'fred_equivalent': 'DTWEXBGS',
    },
}

# Cache
_cache = {}
_cache_ttl = timedelta(hours=1)


def _fetch_alphavantage(params: dict) -> dict:
    """
    Fetch data from Alpha Vantage API.

    Args:
        params: Query parameters including 'function' and 'apikey'

    Returns:
        JSON response dict
    """
    if not ALPHAVANTAGE_API_KEY:
        print("[AlphaVantage] Warning: ALPHAVANTAGE_API_KEY not set. Get a free key at https://www.alphavantage.co/support/#api-key")
        return {'error': 'No API key'}

    params['apikey'] = ALPHAVANTAGE_API_KEY

    # Build URL
    query_string = '&'.join(f"{k}={v}" for k, v in params.items())
    url = f"{ALPHAVANTAGE_BASE_URL}?{query_string}"

    # Check cache
    cache_key = url
    now = datetime.now()
    if cache_key in _cache:
        cached_data, cached_time = _cache[cache_key]
        if now - cached_time < _cache_ttl:
            return cached_data

    try:
        req = Request(url, headers={'User-Agent': 'EconStats/1.0'})
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))

            # Check for API error messages
            if 'Error Message' in data:
                return {'error': data['Error Message']}
            if 'Note' in data:  # Rate limit message
                return {'error': data['Note']}
            if 'Information' in data:  # API key issue
                return {'error': data['Information']}

            _cache[cache_key] = (data, now)
            return data
    except URLError as e:
        print(f"[AlphaVantage] Error: {e}")
        return {'error': str(e)}
    except json.JSONDecodeError as e:
        print(f"[AlphaVantage] Invalid JSON: {e}")
        return {'error': f"Invalid JSON: {e}"}


def _parse_time_series(data: dict, data_key: str = None) -> tuple:
    """
    Parse time series data from Alpha Vantage response.

    Returns: (dates, values) where dates are strings and values are floats
    """
    # Find the time series key (varies by function)
    ts_key = data_key
    if not ts_key:
        for key in data.keys():
            if 'Time Series' in key or key.startswith('data') or key == 'data':
                ts_key = key
                break

    if not ts_key or ts_key not in data:
        return [], []

    time_series = data[ts_key]

    # Handle different data formats
    if isinstance(time_series, list):
        # Economic indicator format: list of {date, value} dicts
        dates = []
        values = []
        for entry in time_series:
            date = entry.get('date')
            value = entry.get('value')
            if date and value:
                try:
                    dates.append(date)
                    values.append(float(value))
                except (ValueError, TypeError):
                    continue
        return dates, values

    elif isinstance(time_series, dict):
        # Time series format: dict of date -> OHLCV
        dates = []
        values = []
        for date_str, ohlcv in sorted(time_series.items()):
            try:
                # Use close price (key varies: '4. close', 'close', etc.)
                value = None
                for key in ['4. close', 'close', '5. adjusted close', 'value']:
                    if key in ohlcv:
                        value = float(ohlcv[key])
                        break

                if value is not None:
                    dates.append(date_str)
                    values.append(value)
            except (ValueError, TypeError):
                continue

        return dates, values

    return [], []


def get_alphavantage_series(series_key: str) -> tuple:
    """
    Fetch an Alpha Vantage series.

    Args:
        series_key: One of the keys in ALPHAVANTAGE_SERIES

    Returns:
        (dates, values, info) tuple compatible with FRED format
    """
    if series_key not in ALPHAVANTAGE_SERIES:
        return [], [], {'error': f"Unknown Alpha Vantage series: {series_key}"}

    series_info = ALPHAVANTAGE_SERIES[series_key]
    function = series_info['function']

    # Build request params based on function type
    params = {'function': function}

    if function == 'TIME_SERIES_DAILY':
        params['symbol'] = series_info['symbol']
        params['outputsize'] = 'full'  # Get all available data
    elif function in ['TIME_SERIES_WEEKLY', 'TIME_SERIES_MONTHLY']:
        params['symbol'] = series_info['symbol']
    elif function == 'FX_DAILY':
        params['from_symbol'] = series_info['from_symbol']
        params['to_symbol'] = series_info['to_symbol']
    elif function == 'TREASURY_YIELD':
        params['interval'] = series_info.get('interval', 'daily')
        params['maturity'] = series_info['maturity']
    elif function in ['WTI', 'BRENT', 'NATURAL_GAS']:
        params['interval'] = series_info.get('interval', 'daily')
    elif function == 'CURRENCY_EXCHANGE_RATE':
        params['from_currency'] = series_info['from_currency']
        params['to_currency'] = series_info['to_currency']
    elif function in ['REAL_GDP', 'CPI', 'FEDERAL_FUNDS_RATE', 'RETAIL_SALES']:
        if 'interval' in series_info:
            params['interval'] = series_info['interval']
    # Other economic indicators don't need extra params

    # Fetch data
    data = _fetch_alphavantage(params)

    if 'error' in data:
        return [], [], {'error': data['error']}

    # Parse based on function type
    if function == 'CURRENCY_EXCHANGE_RATE':
        # Real-time quote, not time series
        rate_data = data.get('Realtime Currency Exchange Rate', {})
        if rate_data:
            rate = rate_data.get('5. Exchange Rate')
            date = rate_data.get('6. Last Refreshed', datetime.now().strftime('%Y-%m-%d'))
            if rate:
                dates = [date[:10]]  # Trim to date only
                values = [float(rate)]
            else:
                return [], [], {'error': 'No exchange rate data'}
        else:
            return [], [], {'error': 'No exchange rate data'}
    else:
        dates, values = _parse_time_series(data)

    if not dates:
        return [], [], {'error': 'No data returned from Alpha Vantage'}

    info = {
        'id': series_key,
        'title': series_info['name'],
        'description': series_info['description'],
        'units': series_info['units'],
        'frequency': series_info['frequency'],
        'source': 'Alpha Vantage',
        'measure_type': series_info['measure_type'],
        'change_type': series_info['change_type'],
        'fred_equivalent': series_info.get('fred_equivalent'),
    }

    return dates, values, info


def get_stock_price(symbol: str) -> tuple:
    """
    Fetch daily stock price for any symbol.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'MSFT')

    Returns:
        (dates, values, info) tuple
    """
    params = {
        'function': 'TIME_SERIES_DAILY',
        'symbol': symbol.upper(),
        'outputsize': 'full',
    }

    data = _fetch_alphavantage(params)

    if 'error' in data:
        return [], [], {'error': data['error']}

    dates, values = _parse_time_series(data)

    if not dates:
        return [], [], {'error': f'No data for symbol {symbol}'}

    info = {
        'id': f'av_stock_{symbol.lower()}',
        'title': f'{symbol.upper()} Stock Price',
        'description': f'Daily closing price for {symbol.upper()}',
        'units': 'dollars',
        'frequency': 'daily',
        'source': 'Alpha Vantage',
        'measure_type': 'nominal',
        'change_type': 'level',
    }

    return dates, values, info


def search_alphavantage_series(query: str) -> list:
    """
    Search for Alpha Vantage series matching a query.

    Returns list of matching series keys.
    """
    query_lower = query.lower()
    matches = []

    for key, info in ALPHAVANTAGE_SERIES.items():
        searchable = (
            info['name'].lower() + ' ' +
            info.get('description', '').lower() + ' ' +
            ' '.join(info.get('keywords', []))
        )

        score = 0
        for word in query_lower.split():
            if word in searchable:
                score += 1

        if score > 0:
            matches.append((key, score, info['name']))

    matches.sort(key=lambda x: -x[1])
    return [m[0] for m in matches]


def get_available_series() -> dict:
    """Return all available Alpha Vantage series for catalog display."""
    return ALPHAVANTAGE_SERIES.copy()


def check_api_key() -> bool:
    """Check if Alpha Vantage API key is configured."""
    return bool(ALPHAVANTAGE_API_KEY)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("Testing Alpha Vantage data fetch...")
    print(f"API Key configured: {check_api_key()}")

    if not check_api_key():
        print("\nTo test, set ALPHAVANTAGE_API_KEY environment variable.")
        print("Get a free key at: https://www.alphavantage.co/support/#api-key")
    else:
        # Test SPY (S&P 500 ETF)
        print("\n1. Testing SPY (S&P 500 ETF):")
        dates, values, info = get_alphavantage_series('av_spy')
        if dates:
            print(f"   Got {len(dates)} observations")
            print(f"   Latest: {dates[-1]} = ${values[-1]:.2f}")
        else:
            print(f"   Error: {info.get('error', 'Unknown error')}")

        # Test Treasury yield
        print("\n2. Testing 10-Year Treasury Yield:")
        dates, values, info = get_alphavantage_series('av_treasury_10y')
        if dates:
            print(f"   Got {len(dates)} observations")
            print(f"   Latest: {dates[-1]} = {values[-1]:.2f}%")
        else:
            print(f"   Error: {info.get('error', 'Unknown error')}")

        # Test unemployment
        print("\n3. Testing Unemployment Rate:")
        dates, values, info = get_alphavantage_series('av_unemployment')
        if dates:
            print(f"   Got {len(dates)} observations")
            print(f"   Latest: {dates[-1]} = {values[-1]:.1f}%")
        else:
            print(f"   Error: {info.get('error', 'Unknown error')}")

        # Test crude oil
        print("\n4. Testing WTI Crude Oil:")
        dates, values, info = get_alphavantage_series('av_crude_oil')
        if dates:
            print(f"   Got {len(dates)} observations")
            print(f"   Latest: {dates[-1]} = ${values[-1]:.2f}/barrel")
        else:
            print(f"   Error: {info.get('error', 'Unknown error')}")

        # Test search
        print("\n5. Testing search for 'treasury yield':")
        matches = search_alphavantage_series("treasury yield")
        print(f"   Matches: {matches}")

        # Test individual stock
        print("\n6. Testing individual stock (AAPL):")
        dates, values, info = get_stock_price('AAPL')
        if dates:
            print(f"   Got {len(dates)} observations")
            print(f"   Latest: {dates[-1]} = ${values[-1]:.2f}")
        else:
            print(f"   Error: {info.get('error', 'Unknown error')}")
