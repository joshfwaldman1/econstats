"""
Premium Economist Analysis Module

This module generates economist-quality analysis by:
1. Looking at data values and trends across multiple indicators
2. Applying economic reasoning to interpret what they mean
3. Connecting multiple indicators into a coherent narrative
4. Highlighting key risks or opportunities

This is what differentiates EconStats from raw data tools - we don't just show
numbers, we explain what they mean and why they matter.

Example output:
    "The labor market remains solid with unemployment at 4.1% and strong job
    gains of 200K. However, inflation at 3.2% remains above the Fed's 2% target,
    suggesting monetary policy will stay restrictive. GDP growth of 2.5% indicates
    resilient expansion despite higher rates. Key watch: whether labor market
    strength can persist as restrictive policy continues."
"""

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from urllib.request import urlopen, Request


# API Keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class IndicatorSnapshot:
    """
    A snapshot of a single economic indicator with context.

    Attributes:
        series_id: FRED series ID or custom identifier
        name: Human-readable name
        value: Current value
        unit: Unit of measurement (%, thousands, index, etc.)
        date: Date of the latest reading
        yoy_change: Year-over-year change (if available)
        yoy_direction: Pre-computed direction string (e.g., "UP 2.5% from year ago")
        mom_change: Month-over-month change (if available)
        mom_direction: Pre-computed direction string
        position_in_range: Where this sits in its 5-year range
        trend_3mo: Recent 3-month trend direction
        category: Economic category (labor, inflation, growth, housing, etc.)
    """
    series_id: str
    name: str
    value: float
    unit: str
    date: str
    yoy_change: Optional[float] = None
    yoy_direction: Optional[str] = None
    mom_change: Optional[float] = None
    mom_direction: Optional[str] = None
    position_in_range: Optional[str] = None
    trend_3mo: Optional[str] = None
    category: Optional[str] = None


@dataclass
class EconomicContext:
    """
    Contextual information that informs the analysis.

    Attributes:
        fed_rate: Current Fed funds rate
        fed_stance: Fed's current stance (tightening, easing, holding)
        inflation_target: Fed's inflation target (2%)
        natural_unemployment: NAIRU estimate (~4.2%)
        recent_fed_action: Most recent Fed decision
        key_events: Recent economic events that matter
    """
    fed_rate: float = 5.25
    fed_stance: str = "restrictive"
    inflation_target: float = 2.0
    natural_unemployment: float = 4.2
    recent_fed_action: Optional[str] = None
    key_events: Optional[List[str]] = None


@dataclass
class EconomistAnalysis:
    """
    The final economist analysis output.

    Attributes:
        headline: One-sentence summary answering the user's question
        narrative: 3-5 bullet points connecting the indicators
        key_insight: The most important takeaway
        risks: Key risks to watch
        opportunities: Potential opportunities
        watch_items: What to monitor going forward
        confidence: How confident we are in this assessment (low/medium/high)
    """
    headline: str
    narrative: List[str]
    key_insight: str
    risks: List[str]
    opportunities: List[str]
    watch_items: List[str]
    confidence: str = "medium"


# =============================================================================
# INDICATOR CATEGORIZATION
# =============================================================================

# Map series IDs to economic categories
SERIES_CATEGORIES = {
    # Labor Market
    'UNRATE': 'labor',
    'PAYEMS': 'labor',
    'ICSA': 'labor',
    'JTSJOL': 'labor',
    'JTSQUR': 'labor',
    'LNS12300060': 'labor',
    'U6RATE': 'labor',
    'CES0500000003': 'labor',  # Average hourly earnings
    'AHETPI': 'labor',

    # Inflation
    'CPIAUCSL': 'inflation',
    'CPILFESL': 'inflation',
    'PCEPI': 'inflation',
    'PCEPILFE': 'inflation',
    'CUSR0000SAH1': 'inflation',  # Shelter CPI
    'CUSR0000SEHA': 'inflation',  # Rent CPI
    'CPIUFDNS': 'inflation',  # Food CPI

    # Growth/Output
    'GDPC1': 'growth',
    'A191RO1Q156NBEA': 'growth',  # GDP YoY
    'A191RL1Q225SBEA': 'growth',  # GDP quarterly
    'INDPRO': 'growth',  # Industrial production
    'RSXFS': 'growth',  # Retail sales
    'PCE': 'growth',  # Personal consumption

    # Interest Rates / Fed
    'FEDFUNDS': 'rates',
    'DGS10': 'rates',
    'DGS2': 'rates',
    'T10Y2Y': 'rates',
    'MORTGAGE30US': 'rates',

    # Housing
    'CSUSHPINSA': 'housing',
    'HOUST': 'housing',
    'PERMIT': 'housing',
    'EXHOSLUSM495S': 'housing',
    'HSN1F': 'housing',
    'MSPUS': 'housing',

    # Consumer
    'UMCSENT': 'consumer',
    'PSAVERT': 'consumer',
    'PI': 'consumer',
    'DSPIC96': 'consumer',

    # Financial
    'SP500': 'financial',
    'VIXCLS': 'financial',
    'BAA10Y': 'financial',
    'NFCI': 'financial',
}


def categorize_indicator(series_id: str, name: str = "") -> str:
    """
    Determine the economic category of an indicator.

    Args:
        series_id: The FRED series ID or custom identifier
        name: The human-readable name (used for fuzzy matching)

    Returns:
        Category string: 'labor', 'inflation', 'growth', 'rates', 'housing',
        'consumer', 'financial', or 'other'
    """
    # Direct lookup
    if series_id in SERIES_CATEGORIES:
        return SERIES_CATEGORIES[series_id]

    # Fuzzy matching by name
    name_lower = name.lower()

    if any(term in name_lower for term in ['unemployment', 'payroll', 'job', 'employ', 'labor', 'wage', 'earnings']):
        return 'labor'
    elif any(term in name_lower for term in ['inflation', 'cpi', 'pce', 'price', 'cost']):
        return 'inflation'
    elif any(term in name_lower for term in ['gdp', 'growth', 'output', 'production', 'retail', 'sales']):
        return 'growth'
    elif any(term in name_lower for term in ['rate', 'treasury', 'yield', 'mortgage', 'fed fund']):
        return 'rates'
    elif any(term in name_lower for term in ['home', 'house', 'housing', 'rent', 'shelter']):
        return 'housing'
    elif any(term in name_lower for term in ['consumer', 'sentiment', 'confidence', 'saving', 'income']):
        return 'consumer'
    elif any(term in name_lower for term in ['stock', 's&p', 'nasdaq', 'dow', 'vix', 'credit', 'spread']):
        return 'financial'

    return 'other'


# =============================================================================
# ECONOMIC REASONING RULES
# =============================================================================

# These rules encode economic relationships for coherent narratives
ECONOMIC_RELATIONSHIPS = {
    # Labor market interpretation
    'labor_tight': {
        'conditions': lambda data: (
            data.get('unemployment', 10) < 4.5 and
            data.get('job_openings_per_unemployed', 0) > 1.0
        ),
        'interpretation': "labor market remains tight with more jobs than job seekers",
        'implication': "wage pressures likely to persist",
    },
    'labor_cooling': {
        'conditions': lambda data: (
            data.get('unemployment', 0) > 4.0 and
            data.get('unemployment_trend', '') == 'rising'
        ),
        'interpretation': "labor market is cooling as unemployment edges higher",
        'implication': "Fed gaining confidence inflation will ease",
    },
    'labor_soft': {
        'conditions': lambda data: data.get('unemployment', 0) > 5.0,
        'interpretation': "labor market shows meaningful slack",
        'implication': "Fed likely shifting focus to employment mandate",
    },

    # Inflation interpretation
    'inflation_hot': {
        'conditions': lambda data: data.get('core_inflation', 0) > 3.5,
        'interpretation': "inflation remains stubbornly elevated",
        'implication': "monetary policy will stay restrictive longer",
    },
    'inflation_progress': {
        'conditions': lambda data: (
            2.5 < data.get('core_inflation', 0) <= 3.5 and
            data.get('inflation_trend', '') == 'falling'
        ),
        'interpretation': "inflation is making progress toward the Fed's 2% target",
        'implication': "rate cuts becoming more likely, but patience required",
    },
    'inflation_target': {
        'conditions': lambda data: data.get('core_inflation', 0) <= 2.5,
        'interpretation': "inflation is near the Fed's 2% target",
        'implication': "Fed has flexibility to focus on growth and employment",
    },

    # Growth interpretation
    'growth_strong': {
        'conditions': lambda data: data.get('gdp_growth', 0) > 2.5,
        'interpretation': "economy is expanding at a healthy pace",
        'implication': "no imminent recession risk, but inflation vigilance needed",
    },
    'growth_moderate': {
        'conditions': lambda data: 1.0 < data.get('gdp_growth', 0) <= 2.5,
        'interpretation': "growth is moderate but positive",
        'implication': "soft landing scenario remains plausible",
    },
    'growth_weak': {
        'conditions': lambda data: data.get('gdp_growth', 0) <= 1.0,
        'interpretation': "economic growth is slowing significantly",
        'implication': "recession risk rising, Fed may need to pivot",
    },

    # Combined narratives
    'goldilocks': {
        'conditions': lambda data: (
            data.get('unemployment', 10) < 4.5 and
            data.get('core_inflation', 10) < 3.0 and
            data.get('gdp_growth', 0) > 1.5
        ),
        'interpretation': "economy is in a 'Goldilocks' zone with solid growth, low unemployment, and moderating inflation",
        'implication': "conditions support continued expansion without aggressive Fed action",
    },
    'stagflation_risk': {
        'conditions': lambda data: (
            data.get('unemployment', 0) > 4.5 and
            data.get('core_inflation', 0) > 3.5
        ),
        'interpretation': "concerning mix of rising unemployment and elevated inflation",
        'implication': "Fed faces difficult tradeoffs - classic stagflation dilemma",
    },
}


def apply_economic_reasoning(indicators: Dict[str, float]) -> List[Dict[str, str]]:
    """
    Apply economic reasoning rules to interpret the data.

    Args:
        indicators: Dictionary mapping indicator names to values

    Returns:
        List of applicable interpretations with their implications
    """
    applicable_rules = []

    for rule_name, rule_def in ECONOMIC_RELATIONSHIPS.items():
        try:
            if rule_def['conditions'](indicators):
                applicable_rules.append({
                    'rule': rule_name,
                    'interpretation': rule_def['interpretation'],
                    'implication': rule_def['implication'],
                })
        except (KeyError, TypeError):
            # Rule conditions not met due to missing data
            continue

    return applicable_rules


# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================

def build_data_context(series_data: List[Tuple]) -> Dict[str, Any]:
    """
    Build a context dictionary from series data for economic reasoning.

    Args:
        series_data: List of (series_id, dates, values, info) tuples

    Returns:
        Dictionary with standardized economic metrics
    """
    context = {}

    for series_id, dates, values, info in series_data:
        if not values:
            continue

        latest = values[-1]
        name = info.get('name', info.get('title', series_id)).lower()

        # Extract key metrics into standardized names
        if series_id == 'UNRATE' or 'unemployment rate' in name:
            context['unemployment'] = latest
            if len(values) >= 3:
                context['unemployment_trend'] = 'rising' if values[-1] > values[-3] else 'falling'

        elif series_id in ['CPIAUCSL', 'CPILFESL', 'PCEPILFE'] or 'core' in name and ('cpi' in name or 'pce' in name):
            # Calculate YoY inflation if we have index values
            if len(values) >= 12:
                yoy = ((values[-1] / values[-12]) - 1) * 100
                context['core_inflation'] = yoy
                if len(values) >= 15:
                    prev_yoy = ((values[-3] / values[-15]) - 1) * 100
                    context['inflation_trend'] = 'falling' if yoy < prev_yoy else 'rising'

        elif series_id in ['A191RO1Q156NBEA', 'A191RL1Q225SBEA'] or 'gdp' in name:
            # For GDP growth rates, use the value directly
            if 'yoy' in name.lower() or 'growth' in name.lower():
                context['gdp_growth'] = latest
            elif info.get('is_yoy'):
                context['gdp_growth'] = latest
            else:
                context['gdp_growth'] = latest

        elif series_id == 'JTSJOL' or 'job opening' in name:
            context['job_openings'] = latest

        elif series_id == 'PAYEMS' or 'payroll' in name:
            if info.get('is_payroll_change'):
                context['monthly_job_change'] = latest
            else:
                context['total_payrolls'] = latest

        elif series_id == 'FEDFUNDS':
            context['fed_rate'] = latest

    # Calculate derived metrics
    if 'job_openings' in context and 'unemployment' in context:
        # Rough estimate of openings per unemployed
        # Job openings in thousands, labor force ~165M
        labor_force = 165000  # thousands
        unemployed = (context['unemployment'] / 100) * labor_force
        if unemployed > 0:
            context['job_openings_per_unemployed'] = context['job_openings'] / unemployed

    return context


def generate_economist_analysis(
    query: str,
    series_data: List[Tuple],
    existing_explanation: str = "",
    news_context: str = ""
) -> EconomistAnalysis:
    """
    Generate premium economist-quality analysis of economic data.

    This function:
    1. Extracts key metrics from the data
    2. Applies economic reasoning rules
    3. Calls an LLM to synthesize into coherent narrative
    4. Returns structured analysis with headline, narrative, risks, and opportunities

    Args:
        query: The user's original question
        series_data: List of (series_id, dates, values, info) tuples
        existing_explanation: Any existing explanation to build on
        news_context: Recent news context if available

    Returns:
        EconomistAnalysis dataclass with structured analysis
    """
    # Build data context for reasoning
    data_context = build_data_context(series_data)

    # Apply rule-based economic reasoning
    applicable_rules = apply_economic_reasoning(data_context)

    # Build data summary for LLM
    data_summary = _build_analysis_summary(series_data)

    # Generate analysis via LLM
    analysis = _call_llm_for_analysis(
        query=query,
        data_summary=data_summary,
        data_context=data_context,
        applicable_rules=applicable_rules,
        news_context=news_context,
    )

    return analysis


def _build_analysis_summary(series_data: List[Tuple]) -> List[Dict]:
    """
    Build a summary of series data for the LLM.

    Args:
        series_data: List of (series_id, dates, values, info) tuples

    Returns:
        List of dictionaries with key data points
    """
    summary = []

    for series_id, dates, values, info in series_data:
        if not values:
            continue

        name = info.get('name', info.get('title', series_id))
        unit = info.get('unit', info.get('units', ''))
        latest = values[-1]
        latest_date = dates[-1] if dates else 'unknown'

        entry = {
            'series_id': series_id,
            'name': name,
            'unit': unit,
            'latest_value': round(latest, 2),
            'latest_date': latest_date,
            'category': categorize_indicator(series_id, name),
        }

        # Add YoY change if available
        if len(values) >= 12:
            year_ago = values[-12]
            if year_ago != 0:
                yoy_change = latest - year_ago
                yoy_pct = (yoy_change / abs(year_ago)) * 100
                entry['yoy_change'] = round(yoy_change, 2)
                entry['yoy_pct_change'] = round(yoy_pct, 1)
                entry['yoy_direction'] = 'UP' if yoy_change > 0 else 'DOWN' if yoy_change < 0 else 'UNCHANGED'

        # Add month-over-month change
        if len(values) >= 2:
            mom_change = values[-1] - values[-2]
            entry['mom_change'] = round(mom_change, 2)
            entry['mom_direction'] = 'UP' if mom_change > 0.01 else 'DOWN' if mom_change < -0.01 else 'FLAT'

        # Add position in range
        recent_vals = values[-60:] if len(values) >= 60 else values
        if recent_vals:
            recent_min = min(recent_vals)
            recent_max = max(recent_vals)
            if recent_max > recent_min:
                position = (latest - recent_min) / (recent_max - recent_min)
                if position > 0.9:
                    entry['position_in_range'] = 'NEAR 5-YEAR HIGH'
                elif position < 0.1:
                    entry['position_in_range'] = 'NEAR 5-YEAR LOW'
                elif position > 0.5:
                    entry['position_in_range'] = 'ABOVE MIDDLE OF RANGE'
                else:
                    entry['position_in_range'] = 'BELOW MIDDLE OF RANGE'

        # Add payroll-specific data
        if info.get('is_payroll_change') and info.get('original_values'):
            orig_values = info['original_values']
            if len(orig_values) >= 2:
                monthly_change = orig_values[-1] - orig_values[-2]
                entry['monthly_job_change'] = round(monthly_change, 1)
            if len(orig_values) >= 13:
                changes_12mo = [orig_values[i] - orig_values[i-1] for i in range(-12, 0)]
                entry['avg_monthly_change_12mo'] = round(sum(changes_12mo) / 12, 1)

        summary.append(entry)

    return summary


def _call_llm_for_analysis(
    query: str,
    data_summary: List[Dict],
    data_context: Dict[str, Any],
    applicable_rules: List[Dict[str, str]],
    news_context: str = "",
) -> EconomistAnalysis:
    """
    Call Claude to generate the economist analysis.

    Args:
        query: User's question
        data_summary: Summarized data points
        data_context: Extracted economic metrics
        applicable_rules: Economic reasoning rules that apply
        news_context: Recent news if available

    Returns:
        EconomistAnalysis dataclass
    """
    if not ANTHROPIC_API_KEY:
        return _generate_fallback_analysis(data_summary, data_context, applicable_rules)

    # Build the rules context
    rules_text = ""
    if applicable_rules:
        rules_text = "\n\nECONOMIC REASONING (pre-computed):\n"
        for rule in applicable_rules:
            rules_text += f"- {rule['interpretation']}. Implication: {rule['implication']}\n"

    # Build news context section
    news_section = ""
    if news_context:
        news_section = f"\n\nRECENT NEWS CONTEXT:\n{news_context}"

    prompt = f"""You are a senior economist at the Federal Reserve or a top investment bank writing a briefing for policymakers. Your job is to synthesize economic data into actionable intelligence.

USER QUESTION: {query}

DATA:
{json.dumps(data_summary, indent=2)}

KEY METRICS EXTRACTED:
{json.dumps(data_context, indent=2)}
{rules_text}
{news_section}

Write a premium economist analysis in this exact JSON format:
{{
    "headline": "One clear sentence that answers the user's question directly",
    "narrative": [
        "First bullet connecting labor market data to the bigger picture",
        "Second bullet on inflation trajectory and Fed implications",
        "Third bullet on growth/momentum",
        "Fourth bullet synthesizing what this means going forward"
    ],
    "key_insight": "The single most important takeaway - the insight a CEO or Fed Chair would want",
    "risks": [
        "Key risk #1 to the outlook",
        "Key risk #2 to the outlook"
    ],
    "opportunities": [
        "Potential opportunity #1",
        "Potential opportunity #2"
    ],
    "watch_items": [
        "What to monitor going forward #1",
        "What to monitor going forward #2"
    ],
    "confidence": "high" | "medium" | "low"
}}

CRITICAL RULES:
1. ANSWER THE QUESTION DIRECTLY - The headline must answer what the user asked
2. CONNECT THE DOTS - Each narrative bullet should show how indicators relate to each other
3. BE SPECIFIC - Use actual numbers and dates from the data (e.g., "4.1% unemployment" not "low unemployment")
4. EXPLAIN CAUSATION - Don't just describe, explain WHY things are happening
5. LOOK FORWARD - What does this mean for the next 3-6 months?
6. NO JARGON without explanation - If you use terms like "restrictive policy", explain what that means
7. FORMAT DATES NATURALLY - "2025-12-01" becomes "December 2025"
8. CONVERT UNITS NATURALLY - "1764.6 thousands" becomes "about 1.8 million"

The confidence level should be:
- "high" if data is recent, consistent, and supports clear conclusions
- "medium" if data is mixed or conclusions require some interpretation
- "low" if data is stale, conflicting, or highly uncertain

Return ONLY valid JSON, no markdown or explanation."""

    url = 'https://api.anthropic.com/v1/messages'
    payload = {
        'model': 'claude-sonnet-4-20250514',
        'max_tokens': 1200,
        'messages': [{'role': 'user', 'content': prompt}]
    }
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01'
    }

    try:
        req = Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode('utf-8'))
            content = result['content'][0]['text'].strip()

            # Parse JSON response
            analysis_dict = _extract_json(content)

            if analysis_dict:
                return EconomistAnalysis(
                    headline=analysis_dict.get('headline', 'Analysis unavailable'),
                    narrative=analysis_dict.get('narrative', []),
                    key_insight=analysis_dict.get('key_insight', ''),
                    risks=analysis_dict.get('risks', []),
                    opportunities=analysis_dict.get('opportunities', []),
                    watch_items=analysis_dict.get('watch_items', []),
                    confidence=analysis_dict.get('confidence', 'medium'),
                )
    except Exception as e:
        print(f"[EconomistAnalysis] LLM error: {e}")

    return _generate_fallback_analysis(data_summary, data_context, applicable_rules)


def _extract_json(text: str) -> Optional[Dict]:
    """Extract JSON from LLM response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0]
    elif '```' in text:
        text = text.split('```')[1].split('```')[0]

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _generate_fallback_analysis(
    data_summary: List[Dict],
    data_context: Dict[str, Any],
    applicable_rules: List[Dict[str, str]]
) -> EconomistAnalysis:
    """
    Generate a basic analysis when LLM is unavailable.

    Args:
        data_summary: Summarized data points
        data_context: Extracted economic metrics
        applicable_rules: Economic reasoning rules that apply

    Returns:
        EconomistAnalysis with basic rule-based content
    """
    # Build headline from data
    headline_parts = []

    if 'unemployment' in data_context:
        headline_parts.append(f"unemployment at {data_context['unemployment']:.1f}%")

    if 'core_inflation' in data_context:
        headline_parts.append(f"core inflation at {data_context['core_inflation']:.1f}%")

    if 'gdp_growth' in data_context:
        headline_parts.append(f"GDP growing {data_context['gdp_growth']:.1f}%")

    headline = f"Economic snapshot: {', '.join(headline_parts)}." if headline_parts else "Economic data overview."

    # Build narrative from applicable rules
    narrative = []
    for rule in applicable_rules[:4]:  # Max 4 bullets
        narrative.append(f"{rule['interpretation'].capitalize()}. {rule['implication'].capitalize()}.")

    if not narrative:
        narrative = ["Data shows mixed signals across economic indicators."]

    # Build basic risks and opportunities
    risks = ["Policy uncertainty remains elevated.", "Global economic conditions could shift."]
    opportunities = ["Economic resilience creates opportunities for growth.", "Data transparency supports informed decision-making."]
    watch_items = ["Federal Reserve policy decisions", "Upcoming employment and inflation reports"]

    return EconomistAnalysis(
        headline=headline,
        narrative=narrative,
        key_insight="Monitor incoming data closely as economic conditions evolve.",
        risks=risks,
        opportunities=opportunities,
        watch_items=watch_items,
        confidence="low",  # Lower confidence for fallback analysis
    )


# =============================================================================
# FORMATTED OUTPUT
# =============================================================================

def format_analysis_for_display(analysis: EconomistAnalysis) -> str:
    """
    Format the economist analysis for display.

    Args:
        analysis: EconomistAnalysis dataclass

    Returns:
        Formatted string for display
    """
    lines = []

    # Headline
    lines.append(analysis.headline)
    lines.append("")

    # Narrative bullets
    for point in analysis.narrative:
        lines.append(f"- {point}")

    lines.append("")

    # Key insight
    if analysis.key_insight:
        lines.append(f"KEY TAKEAWAY: {analysis.key_insight}")
        lines.append("")

    # Risks
    if analysis.risks:
        lines.append("RISKS TO WATCH:")
        for risk in analysis.risks:
            lines.append(f"  - {risk}")
        lines.append("")

    # Opportunities
    if analysis.opportunities:
        lines.append("OPPORTUNITIES:")
        for opp in analysis.opportunities:
            lines.append(f"  - {opp}")
        lines.append("")

    # Watch items
    if analysis.watch_items:
        lines.append("WHAT TO MONITOR:")
        for item in analysis.watch_items:
            lines.append(f"  - {item}")

    return "\n".join(lines)


def format_analysis_as_html(analysis: EconomistAnalysis) -> str:
    """
    Format the economist analysis as HTML for Streamlit display.

    Args:
        analysis: EconomistAnalysis dataclass

    Returns:
        HTML string for display
    """
    html_parts = []

    # Headline
    html_parts.append(f"<p style='font-size: 1.1em; font-weight: 600; margin-bottom: 12px;'>{analysis.headline}</p>")

    # Narrative bullets
    html_parts.append("<ul style='margin: 0 0 12px 0; padding-left: 20px;'>")
    for point in analysis.narrative:
        html_parts.append(f"<li style='margin-bottom: 6px;'>{point}</li>")
    html_parts.append("</ul>")

    # Key insight box
    if analysis.key_insight:
        html_parts.append(f"""
        <div style='background: #FEF3C7; border-left: 4px solid #F59E0B; padding: 12px; margin: 12px 0; border-radius: 4px;'>
            <strong>Key Takeaway:</strong> {analysis.key_insight}
        </div>
        """)

    # Two-column layout for risks and opportunities
    html_parts.append("<div style='display: flex; gap: 16px; margin-top: 12px;'>")

    # Risks column
    if analysis.risks:
        html_parts.append("<div style='flex: 1;'>")
        html_parts.append("<p style='font-weight: 600; color: #DC2626; margin-bottom: 4px;'>Risks:</p>")
        html_parts.append("<ul style='margin: 0; padding-left: 16px; font-size: 0.9em;'>")
        for risk in analysis.risks:
            html_parts.append(f"<li>{risk}</li>")
        html_parts.append("</ul></div>")

    # Opportunities column
    if analysis.opportunities:
        html_parts.append("<div style='flex: 1;'>")
        html_parts.append("<p style='font-weight: 600; color: #059669; margin-bottom: 4px;'>Opportunities:</p>")
        html_parts.append("<ul style='margin: 0; padding-left: 16px; font-size: 0.9em;'>")
        for opp in analysis.opportunities:
            html_parts.append(f"<li>{opp}</li>")
        html_parts.append("</ul></div>")

    html_parts.append("</div>")

    # Watch items
    if analysis.watch_items:
        html_parts.append("<p style='font-weight: 600; margin-top: 12px; margin-bottom: 4px;'>What to Monitor:</p>")
        html_parts.append("<ul style='margin: 0; padding-left: 16px; font-size: 0.9em; color: #6B7280;'>")
        for item in analysis.watch_items:
            html_parts.append(f"<li>{item}</li>")
        html_parts.append("</ul>")

    # Confidence indicator
    confidence_colors = {'high': '#059669', 'medium': '#D97706', 'low': '#DC2626'}
    confidence_color = confidence_colors.get(analysis.confidence, '#6B7280')
    html_parts.append(f"""
    <p style='margin-top: 12px; font-size: 0.8em; color: {confidence_color};'>
        Analysis confidence: {analysis.confidence.upper()}
    </p>
    """)

    return "\n".join(html_parts)


# =============================================================================
# CONVENIENCE FUNCTION FOR APP INTEGRATION
# =============================================================================

def get_premium_analysis(
    query: str,
    series_data: List[Tuple],
    news_context: str = ""
) -> Tuple[EconomistAnalysis, str, str]:
    """
    Main entry point for premium economist analysis.

    Args:
        query: User's question
        series_data: List of (series_id, dates, values, info) tuples
        news_context: Optional news context

    Returns:
        Tuple of (EconomistAnalysis, plain_text_format, html_format)
    """
    analysis = generate_economist_analysis(
        query=query,
        series_data=series_data,
        news_context=news_context,
    )

    plain_text = format_analysis_for_display(analysis)
    html = format_analysis_as_html(analysis)

    return analysis, plain_text, html


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("PREMIUM ECONOMIST ANALYSIS - TEST")
    print("=" * 70)

    # Sample data mimicking what app.py provides
    sample_series_data = [
        ('UNRATE', ['2024-09-01', '2024-10-01', '2024-11-01', '2024-12-01'],
         [4.1, 4.0, 4.2, 4.1], {'name': 'Unemployment Rate', 'unit': '%'}),
        ('PAYEMS', ['2024-09-01', '2024-10-01', '2024-11-01', '2024-12-01'],
         [158000, 158200, 158400, 158600],
         {'name': 'Monthly Job Change', 'unit': 'Thousands', 'is_payroll_change': True,
          'original_values': [157000, 157500, 158000, 158200, 158400, 158600]}),
        ('A191RO1Q156NBEA', ['2024-03-01', '2024-06-01', '2024-09-01', '2024-12-01'],
         [2.2, 2.4, 2.5, 2.3], {'name': 'Real GDP (YoY)', 'unit': '%', 'is_yoy': True}),
        ('PCEPILFE', ['2024-01-01', '2024-02-01', '2024-03-01', '2024-04-01', '2024-05-01',
                      '2024-06-01', '2024-07-01', '2024-08-01', '2024-09-01', '2024-10-01',
                      '2024-11-01', '2024-12-01'],
         [120.0, 120.3, 120.6, 120.9, 121.2, 121.5, 121.8, 122.1, 122.4, 122.7, 123.0, 123.3],
         {'name': 'Core PCE Price Index', 'unit': 'Index'}),
    ]

    print("\n1. Testing data context extraction...")
    context = build_data_context(sample_series_data)
    print(f"Extracted context: {json.dumps(context, indent=2)}")

    print("\n2. Testing economic reasoning...")
    rules = apply_economic_reasoning(context)
    print(f"Applicable rules: {json.dumps(rules, indent=2)}")

    print("\n3. Testing full analysis generation...")
    analysis = generate_economist_analysis(
        query="How is the economy doing?",
        series_data=sample_series_data,
    )
    print(f"\nHeadline: {analysis.headline}")
    print(f"Confidence: {analysis.confidence}")
    print(f"\nNarrative:")
    for point in analysis.narrative:
        print(f"  - {point}")
    print(f"\nKey Insight: {analysis.key_insight}")
    print(f"\nRisks: {analysis.risks}")
    print(f"Opportunities: {analysis.opportunities}")

    print("\n4. Testing formatted output...")
    plain = format_analysis_for_display(analysis)
    print("\nPlain text format:")
    print(plain)

    print("\n" + "=" * 70)
    print("TESTS COMPLETE")
    print("=" * 70)
