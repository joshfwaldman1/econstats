#!/usr/bin/env python3
"""Merge all QA results into a summary report."""

import json
import os
from datetime import datetime

QA_DIR = '/Users/josh/Desktop/econstats/qa'
RESULT_FILES = [
    'results_economy.json',
    'results_jobs.json',
    'results_inflation.json',
    'results_rates.json',
    'results_housing.json',
    'results_demographics.json',
    'results_consumer.json',
    'results_trade_gdp.json',
]

def merge_results():
    """Merge all QA results and generate summary report."""
    all_results = []
    all_scores = []
    all_issues = {}
    category_stats = []

    print("="*70)
    print("QA RESULTS SUMMARY REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    for filename in RESULT_FILES:
        filepath = os.path.join(QA_DIR, filename)
        if not os.path.exists(filepath):
            print(f"\n⚠️  Missing: {filename}")
            continue

        with open(filepath) as f:
            data = json.load(f)

        category = data.get('category', filename)
        avg_score = data.get('average_score', 0)
        total = data.get('total_queries', 0)
        issues = data.get('issues_summary', {})
        results = data.get('results', [])

        all_results.extend(results)
        for r in results:
            if r.get('score', 0) > 0:
                all_scores.append(r['score'])

        for issue, count in issues.items():
            all_issues[issue] = all_issues.get(issue, 0) + count

        category_stats.append({
            'category': category,
            'queries': total,
            'avg_score': avg_score,
            'issues': issues
        })

        print(f"\n{category}: {avg_score:.2f}/5 ({total} queries)")
        if issues:
            print(f"  Issues: {issues}")

    # Overall stats
    overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0
    score_dist = {i: all_scores.count(i) for i in range(1, 6)}

    print("\n" + "="*70)
    print("OVERALL STATISTICS")
    print("="*70)
    print(f"Total Queries Tested: {len(all_results)}")
    print(f"Overall Average Score: {overall_avg:.2f}/5")
    print(f"Score Distribution: {score_dist}")
    print(f"Total Issues: {all_issues}")

    # Quality breakdown
    excellent = sum(1 for s in all_scores if s == 5)
    good = sum(1 for s in all_scores if s == 4)
    acceptable = sum(1 for s in all_scores if s == 3)
    poor = sum(1 for s in all_scores if s <= 2)

    print(f"\nQuality Breakdown:")
    print(f"  ⭐ Excellent (5): {excellent} ({100*excellent/len(all_scores):.1f}%)" if all_scores else "")
    print(f"  ✓✓ Good (4): {good} ({100*good/len(all_scores):.1f}%)" if all_scores else "")
    print(f"  ✓ Acceptable (3): {acceptable} ({100*acceptable/len(all_scores):.1f}%)" if all_scores else "")
    print(f"  ❌ Poor (1-2): {poor} ({100*poor/len(all_scores):.1f}%)" if all_scores else "")

    # Problematic queries
    print("\n" + "="*70)
    print("QUERIES NEEDING ATTENTION (Score <= 3)")
    print("="*70)

    problem_queries = [r for r in all_results if r.get('score', 0) <= 3 and r.get('score', 0) > 0]
    problem_queries.sort(key=lambda x: x.get('score', 0))

    for r in problem_queries:
        print(f"\n'{r['query']}' - Score: {r.get('score')}/5")
        print(f"  Series: {r.get('series', [])}")
        print(f"  Issues: {r.get('issues', [])}")
        print(f"  Fix: {r.get('suggested_fix', 'N/A')}")

    # Demographic check
    print("\n" + "="*70)
    print("DEMOGRAPHIC QUERIES CHECK")
    print("="*70)

    demo_keywords = ['women', 'female', 'men', 'black', 'african american', 'hispanic', 'latino', 'white', 'teen', 'youth', 'older']
    aggregate_series = {'PAYEMS', 'UNRATE', 'LNS11300000', 'LNS12300060'}

    demo_issues = []
    for r in all_results:
        query_lower = r.get('query', '').lower()
        if any(kw in query_lower for kw in demo_keywords):
            series = set(r.get('series', []))
            if series & aggregate_series:
                demo_issues.append(r)

    if demo_issues:
        print(f"⚠️  Found {len(demo_issues)} demographic queries using aggregate series:")
        for r in demo_issues:
            print(f"  '{r['query']}': {r.get('series', [])}")
    else:
        print("✓ All demographic queries use appropriate demographic-specific series")

    # Save merged results
    merged = {
        'generated': datetime.now().isoformat(),
        'overall_average': round(overall_avg, 2),
        'total_queries': len(all_results),
        'score_distribution': score_dist,
        'issues_summary': all_issues,
        'category_stats': category_stats,
        'all_results': all_results
    }

    output_file = os.path.join(QA_DIR, 'qa_merged_results.json')
    with open(output_file, 'w') as f:
        json.dump(merged, f, indent=2)

    print(f"\nMerged results saved to: {output_file}")

    return merged

if __name__ == "__main__":
    merge_results()
