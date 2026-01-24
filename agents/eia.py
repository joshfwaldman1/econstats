"""
EIA (Energy Information Administration) data integration for EconStats.

Provides access to energy data including:
- Crude oil prices (WTI, Brent)
- Gasoline prices (retail, wholesale)
- Natural gas prices (Henry Hub)
- Electricity prices
- Petroleum inventories

API Documentation: https://www.eia.gov/opendata/documentation.php
Registration (free): https://www.eia.gov/opendata/register.php
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

# API Key from environment
EIA_API_KEY = os.environ.get("EIA_API_KEY", "")

# Base URL for EIA API v2
EIA_BASE_URL = "https://api.eia.gov/v2"

# =============================================================================
# EIA SERIES CATALOG
# =============================================================================

EIA_SERIES = {
    # Crude Oil Prices
    'eia_wti_crude': {
        'name': 'WTI Crude Oil Spot Price',
        'description': 'West Texas Intermediate crude oil spot price, Cushing OK ($/barrel)',
        'series_id': 'PET.RWTC.W',  # Weekly
        'route': '/petroleum/pri/spt/data',
        'facets': {'series': 'RWTC'},
        'units': 'dollars per barrel',
        'frequency': 'weekly',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['oil', 'crude', 'wti', 'petroleum', 'energy'],
        'fred_equivalent': 'DCOILWTICO',  # FRED has this too
    },
    'eia_brent_crude': {
        'name': 'Brent Crude Oil Spot Price',
        'description': 'Brent crude oil spot price, Europe ($/barrel)',
        'series_id': 'PET.RBRTE.W',
        'route': '/petroleum/pri/spt/data',
        'facets': {'series': 'RBRTE'},
        'units': 'dollars per barrel',
        'frequency': 'weekly',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['oil', 'crude', 'brent', 'petroleum', 'energy', 'europe'],
        'fred_equivalent': 'DCOILBRENTEU',
    },

    # Gasoline Prices
    'eia_gasoline_retail': {
        'name': 'US Regular Gasoline Retail Price',
        'description': 'Average retail price of regular grade gasoline, all formulations ($/gallon)',
        'series_id': 'PET.EMM_EPMR_PTE_NUS_DPG.W',
        'route': '/petroleum/pri/gnd/data',
        'facets': {'series': 'EMM_EPMR_PTE_NUS_DPG'},
        'units': 'dollars per gallon',
        'frequency': 'weekly',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['gas', 'gasoline', 'fuel', 'retail', 'pump price'],
        'fred_equivalent': 'GASREGW',
    },
    'eia_diesel_retail': {
        'name': 'US Diesel Retail Price',
        'description': 'Average retail price of diesel fuel ($/gallon)',
        'series_id': 'PET.EMD_EPD2D_PTE_NUS_DPG.W',
        'route': '/petroleum/pri/gnd/data',
        'facets': {'series': 'EMD_EPD2D_PTE_NUS_DPG'},
        'units': 'dollars per gallon',
        'frequency': 'weekly',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['diesel', 'fuel', 'trucking', 'shipping'],
    },

    # Natural Gas
    'eia_natural_gas_henry_hub': {
        'name': 'Henry Hub Natural Gas Spot Price',
        'description': 'Natural gas spot price at Henry Hub, Louisiana ($/MMBtu)',
        'series_id': 'NG.RNGWHHD.M',  # Monthly
        'route': '/natural-gas/pri/sum/data',
        'facets': {'series': 'RNGWHHD'},
        'units': 'dollars per MMBtu',
        'frequency': 'monthly',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['natural gas', 'gas', 'henry hub', 'energy', 'lng'],
        'fred_equivalent': 'MHHNGSP',
    },

    # Petroleum Inventories
    'eia_crude_stocks': {
        'name': 'US Crude Oil Stocks',
        'description': 'Total US crude oil stocks excluding SPR (million barrels)',
        'series_id': 'PET.WCESTUS1.W',
        'route': '/petroleum/stoc/wstk/data',
        'facets': {'series': 'WCESTUS1'},
        'units': 'million barrels',
        'frequency': 'weekly',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['crude', 'oil', 'inventory', 'stocks', 'supply'],
    },
    'eia_gasoline_stocks': {
        'name': 'US Gasoline Stocks',
        'description': 'Total US motor gasoline stocks (million barrels)',
        'series_id': 'PET.WGTSTUS1.W',
        'route': '/petroleum/stoc/wstk/data',
        'facets': {'series': 'WGTSTUS1'},
        'units': 'million barrels',
        'frequency': 'weekly',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['gasoline', 'inventory', 'stocks', 'supply'],
    },

    # Electricity (average retail price)
    'eia_electricity_residential': {
        'name': 'US Residential Electricity Price',
        'description': 'Average retail price of electricity for residential customers (cents/kWh)',
        'series_id': 'ELEC.PRICE.US-RES.M',
        'route': '/electricity/retail-sales/data',
        'facets': {'sectorid': 'RES', 'stateid': 'US'},
        'units': 'cents per kWh',
        'frequency': 'monthly',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['electricity', 'power', 'residential', 'utility', 'electric bill'],
    },

    # Production
    'eia_crude_production': {
        'name': 'US Crude Oil Production',
        'description': 'US field production of crude oil (thousand barrels per day)',
        'series_id': 'PET.WCRFPUS2.W',
        'route': '/petroleum/sum/sndw/data',
        'facets': {'series': 'WCRFPUS2'},
        'units': 'thousand barrels per day',
        'frequency': 'weekly',
        'measure_type': 'nominal',
        'change_type': 'level',
        'keywords': ['crude', 'oil', 'production', 'supply', 'output'],
    },
}

# Cache
_cache = {}
_cache_ttl = timedelta(hours=1)


def _fetch_eia_v2(route: str, params: dict = None) -> dict:
    """
    Fetch data from EIA API v2.

    Args:
        route: API route (e.g., '/petroleum/pri/spt/data')
        params: Additional query parameters

    Returns:
        JSON response dict
    """
    if not EIA_API_KEY:
        print("[EIA] Warning: EIA_API_KEY not set. Get a free key at https://www.eia.gov/opendata/register.php")
        return {'error': 'No API key'}

    # Build URL
    url = f"{EIA_BASE_URL}{route}"
    query_parts = [f"api_key={EIA_API_KEY}"]

    if params:
        for key, value in params.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    query_parts.append(f"facets[{k}][]={v}")
            elif isinstance(value, list):
                for v in value:
                    query_parts.append(f"{key}[]={v}")
            else:
                query_parts.append(f"{key}={value}")

    url = f"{url}?{'&'.join(query_parts)}"

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
            _cache[cache_key] = (data, now)
            return data
    except URLError as e:
        print(f"[EIA] Error fetching {route}: {e}")
        return {'error': str(e)}
    except json.JSONDecodeError as e:
        print(f"[EIA] Invalid JSON response: {e}")
        return {'error': f"Invalid JSON: {e}"}


def _fetch_eia_legacy(series_id: str) -> dict:
    """
    Fetch data using legacy series ID (EIA API v1 compatibility).

    This uses the v2/seriesid endpoint which translates legacy series IDs.
    """
    if not EIA_API_KEY:
        print("[EIA] Warning: EIA_API_KEY not set.")
        return {'error': 'No API key'}

    url = f"{EIA_BASE_URL}/seriesid/{series_id}?api_key={EIA_API_KEY}"

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
            _cache[cache_key] = (data, now)
            return data
    except URLError as e:
        print(f"[EIA] Error fetching series {series_id}: {e}")
        return {'error': str(e)}
    except json.JSONDecodeError as e:
        print(f"[EIA] Invalid JSON: {e}")
        return {'error': f"Invalid JSON: {e}"}


def get_eia_series(series_key: str) -> tuple:
    """
    Fetch an EIA series.

    Args:
        series_key: One of the keys in EIA_SERIES

    Returns:
        (dates, values, info) tuple compatible with FRED format
    """
    if series_key not in EIA_SERIES:
        return [], [], {'error': f"Unknown EIA series: {series_key}"}

    series_info = EIA_SERIES[series_key]
    series_id = series_info['series_id']

    # Try legacy endpoint (simpler, more reliable)
    data = _fetch_eia_legacy(series_id)

    if 'error' in data:
        return [], [], {'error': data['error']}

    # Parse response - v2 seriesid endpoint returns data in 'response' key
    response = data.get('response', {})
    if not response:
        # Try direct 'data' key
        response = data

    data_array = response.get('data', [])

    if not data_array:
        return [], [], {'error': 'No data returned from EIA'}

    # Extract dates and values
    # EIA returns data as list of dicts with 'period' and 'value' keys
    dates = []
    values = []

    for entry in data_array:
        period = entry.get('period')
        value = entry.get('value')

        if period and value is not None:
            try:
                # Period format varies: YYYY-MM-DD, YYYY-MM, YYYY
                if len(period) == 7:  # YYYY-MM
                    period = f"{period}-01"
                elif len(period) == 4:  # YYYY
                    period = f"{period}-01-01"

                dates.append(period)
                values.append(float(value))
            except (ValueError, TypeError):
                continue

    # EIA returns data newest first, reverse for chronological order
    dates = dates[::-1]
    values = values[::-1]

    info = {
        'id': series_key,
        'title': series_info['name'],
        'description': series_info['description'],
        'units': series_info['units'],
        'frequency': series_info['frequency'],
        'source': 'U.S. Energy Information Administration',
        'measure_type': series_info['measure_type'],
        'change_type': series_info['change_type'],
        'fred_equivalent': series_info.get('fred_equivalent'),
    }

    return dates, values, info


def search_eia_series(query: str) -> list:
    """
    Search for EIA series matching a query.

    Returns list of matching series keys.
    """
    query_lower = query.lower()
    matches = []

    for key, info in EIA_SERIES.items():
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
    """Return all available EIA series for catalog display."""
    return EIA_SERIES.copy()


def check_api_key() -> bool:
    """Check if EIA API key is configured."""
    return bool(EIA_API_KEY)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("Testing EIA data fetch...")
    print(f"API Key configured: {check_api_key()}")

    if not check_api_key():
        print("\nTo test, set EIA_API_KEY environment variable.")
        print("Get a free key at: https://www.eia.gov/opendata/register.php")
    else:
        # Test WTI crude
        print("\n1. Testing WTI Crude Oil Price:")
        dates, values, info = get_eia_series('eia_wti_crude')
        if dates:
            print(f"   Got {len(dates)} observations")
            print(f"   Latest: {dates[-1]} = ${values[-1]:.2f}/barrel")
        else:
            print(f"   Error: {info.get('error', 'Unknown error')}")

        # Test gasoline
        print("\n2. Testing Gasoline Retail Price:")
        dates, values, info = get_eia_series('eia_gasoline_retail')
        if dates:
            print(f"   Got {len(dates)} observations")
            print(f"   Latest: {dates[-1]} = ${values[-1]:.3f}/gallon")
        else:
            print(f"   Error: {info.get('error', 'Unknown error')}")

        # Test natural gas
        print("\n3. Testing Henry Hub Natural Gas:")
        dates, values, info = get_eia_series('eia_natural_gas_henry_hub')
        if dates:
            print(f"   Got {len(dates)} observations")
            print(f"   Latest: {dates[-1]} = ${values[-1]:.2f}/MMBtu")
        else:
            print(f"   Error: {info.get('error', 'Unknown error')}")

        # Test search
        print("\n4. Testing search for 'crude oil':")
        matches = search_eia_series("crude oil")
        print(f"   Matches: {matches}")
