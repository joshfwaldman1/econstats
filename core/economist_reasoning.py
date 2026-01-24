"""
Economist reasoning module for EconStats.

This module implements real-time AI reasoning about what economic indicators
an analyst would need to answer a question - rather than relying on pre-computed
query-to-series mappings.

Flow:
1. Query comes in
2. Check for direct data requests (e.g., "What is the Fed funds rate?") - return the actual data
3. For analytical questions, AI reasons about what indicators are needed
4. Search FRED for those indicators
5. Return the series

This is the PRIMARY approach. Pre-computed plans are a fast-path cache/backstop.
"""

import json
import os
import re
from typing import Optional
from urllib.request import urlopen, Request

# API Keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# =============================================================================
# DIRECT DATA MAPPINGS
# For unambiguous questions asking for specific data, return the data directly.
# This prevents over-interpretation (e.g., "What is the Fed rate?" should return
# FEDFUNDS, not inflation metrics that influence rates).
# =============================================================================

DIRECT_SERIES_MAPPINGS = {
    # Federal Reserve / Interest Rates
    'fed funds rate': ['FEDFUNDS', 'DFEDTARU'],
    'fed rate': ['FEDFUNDS', 'DFEDTARU'],
    'federal funds': ['FEDFUNDS'],
    'interest rate': ['FEDFUNDS', 'DGS10', 'DGS2'],
    'interest rates': ['FEDFUNDS', 'DGS10', 'DGS2'],
    'treasury yield': ['DGS10', 'DGS2', 'DGS30'],
    'treasury yields': ['DGS10', 'DGS2', 'DGS30'],
    '10 year treasury': ['DGS10'],
    '10-year treasury': ['DGS10'],
    '2 year treasury': ['DGS2'],
    'yield curve': ['T10Y2Y', 'DGS10', 'DGS2'],
    'mortgage rate': ['MORTGAGE30US', 'MORTGAGE15US'],
    'mortgage rates': ['MORTGAGE30US', 'MORTGAGE15US'],
    '30 year mortgage': ['MORTGAGE30US'],
    '30-year mortgage': ['MORTGAGE30US'],

    # Inflation - specific measures
    'core inflation': ['CPILFESL', 'PCEPILFE'],
    'core cpi': ['CPILFESL'],
    'core pce': ['PCEPILFE'],
    'cpi': ['CPIAUCSL', 'CPILFESL'],
    'pce': ['PCEPI', 'PCEPILFE'],
    'inflation rate': ['CPIAUCSL', 'PCEPILFE'],

    # GDP - specific measures
    'gdp': ['GDPC1', 'A191RL1Q225SBEA'],
    'real gdp': ['GDPC1'],
    'gdp growth': ['A191RL1Q225SBEA', 'GDPC1'],
    'economic growth': ['GDPC1', 'A191RL1Q225SBEA'],
    'recession': ['GDPC1', 'T10Y2Y', 'UNRATE', 'UMCSENT'],
    'is a recession coming': ['T10Y2Y', 'GDPC1', 'UMCSENT', 'ICSA'],
    'recession risk': ['T10Y2Y', 'GDPC1', 'UMCSENT', 'ICSA'],

    # Employment - specific measures
    'unemployment rate': ['UNRATE', 'U6RATE'],
    'unemployment': ['UNRATE', 'U6RATE'],
    'payrolls': ['PAYEMS'],
    'nonfarm payrolls': ['PAYEMS'],
    'jobs report': ['PAYEMS', 'UNRATE'],
    'job openings': ['JTSJOL'],
    'initial claims': ['ICSA'],
    'jobless claims': ['ICSA'],

    # Housing - specific measures
    'home prices': ['CSUSHPINSA', 'MSPUS'],
    'house prices': ['CSUSHPINSA', 'MSPUS'],
    'housing prices': ['CSUSHPINSA', 'MSPUS'],
    'housing starts': ['HOUST', 'HOUST1F'],
    'building permits': ['PERMIT'],
    'housing market': ['CSUSHPINSA', 'HOUST', 'MORTGAGE30US', 'EXHOSLUSM495S'],
    'existing home sales': ['EXHOSLUSM495S'],
    'new home sales': ['HSN1F'],

    # Consumer
    'consumer sentiment': ['UMCSENT'],
    'consumer confidence': ['UMCSENT'],
    'retail sales': ['RSXFS'],

    # Other common
    'oil price': ['DCOILWTICO'],
    'oil prices': ['DCOILWTICO'],
    'gas prices': ['GASREGW'],
    'dollar index': ['DTWEXBGS'],
    's&p 500': ['SP500'],
    'stock market': ['SP500', 'DJIA'],
}


def check_direct_mapping(query: str) -> Optional[list]:
    """
    Check if query is asking for specific data that has a direct answer.

    Returns list of series IDs if matched, None otherwise.
    """
    query_lower = query.lower().strip()

    # Remove common question words
    for prefix in ['what is the', 'what is', 'what are the', 'what are',
                   'show me the', 'show me', 'current', 'latest', 'today\'s']:
        if query_lower.startswith(prefix):
            query_lower = query_lower[len(prefix):].strip()

    # Remove trailing question mark and common suffixes
    query_lower = query_lower.rstrip('?').strip()
    for suffix in ['right now', 'today', 'currently', 'now']:
        if query_lower.endswith(suffix):
            query_lower = query_lower[:-len(suffix)].strip()

    # Direct match
    if query_lower in DIRECT_SERIES_MAPPINGS:
        return DIRECT_SERIES_MAPPINGS[query_lower]

    # Check if query contains any direct mapping key
    for key, series in DIRECT_SERIES_MAPPINGS.items():
        # Use word boundary matching to avoid partial matches
        pattern = r'\b' + re.escape(key) + r'\b'
        if re.search(pattern, query_lower):
            return series

    return None

REASONING_PROMPT = """You are a credible economic analyst (think Jason Furman, Claudia Sahm, or a Fed economist).

A user asked: "{query}"

Think through what data you would NEED to answer this question properly. Don't give me FRED series IDs - I need you to reason about what economic CONCEPTS and INDICATORS an analyst would examine.

Return JSON:
{{
    "reasoning": "Brief explanation of your analytical approach (1-2 sentences)",
    "indicators": [
        {{
            "concept": "unemployment rate",
            "why": "Direct measure of labor market slack",
            "search_terms": ["unemployment rate", "jobless rate"]
        }},
        {{
            "concept": "job openings",
            "why": "Shows labor demand - tight market has high openings vs unemployed",
            "search_terms": ["job openings", "JOLTS openings"]
        }}
    ],
    "time_context": "recent" | "historical" | "comparison",
    "display_suggestion": "line chart showing trends" | "compare side by side" | etc.
}}

Rules:
1. Think like an economist writing a briefing - what would you NEED to know?
2. Include 2-4 indicators that tell different parts of the story
3. Each indicator should add unique insight (no redundant measures)
4. search_terms MUST be specific and directly describe the indicator:
   - For wages: "average hourly earnings", "wage growth", "compensation"
   - For inflation: "consumer price index", "CPI", "PCE price index"
   - For employment: "nonfarm payrolls", "employment level", "jobs"
   - DO NOT use generic terms like "rate", "index", "level" alone
5. Consider: Is this about levels, changes, or comparisons?

IMPORTANT: Your job is to REASON about what's needed, not to recall series IDs from memory.
"""


def call_gemini_reasoning(query: str, retries: int = 2) -> Optional[dict]:
    """
    Call Gemini to reason about what an economist would need.

    Uses Gemini Flash for speed - this is the fast thinking step.
    """
    if not GEMINI_API_KEY:
        return None

    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}'

    prompt = REASONING_PROMPT.format(query=query)

    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.3,  # Lower temp for more consistent reasoning
            'maxOutputTokens': 800
        }
    }
    headers = {'Content-Type': 'application/json'}

    for attempt in range(retries):
        try:
            req = Request(url, data=json.dumps(payload).encode('utf-8'),
                         headers=headers, method='POST')
            with urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result['candidates'][0]['content']['parts'][0]['text']
                return _extract_json(content)
        except Exception as e:
            if attempt == retries - 1:
                print(f"  Reasoning ERROR: {e}")
                return None
    return None


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response."""
    try:
        # Try direct parse
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


def reason_about_query(query: str, verbose: bool = False) -> dict:
    """
    Main entry point: Reason about what economic data is needed.

    Returns:
        {
            "reasoning": "To assess labor market health, we need...",
            "indicators": [
                {"concept": "...", "why": "...", "search_terms": [...]}
            ],
            "search_terms": ["term1", "term2", ...],  # Flattened for easy use
            "direct_series": ["FEDFUNDS", ...],  # If direct mapping found
            "time_context": "recent",
            "display_suggestion": "..."
        }
    """
    if verbose:
        print(f"  Reasoning about: {query}")

    # FIRST: Check for direct data requests
    # Questions like "What is the Fed funds rate?" should return the actual rate,
    # not factors that influence rates.
    direct_series = check_direct_mapping(query)
    if direct_series:
        if verbose:
            print(f"  Direct mapping found: {direct_series}")
        return {
            "reasoning": f"Showing the requested data directly.",
            "indicators": [],
            "search_terms": [],
            "direct_series": direct_series,
            "time_context": "recent",
            "display_suggestion": "line chart"
        }

    # For analytical questions, use AI reasoning
    result = call_gemini_reasoning(query)

    if not result:
        # Fallback: extract basic search terms from query
        return {
            "reasoning": "Using keyword extraction (AI reasoning unavailable)",
            "indicators": [],
            "search_terms": _extract_keywords(query),
            "time_context": "recent",
            "display_suggestion": "line chart"
        }

    # Flatten search terms from all indicators
    all_search_terms = []
    for indicator in result.get("indicators", []):
        all_search_terms.extend(indicator.get("search_terms", []))

    result["search_terms"] = all_search_terms

    if verbose:
        print(f"  Reasoning: {result.get('reasoning', 'N/A')}")
        print(f"  Indicators: {[i.get('concept') for i in result.get('indicators', [])]}")

    return result


def _extract_keywords(query: str) -> list:
    """Basic keyword extraction as fallback."""
    # Remove common words
    stopwords = {'what', 'is', 'the', 'how', 'are', 'doing', 'with', 'in', 'of',
                 'to', 'a', 'an', 'and', 'or', 'for', 'on', 'at', 'by', 'about',
                 'does', 'do', 'did', 'has', 'have', 'been', 'be', 'will', 'would',
                 'could', 'should', 'can', 'may', 'might', 'current', 'currently',
                 'right', 'now', 'today', 'recently', 'latest', 'recent'}

    words = query.lower().replace('?', '').replace(',', '').split()
    keywords = [w for w in words if w not in stopwords and len(w) > 2]

    return keywords[:4]


# Quick test
if __name__ == "__main__":
    test_queries = [
        "How is the job market doing?",
        "Is inflation coming down?",
        "Are wages keeping up with prices?",
        "What's happening with housing?",
    ]

    for q in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {q}")
        result = reason_about_query(q, verbose=True)
        print(f"Search terms: {result.get('search_terms', [])}")
