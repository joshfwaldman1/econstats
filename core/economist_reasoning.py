"""
Economist reasoning module for EconStats.

This module implements real-time AI reasoning about what economic indicators
an analyst would need to answer a question - rather than relying on pre-computed
query-to-series mappings.

Flow:
1. Query comes in
2. AI reasons: "To answer this, an economist would want X, Y, Z indicators because..."
3. We search FRED for those indicators
4. Return the series

This is the PRIMARY approach. Pre-computed plans are a fast-path cache/backstop.
"""

import json
import os
from typing import Optional
from urllib.request import urlopen, Request

# API Keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

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
            "time_context": "recent",
            "display_suggestion": "..."
        }
    """
    if verbose:
        print(f"  Reasoning about: {query}")

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
