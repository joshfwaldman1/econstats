#!/usr/bin/env python3
"""Base utilities for QA testing agents."""

import json
import os
import sys
import time
from urllib.request import urlopen, Request

sys.path.insert(0, '/Users/josh/Desktop/econstats')
import glob

def load_query_plans():
    """Load all query plans from agents/*.json files."""
    plans = {}
    agents_dir = '/Users/josh/Desktop/econstats/agents'
    for plan_file in glob.glob(os.path.join(agents_dir, 'plans_*.json')):
        try:
            with open(plan_file, 'r') as f:
                plans.update(json.load(f))
        except Exception:
            pass
    return plans

QUERY_PLANS = load_query_plans()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Series name lookup for evaluation
SERIES_NAMES = {
    'A191RL1Q225SBEA': 'Real GDP Growth Rate',
    'GDPC1': 'Real GDP Level',
    'UNRATE': 'Unemployment Rate (U-3)',
    'U6RATE': 'Unemployment Rate (U-6)',
    'PAYEMS': 'Total Nonfarm Payrolls',
    'LNS12300060': 'Prime-Age Employment-Pop Ratio (25-54)',
    'LNS11300060': 'Prime-Age Labor Force Participation',
    'LNS11300000': 'Labor Force Participation Rate',
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
    'RSXFS': 'Retail Sales',
    'UMCSENT': 'Consumer Sentiment',
    'SP500': 'S&P 500',
    'JTSJOL': 'Job Openings (JOLTS)',
    'JTSQUR': 'Quits Rate (JOLTS)',
    'ICSA': 'Initial Jobless Claims',
    'DCOILWTICO': 'WTI Crude Oil Price',
    'GASREGW': 'Gas Price',
    'BOPGSTB': 'Trade Balance',
    'IMPCH': 'Imports from China',
    'LNS14000002': 'Unemployment Rate - Women',
    'LNS12300062': 'Prime-Age Emp-Pop Ratio - Women',
    'LNS11300002': 'LFPR - Women',
    'LNS14000001': 'Unemployment Rate - Men',
    'LNS14000006': 'Unemployment Rate - Black',
    'LNS14000009': 'Unemployment Rate - Hispanic',
    'PSAVERT': 'Personal Savings Rate',
    'INDPRO': 'Industrial Production',
}


def get_series_names(series_ids):
    """Convert series IDs to human-readable names."""
    return [SERIES_NAMES.get(s, s) for s in series_ids]


def call_evaluator(query: str, series: list, show_yoy: bool) -> dict:
    """Call Claude to evaluate if the series are appropriate for the query."""

    series_desc = ', '.join(get_series_names(series))

    prompt = f"""You are a senior economist evaluating an economic data dashboard.

A user asked: "{query}"
The system returned these FRED series: {series}
Series names: {series_desc}
Show as year-over-year: {show_yoy}

Rate this response on a scale of 1-5:
- 5: Perfect - exactly the right data for this query
- 4: Good - appropriate data, maybe missing one minor thing
- 3: Acceptable - relevant but could be better
- 2: Poor - missing key data or showing wrong series
- 1: Bad - completely wrong data for this query

Also flag these issues if present:
- WRONG_SERIES: Shows data that doesn't answer the question
- MISSING_KEY: Missing an obviously important series
- AGGREGATE_FOR_DEMOGRAPHIC: Uses aggregate data (PAYEMS, UNRATE) for a demographic question (women, Black, etc.)
- TOO_MANY: More than 4 series (overwhelming)
- TOO_FEW: Should show more context
- WRONG_YOY: Should/shouldn't show YoY transformation

Return JSON only:
{{
  "score": 4,
  "issues": [],
  "explanation": "Brief explanation",
  "suggested_fix": "What would make it better (if anything)"
}}"""

    url = 'https://api.anthropic.com/v1/messages'
    payload = {
        'model': 'claude-sonnet-4-20250514',
        'max_tokens': 500,
        'messages': [{'role': 'user', 'content': prompt}]
    }
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01'
    }

    try:
        req = Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            content = result['content'][0]['text']
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            return json.loads(content.strip())
    except Exception as e:
        return {'score': 0, 'issues': ['EVAL_ERROR'], 'explanation': str(e), 'suggested_fix': ''}


def evaluate_queries(queries: list, category: str, output_file: str):
    """Evaluate a list of queries and save results."""
    print(f"\n{'='*60}")
    print(f"QA AGENT: {category}")
    print(f"{'='*60}")
    print(f"Evaluating {len(queries)} queries...")

    results = []
    scores = []
    issues_count = {}

    for i, query in enumerate(queries):
        print(f"\n[{i+1}/{len(queries)}] Testing: '{query}'")

        # Get what the app would return
        plan = QUERY_PLANS.get(query.lower().strip(), {})

        if not plan:
            print(f"  ⚠️  No pre-computed plan found")
            results.append({
                'query': query,
                'series': [],
                'score': 0,
                'issues': ['NO_PLAN'],
                'explanation': 'No pre-computed plan exists for this query',
                'suggested_fix': 'Add this query to the plans'
            })
            continue

        series = plan.get('series', [])
        show_yoy = plan.get('show_yoy', False)

        print(f"  Series: {series}")

        # Evaluate with Claude
        eval_result = call_evaluator(query, series, show_yoy)

        score = eval_result.get('score', 0)
        issues = eval_result.get('issues', [])

        scores.append(score)
        for issue in issues:
            issues_count[issue] = issues_count.get(issue, 0) + 1

        print(f"  Score: {score}/5 {['❌','⚠️','😐','✓','✓✓','⭐'][min(score,5)]}")
        if issues:
            print(f"  Issues: {issues}")

        results.append({
            'query': query,
            'series': series,
            'series_names': get_series_names(series),
            'show_yoy': show_yoy,
            **eval_result
        })

        time.sleep(0.3)  # Rate limiting

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
