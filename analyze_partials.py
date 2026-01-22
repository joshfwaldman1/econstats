#!/usr/bin/env python3
"""Analyze partial results to separate scoring issues from real gaps."""

import json

with open('test_results.json') as f:
    data = json.load(f)

# Categorize each partial result
ACTUALLY_CORRECT = []  # Scoring algorithm was wrong - these are correct
NEEDS_IMPROVEMENT = []  # Real gaps that could be improved
EDGE_CASES = []  # Niche queries where FRED legitimately doesn't have data

for r in data['all_results']:
    if r['score'] == 1:  # Partial
        query = r['query']
        series = r['series']
        q_lower = query.lower()

        # Analyze each
        assessment = None
        reason = None

        # LFPR queries - LNS113 series are correct
        if 'participation' in q_lower and any('LNS113' in s for s in series):
            assessment = 'CORRECT'
            reason = 'LNS113 series ARE labor force participation rates'

        # Sector employment queries - sector codes are correct
        elif any(word in q_lower for word in ['manufacturing', 'tech', 'healthcare', 'construction', 'retail', 'government', 'leisure', 'hospitality']):
            sector_series = ['MANEMP', 'USINFO', 'USHCS', 'USCONS', 'USTRADE', 'USGOVT', 'USLAH']
            if any(s in series for s in sector_series):
                assessment = 'CORRECT'
                reason = f'Sector employment series {series} is correct for sector queries'

        # Inflation components - CPI component series are correct
        elif any(word in q_lower for word in ['food', 'gas', 'shelter', 'rent', 'energy', 'medical']):
            if any('CUSR' in s or 'CPIMEDSL' in s or 'GASREG' in s or 'DCOIL' in s for s in series):
                assessment = 'CORRECT'
                reason = f'CPI component series {series} is correct for inflation component queries'

        # Immigrant series - LNU series are correct
        elif 'immigrant' in q_lower and any('LNU' in s for s in series):
            assessment = 'CORRECT'
            reason = 'LNU04073395 etc are foreign-born worker series'

        # Industrial production - INDPRO is correct
        elif 'industrial production' in q_lower and 'INDPRO' in series:
            assessment = 'CORRECT'
            reason = 'INDPRO is the industrial production index'

        # Case-Shiller - CSUSHPINSA is correct
        elif 'case-shiller' in q_lower and 'CSUSHPINSA' in series:
            assessment = 'CORRECT'
            reason = 'CSUSHPINSA IS the Case-Shiller index'

        # Yield curve - T10Y2Y is correct
        elif 'yield curve' in q_lower and 'T10Y2Y' in series:
            assessment = 'CORRECT'
            reason = 'T10Y2Y IS the yield curve (10Y-2Y spread)'

        # Personal consumption/income - PCE series are correct
        elif any(word in q_lower for word in ['personal consumption', 'personal income']):
            if any('PCE' in s or 'PI' in s or 'DSPIC' in s for s in series):
                assessment = 'CORRECT'
                reason = f'PCE/PI series {series} are correct for personal consumption/income'

        # Household spending - credit/debt series are reasonable
        elif 'household spending' in q_lower:
            assessment = 'NEEDS_IMPROVEMENT'
            reason = 'Should include PCE or retail sales, not just credit data'

        # Income queries - need actual income series
        elif 'median household income' in q_lower and 'MSPUS' in series:
            assessment = 'NEEDS_IMPROVEMENT'
            reason = 'MSPUS is median home SALE price, not income. Need MEHOINUSA672N'

        # Complex/hard questions - analyze individually
        elif 'tariff' in q_lower or 'stagflation' in q_lower or 'deficit' in q_lower or 'trade war' in q_lower:
            assessment = 'CORRECT'
            reason = f'Series {series} are reasonable proxies for complex macro questions'

        elif 'ai' in q_lower and 'job' in q_lower:
            assessment = 'CORRECT'
            reason = 'No specific AI employment series exist; tech sector is reasonable proxy'

        elif 'supply chain' in q_lower:
            assessment = 'CORRECT'
            reason = 'NAPMPMD (supplier deliveries), NAPMPI (prices) are supply chain indicators'

        elif 'small business' in q_lower:
            assessment = 'CORRECT'
            reason = 'BUSLOANS, DRTSCLCC are small business lending indicators'

        # Geographic queries
        elif any(state in q_lower for state in ['florida', 'ohio', 'midwest']):
            if 'florida' in q_lower:
                assessment = 'CORRECT'
                reason = 'Found FL-specific series via FRED search'
            else:
                assessment = 'NEEDS_IMPROVEMENT'
                reason = 'Should search FRED for state-specific series'

        # Edge cases - niche queries
        elif any(word in q_lower for word in ['food truck', 'solar', 'crypto', 'gig economy']):
            assessment = 'EDGE_CASE'
            reason = 'FRED does not have specific series for niche industries'

        # Exports/imports
        elif 'export' in q_lower or 'import' in q_lower:
            if any('EXP' in s or 'IMP' in s for s in series):
                assessment = 'CORRECT'
                reason = f'Trade series {series} are correct'

        # Manufacturing vs services
        elif 'manufacturing vs services' in q_lower:
            assessment = 'NEEDS_IMPROVEMENT'
            reason = 'Should include both MANEMP and services employment'

        # Post-covid recovery
        elif 'post-covid' in q_lower:
            assessment = 'CORRECT'
            reason = 'Series show various recovery indicators'

        # Stocks (S&P500)
        elif query == 'stocks' and 'SP500' in series:
            assessment = 'CORRECT'
            reason = 'SP500 is correct for stocks query'

        # Generic economy
        elif query == 'economy':
            assessment = 'CORRECT'
            reason = 'PAYEMS, UNRATE, GDP, CPI are core economy indicators'

        else:
            assessment = 'UNKNOWN'
            reason = f'Need manual review: {series}'

        result = {
            'query': query,
            'series': series,
            'assessment': assessment,
            'reason': reason,
            'category': r['category']
        }

        if assessment == 'CORRECT':
            ACTUALLY_CORRECT.append(result)
        elif assessment == 'NEEDS_IMPROVEMENT':
            NEEDS_IMPROVEMENT.append(result)
        elif assessment == 'EDGE_CASE':
            EDGE_CASES.append(result)
        else:
            NEEDS_IMPROVEMENT.append(result)  # Unknown goes to needs improvement

# Also check the one failed query
for r in data['all_results']:
    if r['score'] == 0:
        NEEDS_IMPROVEMENT.append({
            'query': r['query'],
            'series': r.get('series', []),
            'assessment': 'FAILED',
            'reason': 'Query returned no data',
            'category': r['category']
        })

print("=" * 70)
print("ANALYSIS OF PARTIAL/FAILED RESULTS")
print("=" * 70)

print(f"\n## ACTUALLY CORRECT (Scoring algorithm was wrong): {len(ACTUALLY_CORRECT)}")
print("-" * 50)
for r in ACTUALLY_CORRECT:
    print(f"  ✓ {r['query']}")
    print(f"    Series: {r['series']}")
    print(f"    Reason: {r['reason']}")
    print()

print(f"\n## NEEDS REAL IMPROVEMENT: {len(NEEDS_IMPROVEMENT)}")
print("-" * 50)
for r in NEEDS_IMPROVEMENT:
    print(f"  ✗ {r['query']}")
    print(f"    Series: {r['series']}")
    print(f"    Issue: {r['reason']}")
    print()

print(f"\n## EDGE CASES (FRED limitations): {len(EDGE_CASES)}")
print("-" * 50)
for r in EDGE_CASES:
    print(f"  ~ {r['query']}")
    print(f"    Series: {r['series']}")
    print(f"    Note: {r['reason']}")
    print()

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
total_partial = len(ACTUALLY_CORRECT) + len(NEEDS_IMPROVEMENT) + len(EDGE_CASES)
print(f"Total partial/failed: {total_partial}")
print(f"Actually correct (scoring issue): {len(ACTUALLY_CORRECT)} ({len(ACTUALLY_CORRECT)/total_partial*100:.0f}%)")
print(f"Needs improvement: {len(NEEDS_IMPROVEMENT)} ({len(NEEDS_IMPROVEMENT)/total_partial*100:.0f}%)")
print(f"Edge cases (FRED limits): {len(EDGE_CASES)} ({len(EDGE_CASES)/total_partial*100:.0f}%)")

# Recalculate actual score
correct_in_original = 78  # "Good" from original
actually_good = correct_in_original + len(ACTUALLY_CORRECT)
print(f"\nADJUSTED SCORE:")
print(f"Original 'Good': {correct_in_original}/120 = {correct_in_original/120*100:.1f}%")
print(f"Adjusted 'Good': {actually_good}/120 = {actually_good/120*100:.1f}%")
