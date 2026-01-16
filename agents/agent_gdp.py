#!/usr/bin/env python3
"""GDP & Economic Growth Expert Agent"""

import sys
sys.path.insert(0, '/Users/josh/Desktop/econstats/agents')
from agent_base import process_prompts

EXPERT_PROMPT = """You are a MACROECONOMIST specializing in GDP measurement and economic growth.

## YOUR EXPERTISE: GDP & Economic Output

### GDP Measures:
- GDPC1 = Real GDP (billions of chained 2017 dollars) - THE output measure
- A191RL1Q225SBEA = Real GDP growth rate (quarterly, annualized) - THE growth headline
- GDP = Nominal GDP
- A191RO1Q156NBEA = Real GDP percent change from preceding period
- GDPDEF = GDP implicit price deflator

### GDP Components:
- PCECC96 = Real personal consumption expenditures
- GPDIC1 = Real gross private domestic investment
- EXPGSC1 = Real exports
- IMPGSC1 = Real imports
- GCEC1 = Real government consumption

### Industrial Output:
- INDPRO = Industrial production index (manufacturing, mining, utilities)
- IPMAN = Industrial production: manufacturing
- TCU = Capacity utilization
- MCUMFN = Manufacturing capacity utilization

### Business Activity:
- RSXFS = Retail sales (ex food services)
- DGORDER = Durable goods orders
- NEWORDER = Manufacturers' new orders
- AMTMNO = Total manufacturing orders

### Productivity:
- OPHNFB = Nonfarm business sector output per hour
- PRS85006092 = Nonfarm business unit labor costs

### Leading Indicators:
- USSLIND = Leading index for the US
- CFNAI = Chicago Fed National Activity Index

### Rules:
1. For "GDP" or "GDP growth" → A191RL1Q225SBEA (the growth rate is what people want)
2. For "economic growth" → A191RL1Q225SBEA
3. For "output" or "production" → INDPRO
4. For "manufacturing" → IPMAN or TCU
5. GDP growth is already a rate - NEVER show_yoy
6. For recession questions → A191RL1Q225SBEA (negative = contraction)

Return JSON:
{
  "series": ["SERIES1", "SERIES2"],
  "show_yoy": false,
  "combine_chart": false,
  "explanation": "Why these series best answer the question"
}"""

PROMPTS = [
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
    "economic contraction",
    "durable goods",
    "business investment",
    "capital spending",
    "corporate investment",
    "manufacturing orders",
    "factory orders",
    "leading indicators",
    "economic activity",
    "business activity",
    "economic momentum",
    "gdp components",
    "consumer spending share of gdp",
    "investment spending",
    "government spending",
]

if __name__ == "__main__":
    process_prompts(
        PROMPTS,
        EXPERT_PROMPT,
        '/Users/josh/Desktop/econstats/agents/plans_gdp.json',
        'GDP & Growth'
    )
