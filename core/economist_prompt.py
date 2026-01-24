"""
Structured prompt templates for economic analysis.

This module provides prompt templates that guide LLMs to think like credible
economists (Jason Furman, Claudia Sahm style) when analyzing economic questions.

The prompts enforce a disciplined analytical framework:
1. Frame the question properly
2. Map the causal chain
3. Provide historical context
4. Acknowledge conflicting signals
5. Look forward with probabilistic thinking

Usage:
    from core.economist_prompt import build_economist_prompt, ANALYSIS_TEMPLATES

    prompt = build_economist_prompt(
        query="Is inflation coming down?",
        data_context={"cpi_yoy": 2.9, "core_pce": 2.7, ...}
    )
"""

from typing import Dict, Any, Optional


# =============================================================================
# CORE ECONOMIST PROMPT TEMPLATE
# =============================================================================

ECONOMIST_PROMPT_TEMPLATE = """You are a credible economic analyst with deep expertise in macroeconomics and policy.
Think like Jason Furman (Harvard, former CEA Chair) or Claudia Sahm (Fed economist, Sahm Rule creator).

Your analysis must be rigorous, evidence-based, and intellectually honest about uncertainty.

## USER QUESTION
{query}

## CURRENT DATA CONTEXT
{data_context_formatted}

---

Structure your analysis using these five sections:

## 1. FRAME THE QUESTION

First, clarify exactly what the user is trying to understand:
- **Core question**: What is the fundamental economic question being asked?
- **Levels vs changes vs direction**: Are they asking about the current level, the rate of change, or where things are heading?
- **Time horizon**: Near-term (next few months), medium-term (1-2 years), or longer-term structural?
- **Implicit assumptions**: What beliefs or concerns might underlie this question?

Be precise. "Is inflation high?" is different from "Is inflation falling?" is different from "Will inflation hit 2%?"

## 2. CAUSAL CHAIN

Map out the economic logic:
- **Primary drivers**: What are the 2-3 main forces driving the relevant economic variable?
- **Transmission mechanisms**: How do these forces actually affect the outcome? (e.g., higher rates -> reduced borrowing -> slower spending -> lower inflation)
- **Typical lag structure**: How long do these mechanisms typically take to work through the economy?
  - Monetary policy: 12-18 months for full effect
  - Fiscal policy: 3-12 months depending on type
  - Labor market: 6-12 months lagged indicator
  - Inflation expectations: Can be immediate or persistent

## 3. HISTORICAL CONTEXT

Ground the analysis in evidence:
- **Similar past conditions**: When have we seen comparable economic conditions? (Be specific about dates and metrics)
- **What happened next**: What was the outcome in those historical episodes?
- **Why this time might differ**: What structural or policy differences exist today vs. historical precedent?
- **Base rates**: What do the historical base rates tell us about likely outcomes?

Avoid recency bias. Consider multiple historical analogies, not just the most recent.

## 4. CONFLICTING SIGNALS

Acknowledge complexity and uncertainty:
- **Data supporting consensus**: What evidence supports the mainstream view?
- **Data contradicting consensus**: What evidence cuts against it?
- **How to weight them**: Why might one set of signals be more informative than another?
- **Known unknowns**: What key uncertainties could swing the outcome?

Good economists update their priors. Show how different data points should update our beliefs.

## 5. FORWARD LOOK

Provide actionable forward guidance:
- **Key variables to watch**: What 2-3 data releases or events will be most informative going forward?
- **Base case scenario**: What is the most likely outcome, with approximate probability?
- **Upside risks**: What could make things turn out better than expected?
- **Downside risks**: What could make things turn out worse?
- **Fed's likely thinking**: How is the Fed probably interpreting current conditions?

Be specific about signposts that would cause you to update your view.

---

Remember:
- Acknowledge uncertainty; don't pretend to know more than the data supports
- Distinguish between what we know, what we think, and what we're guessing
- Avoid partisan framing; focus on economic fundamentals
- If the data is genuinely mixed, say so clearly
"""


# =============================================================================
# ANALYSIS TEMPLATES FOR COMMON QUERY TYPES
# =============================================================================

ANALYSIS_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "inflation": {
        "description": "Analysis template for inflation-related questions",
        "key_series": ["CPIAUCSL", "PCEPILFE", "CPILFESL", "T5YIE", "MICH"],
        "frame_guidance": """
Focus on:
- Headline vs core (which matters more depends on time horizon)
- Goods vs services decomposition (services are stickier)
- Shelter's outsized CPI weight and its lag (12+ months behind market rents)
- Inflation expectations (breakevens, surveys) as forward indicator
""",
        "causal_chain_guidance": """
Key transmission mechanisms:
- Demand-pull: Strong spending -> businesses raise prices -> inflation
- Cost-push: Input costs (oil, wages) -> passed through to consumers
- Expectations: Expected inflation -> wage demands -> actual inflation
- Monetary policy works with 12-18 month lag through demand channel
""",
        "historical_context_guidance": """
Relevant historical episodes:
- 1970s: Supply shocks + accommodative policy = entrenched inflation
- 1980s Volcker: Aggressive tightening broke inflation (with recession cost)
- 2021-2022: Supply chain + demand surge = highest inflation since 1980s
- 2023-2024: Disinflation without recession (soft landing narrative)
""",
        "forward_look_guidance": """
Key indicators to watch:
- Core services ex-housing (supercore) - Fed's focus area
- Shelter CPI trajectory (lagging indicator of past rents)
- Wage growth vs productivity
- Inflation expectations surveys
- Fed communications on "last mile" of disinflation
"""
    },

    "jobs": {
        "description": "Analysis template for employment/labor market questions",
        "key_series": ["PAYEMS", "UNRATE", "JTSJOL", "ICSA", "CES0500000003"],
        "frame_guidance": """
Focus on:
- Job GAINS (payroll changes) vs unemployment RATE (different signals)
- Labor demand (openings) vs labor supply (participation)
- Wages: nominal growth vs real (inflation-adjusted)
- Breadth: Is job growth broad-based or concentrated?
""",
        "causal_chain_guidance": """
Key transmission mechanisms:
- Hiring flows: Openings -> hires -> employment gains
- Separation flows: Quits (voluntary) vs layoffs (involuntary)
- Labor supply: Demographics, participation decisions, immigration
- Wage Phillips curve: Tight labor market -> wage pressure -> inflation
""",
        "historical_context_guidance": """
Relevant historical episodes:
- 2019: 3.5% unemployment without wage spiral (labor supply response)
- 2020: Fastest job losses ever, then fastest recovery
- 2022-2023: "Great Resignation" and labor shortage
- Sahm Rule: 0.5pp rise in unemployment from low signals recession
""",
        "forward_look_guidance": """
Key indicators to watch:
- Initial claims (most timely labor market indicator)
- Job openings/unemployed ratio (labor market tightness)
- Prime-age employment-population ratio (better than headline unemployment)
- Quits rate (worker confidence signal)
- Temporary help employment (leading indicator)
"""
    },

    "recession": {
        "description": "Analysis template for recession risk questions",
        "key_series": ["T10Y2Y", "UNRATE", "SAHMREALTIME", "UMCSENT", "ICSA"],
        "frame_guidance": """
Focus on:
- NBER definition: Significant decline in activity, broad-based, lasting
- Leading indicators vs coincident vs lagging
- Probability assessment, not binary prediction
- Timeframe: Near-term (6mo) vs medium-term (12-24mo) risks
""",
        "causal_chain_guidance": """
Typical recession mechanics:
- Yield curve inversion -> credit tightening -> reduced investment -> layoffs
- Negative shock (oil, financial crisis) -> uncertainty -> spending pullback
- Monetary overtightening -> demand destruction -> employment contraction
- Average lead time: Yield curve inverts 12-18 months before recession
""",
        "historical_context_guidance": """
Relevant historical episodes:
- 2008-09: Financial crisis, worst since Depression
- 2020: Pandemic shock, shortest recession on record (2 months)
- 2022-23: Yield curve inversion but no recession (yet?)
- False positives: 1966, 1998 yield curve inversions without recession
""",
        "forward_look_guidance": """
Key indicators to watch:
- Sahm Rule (3-month avg unemployment rise of 0.5pp+ from low)
- Initial claims trend (uptick of 50K+ is warning sign)
- Credit conditions (Senior Loan Officer Survey)
- Consumer spending momentum
- Corporate earnings guidance
"""
    },

    "fed_policy": {
        "description": "Analysis template for Federal Reserve policy questions",
        "key_series": ["FEDFUNDS", "DGS2", "DGS10", "PCEPILFE", "UNRATE"],
        "frame_guidance": """
Focus on:
- Dual mandate: Maximum employment AND price stability
- Fed's reaction function: What data moves them?
- Terminal rate expectations vs dot plot
- Pace and magnitude: How fast, how far?
""",
        "causal_chain_guidance": """
Monetary policy transmission:
- Short rates -> financial conditions -> borrowing costs -> spending
- Expectations channel: Forward guidance affects longer rates
- Wealth effect: Asset prices -> consumer confidence -> spending
- Time lags: 12-18 months for full effect on real economy
""",
        "historical_context_guidance": """
Relevant historical episodes:
- 2022-23: Fastest hiking cycle in 40 years (0 to 5.25%+)
- 2019: "Insurance cuts" (3 cuts without recession)
- 2013: Taper tantrum (communication lesson)
- Volcker 1980s: Showed Fed CAN break inflation (at cost)
""",
        "forward_look_guidance": """
Key indicators to watch:
- Core PCE trajectory (Fed's preferred measure)
- Labor market conditions (employment side of mandate)
- Inflation expectations (risk of unanchoring)
- Financial conditions (doing the Fed's work or not)
- FOMC communications, dot plot, SEP projections
"""
    },

    "gdp": {
        "description": "Analysis template for GDP/economic growth questions",
        "key_series": ["GDPC1", "A191RL1Q225SBEA", "A191RO1Q156NBEA", "GDPNOW"],
        "frame_guidance": """
Focus on:
- YoY growth (smoother trend) vs quarterly annualized (timely but noisy)
- Composition: Consumption, investment, government, net exports
- Nominal vs real (inflation-adjusted)
- Output gap: Above or below potential?
""",
        "causal_chain_guidance": """
GDP growth drivers:
- Consumer spending (70% of GDP): Income growth, confidence, wealth
- Business investment: Rates, profits, confidence, capacity utilization
- Government: Fiscal policy stance (stimulus vs austerity)
- Net exports: Dollar strength, global demand, supply chains
""",
        "historical_context_guidance": """
Relevant historical episodes:
- Post-2008: Slow recovery (~2% trend growth)
- 2020: -31% Q2, then +33% Q3 (unprecedented volatility)
- 2021-22: Rapid recovery, above-trend growth
- Long-run potential: ~1.8-2.0% real GDP growth
""",
        "forward_look_guidance": """
Key indicators to watch:
- GDPNow/Nowcasts (real-time tracking, but volatile)
- Retail sales (consumer spending proxy)
- Industrial production (goods economy)
- ISM surveys (leading indicators)
- Monthly jobs report (income -> spending -> GDP)
"""
    }
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _format_data_context(data_context: Dict[str, Any]) -> str:
    """
    Format data context dictionary into readable string for prompt injection.

    Args:
        data_context: Dictionary of current economic data values

    Returns:
        Formatted string representation of the data
    """
    if not data_context:
        return "No specific data context provided. Use your knowledge of recent economic conditions."

    lines = []
    for key, value in data_context.items():
        # Format the key for readability
        readable_key = key.replace("_", " ").title()

        # Format the value appropriately
        if isinstance(value, float):
            if abs(value) < 10:
                formatted_value = f"{value:.2f}"
            else:
                formatted_value = f"{value:,.1f}"
        elif isinstance(value, dict):
            # Handle nested data (e.g., series with date and value)
            formatted_value = ", ".join(f"{k}: {v}" for k, v in value.items())
        elif isinstance(value, list):
            # Handle list of values (e.g., recent observations)
            formatted_value = ", ".join(str(v) for v in value[:5])
            if len(value) > 5:
                formatted_value += f"... ({len(value)} total)"
        else:
            formatted_value = str(value)

        lines.append(f"- {readable_key}: {formatted_value}")

    return "\n".join(lines)


def _detect_query_type(query: str) -> Optional[str]:
    """
    Detect the type of economic query to select appropriate template.

    Args:
        query: User's economic question

    Returns:
        Query type key (inflation, jobs, recession, fed_policy, gdp) or None
    """
    query_lower = query.lower()

    # Keyword patterns for each query type
    # More specific terms should be listed first for proper matching
    patterns = {
        "inflation": [
            "inflation", "cpi", "pce", "price level", "price index",
            "cost of living", "deflation", "disinflation", "rising prices"
        ],
        "jobs": [
            "job", "employment", "unemployment", "labor", "payroll",
            "hiring", "layoff", "workforce", "wage", "worker"
        ],
        "recession": [
            "recession", "downturn", "contraction", "economic crisis",
            "hard landing", "soft landing", "slowdown"
        ],
        "fed_policy": [
            "fed ", "federal reserve", "interest rate", "rate cut",
            "rate hike", "monetary policy", "fomc", "powell", "tightening",
            "rate decision", "basis points"
        ],
        "gdp": [
            "gdp", "economic growth", "output", "production",
            "economic activity", "expansion", "growing", "growth rate",
            "how fast", "economy grow"
        ]
    }

    # Score each type based on keyword matches
    scores = {}
    for query_type, keywords in patterns.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[query_type] = score

    if not scores:
        return None

    # Return the type with highest score
    return max(scores, key=scores.get)


def _get_template_guidance(query_type: str) -> str:
    """
    Get template-specific guidance for a query type.

    Args:
        query_type: One of the ANALYSIS_TEMPLATES keys

    Returns:
        Formatted guidance string to append to prompt
    """
    if query_type not in ANALYSIS_TEMPLATES:
        return ""

    template = ANALYSIS_TEMPLATES[query_type]

    guidance_parts = [
        f"\n## ANALYSIS GUIDANCE FOR {query_type.upper().replace('_', ' ')} QUESTIONS\n"
    ]

    if "frame_guidance" in template:
        guidance_parts.append(f"### Framing Considerations\n{template['frame_guidance']}")

    if "causal_chain_guidance" in template:
        guidance_parts.append(f"### Causal Chain Notes\n{template['causal_chain_guidance']}")

    if "historical_context_guidance" in template:
        guidance_parts.append(f"### Historical Context Notes\n{template['historical_context_guidance']}")

    if "forward_look_guidance" in template:
        guidance_parts.append(f"### Forward Look Notes\n{template['forward_look_guidance']}")

    return "\n".join(guidance_parts)


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def build_economist_prompt(
    query: str,
    data_context: Dict[str, Any],
    include_template_guidance: bool = True
) -> str:
    """
    Build a structured economist prompt for LLM analysis.

    This function constructs a prompt that guides the LLM to think like a
    credible economist, enforcing a disciplined analytical framework.

    Args:
        query: The user's economic question
        data_context: Dictionary of current economic data values. Can include:
            - Series values: {"cpi_yoy": 2.9, "unemployment": 4.1}
            - Nested data: {"gdp": {"value": 2.8, "date": "2024-Q3"}}
            - Recent observations: {"payrolls": [256000, 180000, 165000]}
        include_template_guidance: Whether to include query-type specific
            guidance from ANALYSIS_TEMPLATES (default: True)

    Returns:
        Complete prompt string ready for LLM input

    Example:
        >>> prompt = build_economist_prompt(
        ...     query="Is inflation coming down?",
        ...     data_context={
        ...         "cpi_yoy": 2.9,
        ...         "core_pce": 2.7,
        ...         "shelter_cpi": 5.2,
        ...         "fed_funds": 5.25
        ...     }
        ... )
        >>> # prompt now contains the full economist analysis template
    """
    # Format the data context
    data_context_formatted = _format_data_context(data_context)

    # Build the base prompt
    prompt = ECONOMIST_PROMPT_TEMPLATE.format(
        query=query,
        data_context_formatted=data_context_formatted
    )

    # Optionally add query-type specific guidance
    if include_template_guidance:
        query_type = _detect_query_type(query)
        if query_type:
            guidance = _get_template_guidance(query_type)
            prompt += guidance

    return prompt


def get_analysis_template(query_type: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the analysis template for a specific query type.

    Args:
        query_type: One of "inflation", "jobs", "recession", "fed_policy", "gdp"

    Returns:
        Template dictionary or None if not found
    """
    return ANALYSIS_TEMPLATES.get(query_type)


def list_template_types() -> list:
    """
    List all available analysis template types.

    Returns:
        List of template type keys
    """
    return list(ANALYSIS_TEMPLATES.keys())


# =============================================================================
# TEST/DEMO
# =============================================================================

if __name__ == "__main__":
    # Test the prompt builder with sample queries

    print("=" * 80)
    print("ECONOMIST PROMPT BUILDER - TEST")
    print("=" * 80)

    # Test 1: Inflation query with data context
    print("\n--- Test 1: Inflation Query ---\n")

    inflation_context = {
        "cpi_yoy": 2.9,
        "core_pce": 2.7,
        "shelter_cpi_yoy": 5.2,
        "fed_funds_rate": 5.25,
        "breakeven_5y": 2.3,
        "recent_cpi_readings": [2.9, 3.0, 3.2, 3.4]
    }

    inflation_prompt = build_economist_prompt(
        query="Is inflation coming down? Will the Fed cut rates soon?",
        data_context=inflation_context
    )

    print(f"Prompt length: {len(inflation_prompt)} characters")
    print("\nFirst 500 characters of prompt:")
    print(inflation_prompt[:500])
    print("...")

    # Test 2: Jobs query
    print("\n--- Test 2: Jobs Query ---\n")

    jobs_context = {
        "unemployment_rate": 4.1,
        "payroll_change": 256000,
        "job_openings": 8.1,  # millions
        "initial_claims": 215000,
        "wage_growth_yoy": 4.2
    }

    jobs_prompt = build_economist_prompt(
        query="How is the job market holding up?",
        data_context=jobs_context
    )

    print(f"Prompt length: {len(jobs_prompt)} characters")
    detected_type = _detect_query_type("How is the job market holding up?")
    print(f"Detected query type: {detected_type}")

    # Test 3: Query type detection
    print("\n--- Test 3: Query Type Detection ---\n")

    test_queries = [
        "Is inflation coming down?",
        "What's happening with the labor market?",
        "Are we heading into a recession?",
        "When will the Fed cut rates?",
        "How fast is the economy growing?",
        "What's the outlook for housing prices?",  # No specific template
    ]

    for q in test_queries:
        query_type = _detect_query_type(q)
        print(f"  '{q}' -> {query_type or 'no specific template'}")

    # Test 4: List templates
    print("\n--- Test 4: Available Templates ---\n")

    for template_type in list_template_types():
        template = get_analysis_template(template_type)
        print(f"  {template_type}:")
        print(f"    Description: {template['description']}")
        print(f"    Key series: {template['key_series']}")

    # Test 5: Empty context
    print("\n--- Test 5: Empty Data Context ---\n")

    empty_prompt = build_economist_prompt(
        query="What's the economic outlook?",
        data_context={}
    )

    print("Empty context message in prompt:")
    print("  'No specific data context provided...' present:",
          "No specific data context provided" in empty_prompt)

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)
