#!/usr/bin/env python3
"""
Test EconStats with 100 diverse questions and rate the responses.
"""

import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock streamlit before importing app
class MockStreamlit:
    def cache_data(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def spinner(self, *args, **kwargs):
        class CM:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        return CM()
    def __getattr__(self, name):
        return lambda *args, **kwargs: None

sys.modules['streamlit'] = MockStreamlit()

# Now import from app
from app import (
    find_query_plan,
    hybrid_query_plan,
    search_series,
    extract_temporal_filter,
    extract_demographic_groups,
    detect_geographic_scope,
    SERIES_DB,
    load_query_plans,
)

# Load plans
load_query_plans()

# 100 test questions organized by category
TEST_QUESTIONS = {
    "Employment - General": [
        "How is the job market?",
        "What is the unemployment rate?",
        "How many jobs were added last month?",
        "Show me employment trends",
        "What is the labor force participation rate?",
        "How is the labor market doing?",
        "Show me nonfarm payrolls",
        "What is the current jobs situation?",
    ],
    "Employment - Sectors": [
        "How is manufacturing employment?",
        "Show me tech sector jobs",
        "Healthcare employment trends",
        "Construction jobs",
        "Retail employment",
        "Government employment",
        "How are restaurant jobs doing?",
        "Leisure and hospitality employment",
    ],
    "Employment - Demographics": [
        "Black unemployment rate",
        "Hispanic employment",
        "Women in the workforce",
        "Youth unemployment",
        "How are Black workers doing?",
        "Immigrant labor force participation",
        "Men vs women employment",
        "Older worker employment",
    ],
    "Inflation - General": [
        "What is inflation?",
        "Show me CPI",
        "How is inflation doing?",
        "What is the inflation rate?",
        "Core inflation trends",
        "PCE inflation",
        "Is inflation going up or down?",
        "Consumer prices",
    ],
    "Inflation - Components": [
        "Food prices",
        "Gas prices",
        "Shelter inflation",
        "Housing costs inflation",
        "Energy prices",
        "Used car prices",
        "Medical care inflation",
        "Rent inflation",
    ],
    "GDP and Growth": [
        "What is GDP growth?",
        "How is the economy doing?",
        "Show me real GDP",
        "Economic growth rate",
        "Is the economy in recession?",
        "GDP trends",
        "Quarterly GDP growth",
        "Industrial production",
    ],
    "Housing": [
        "How is the housing market?",
        "Home prices",
        "Mortgage rates",
        "Housing starts",
        "Home sales",
        "New home construction",
        "Housing affordability",
        "Case-Shiller index",
    ],
    "Interest Rates": [
        "What is the fed funds rate?",
        "Interest rates",
        "10-year Treasury yield",
        "Mortgage rates trend",
        "Fed policy rate",
        "Short term interest rates",
        "Long term rates",
        "Yield curve",
    ],
    "Consumer": [
        "Consumer spending",
        "Retail sales",
        "Consumer sentiment",
        "Consumer confidence",
        "Personal consumption",
        "Household spending",
        "Are consumers spending?",
        "Consumer outlook",
    ],
    "Wages and Income": [
        "Wage growth",
        "Average hourly earnings",
        "Real wages",
        "Income trends",
        "Are wages keeping up with inflation?",
        "Median household income",
        "Personal income",
        "Earnings growth",
    ],
    "Geographic": [
        "Texas unemployment",
        "California economy",
        "How is Florida doing?",
        "New York employment",
        "Midwest manufacturing",
        "Ohio jobs",
        "Pennsylvania economy",
        "Georgia unemployment rate",
    ],
    "Temporal": [
        "Inflation in 2022",
        "Pre-covid unemployment",
        "GDP during the pandemic",
        "Post-covid recovery",
        "Unemployment during great recession",
        "Last 5 years of job growth",
        "2023 inflation",
        "Employment since 2020",
    ],
    "Complex/Hard Questions": [
        "How are tariffs affecting the economy?",
        "Is there stagflation?",
        "What is the federal deficit?",
        "Trade war impact on manufacturing",
        "How is AI affecting jobs?",
        "Supply chain issues",
        "Small business trends",
        "Labor shortage",
    ],
    "Comparative": [
        "Inflation vs wage growth",
        "GDP vs employment",
        "Unemployment rate vs job openings",
        "Compare CPI and PCE",
        "Housing prices vs income",
        "Exports vs imports",
        "Manufacturing vs services",
        "10-year vs 2-year Treasury",
    ],
    "Edge Cases": [
        "food trucks",
        "solar industry jobs",
        "cryptocurrency",
        "gig economy",
        "rates",
        "stocks",
        "economy",
        "jobs",
    ],
}

def rate_response(query: str, result: dict, category: str) -> dict:
    """Rate a query response on multiple dimensions."""

    rating = {
        'query': query,
        'category': category,
        'series_found': len(result.get('series', [])),
        'has_explanation': bool(result.get('explanation')),
        'no_data': result.get('no_data_available', False),
    }

    series = result.get('series', [])
    explanation = result.get('explanation', '')

    # Score: 0-3
    # 3 = Excellent (relevant series, good explanation)
    # 2 = Good (some relevant series OR good explanation)
    # 1 = Partial (found something but may not be ideal)
    # 0 = Failed (no data or completely irrelevant)

    if result.get('no_data_available'):
        rating['score'] = 0
        rating['assessment'] = 'NO_DATA'
    elif not series:
        rating['score'] = 0
        rating['assessment'] = 'EMPTY'
    else:
        # Check if series seem relevant based on IDs and query
        query_lower = query.lower()

        # Known good series for common queries
        relevance_score = 0

        # Employment queries
        if any(w in query_lower for w in ['job', 'employment', 'unemploy', 'labor', 'payroll', 'workforce']):
            if any(s in series for s in ['PAYEMS', 'UNRATE', 'CIVPART', 'LNS12300000', 'U6RATE', 'JTSJOL']):
                relevance_score += 2
            elif any('LNS' in s or 'LNU' in s or 'EMP' in s or 'UR' in s for s in series):
                relevance_score += 1

        # Sector employment queries (manufacturing, construction, healthcare, etc.)
        sector_keywords = ['manufacturing', 'construction', 'healthcare', 'retail', 'hospitality',
                          'restaurant', 'tech', 'government', 'leisure', 'information', 'service']
        if any(w in query_lower for w in sector_keywords):
            sector_series = ['MANEMP', 'USCONS', 'USHCS', 'USTRADE', 'USLAH', 'USINFO', 'USGOVT',
                           'SRVPRD', 'IPMAN', 'HOUST', 'PERMIT']
            if any(s in series for s in sector_series):
                relevance_score += 2

        # Inflation queries
        if any(w in query_lower for w in ['inflation', 'cpi', 'price', 'pce']):
            if any(s in series for s in ['CPIAUCSL', 'CPILFESL', 'PCEPI', 'PCEPILFE']):
                relevance_score += 2
            elif any('CPI' in s or 'PCE' in s or 'PRICE' in s or s.startswith('CUSR') for s in series):
                relevance_score += 1

        # Inflation component queries (gas, shelter, energy, food, medical, rent)
        component_keywords = ['gas', 'shelter', 'energy', 'food', 'medical', 'rent', 'grocery']
        if any(w in query_lower for w in component_keywords):
            component_series = ['GASREGW', 'CUSR0000SAH1', 'CUSR0000SEHA', 'CUSR0000SEHC',
                               'CUSR0000SAF11', 'CUSR0000SEFV', 'CUSR0000SAM', 'CPIMEDSL',
                               'CUSR0000SETB01', 'CUSR0000SEHE', 'DCOILWTICO']
            if any(s in series for s in component_series):
                relevance_score += 2
            elif any(s.startswith('CUSR') for s in series):
                relevance_score += 1

        # GDP queries
        if any(w in query_lower for w in ['gdp', 'economy', 'growth', 'recession']):
            if any(s in series for s in ['GDPC1', 'GDP', 'A191RL1Q225SBEA', 'A191RO1Q156NBEA', 'BBKMLEIX']):
                relevance_score += 2
            elif any('GDP' in s for s in series):
                relevance_score += 1

        # Industrial production queries
        if any(w in query_lower for w in ['industrial', 'production', 'output', 'factory']):
            if any(s in series for s in ['INDPRO', 'IPMAN', 'TCU', 'CAPUTLG3311A2S']):
                relevance_score += 2

        # Housing queries
        if any(w in query_lower for w in ['housing', 'home', 'mortgage', 'house', 'case-shiller', 'shiller']):
            if any(s in series for s in ['CSUSHPINSA', 'MORTGAGE30US', 'HOUST', 'EXHOSLUSM495S', 'MSPUS', 'FIXHAI']):
                relevance_score += 2
            elif any('HOUS' in s or 'HOME' in s or 'MORT' in s for s in series):
                relevance_score += 1

        # Interest rate queries
        if any(w in query_lower for w in ['interest', 'fed', 'treasury', 'yield', 'rate', 'curve']) and 'inflation' not in query_lower:
            if any(s in series for s in ['FEDFUNDS', 'DGS10', 'DGS2', 'MORTGAGE30US', 'T10Y2Y', 'DGS30']):
                relevance_score += 2
            elif any('DGS' in s or 'RATE' in s or 'T10Y' in s for s in series):
                relevance_score += 1

        # Consumer queries
        if any(w in query_lower for w in ['consumer', 'retail', 'spending', 'sentiment', 'consumption', 'household']):
            if any(s in series for s in ['UMCSENT', 'PCE', 'PCEC96', 'RSAFS', 'RSXFS', 'DSPIC96']):
                relevance_score += 2
            elif any('SENT' in s or 'PCE' in s or 'RS' in s for s in series):
                relevance_score += 1

        # Demographic queries
        if any(w in query_lower for w in ['black', 'hispanic', 'women', 'men', 'youth', 'immigrant', 'foreign-born']):
            # Check for demographic-specific series (both LNS and LNU prefixes)
            if any(s.startswith('LNS14') or s.startswith('LNS12') or s.startswith('LNS11') or
                   s.startswith('LNU04') or s.startswith('LNU02') or s.startswith('LNU01') for s in series):
                relevance_score += 2

        # Wage queries
        if any(w in query_lower for w in ['wage', 'earning', 'income', 'salary', 'personal income']):
            if any(s in series for s in ['CES0500000003', 'LES1252881600Q', 'AHETPI', 'MEHOINUSA672N', 'PI', 'DSPIC96']):
                relevance_score += 2
            elif any('EARN' in s or 'WAGE' in s or 'INCOME' in s for s in series):
                relevance_score += 1

        # Geographic/state queries
        state_prefixes = ['TX', 'CA', 'FL', 'NY', 'OH', 'PA', 'GA', 'IL', 'NC', 'MI']
        if any(state.lower() in query_lower for state in ['texas', 'california', 'florida', 'new york',
               'ohio', 'pennsylvania', 'georgia', 'illinois', 'midwest']):
            # Check for state-specific series (e.g., TXUR, CAUR, OHNA, etc.)
            if any(any(s.startswith(prefix) for prefix in state_prefixes) for s in series):
                relevance_score += 2

        # Trade/exports/imports queries
        if any(w in query_lower for w in ['trade', 'export', 'import', 'tariff', 'deficit']):
            trade_series = ['BOPGSTB', 'EXPGSC1', 'IMPGSC1', 'NETEXP', 'IMPGS', 'EXPGS', 'IMPCH']
            if any(s in series for s in trade_series):
                relevance_score += 2

        # Deficit/fiscal queries
        if any(w in query_lower for w in ['deficit', 'debt', 'budget', 'fiscal']):
            fiscal_series = ['FYFSD', 'GFDEBTN', 'FGEXPND', 'FGRECPT']
            if any(s in series for s in fiscal_series):
                relevance_score += 2

        # Supply chain queries
        if any(w in query_lower for w in ['supply chain', 'supplier', 'freight', 'delivery']):
            supply_series = ['NAPMPMD', 'NAPMPI', 'TSIFRGHT', 'RAILFRTINTERMODAL']
            if any(s in series for s in supply_series):
                relevance_score += 2

        # Stock market queries
        if any(w in query_lower for w in ['stock', 'market', 's&p', 'equity']):
            if any(s in series for s in ['SP500', 'VIXCLS', 'WILLSMLCAP']):
                relevance_score += 2

        # Default: at least found something
        if relevance_score == 0 and series:
            relevance_score = 1

        # Cap at 3
        rating['score'] = min(relevance_score, 3)

        if rating['score'] >= 2:
            rating['assessment'] = 'GOOD'
        elif rating['score'] == 1:
            rating['assessment'] = 'PARTIAL'
        else:
            rating['assessment'] = 'WEAK'

    rating['series'] = series[:4]
    rating['explanation_preview'] = explanation[:100] if explanation else ''

    return rating


def run_tests():
    """Run all 100 tests and generate report."""

    print("=" * 80)
    print("EconStats 100-Question Test Suite")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    all_results = []
    category_scores = {}

    total_questions = sum(len(qs) for qs in TEST_QUESTIONS.values())
    current = 0

    for category, questions in TEST_QUESTIONS.items():
        print(f"\n{'='*60}")
        print(f"Category: {category}")
        print(f"{'='*60}")

        category_results = []

        for query in questions:
            current += 1
            print(f"\n[{current}/{total_questions}] Testing: {query}")

            try:
                # First try precomputed plans
                result = find_query_plan(query)
                source = 'precomputed'

                if not result:
                    # Try hybrid search
                    result = hybrid_query_plan(query, verbose=False)
                    source = 'hybrid'

                if not result:
                    result = {'series': [], 'explanation': '', 'no_data_available': True}
                    source = 'none'

                rating = rate_response(query, result, category)
                rating['source'] = source

                # Print result
                score_emoji = {3: '✅', 2: '🟡', 1: '🟠', 0: '❌'}[rating['score']]
                print(f"  {score_emoji} Score: {rating['score']}/3 ({rating['assessment']})")
                print(f"  Series: {rating['series']}")
                print(f"  Source: {source}")

                category_results.append(rating)
                all_results.append(rating)

            except Exception as e:
                print(f"  ❌ ERROR: {e}")
                error_rating = {
                    'query': query,
                    'category': category,
                    'score': 0,
                    'assessment': 'ERROR',
                    'error': str(e),
                    'series': [],
                }
                category_results.append(error_rating)
                all_results.append(error_rating)

        # Category summary
        cat_scores = [r['score'] for r in category_results]
        cat_avg = sum(cat_scores) / len(cat_scores) if cat_scores else 0
        category_scores[category] = {
            'avg_score': cat_avg,
            'good': sum(1 for s in cat_scores if s >= 2),
            'partial': sum(1 for s in cat_scores if s == 1),
            'failed': sum(1 for s in cat_scores if s == 0),
            'total': len(cat_scores),
        }

        print(f"\n  Category Average: {cat_avg:.2f}/3")
        print(f"  Good: {category_scores[category]['good']}, Partial: {category_scores[category]['partial']}, Failed: {category_scores[category]['failed']}")

    # Final report
    print("\n" + "=" * 80)
    print("FINAL REPORT")
    print("=" * 80)

    total_scores = [r['score'] for r in all_results]
    overall_avg = sum(total_scores) / len(total_scores) if total_scores else 0

    print(f"\nOverall Score: {overall_avg:.2f}/3 ({overall_avg/3*100:.1f}%)")
    print(f"Total Questions: {len(all_results)}")
    print(f"Good (2-3): {sum(1 for s in total_scores if s >= 2)} ({sum(1 for s in total_scores if s >= 2)/len(total_scores)*100:.1f}%)")
    print(f"Partial (1): {sum(1 for s in total_scores if s == 1)} ({sum(1 for s in total_scores if s == 1)/len(total_scores)*100:.1f}%)")
    print(f"Failed (0): {sum(1 for s in total_scores if s == 0)} ({sum(1 for s in total_scores if s == 0)/len(total_scores)*100:.1f}%)")

    print("\n" + "-" * 60)
    print("Category Breakdown:")
    print("-" * 60)

    sorted_cats = sorted(category_scores.items(), key=lambda x: x[1]['avg_score'], reverse=True)
    for cat, stats in sorted_cats:
        pct = stats['avg_score'] / 3 * 100
        bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
        print(f"{cat:30} {stats['avg_score']:.2f}/3 [{bar}] {pct:.0f}%")

    print("\n" + "-" * 60)
    print("Failed Queries (score=0):")
    print("-" * 60)
    for r in all_results:
        if r['score'] == 0:
            print(f"  • {r['query']} [{r['category']}] - {r.get('assessment', 'UNKNOWN')}")

    print("\n" + "-" * 60)
    print("Partial Queries (score=1):")
    print("-" * 60)
    for r in all_results:
        if r['score'] == 1:
            print(f"  • {r['query']} [{r['category']}] - Series: {r.get('series', [])}")

    # Save detailed results to JSON
    output_file = 'test_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'overall_score': overall_avg,
            'total_questions': len(all_results),
            'category_scores': category_scores,
            'all_results': all_results,
        }, f, indent=2)

    print(f"\nDetailed results saved to: {output_file}")
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return overall_avg, all_results


if __name__ == '__main__':
    run_tests()
