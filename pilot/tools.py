"""
FRED data tools for the economist agent.
"""

import json
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from typing import Optional
import os

FRED_API_KEY = os.environ.get('FRED_API_KEY', 'c43c82548c611ec46800c51f898026d6')
FRED_BASE = 'https://api.stlouisfed.org/fred'

# Common series reference
SERIES_INFO = {
    'PAYEMS': 'Nonfarm Payrolls (thousands)',
    'UNRATE': 'Unemployment Rate (%)',
    'CPIAUCSL': 'CPI All Items (index)',
    'CPILFESL': 'Core CPI (index)',
    'PCEPILFE': 'Core PCE (index)',
    'GDPC1': 'Real GDP (billions)',
    'A191RL1Q225SBEA': 'Real GDP Growth (quarterly annualized %)',
    'FEDFUNDS': 'Fed Funds Rate (%)',
    'DGS10': '10-Year Treasury (%)',
    'T10Y2Y': 'Yield Curve 10Y-2Y (%)',
    'CSUSHPINSA': 'Case-Shiller Home Price Index',
    'MORTGAGE30US': '30-Year Mortgage Rate (%)',
    'UMCSENT': 'Consumer Sentiment',
    'RSXFS': 'Retail Sales ex Food Services (millions)',
    'INDPRO': 'Industrial Production Index',
    'JTSJOL': 'Job Openings (thousands)',
    'ICSA': 'Initial Jobless Claims',
    'LES1252881600Q': 'Real Median Weekly Earnings ($)',
}


def fred_request(endpoint: str, params: dict) -> dict:
    """Make a request to the FRED API."""
    params['api_key'] = FRED_API_KEY
    params['file_type'] = 'json'
    url = f"{FRED_BASE}/{endpoint}?{urlencode(params)}"
    try:
        req = Request(url, headers={'User-Agent': 'EconStats-Pilot/1.0'})
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e)}


def fetch_series(series_id: str, years: int = 10) -> dict:
    """
    Fetch data for a FRED series.

    Args:
        series_id: FRED series ID (e.g., 'UNRATE', 'PAYEMS')
        years: Number of years of history to fetch

    Returns:
        Dict with dates, values, and metadata
    """
    params = {
        'series_id': series_id,
        'limit': 10000,
        'sort_order': 'asc'
    }
    if years:
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime('%Y-%m-%d')
        params['observation_start'] = start_date

    data = fred_request('series/observations', params)
    if 'error' in data:
        return {'error': data['error'], 'series_id': series_id}

    observations = data.get('observations', [])
    dates, values = [], []
    for obs in observations:
        try:
            val = float(obs['value'])
            dates.append(obs['date'])
            values.append(val)
        except (ValueError, KeyError):
            continue

    if not values:
        return {'error': 'No data returned', 'series_id': series_id}

    return {
        'series_id': series_id,
        'name': SERIES_INFO.get(series_id, series_id),
        'dates': dates,
        'values': values,
        'latest_date': dates[-1],
        'latest_value': values[-1],
        'min_value': min(values),
        'max_value': max(values),
        'data_points': len(values)
    }


def search_fred(query: str, limit: int = 5) -> list:
    """
    Search FRED for series matching a query.

    Args:
        query: Search terms (e.g., 'manufacturing employment')
        limit: Max results to return

    Returns:
        List of matching series with id, title, popularity
    """
    data = fred_request('series/search', {
        'search_text': query,
        'limit': limit,
        'order_by': 'popularity',
        'sort_order': 'desc'
    })

    if 'error' in data:
        return [{'error': data['error']}]

    results = []
    for s in data.get('seriess', []):
        results.append({
            'series_id': s['id'],
            'title': s['title'],
            'frequency': s.get('frequency', 'Unknown'),
            'units': s.get('units', ''),
            'seasonal_adjustment': s.get('seasonal_adjustment_short', ''),
            'popularity': s.get('popularity', 0)
        })

    return results


def calculate_yoy_change(values: list) -> Optional[float]:
    """Calculate year-over-year percent change from a values list."""
    if len(values) < 12:
        return None
    return ((values[-1] - values[-12]) / values[-12]) * 100


def calculate_stats(data: dict) -> dict:
    """
    Calculate statistics for a fetched series.

    Args:
        data: Output from fetch_series()

    Returns:
        Dict with computed statistics
    """
    if 'error' in data:
        return data

    values = data['values']
    dates = data['dates']

    stats = {
        'series_id': data['series_id'],
        'name': data['name'],
        'latest_date': data['latest_date'],
        'latest_value': round(data['latest_value'], 2),
    }

    # YoY change
    if len(values) >= 12:
        yoy = calculate_yoy_change(values)
        stats['yoy_change_pct'] = round(yoy, 2) if yoy else None
        stats['value_1yr_ago'] = round(values[-12], 2)

    # Recent trend (3-month change)
    if len(values) >= 3:
        recent_change = ((values[-1] - values[-3]) / values[-3]) * 100
        stats['change_3mo_pct'] = round(recent_change, 2)

    # 5-year range
    recent_60 = values[-60:] if len(values) >= 60 else values
    stats['range_5yr_min'] = round(min(recent_60), 2)
    stats['range_5yr_max'] = round(max(recent_60), 2)

    # For employment data, calculate job changes
    if data['series_id'] == 'PAYEMS':
        if len(values) >= 2:
            stats['monthly_job_change_k'] = round(values[-1] - values[-2], 1)
        if len(values) >= 4:
            changes = [values[i] - values[i-1] for i in range(-3, 0)]
            stats['avg_monthly_change_3mo_k'] = round(sum(changes) / 3, 1)
        if len(values) >= 13:
            changes = [values[i] - values[i-1] for i in range(-12, 0)]
            stats['avg_monthly_change_12mo_k'] = round(sum(changes) / 12, 1)

    return stats


def compare_periods(data: dict, start1: str, end1: str, start2: str, end2: str) -> dict:
    """
    Compare a series across two time periods.

    Args:
        data: Output from fetch_series()
        start1, end1: First period (YYYY-MM-DD format)
        start2, end2: Second period (YYYY-MM-DD format)

    Returns:
        Comparison statistics
    """
    if 'error' in data:
        return data

    dates = data['dates']
    values = data['values']

    def get_period_values(start, end):
        period_vals = []
        for d, v in zip(dates, values):
            if start <= d <= end:
                period_vals.append(v)
        return period_vals

    p1_vals = get_period_values(start1, end1)
    p2_vals = get_period_values(start2, end2)

    if not p1_vals or not p2_vals:
        return {'error': 'No data in one or both periods'}

    return {
        'series_id': data['series_id'],
        'name': data['name'],
        'period1': {
            'start': start1,
            'end': end1,
            'start_value': round(p1_vals[0], 2),
            'end_value': round(p1_vals[-1], 2),
            'change_pct': round(((p1_vals[-1] - p1_vals[0]) / p1_vals[0]) * 100, 2),
            'avg_value': round(sum(p1_vals) / len(p1_vals), 2),
        },
        'period2': {
            'start': start2,
            'end': end2,
            'start_value': round(p2_vals[0], 2),
            'end_value': round(p2_vals[-1], 2),
            'change_pct': round(((p2_vals[-1] - p2_vals[0]) / p2_vals[0]) * 100, 2),
            'avg_value': round(sum(p2_vals) / len(p2_vals), 2),
        }
    }


# Quick reference for the agent
COMMON_QUERIES = {
    'jobs': ['PAYEMS', 'UNRATE', 'JTSJOL'],
    'inflation': ['CPIAUCSL', 'CPILFESL', 'PCEPILFE'],
    'gdp': ['GDPC1', 'A191RL1Q225SBEA'],
    'rates': ['FEDFUNDS', 'DGS10', 'T10Y2Y'],
    'housing': ['CSUSHPINSA', 'MORTGAGE30US'],
    'consumer': ['UMCSENT', 'RSXFS'],
    'recession': ['UNRATE', 'PAYEMS', 'A191RL1Q225SBEA', 'T10Y2Y'],
}


if __name__ == '__main__':
    # Quick test
    print("Testing fetch_series...")
    data = fetch_series('UNRATE', years=5)
    print(f"UNRATE: {data['latest_value']}% as of {data['latest_date']}")

    print("\nTesting calculate_stats...")
    stats = calculate_stats(data)
    print(f"Stats: {stats}")

    print("\nTesting search_fred...")
    results = search_fred('manufacturing employment')
    for r in results[:3]:
        print(f"  {r['series_id']}: {r['title']}")
