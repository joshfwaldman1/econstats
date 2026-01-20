#!/usr/bin/env python3
"""
CLI runner for the economist agent pilot.

Usage:
    python run.py "What's the current state of the job market?"
    python run.py "How does inflation compare to wage growth?"
    python run.py "Compare job recovery after 2008 vs 2020 recessions"
"""

import sys
import os

# Ensure ANTHROPIC_API_KEY is set
if not os.environ.get('ANTHROPIC_API_KEY'):
    print("Error: ANTHROPIC_API_KEY environment variable not set")
    print("Run: export ANTHROPIC_API_KEY='your-key-here'")
    sys.exit(1)

from agent import run_query


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nExample queries:")
        print('  python run.py "What\'s the current unemployment rate?"')
        print('  python run.py "How is inflation trending?"')
        print('  python run.py "Compare the 2008 vs 2020 job recovery"')
        print('  python run.py "Is the yield curve inverted?"')
        sys.exit(0)

    query = ' '.join(sys.argv[1:])
    result = run_query(query, verbose=True)

    print(f"\n{'='*60}")
    print("FINAL ANALYSIS:")
    print('='*60)
    print(result)


if __name__ == '__main__':
    main()
