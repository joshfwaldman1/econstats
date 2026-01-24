"""
Summary Generator for EconStats.

This module generates analytical (not just descriptive) economic summaries.
The key insight: good economic analysis focuses on the "why" and "what's next",
not just the "what".

Bad summary: "CPI is 2.7%, down from 9% peak"
Good summary: "Inflation has fallen sharply but the last mile to 2% is proving
              difficult. Shelter (4.6%) is the main holdout - it lags rate hikes
              by 18-24 months, so relief should come by mid-2025. Goods are
              deflating (-1.2%), helping offset sticky services."

Key principles:
1. Lead with the insight, not the number
2. Explain causation and lags (Fed policy takes 12-18 months to hit inflation)
3. Note conflicting signals when they exist
4. End with a forward-looking statement
"""

import json
import os
import re
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request

# API Keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


# =============================================================================
# ECONOMIC FRAMEWORKS
# These capture how economists actually think about causal relationships
# =============================================================================

ECONOMIC_FRAMEWORKS = {
    "inflation": {
        "causal_chain": [
            "Fed raises rates -> mortgage rates rise -> housing demand falls -> shelter inflation lags 18-24 months",
            "Strong labor market -> wage growth -> services inflation sticky",
            "Supply chain normalization -> goods deflation (often negative now)",
            "Oil prices volatile -> energy component swings headline CPI",
        ],
        "key_lags": {
            "shelter": "18-24 months after rate hikes (new rents already falling, CPI rent lags)",
            "wages": "6-12 months after labor market loosening",
            "goods": "Near-term (supply chain effects immediate)",
        },
        "signals_to_watch": [
            "Core services ex-housing (supercore) - Fed's focus",
            "New tenant rent index vs CPI rent (leading indicator)",
            "Wage growth vs productivity (unit labor costs)",
        ],
        "fed_reaction": "Fed targets 2% PCE inflation; core PCE > 2.5% keeps them hawkish",
    },
    "labor_market": {
        "causal_chain": [
            "Rate hikes -> business investment falls -> hiring slows -> openings drop first",
            "Openings drop -> quits fall (workers less confident) -> wage growth moderates",
            "Continued weakness -> layoffs rise -> unemployment increases (lagging indicator)",
            "Sahm Rule: 0.5pp rise in 3-month avg unemployment = recession signal",
        ],
        "key_lags": {
            "job_openings": "Leading indicator (first to fall in slowdown)",
            "quits_rate": "Leading indicator (workers quit less when uncertain)",
            "unemployment": "Lagging indicator (rises late in cycle)",
            "initial_claims": "Most timely weekly signal of layoffs",
        },
        "signals_to_watch": [
            "Job openings per unemployed worker (was 2.0 at peak, now falling)",
            "Quits rate below 2.3% signals weak worker confidence",
            "3-month payroll avg more stable than single month",
        ],
        "current_dynamic": "Labor market normalizing from overheated 2022-2023 levels",
    },
    "recession": {
        "causal_chain": [
            "Yield curve inverts -> banks tighten lending -> business investment falls",
            "Consumer spending slows -> production cuts -> layoffs begin",
            "Unemployment rises 0.5pp from lows -> Sahm Rule triggers -> recession confirmed",
        ],
        "key_signals": {
            "yield_curve": "Inverted curve predicts recession 12-18 months ahead (has inverted)",
            "sahm_rule": "0.5pp rise in 3-mo avg unemployment from 12-mo low",
            "leading_indicators": "LEI declining 6+ months often precedes recession",
            "consumer_sentiment": "Sharp drops often precede spending pullback",
        },
        "conflicting_signals": [
            "Yield curve inverted (bearish) but labor market still strong (bullish)",
            "Consumer sentiment weak but spending solid",
            "Manufacturing contracting but services expanding",
        ],
    },
    "fed_policy": {
        "causal_chain": [
            "Inflation above target -> Fed raises rates -> financial conditions tighten",
            "Labor market weakens -> wage growth slows -> services inflation moderates",
            "Inflation approaches 2% -> Fed pauses then cuts -> economy rebounds",
        ],
        "reaction_function": {
            "hiking": "Core PCE > 2.5% and unemployment < 4.5% = rates higher for longer",
            "cutting": "Core PCE trending to 2%, unemployment rising = rate cuts begin",
            "neutral_rate": "R* estimated at 2.5-3.0% - terminal rate above this is restrictive",
        },
        "market_expectations": "Fed funds futures show market's rate path expectations",
        "dot_plot": "FOMC median projections - but markets often disagree",
    },
    "housing": {
        "causal_chain": [
            "Fed hikes -> mortgage rates spike -> affordability collapses",
            "Existing owners locked in at low rates -> supply shortage -> prices sticky",
            "New construction responds to high prices -> eventual supply relief",
        ],
        "key_dynamics": {
            "lock_in_effect": "Owners with 3% mortgages won't sell to buy at 7%",
            "affordability": "Payment-to-income ratio at multi-decade highs",
            "rent_vs_buy": "Renting now often cheaper than buying (unusual)",
        },
    },
    "gdp_growth": {
        "causal_chain": [
            "Consumer spending (70% of GDP) drives growth",
            "Business investment responds to demand outlook and rates",
            "Government spending provides fiscal support",
            "Net exports typically small drag for US",
        ],
        "key_dynamics": {
            "consumer": "Labor income + wealth effects + savings drawdown",
            "business_investment": "Sensitive to rates and profit expectations",
            "inventories": "Volatile quarter-to-quarter, often mean-reverts",
        },
        "trend_growth": "US potential growth ~2% annually; above = expansion, below = slowdown",
    },
}


# =============================================================================
# QUERY-SPECIFIC PROMPT TEMPLATES
# Different topics need different analytical focus
# =============================================================================

TOPIC_PROMPTS = {
    "inflation": """Analyze inflation with focus on:
- COMPOSITION: Break down core vs headline, goods vs services, shelter vs everything else
- SHELTER LAG: CPI rent lags new tenant rents by 12-18 months - is relief coming?
- GOODS DEFLATION: Are goods prices falling? This helps offset sticky services
- FED REACTION: With this reading, what does the Fed do? Is 2% within reach?
- FORWARD: When does inflation hit 2%? What could derail the path?

Key insight: The "last mile" to 2% inflation is the hardest. Explain why.""",

    "jobs": """Analyze the labor market with focus on:
- LEADING vs LAGGING: Job openings and quits are LEADING (fall first). Unemployment is LAGGING (rises last).
- NORMALIZATION vs WEAKENING: Is this a healthy return from overheated 2022 or concerning deterioration?
- WAGE-PRICE SPIRAL: Is wage growth (compare to productivity) feeding into inflation?
- FLOW RATES: Hiring rate, quits rate, layoff rate tell different stories
- FORWARD: What does this mean for Fed policy? Is a soft landing still achievable?

Key insight: The labor market tells different stories depending on which metrics you prioritize.""",

    "recession": """Analyze recession risk with focus on:
- SIGNAL CONFLICTS: Some indicators say recession (yield curve, LEI), others say expansion (jobs, spending)
- HISTORICAL PATTERNS: How does current data compare to pre-recession periods?
- SAHM RULE: Current reading? How close to 0.5pp trigger?
- PROBABILITY: What's your probability estimate for recession in next 12 months?
- FORWARD: What would need to happen for recession to become likely or unlikely?

Key insight: Recession signals are mixed - explain the case for and against.""",

    "fed": """Analyze Fed policy with focus on:
- REACTION FUNCTION: Given inflation and jobs data, what's the Fed's likely move?
- DOT PLOT vs MARKETS: Where does the Fed see rates going vs market expectations?
- TERMINAL RATE: How high do rates need to go? When can cuts begin?
- FINANCIAL CONDITIONS: Are current rates restrictive enough?
- FORWARD: What data would change the Fed's path?

Key insight: The Fed data-dependent - explain what data would matter most.""",

    "housing": """Analyze housing with focus on:
- AFFORDABILITY: How do mortgage rates + prices affect buying power?
- LOCK-IN EFFECT: Owners with low rates won't sell - supply implications
- RENT vs BUY: Which makes more sense at current prices/rates?
- NEW CONSTRUCTION: Is supply coming to ease prices?
- FORWARD: What would it take for housing to become affordable again?

Key insight: The housing market is frozen by rate lock-in - explain the dynamics.""",

    "gdp": """Analyze economic growth with focus on:
- COMPONENTS: Consumer spending, business investment, government, net exports
- SUSTAINABILITY: Is growth driven by sustainable factors or one-time effects?
- TREND vs CYCLE: Is the economy above or below potential? Output gap?
- FORWARD: What's the growth outlook for the next 2-4 quarters?

Key insight: GDP is backward-looking - explain what it means for the future.""",
}


# Base prompt template that works for any topic
SUMMARY_PROMPT_TEMPLATE = """You are a senior economist writing a market briefing. Your job is to explain
not just WHAT the data shows, but WHY it's happening and WHAT IT MEANS.

USER QUESTION: {query}

DATA:
{data_json}

{topic_guidance}

{framework_context}

{news_context}

Write 2-3 sentences that are ANALYTICAL, not descriptive.

FORMAT RULES:
1. LEAD WITH THE INSIGHT, not the number
   BAD: "CPI rose to 2.7% in December"
   GOOD: "Inflation's last mile to 2% is proving sticky as shelter costs remain elevated"

2. EXPLAIN CAUSATION, not just correlation
   BAD: "Unemployment rose as hiring slowed"
   GOOD: "Employers are pulling back on hiring as higher rates dampen demand, pushing unemployment up"

3. NOTE CONFLICTING SIGNALS when they exist
   BAD: "The economy is slowing"
   GOOD: "Job openings are falling but hiring remains solid - a soft landing signature"

4. END WITH FORWARD-LOOKING STATEMENT
   BAD: "The Fed will monitor incoming data"
   GOOD: "If shelter inflation keeps falling at this pace, the Fed can cut rates by June"

5. BE SPECIFIC with numbers and dates
   BAD: "Inflation is coming down"
   GOOD: "Core PCE has fallen from 5.5% to 2.8% - another 0.8pp to reach the Fed's 2% target"

WRITE YOUR 2-3 SENTENCE ANALYTICAL SUMMARY NOW:"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def detect_topic(query: str, series_data: List[Dict]) -> str:
    """Detect the primary topic of a query for specialized prompts."""
    query_lower = query.lower()

    # Check for multi-word phrases FIRST (more specific matches)
    phrase_topics = {
        "housing": ["home price", "house price", "housing price", "real estate",
                    "mortgage rate", "housing market", "home value"],
        "inflation": ["food price", "gas price", "energy price", "price level"],
    }

    for topic, phrases in phrase_topics.items():
        if any(phrase in query_lower for phrase in phrases):
            return topic

    # Check query keywords (ordered by specificity - housing before inflation due to 'prices')
    topic_keywords = {
        "recession": ["recession", "slowdown", "downturn", "contraction", "soft landing"],
        "fed": ["fed", "federal reserve", "monetary policy", "fomc", "powell",
                "dot plot", "rate cut", "rate hike"],
        "housing": ["housing", "home", "mortgage", "real estate"],
        "jobs": ["job", "employment", "unemployment", "payroll", "hiring", "labor", "workers",
                 "layoff", "claims", "wage", "earnings"],
        "gdp": ["gdp", "growth", "output", "economy", "economic growth"],
        "inflation": ["inflation", "cpi", "pce", "prices", "deflation", "shelter", "rent"],
    }

    for topic, keywords in topic_keywords.items():
        if any(kw in query_lower for kw in keywords):
            return topic

    # Check series names as fallback
    if series_data:
        series_names = " ".join([s.get("name", "").lower() for s in series_data])
        for topic, keywords in topic_keywords.items():
            if any(kw in series_names for kw in keywords):
                return topic

    return "general"


def build_framework_context(topic: str) -> str:
    """Build context from economic frameworks for the given topic."""
    # Map topic names to framework names (they differ for some)
    topic_to_framework = {
        "jobs": "labor_market",
        "fed": "fed_policy",
        "gdp": "gdp_growth",
    }
    framework_key = topic_to_framework.get(topic, topic)

    if framework_key not in ECONOMIC_FRAMEWORKS:
        return ""

    framework = ECONOMIC_FRAMEWORKS[framework_key]
    context_parts = []

    if "causal_chain" in framework:
        context_parts.append("CAUSAL RELATIONSHIPS:")
        for chain in framework["causal_chain"]:
            context_parts.append(f"  - {chain}")

    if "key_lags" in framework:
        context_parts.append("\nKEY LAGS TO CONSIDER:")
        for indicator, lag in framework["key_lags"].items():
            context_parts.append(f"  - {indicator}: {lag}")

    if "signals_to_watch" in framework:
        context_parts.append("\nSIGNALS TO WATCH:")
        for signal in framework["signals_to_watch"]:
            context_parts.append(f"  - {signal}")

    return "\n".join(context_parts)


def format_series_data_for_prompt(series_data: List[Dict]) -> str:
    """Format series data for the prompt in a clean JSON format."""
    # Clean up the data for the prompt
    cleaned = []
    for s in series_data:
        item = {
            "name": s.get("name", s.get("series_id", "Unknown")),
            "latest_value": s.get("latest_value"),
            "latest_date": s.get("latest_date"),
        }
        if s.get("yoy_change") is not None:
            item["yoy_change"] = s["yoy_change"]
        if s.get("monthly_job_change") is not None:
            item["monthly_job_change"] = s["monthly_job_change"]
        if s.get("avg_monthly_change_3mo") is not None:
            item["avg_3mo"] = s["avg_monthly_change_3mo"]
        cleaned.append(item)

    return json.dumps(cleaned, indent=2)


# =============================================================================
# MAIN SUMMARY GENERATION FUNCTION
# =============================================================================

def generate_analytical_summary(
    query: str,
    data: List[Dict],
    context: Optional[Dict] = None
) -> str:
    """Generate an analytical (not just descriptive) economic summary.

    This function produces summaries that focus on causation, conflicting signals,
    and forward-looking implications rather than just stating what the data shows.

    Args:
        query: The user's original question
        data: List of dicts with series data. Each dict should have:
            - name: Series name
            - latest_value: Most recent value
            - latest_date: Date of latest value
            - yoy_change: (optional) Year-over-year change
            - unit: (optional) Unit of measurement
        context: Optional dict with additional context:
            - news_context: Recent news/events to incorporate
            - frameworks: Pre-built framework context to use
            - causal_chains: Specific causal chains to reference

    Returns:
        2-3 sentence analytical summary string

    Example:
        >>> data = [{"name": "CPI", "latest_value": 2.7, "yoy_change": -0.2}]
        >>> generate_analytical_summary("What's happening with inflation?", data)
        "Inflation has fallen sharply but the last mile to 2% is proving difficult..."
    """
    if not ANTHROPIC_API_KEY or not data:
        return ""

    context = context or {}

    # Detect topic for specialized prompt
    topic = detect_topic(query, data)

    # Build topic-specific guidance
    topic_guidance = TOPIC_PROMPTS.get(topic, "")
    if topic_guidance:
        topic_guidance = f"ANALYTICAL FOCUS:\n{topic_guidance}"

    # Build framework context
    framework_context = context.get("frameworks", "") or build_framework_context(topic)
    if framework_context:
        framework_context = f"ECONOMIC FRAMEWORK:\n{framework_context}"

    # News context
    news_context = context.get("news_context", "")
    if news_context:
        news_context = f"RECENT NEWS/CONTEXT:\n{news_context}"

    # Format data
    data_json = format_series_data_for_prompt(data)

    # Build the prompt
    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        query=query,
        data_json=data_json,
        topic_guidance=topic_guidance,
        framework_context=framework_context,
        news_context=news_context,
    )

    # Call Claude API
    url = 'https://api.anthropic.com/v1/messages'
    payload = {
        'model': 'claude-sonnet-4-20250514',
        'max_tokens': 400,  # Keep summaries concise
        'messages': [{'role': 'user', 'content': prompt}]
    }
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01'
    }

    try:
        req = Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
            summary = result['content'][0]['text'].strip()
            # Clean up any markdown or quotes
            summary = summary.strip('"\'')
            return summary
    except Exception as e:
        print(f"[SummaryGenerator] Error: {e}")
        return ""


# =============================================================================
# CONVENIENCE FUNCTIONS FOR SPECIFIC TOPICS
# =============================================================================

def generate_inflation_summary(data: List[Dict], news_context: str = "") -> str:
    """Generate inflation-focused analytical summary."""
    return generate_analytical_summary(
        query="What's happening with inflation?",
        data=data,
        context={
            "news_context": news_context,
            "frameworks": build_framework_context("inflation"),
        }
    )


def generate_jobs_summary(data: List[Dict], news_context: str = "") -> str:
    """Generate labor market-focused analytical summary."""
    return generate_analytical_summary(
        query="How is the labor market doing?",
        data=data,
        context={
            "news_context": news_context,
            "frameworks": build_framework_context("labor_market"),
        }
    )


def generate_recession_summary(data: List[Dict], news_context: str = "") -> str:
    """Generate recession risk-focused analytical summary."""
    return generate_analytical_summary(
        query="What is the recession risk?",
        data=data,
        context={
            "news_context": news_context,
            "frameworks": build_framework_context("recession"),
        }
    )


def generate_fed_summary(data: List[Dict], news_context: str = "") -> str:
    """Generate Fed policy-focused analytical summary."""
    return generate_analytical_summary(
        query="What will the Fed do?",
        data=data,
        context={
            "news_context": news_context,
            "frameworks": build_framework_context("fed_policy"),
        }
    )


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def _test_with_sample_data():
    """Test the summary generator with sample data."""

    # Sample inflation data
    inflation_data = [
        {
            "name": "Consumer Price Index (CPI)",
            "series_id": "CPIAUCSL",
            "latest_value": 2.7,
            "latest_date": "2024-12-01",
            "yoy_change": -0.2,
            "recent_5yr_min": 0.1,
            "recent_5yr_max": 9.1,
        },
        {
            "name": "Core CPI (ex food and energy)",
            "series_id": "CPILFESL",
            "latest_value": 3.2,
            "latest_date": "2024-12-01",
            "yoy_change": -0.1,
        },
        {
            "name": "Shelter CPI",
            "series_id": "CUSR0000SAH1",
            "latest_value": 4.6,
            "latest_date": "2024-12-01",
            "yoy_change": -0.8,
        },
    ]

    print("=" * 60)
    print("INFLATION SUMMARY TEST")
    print("=" * 60)
    print("\nInput data:")
    print(json.dumps(inflation_data, indent=2))
    print("\nGenerating summary...")

    summary = generate_analytical_summary(
        query="What's happening with inflation?",
        data=inflation_data,
    )
    print(f"\nSummary:\n{summary}")

    # Sample jobs data
    jobs_data = [
        {
            "name": "Unemployment Rate",
            "series_id": "UNRATE",
            "latest_value": 4.1,
            "latest_date": "2024-12-01",
            "yoy_change": 0.4,
        },
        {
            "name": "Total Nonfarm Payrolls",
            "series_id": "PAYEMS",
            "latest_value": 159000,
            "latest_date": "2024-12-01",
            "monthly_job_change": 227,
            "avg_monthly_change_3mo": 180,
            "avg_monthly_change_12mo": 186,
        },
        {
            "name": "Job Openings",
            "series_id": "JTSJOL",
            "latest_value": 8800,
            "latest_date": "2024-11-01",
            "yoy_change": -900,
        },
    ]

    print("\n" + "=" * 60)
    print("JOBS SUMMARY TEST")
    print("=" * 60)
    print("\nInput data:")
    print(json.dumps(jobs_data, indent=2))
    print("\nGenerating summary...")

    summary = generate_analytical_summary(
        query="How is the job market doing?",
        data=jobs_data,
    )
    print(f"\nSummary:\n{summary}")


if __name__ == "__main__":
    _test_with_sample_data()
