"""
Zillow data integration for EconStats.

Fetches housing market data from Zillow Research's free public CSVs.
Data includes:
- ZORI (Zillow Observed Rent Index) - actual market rents
- ZHVI (Zillow Home Value Index) - home values
- Various cuts by metro, state, zip

CSV URLs: https://www.zillow.com/research/data/
"""

import csv
import io
from datetime import datetime, timedelta
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

# =============================================================================
# ZILLOW SERIES CATALOG
# =============================================================================

ZILLOW_SERIES = {
    # Rent indices
    'zillow_zori_national': {
        'name': 'Zillow Observed Rent Index (National)',
        'description': 'Typical observed market rent across the US, smoothed and seasonally adjusted',
        'url': 'https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv',
        'geography': 'national',  # We'll filter for US average
        'measure_type': 'nominal',
        'change_type': 'level',
        'units': 'dollars',
        'frequency': 'monthly',
        'keywords': ['rent', 'rental', 'apartment', 'zillow', 'market rent'],
    },
    'zillow_zhvi_national': {
        'name': 'Zillow Home Value Index (National)',
        'description': 'Typical home value across the US, smoothed and seasonally adjusted',
        'url': 'https://files.zillowstatic.com/research/public_csvs/zhvi/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv',
        'geography': 'national',
        'measure_type': 'nominal',
        'change_type': 'level',
        'units': 'dollars',
        'frequency': 'monthly',
        'keywords': ['home value', 'house price', 'zillow', 'zhvi', 'home price'],
    },
    'zillow_rent_yoy': {
        'name': 'Zillow Rent Growth (YoY %)',
        'description': 'Year-over-year percent change in typical market rent',
        'derived_from': 'zillow_zori_national',
        'measure_type': 'nominal',
        'change_type': 'yoy',
        'units': 'percent',
        'frequency': 'monthly',
        'keywords': ['rent inflation', 'rent growth', 'rental prices'],
    },
    'zillow_home_value_yoy': {
        'name': 'Zillow Home Value Growth (YoY %)',
        'description': 'Year-over-year percent change in typical home value',
        'derived_from': 'zillow_zhvi_national',
        'measure_type': 'nominal',
        'change_type': 'yoy',
        'units': 'percent',
        'frequency': 'monthly',
        'keywords': ['home price growth', 'house price inflation', 'housing appreciation'],
    },
}

# Cache for fetched data (avoid repeated downloads)
_cache = {}
_cache_ttl = timedelta(hours=1)


def _fetch_csv(url: str) -> list:
    """Fetch and parse a CSV from Zillow."""
    cache_key = url
    now = datetime.now()

    # Check cache
    if cache_key in _cache:
        cached_data, cached_time = _cache[cache_key]
        if now - cached_time < _cache_ttl:
            return cached_data

    try:
        req = Request(url, headers={'User-Agent': 'EconStats/1.0'})
        with urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8')
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
            _cache[cache_key] = (rows, now)
            return rows
    except URLError as e:
        print(f"[Zillow] Error fetching {url}: {e}")
        return []


def _parse_zillow_metro_csv(rows: list, target_region: str = "United States") -> tuple:
    """
    Parse Zillow metro-level CSV and extract national data.

    Zillow CSVs have format:
    RegionID, SizeRank, RegionName, RegionType, StateName, 2015-01-31, 2015-02-28, ...

    Returns: (dates, values) where dates are datetime objects
    """
    if not rows:
        return [], []

    header = rows[0]

    # Find date columns (format: YYYY-MM-DD)
    date_cols = []
    for i, col in enumerate(header):
        if len(col) == 10 and col[4] == '-' and col[7] == '-':
            try:
                datetime.strptime(col, '%Y-%m-%d')
                date_cols.append((i, col))
            except ValueError:
                continue

    if not date_cols:
        print("[Zillow] No date columns found in CSV")
        return [], []

    # Find the target region row (United States for national)
    target_row = None
    for row in rows[1:]:
        if len(row) > 2:
            region_name = row[2] if len(row) > 2 else ""
            if target_region.lower() in region_name.lower():
                target_row = row
                break

    if not target_row:
        print(f"[Zillow] Region '{target_region}' not found in CSV")
        return [], []

    # Extract dates and values
    dates = []
    values = []
    for col_idx, date_str in date_cols:
        if col_idx < len(target_row):
            val_str = target_row[col_idx]
            if val_str and val_str.strip():
                try:
                    val = float(val_str)
                    dates.append(datetime.strptime(date_str, '%Y-%m-%d'))
                    values.append(val)
                except ValueError:
                    continue

    return dates, values


def _calculate_yoy(dates: list, values: list) -> tuple:
    """Calculate year-over-year percent change."""
    if len(dates) < 13:
        return [], []

    # Create lookup by (year, month)
    by_month = {}
    for d, v in zip(dates, values):
        by_month[(d.year, d.month)] = v

    yoy_dates = []
    yoy_values = []

    for d, v in zip(dates, values):
        prev_key = (d.year - 1, d.month)
        if prev_key in by_month:
            prev_v = by_month[prev_key]
            if prev_v and prev_v != 0:
                pct_change = ((v - prev_v) / prev_v) * 100
                yoy_dates.append(d)
                yoy_values.append(round(pct_change, 2))

    return yoy_dates, yoy_values


def get_zillow_series(series_key: str) -> tuple:
    """
    Fetch a Zillow series.

    Args:
        series_key: One of the keys in ZILLOW_SERIES

    Returns:
        (dates, values, info) tuple compatible with FRED format
        - dates: list of 'YYYY-MM-DD' strings
        - values: list of float values
        - info: dict with series metadata
    """
    if series_key not in ZILLOW_SERIES:
        return [], [], {'error': f"Unknown Zillow series: {series_key}"}

    series_info = ZILLOW_SERIES[series_key]

    # Handle derived series (YoY calculations)
    if 'derived_from' in series_info:
        base_key = series_info['derived_from']
        base_dates, base_values, base_info = get_zillow_series(base_key)

        if not base_dates:
            return [], [], {'error': f"Could not fetch base series {base_key}"}

        # Convert string dates back to datetime for calculation
        dt_dates = [datetime.strptime(d, '%Y-%m-%d') for d in base_dates]
        yoy_dates, yoy_values = _calculate_yoy(dt_dates, base_values)

        # Convert back to strings
        date_strings = [d.strftime('%Y-%m-%d') for d in yoy_dates]

        info = {
            'id': series_key,
            'title': series_info['name'],
            'description': series_info['description'],
            'units': series_info['units'],
            'frequency': series_info['frequency'],
            'source': 'Zillow Research',
            'measure_type': series_info['measure_type'],
            'change_type': series_info['change_type'],
        }

        return date_strings, yoy_values, info

    # Fetch raw CSV data
    url = series_info.get('url')
    if not url:
        return [], [], {'error': f"No URL for series {series_key}"}

    rows = _fetch_csv(url)
    if not rows:
        return [], [], {'error': f"Could not fetch data from Zillow"}

    dates, values = _parse_zillow_metro_csv(rows)

    if not dates:
        return [], [], {'error': f"Could not parse Zillow data"}

    # Convert dates to strings
    date_strings = [d.strftime('%Y-%m-%d') for d in dates]

    info = {
        'id': series_key,
        'title': series_info['name'],
        'description': series_info['description'],
        'units': series_info['units'],
        'frequency': series_info['frequency'],
        'source': 'Zillow Research',
        'measure_type': series_info['measure_type'],
        'change_type': series_info['change_type'],
    }

    return date_strings, values, info


def search_zillow_series(query: str) -> list:
    """
    Search for Zillow series matching a query.

    Returns list of matching series keys.
    """
    query_lower = query.lower()
    matches = []

    for key, info in ZILLOW_SERIES.items():
        # Check name, description, and keywords
        searchable = (
            info['name'].lower() + ' ' +
            info.get('description', '').lower() + ' ' +
            ' '.join(info.get('keywords', []))
        )

        # Score by keyword matches
        score = 0
        for word in query_lower.split():
            if word in searchable:
                score += 1

        if score > 0:
            matches.append((key, score, info['name']))

    # Sort by score descending
    matches.sort(key=lambda x: -x[1])

    return [m[0] for m in matches]


def get_available_series() -> dict:
    """Return all available Zillow series for catalog display."""
    return ZILLOW_SERIES.copy()


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("Testing Zillow data fetch...")

    # Test ZORI
    print("\n1. Testing ZORI (National Rent Index):")
    dates, values, info = get_zillow_series('zillow_zori_national')
    if dates:
        print(f"   Got {len(dates)} observations")
        print(f"   Latest: {dates[-1]} = ${values[-1]:,.0f}")
        print(f"   Earliest: {dates[0]} = ${values[0]:,.0f}")
    else:
        print(f"   Error: {info.get('error', 'Unknown error')}")

    # Test ZHVI
    print("\n2. Testing ZHVI (National Home Value Index):")
    dates, values, info = get_zillow_series('zillow_zhvi_national')
    if dates:
        print(f"   Got {len(dates)} observations")
        print(f"   Latest: {dates[-1]} = ${values[-1]:,.0f}")
    else:
        print(f"   Error: {info.get('error', 'Unknown error')}")

    # Test YoY rent
    print("\n3. Testing Rent YoY:")
    dates, values, info = get_zillow_series('zillow_rent_yoy')
    if dates:
        print(f"   Got {len(dates)} observations")
        print(f"   Latest: {dates[-1]} = {values[-1]:.1f}%")
    else:
        print(f"   Error: {info.get('error', 'Unknown error')}")

    # Test search
    print("\n4. Testing search for 'rent':")
    matches = search_zillow_series("rent")
    print(f"   Matches: {matches}")
