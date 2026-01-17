#!/usr/bin/env python3
"""
Generate smart query plans for the 200 most likely economic prompts.
These will be used as a structured lookup to avoid Claude API calls for common queries.
"""

import json
import os
import time
from urllib.request import urlopen, Request

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# 200 most likely economic prompts organized by category
COMMON_PROMPTS = [
    # Economy Overview (20)
    "how is the economy",
    "how is the economy doing",
    "economic overview",
    "state of the economy",
    "is the economy good",
    "is the economy bad",
    "economy today",
    "current economic conditions",
    "economic health",
    "how's the economy",
    "economy 2024",
    "economy 2025",
    "us economy",
    "american economy",
    "economic outlook",
    "economic forecast",
    "is there a recession",
    "are we in a recession",
    "recession risk",
    "recession indicators",

    # Jobs & Employment (30)
    "jobs",
    "job market",
    "employment",
    "unemployment",
    "unemployment rate",
    "how is the job market",
    "labor market",
    "hiring",
    "job growth",
    "job openings",
    "jolts",
    "payrolls",
    "nonfarm payrolls",
    "jobs report",
    "employment rate",
    "jobless rate",
    "weekly jobless claims",
    "initial claims",
    "continuing claims",
    "labor force participation",
    "participation rate",
    "prime age employment",
    "employment to population ratio",
    "underemployment",
    "u6 unemployment",
    "long term unemployment",
    "job quits",
    "quit rate",
    "layoffs",
    "job cuts",

    # Wages & Income (15)
    "wages",
    "wage growth",
    "average hourly earnings",
    "earnings",
    "income",
    "real wages",
    "wage inflation",
    "compensation",
    "hourly pay",
    "weekly earnings",
    "median income",
    "household income",
    "personal income",
    "disposable income",
    "salary growth",

    # Inflation & Prices (25)
    "inflation",
    "cpi",
    "consumer price index",
    "core inflation",
    "core cpi",
    "pce",
    "pce inflation",
    "core pce",
    "price increases",
    "cost of living",
    "prices",
    "inflation rate",
    "is inflation high",
    "is inflation coming down",
    "deflation",
    "disinflation",
    "food prices",
    "grocery prices",
    "gas prices",
    "gasoline prices",
    "energy prices",
    "oil prices",
    "rent inflation",
    "shelter inflation",
    "housing inflation",

    # Interest Rates & Fed (20)
    "interest rates",
    "rates",
    "fed",
    "federal reserve",
    "fed funds rate",
    "federal funds rate",
    "fed policy",
    "monetary policy",
    "rate hikes",
    "rate cuts",
    "will the fed cut rates",
    "treasury yields",
    "10 year treasury",
    "2 year treasury",
    "yield curve",
    "inverted yield curve",
    "bond yields",
    "mortgage rates",
    "30 year mortgage",
    "borrowing costs",

    # Housing (15)
    "housing",
    "housing market",
    "home prices",
    "house prices",
    "real estate",
    "home sales",
    "existing home sales",
    "new home sales",
    "housing starts",
    "building permits",
    "housing affordability",
    "rent prices",
    "case shiller",
    "home values",
    "housing inventory",

    # GDP & Growth (15)
    "gdp",
    "gdp growth",
    "economic growth",
    "real gdp",
    "gdp report",
    "quarterly gdp",
    "growth rate",
    "output",
    "production",
    "industrial production",
    "manufacturing",
    "factory output",
    "capacity utilization",
    "productivity",
    "economic expansion",

    # Consumer & Spending (15)
    "consumer spending",
    "retail sales",
    "consumer sentiment",
    "consumer confidence",
    "spending",
    "consumption",
    "personal spending",
    "consumer",
    "michigan consumer sentiment",
    "conference board",
    "credit card spending",
    "savings rate",
    "personal savings",
    "consumer debt",
    "household debt",

    # Stock Market (10)
    "stock market",
    "stocks",
    "s&p 500",
    "sp500",
    "dow jones",
    "nasdaq",
    "market",
    "equities",
    "stock prices",
    "market performance",

    # Demographics - Women (10)
    "women",
    "women employment",
    "women unemployment",
    "women in the workforce",
    "women labor force",
    "female employment",
    "female unemployment",
    "women's jobs",
    "working women",
    "gender employment gap",

    # Demographics - Other (15)
    "men employment",
    "men unemployment",
    "black unemployment",
    "african american unemployment",
    "hispanic unemployment",
    "latino unemployment",
    "white unemployment",
    "asian unemployment",
    "youth unemployment",
    "teen unemployment",
    "older workers",
    "veterans employment",
    "disability employment",
    "immigrant workers",
    "education and employment",

    # Trade & International (10)
    "trade",
    "trade deficit",
    "trade balance",
    "imports",
    "exports",
    "china trade",
    "tariffs",
    "dollar",
    "exchange rate",
    "current account",

    # Specific Sectors (15)
    "tech jobs",
    "technology employment",
    "manufacturing jobs",
    "construction jobs",
    "healthcare jobs",
    "retail jobs",
    "restaurant jobs",
    "hospitality jobs",
    "finance jobs",
    "government jobs",
    "education jobs",
    "energy sector",
    "auto industry",
    "auto sales",
    "small business",

    # Comparisons & Specific (5)
    "compare inflation and wages",
    "jobs vs inflation",
    "pre-covid comparison",
    "since the pandemic",
    "historical comparison",
]

PLANNER_PROMPT = """You are an expert economist creating a query plan for a FRED economic data dashboard.

Given the user query below, determine the BEST 1-4 FRED series to display. Be precise and use real FRED series IDs.

## KNOWN SERIES (use these when applicable):

### Employment
- PAYEMS = Total nonfarm payrolls
- UNRATE = Unemployment rate (U-3)
- LNS12300060 = Prime-age (25-54) employment-population ratio
- LNS11300000 = Labor force participation rate
- CES0500000003 = Average hourly earnings
- JTSJOL = Job openings
- ICSA = Initial jobless claims
- CCSA = Continuing claims

### Demographics
- LNS14000002 = Women's unemployment rate
- LNS12300062 = Prime-age women's employment ratio
- LNS11300002 = Women's labor force participation
- LNS14000001 = Men's unemployment rate
- LNS14000006 = Black unemployment rate
- LNS14000009 = Hispanic unemployment rate

### Inflation
- CPIAUCSL = CPI (show as YoY)
- CPILFESL = Core CPI (show as YoY)
- PCEPILFE = Core PCE (show as YoY)
- CUSR0000SAH1 = Shelter CPI
- GASREGW = Gas prices

### GDP & Output
- GDPC1 = Real GDP
- A191RL1Q225SBEA = Real GDP growth rate
- INDPRO = Industrial production

### Interest Rates
- FEDFUNDS = Fed funds rate
- DGS10 = 10-year Treasury
- DGS2 = 2-year Treasury
- T10Y2Y = Yield curve spread
- MORTGAGE30US = 30-year mortgage rate

### Housing
- CSUSHPINSA = Case-Shiller home prices
- HOUST = Housing starts
- EXHOSLUSM495S = Existing home sales

### Consumer
- RSXFS = Retail sales
- UMCSENT = Consumer sentiment
- PSAVERT = Personal savings rate

### Stocks & Trade
- SP500 = S&P 500
- BOPGSTB = Trade balance
- DCOILWTICO = Oil prices

## RULES:
1. For demographic questions (women, men, race), ONLY use demographic-specific series, never PAYEMS or UNRATE
2. For "how is the economy" type questions, use GDP growth + unemployment + inflation
3. For inflation, default to showing YoY transformation
4. Keep it simple: 1-2 series for simple questions, 3-4 max for complex ones
5. Only set combine_chart=true when ALL of these are true:
   - Series share the same units (e.g., both are rates, both are indexes)
   - Scales are comparable (e.g., both 0-10%, not one 0-5% and another 0-100%)
   - Visual comparison adds insight (comparing them on one chart tells a story)
   Otherwise use separate charts (combine_chart=false).

Return JSON only:
{
  "series": ["SERIES1", "SERIES2"],
  "show_yoy": false,
  "combine_chart": false,
  "explanation": "Brief explanation"
}

USER QUERY: """


def call_claude(prompt: str) -> dict:
    """Call Claude to generate a query plan."""
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
            # Extract JSON from response
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            return json.loads(content.strip())
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def main():
    print("=" * 60)
    print("GENERATING QUERY PLANS FOR COMMON ECONOMIC PROMPTS")
    print("=" * 60)
    print(f"\nTotal prompts to process: {len(COMMON_PROMPTS)}")
    print("\nThis will take a while. Output will be saved to query_plans.py\n")

    plans = {}
    errors = []

    for i, prompt in enumerate(COMMON_PROMPTS):
        print(f"[{i+1}/{len(COMMON_PROMPTS)}] Processing: '{prompt}'")

        result = call_claude(PLANNER_PROMPT + prompt)

        if result:
            plans[prompt] = {
                'series': result.get('series', []),
                'show_yoy': result.get('show_yoy', False),
                'combine_chart': result.get('combine_chart', False),
            }
            print(f"  -> {result.get('series', [])}")
        else:
            errors.append(prompt)
            print(f"  -> FAILED")

        # Rate limiting - be nice to the API
        time.sleep(0.5)

    # Save results
    output_file = '/Users/josh/Desktop/econstats/query_plans.py'
    with open(output_file, 'w') as f:
        f.write('"""Auto-generated query plans for common economic prompts."""\n\n')
        f.write('QUERY_PLANS = ')
        f.write(json.dumps(plans, indent=2))
        f.write('\n')

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    print(f"\nSuccessfully generated: {len(plans)} plans")
    print(f"Errors: {len(errors)}")
    if errors:
        print(f"Failed prompts: {errors[:10]}...")
    print(f"\nOutput saved to: {output_file}")


if __name__ == "__main__":
    main()
