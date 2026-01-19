#!/usr/bin/env python3
"""
Base utilities for QA testing - tests query plans and FRED data fetching.
Standalone tests that don't require importing from app.py.
"""

import json
import os
import glob
import time
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.parse import urlencode

# FRED API configuration
FRED_API_KEY = os.environ.get('FRED_API_KEY', 'c43c82548c611ec46800c51f898026d6')
FRED_BASE = 'https://api.stlouisfed.org/fred'


def load_query_plans():
    """Load all query plans from agents/*.json files."""
    plans = {}
    agents_dir = '/Users/josh/Desktop/econstats/agents'
    for plan_file in glob.glob(os.path.join(agents_dir, 'plans_*.json')):
        try:
            with open(plan_file, 'r') as f:
                plans.update(json.load(f))
        except Exception as e:
            print(f"Warning: Failed to load {plan_file}: {e}")
    return plans


QUERY_PLANS = load_query_plans()


# Series name lookup for display
SERIES_NAMES = {
    'A191RL1Q225SBEA': 'Real GDP Growth Rate (Quarterly)',
    'A191RO1Q156NBEA': 'Real GDP Growth Rate (YoY)',
    'PB0000031Q225SBEA': 'Core GDP (Private Demand)',
    'GDPNOW': 'GDPNow (Atlanta Fed)',
    'GDPC1': 'Real GDP Level',
    'UNRATE': 'Unemployment Rate (U-3)',
    'U6RATE': 'Unemployment Rate (U-6)',
    'PAYEMS': 'Total Nonfarm Payrolls',
    'LNS12300060': 'Prime-Age Employment-Pop Ratio (25-54)',
    'LNS11300060': 'Prime-Age Labor Force Participation',
    'LNS11300000': 'Labor Force Participation Rate',
    'JTSJOL': 'Job Openings (JOLTS)',
    'JTSQUR': 'Quits Rate (JOLTS)',
    'JTSHIR': 'Hires Rate (JOLTS)',
    'ICSA': 'Initial Jobless Claims',
    'CPIAUCSL': 'CPI All Items',
    'CPILFESL': 'Core CPI',
    'PCEPILFE': 'Core PCE (Fed Target)',
    'PCEPI': 'PCE Price Index',
    'CUSR0000SAH1': 'CPI Shelter',
    'CUSR0000SEHA': 'CPI Rent of Primary Residence',
    'FEDFUNDS': 'Federal Funds Rate',
    'DGS10': '10-Year Treasury',
    'DGS2': '2-Year Treasury',
    'T10Y2Y': 'Yield Curve (10Y-2Y)',
    'MORTGAGE30US': '30-Year Mortgage Rate',
    'CSUSHPINSA': 'Case-Shiller Home Price Index',
    'HOUST': 'Housing Starts',
    'EXHOSLUSM495S': 'Existing Home Sales',
    'RSXFS': 'Retail Sales (ex Food Services)',
    'UMCSENT': 'Consumer Sentiment',
    'SP500': 'S&P 500',
    'DCOILWTICO': 'WTI Crude Oil Price',
    'GASREGW': 'Gas Price',
    'BOPGSTB': 'Trade Balance',
    'IMPCH': 'Imports from China',
    'PSAVERT': 'Personal Savings Rate',
    'INDPRO': 'Industrial Production',
    'LNS14000002': 'Unemployment Rate - Women',
    'LNS12300062': 'Prime-Age Emp-Pop Ratio - Women',
    'LNS11300002': 'LFPR - Women',
    'LNS14000001': 'Unemployment Rate - Men',
    'LNS14000006': 'Unemployment Rate - Black',
    'LNS14000009': 'Unemployment Rate - Hispanic',
}


def get_series_name(series_id):
    """Get human-readable name for a series."""
    return SERIES_NAMES.get(series_id, series_id)


def get_series_names(series_ids):
    """Convert series IDs to human-readable names."""
    return [get_series_name(s) for s in series_ids]


def fred_request(endpoint, params):
    """Make a request to the FRED API."""
    params['api_key'] = FRED_API_KEY
    params['file_type'] = 'json'
    url = f"{FRED_BASE}/{endpoint}?{urlencode(params)}"
    try:
        req = Request(url, headers={'User-Agent': 'EconStats-QA/1.0'})
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e)}


def get_observations(series_id, years=5):
    """Get observations for a series from FRED."""
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

    return dates, values, {}


def find_query_plan(query):
    """
    Find the best matching query plan.
    Simplified version that checks exact and synonym matches.
    """
    if not QUERY_PLANS:
        return None

    q = query.lower().strip()

    # 1. Exact match
    if q in QUERY_PLANS:
        return QUERY_PLANS[q]

    # 2. Check synonyms
    for plan_key, plan in QUERY_PLANS.items():
        synonyms = plan.get('synonyms', [])
        if q in synonyms:
            return plan

    # 3. Partial match - find plans containing the query as a word
    for plan_key, plan in QUERY_PLANS.items():
        if q in plan_key or plan_key in q:
            return plan

    return None


def test_query(query, verbose=True):
    """
    Test a single query through the full pipeline.

    Returns dict with:
    - query: the input query
    - plan_found: bool
    - series: list of series IDs
    - series_names: human-readable names
    - data_fetched: bool for each series
    - data_points: count of data points for each series
    - score: 1-5 based on results
    - issues: list of any problems
    """
    result = {
        'query': query,
        'plan_found': False,
        'series': [],
        'series_names': [],
        'show_yoy': False,
        'data_results': [],
        'score': 0,
        'issues': [],
        'explanation': ''
    }

    # Step 1: Find query plan
    plan = find_query_plan(query)

    if not plan:
        result['issues'].append('NO_PLAN')
        result['explanation'] = f'No query plan found for "{query}"'
        result['score'] = 1
        if verbose:
            print(f"  NO PLAN found")
        return result

    result['plan_found'] = True
    result['series'] = plan.get('series', [])
    result['series_names'] = get_series_names(result['series'])
    result['show_yoy'] = plan.get('show_yoy', False)

    if verbose:
        print(f"  Plan: {len(result['series'])} series - {result['series']}")

    if not result['series']:
        result['issues'].append('EMPTY_PLAN')
        result['explanation'] = 'Query plan has no series'
        result['score'] = 1
        return result

    # Step 2: Fetch data for each series
    all_success = True
    total_points = 0

    for idx, series_id in enumerate(result['series']):
        if idx > 0:
            time.sleep(0.3)  # Rate limit between series
        try:
            dates, values, info = get_observations(series_id, years=5)

            if dates and values:
                result['data_results'].append({
                    'series_id': series_id,
                    'name': get_series_name(series_id),
                    'success': True,
                    'data_points': len(values),
                    'latest_date': dates[-1] if dates else None,
                    'latest_value': values[-1] if values else None
                })
                total_points += len(values)
                if verbose:
                    print(f"    {series_id}: {len(values)} points, latest: {dates[-1]} = {values[-1]:.2f}")
            else:
                result['data_results'].append({
                    'series_id': series_id,
                    'name': get_series_name(series_id),
                    'success': False,
                    'error': info.get('error', 'No data returned')
                })
                result['issues'].append(f'NO_DATA:{series_id}')
                all_success = False
                if verbose:
                    print(f"    {series_id}: NO DATA - {info.get('error', 'unknown')}")

        except Exception as e:
            result['data_results'].append({
                'series_id': series_id,
                'name': get_series_name(series_id),
                'success': False,
                'error': str(e)
            })
            result['issues'].append(f'FETCH_ERROR:{series_id}')
            all_success = False
            if verbose:
                print(f"    {series_id}: ERROR - {e}")

    # Step 3: Score the result
    if all_success and total_points > 0:
        # Check if we have reasonable number of series
        num_series = len(result['series'])
        if num_series >= 2 and num_series <= 4:
            result['score'] = 5
            result['explanation'] = f'Excellent: {num_series} series, {total_points} total data points'
        elif num_series == 1:
            result['score'] = 4
            result['explanation'] = f'Good: Single series with {total_points} data points'
        elif num_series > 4:
            result['score'] = 3
            result['issues'].append('TOO_MANY_SERIES')
            result['explanation'] = f'OK but {num_series} series may be overwhelming'
        else:
            result['score'] = 4
            result['explanation'] = f'Good: {num_series} series fetched successfully'
    elif total_points > 0:
        # Some series failed
        success_count = sum(1 for r in result['data_results'] if r.get('success'))
        result['score'] = 3 if success_count > 0 else 2
        result['explanation'] = f'Partial: {success_count}/{len(result["series"])} series fetched'
    else:
        result['score'] = 1
        result['explanation'] = 'Failed: No data could be fetched'

    return result


def evaluate_queries(queries, category, output_file):
    """Evaluate a list of queries and save results."""
    print(f"\n{'='*60}")
    print(f"QA AGENT: {category}")
    print(f"{'='*60}")
    print(f"Testing {len(queries)} queries with FRED API...")
    print(f"FRED API Key: {FRED_API_KEY[:8]}..." if FRED_API_KEY else "NO API KEY!")
    print(f"Loaded {len(QUERY_PLANS)} query plans")

    results = []
    scores = []
    issues_count = {}

    for i, query in enumerate(queries):
        print(f"\n[{i+1}/{len(queries)}] Testing: '{query}'")

        result = test_query(query, verbose=True)

        scores.append(result['score'])
        for issue in result['issues']:
            # Normalize issue names (strip series IDs for counting)
            issue_type = issue.split(':')[0]
            issues_count[issue_type] = issues_count.get(issue_type, 0) + 1

        score_icon = ['', '!', '!', '~', '+', '*'][min(result['score'], 5)]
        print(f"  Score: {result['score']}/5 {score_icon}")
        if result['issues']:
            print(f"  Issues: {result['issues']}")

        results.append(result)

        # Delay between queries to respect FRED rate limits (~120 requests/min)
        time.sleep(0.6)

    # Calculate summary stats
    avg_score = sum(scores) / len(scores) if scores else 0
    score_dist = {i: scores.count(i) for i in range(1, 6)}

    summary = {
        'category': category,
        'total_queries': len(queries),
        'average_score': round(avg_score, 2),
        'score_distribution': score_dist,
        'issues_summary': issues_count,
        'results': results
    }

    # Save results
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'-'*60}")
    print(f"SUMMARY: {category}")
    print(f"{'-'*60}")
    print(f"Average Score: {avg_score:.2f}/5")
    print(f"Score Distribution: {score_dist}")
    print(f"Issues Found: {issues_count}")
    print(f"Results saved to: {output_file}")

    return summary
