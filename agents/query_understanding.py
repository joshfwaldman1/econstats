"""
Query Understanding Module - "Thinking First" Layer for EconStats.

This module implements a deep query understanding step that runs BEFORE any routing
or plan matching. The goal is to truly understand what the user is asking before
deciding how to answer it.

Architecture:
1. Raw query comes in
2. Gemini deeply analyzes the query intent, entities, and requirements
3. Returns a structured understanding that guides all downstream routing

This prevents issues like:
- Matching "Black workers" to women's employment data
- Showing irrelevant data for specific questions
- Missing the true intent behind complex queries
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request

# API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Cache for query understanding results (1-hour TTL)
# This avoids repeated expensive Gemini calls for similar queries
_understanding_cache: dict = {}
_understanding_cache_ttl = timedelta(hours=1)

# =============================================================================
# QUERY UNDERSTANDING PROMPT
# The "thinking first" prompt that deeply analyzes user intent
# =============================================================================

UNDERSTANDING_PROMPT = """You are an expert economist and data analyst. Your job is to DEEPLY UNDERSTAND what the user is really asking before we fetch any data.

USER QUERY: "{query}"

## YOUR TASK: Analyze the query and return a structured understanding.

Think step by step:
1. What is the user REALLY asking? (Not just the literal words)
2. What ENTITIES are mentioned? (regions, demographics, sectors, time periods)
3. What TYPE of query is this? (factual, analytical, comparison, forecast)
4. What DATA SOURCES would best answer this? (FRED, Zillow, EIA, international data)
5. What are potential PITFALLS? (wrong data, misleading comparisons, etc.)

## ENTITY EXTRACTION

Extract ALL relevant entities:

**Demographics** (be VERY specific - these must match exactly):
- race: "black", "african american", "hispanic", "latino", "asian", "white"
- gender: "women", "men", "female", "male"
- age: "youth", "teen", "young", "older", "elderly", "prime age"
- other: "veteran", "immigrant", "foreign-born", "native-born", "disabled"

**Regions** (for routing to correct data source):
- US regions: specific states, "national", "american"
- International: "eurozone", "europe", "uk", "china", "japan", "germany", etc.

**Sectors/Industries**:
- "manufacturing", "construction", "retail", "restaurants", "tech", "healthcare", etc.

**Time references**:
- Specific: "2023", "last year", "Q3 2024"
- Relative: "recent", "currently", "trend"
- Periods: "pre-covid", "during covid", "post-pandemic", "great recession"

## QUERY TYPE CLASSIFICATION

Determine the query type:

1. **FACTUAL** - Asking for a specific number/rate
   - "What is the unemployment rate?"
   - "What's the Fed funds rate?"

2. **ANALYTICAL** - Asking for insight/interpretation
   - "How is the job market doing?"
   - "Is inflation coming down?"

3. **COMPARISON** - Asking to compare entities
   - "US vs Eurozone GDP"
   - "How does Black unemployment compare to overall?"

4. **FORECAST** - Asking about the future
   - "Will the Fed cut rates?"
   - "Is a recession coming?"

5. **CAUSAL** - Asking why something happened
   - "Why did inflation spike in 2022?"
   - "What caused the housing crash?"

## DATA SOURCE ROUTING

Based on the query, which sources should we use?

- **FRED** (default): US economic data
- **DBNOMICS** (international): Eurozone, UK, Japan, China, etc.
- **ZILLOW** (housing): Actual market rents, home values
- **EIA** (energy): Oil, gas, electricity prices
- **ALPHAVANTAGE** (markets): Stock indices, forex, daily data
- **POLYMARKET** (forecasts): Prediction markets for forward-looking
- **FED_SEP** (Fed): FOMC projections, dot plot

## RESPONSE FORMAT

Return JSON:
```json
{{
    "intent": {{
        "core_question": "What is the user fundamentally asking?",
        "query_type": "factual|analytical|comparison|forecast|causal",
        "complexity": "simple|moderate|complex",
        "requires_interpretation": true/false
    }},
    "entities": {{
        "demographics": ["black", "women", etc.] or [],
        "regions": ["us", "eurozone", etc.] or [],
        "sectors": ["restaurants", "manufacturing", etc.] or [],
        "time_period": {{
            "type": "specific|relative|period|none",
            "value": "2023" or "recent" or "pre-covid" or null
        }}
    }},
    "routing": {{
        "primary_source": "fred|dbnomics|zillow|eia|alphavantage",
        "secondary_sources": ["polymarket", "fed_sep"],
        "is_comparison": true/false,
        "is_international": true/false,
        "is_demographic_specific": true/false,
        "is_sector_specific": true/false
    }},
    "data_requirements": {{
        "indicators_needed": ["unemployment rate", "job growth", etc.],
        "must_be_group_specific": true/false,
        "notes": "Any special requirements or warnings"
    }},
    "pitfalls": [
        "Don't use overall unemployment for demographic queries",
        "Compare YoY to YoY, not YoY to QoQ"
    ]
}}
```

## EXAMPLES

Query: "How are Black workers doing?"
```json
{{
    "intent": {{
        "core_question": "Economic status of Black workers in the labor market",
        "query_type": "analytical",
        "complexity": "moderate",
        "requires_interpretation": true
    }},
    "entities": {{
        "demographics": ["black"],
        "regions": ["us"],
        "sectors": [],
        "time_period": {{"type": "relative", "value": "recent"}}
    }},
    "routing": {{
        "primary_source": "fred",
        "secondary_sources": [],
        "is_comparison": false,
        "is_international": false,
        "is_demographic_specific": true,
        "is_sector_specific": false
    }},
    "data_requirements": {{
        "indicators_needed": ["Black unemployment rate", "Black employment rate", "Black labor force participation"],
        "must_be_group_specific": true,
        "notes": "MUST use Black-specific series only - never use overall UNRATE or women's data"
    }},
    "pitfalls": [
        "Do NOT use overall unemployment rate (UNRATE)",
        "Do NOT use women's employment data",
        "Use LNS14000006 for Black unemployment, not LNS14000002 (women)"
    ]
}}
```

Query: "US vs Eurozone GDP growth"
```json
{{
    "intent": {{
        "core_question": "Compare economic growth rates between US and Eurozone",
        "query_type": "comparison",
        "complexity": "moderate",
        "requires_interpretation": true
    }},
    "entities": {{
        "demographics": [],
        "regions": ["us", "eurozone"],
        "sectors": [],
        "time_period": {{"type": "relative", "value": "recent"}}
    }},
    "routing": {{
        "primary_source": "fred",
        "secondary_sources": ["dbnomics"],
        "is_comparison": true,
        "is_international": true,
        "is_demographic_specific": false,
        "is_sector_specific": false
    }},
    "data_requirements": {{
        "indicators_needed": ["US real GDP growth YoY", "Eurozone real GDP growth YoY"],
        "must_be_group_specific": false,
        "notes": "MUST compare same measure type - both YoY real growth, not QoQ vs YoY"
    }},
    "pitfalls": [
        "Compare YoY to YoY, not YoY to QoQ",
        "Use real (inflation-adjusted) for both, not nominal vs real",
        "Eurozone data is from DBnomics, not FRED"
    ]
}}
```

Be thorough. This understanding drives all downstream decisions.
"""


def _get_understanding_cache_key(query: str) -> str:
    """Generate cache key for query understanding."""
    # Normalize query for better cache hits
    normalized = query.lower().strip().rstrip('?').strip()
    return f"understanding:{normalized}"


def _get_cached_understanding(cache_key: str) -> Optional[Dict]:
    """Get cached understanding result if still valid."""
    if cache_key in _understanding_cache:
        result, timestamp = _understanding_cache[cache_key]
        if datetime.now() - timestamp < _understanding_cache_ttl:
            return result
        else:
            del _understanding_cache[cache_key]
    return None


def _set_understanding_cache(cache_key: str, result: Dict) -> None:
    """Cache an understanding result."""
    _understanding_cache[cache_key] = (result, datetime.now())
    # Limit cache size to prevent unbounded growth
    if len(_understanding_cache) > 200:
        # Remove oldest 50 entries
        oldest_keys = sorted(
            _understanding_cache.keys(),
            key=lambda k: _understanding_cache[k][1]
        )[:50]
        for k in oldest_keys:
            del _understanding_cache[k]


def understand_query(query: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Deeply understand a query before any routing or data fetching.

    OPTIMIZED: Results are cached for 1 hour to avoid repeated Gemini calls.
    Cache hit rate expected: 50-70% in typical sessions.

    This is the "thinking first" step that should run before:
    - Checking pre-computed plans
    - Running economist reasoning
    - Routing to data sources

    Args:
        query: The user's raw query string
        verbose: Whether to print debug output

    Returns:
        A structured understanding dict with:
        - intent: What the user is really asking
        - entities: Demographics, regions, sectors, time periods mentioned
        - routing: What data sources and paths to use
        - data_requirements: What indicators are needed
        - pitfalls: Potential issues to avoid
    """
    # Check cache first (saves 5-8s per cache hit)
    cache_key = _get_understanding_cache_key(query)
    cached_result = _get_cached_understanding(cache_key)
    if cached_result:
        if verbose:
            print(f"  [QueryUnderstanding] Cache hit for: {query}")
        return cached_result

    if verbose:
        print(f"  [QueryUnderstanding] Analyzing: {query}")

    # Call Gemini for deep understanding
    result = _call_gemini_understanding(query)

    if not result:
        # Fallback to rule-based understanding
        if verbose:
            print(f"  [QueryUnderstanding] Gemini failed, using rule-based fallback")
        # IMPORTANT: Still validate the rule-based result to add secondary sources
        result = _rule_based_understanding(query)
        result = _validate_understanding(result, query)
        # Cache the fallback result too
        _set_understanding_cache(cache_key, result)
        return result

    # Validate and enrich the result
    result = _validate_understanding(result, query)

    if verbose:
        print(f"  [QueryUnderstanding] Intent: {result.get('intent', {}).get('core_question', 'Unknown')}")
        print(f"  [QueryUnderstanding] Type: {result.get('intent', {}).get('query_type', 'Unknown')}")
        print(f"  [QueryUnderstanding] Primary source: {result.get('routing', {}).get('primary_source', 'fred')}")
        if result.get('entities', {}).get('demographics'):
            print(f"  [QueryUnderstanding] Demographics: {result['entities']['demographics']}")

    # Cache the result before returning
    _set_understanding_cache(cache_key, result)
    return result


def _call_gemini_understanding(query: str, retries: int = 2) -> Optional[Dict]:
    """
    Call Gemini to deeply understand the query.

    Uses Gemini 2.0 Flash for speed while maintaining quality.
    """
    if not GEMINI_API_KEY:
        return None

    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}'

    prompt = UNDERSTANDING_PROMPT.format(query=query)

    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.2,  # Low temperature for consistent analysis
            'maxOutputTokens': 1200
        }
    }
    headers = {'Content-Type': 'application/json'}

    for attempt in range(retries):
        try:
            req = Request(url, data=json.dumps(payload).encode('utf-8'),
                         headers=headers, method='POST')
            with urlopen(req, timeout=20) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result['candidates'][0]['content']['parts'][0]['text']
                return _extract_json(content)
        except Exception as e:
            if attempt == retries - 1:
                print(f"  [QueryUnderstanding] Gemini ERROR: {e}")
                return None
    return None


def _extract_json(text: str) -> Optional[Dict]:
    """Extract JSON from Gemini response."""
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


def _validate_understanding(understanding: Dict, query: str) -> Dict:
    """
    Validate and enrich the understanding result.

    Ensures required fields exist and applies additional rules.
    """
    # Ensure required structure
    if 'intent' not in understanding:
        understanding['intent'] = {
            'core_question': query,
            'query_type': 'analytical',
            'complexity': 'moderate',
            'requires_interpretation': True
        }

    if 'entities' not in understanding:
        understanding['entities'] = {
            'demographics': [],
            'regions': [],
            'sectors': [],
            'time_period': {'type': 'none', 'value': None}
        }

    if 'routing' not in understanding:
        understanding['routing'] = {
            'primary_source': 'fred',
            'secondary_sources': [],
            'is_comparison': False,
            'is_international': False,
            'is_demographic_specific': False,
            'is_sector_specific': False
        }

    if 'data_requirements' not in understanding:
        understanding['data_requirements'] = {
            'indicators_needed': [],
            'must_be_group_specific': False,
            'notes': ''
        }

    if 'pitfalls' not in understanding:
        understanding['pitfalls'] = []

    # Apply additional validation rules
    query_lower = query.lower()

    # If demographics are mentioned, enforce demographic-specific requirement
    demographics = understanding['entities'].get('demographics', [])
    if demographics:
        understanding['routing']['is_demographic_specific'] = True
        understanding['data_requirements']['must_be_group_specific'] = True

        # Add pitfall warnings based on demographics
        if 'black' in demographics or 'african american' in demographics:
            if "Do NOT use women's employment data" not in understanding['pitfalls']:
                understanding['pitfalls'].append("Do NOT use women's employment data for Black workers query")
        if 'women' in demographics or 'female' in demographics:
            if "Do NOT use Black/Hispanic employment data" not in understanding['pitfalls']:
                understanding['pitfalls'].append("Do NOT use Black/Hispanic employment data for women's query")

    # Check for comparison keywords
    comparison_keywords = ['vs', 'versus', 'compared to', 'compare', 'relative to']
    if any(kw in query_lower for kw in comparison_keywords):
        understanding['routing']['is_comparison'] = True
        understanding['intent']['query_type'] = 'comparison'

    # Check for international regions
    intl_regions = ['eurozone', 'europe', 'uk', 'china', 'japan', 'germany', 'canada', 'mexico', 'india', 'brazil']
    if any(region in query_lower for region in intl_regions):
        understanding['routing']['is_international'] = True
        if 'dbnomics' not in understanding['routing'].get('secondary_sources', []):
            understanding['routing']['secondary_sources'] = understanding['routing'].get('secondary_sources', []) + ['dbnomics']

    # Check for housing/rent queries -> Zillow might be better
    housing_keywords = ['rent', 'market rent', 'actual rent', 'zillow', 'home value', 'home price']
    if any(kw in query_lower for kw in housing_keywords):
        if 'zillow' not in understanding['routing'].get('secondary_sources', []):
            understanding['routing']['secondary_sources'] = understanding['routing'].get('secondary_sources', []) + ['zillow']

    # Check for forecast queries -> Polymarket/Fed SEP might help
    forecast_keywords = ['will', 'going to', 'predict', 'forecast', 'future', 'expect', 'coming']
    if any(kw in query_lower for kw in forecast_keywords):
        understanding['intent']['query_type'] = 'forecast'
        if 'polymarket' not in understanding['routing'].get('secondary_sources', []):
            understanding['routing']['secondary_sources'] = understanding['routing'].get('secondary_sources', []) + ['polymarket']

    # Check for Fed-related queries
    fed_keywords = ['fed', 'fomc', 'dot plot', 'rate path', 'powell', 'federal reserve']
    if any(kw in query_lower for kw in fed_keywords):
        if 'fed_sep' not in understanding['routing'].get('secondary_sources', []):
            understanding['routing']['secondary_sources'] = understanding['routing'].get('secondary_sources', []) + ['fed_sep']

    return understanding


def _rule_based_understanding(query: str) -> Dict:
    """
    Fallback rule-based understanding when Gemini is unavailable.

    Uses pattern matching to extract basic understanding.
    """
    query_lower = query.lower()

    # Initialize result structure
    result = {
        'intent': {
            'core_question': query,
            'query_type': 'analytical',
            'complexity': 'moderate',
            'requires_interpretation': True
        },
        'entities': {
            'demographics': [],
            'regions': ['us'],
            'sectors': [],
            'time_period': {'type': 'relative', 'value': 'recent'}
        },
        'routing': {
            'primary_source': 'fred',
            'secondary_sources': [],
            'is_comparison': False,
            'is_international': False,
            'is_demographic_specific': False,
            'is_sector_specific': False
        },
        'data_requirements': {
            'indicators_needed': [],
            'must_be_group_specific': False,
            'notes': 'Rule-based fallback - may be less accurate'
        },
        'pitfalls': []
    }

    # Detect demographics
    demographic_patterns = {
        'black': ['black', 'african american', 'african-american'],
        'hispanic': ['hispanic', 'latino', 'latina'],
        'women': ['women', 'female', 'woman'],
        'men': ['men', 'male', 'man '],
        'youth': ['youth', 'young', 'teen', 'teenage'],
        'veteran': ['veteran'],
        'immigrant': ['immigrant', 'foreign-born', 'foreign born']
    }

    for demo_key, patterns in demographic_patterns.items():
        if any(p in query_lower for p in patterns):
            result['entities']['demographics'].append(demo_key)
            result['routing']['is_demographic_specific'] = True
            result['data_requirements']['must_be_group_specific'] = True

    # Detect regions
    intl_regions = {
        'eurozone': ['eurozone', 'euro zone', 'euro area', 'europe'],
        'uk': ['uk', 'britain', 'united kingdom', 'england'],
        'china': ['china', 'chinese'],
        'japan': ['japan', 'japanese'],
        'germany': ['germany', 'german']
    }

    for region, patterns in intl_regions.items():
        if any(p in query_lower for p in patterns):
            result['entities']['regions'].append(region)
            result['routing']['is_international'] = True
            result['routing']['secondary_sources'].append('dbnomics')

    # Detect sectors
    sector_patterns = {
        'manufacturing': ['manufacturing', 'factory', 'factories'],
        'construction': ['construction', 'building'],
        'restaurants': ['restaurant', 'food service', 'dining'],
        'retail': ['retail', 'store', 'shops'],
        'tech': ['tech', 'technology', 'software', 'semiconductor'],
        'healthcare': ['healthcare', 'health care', 'medical', 'hospital']
    }

    for sector, patterns in sector_patterns.items():
        if any(p in query_lower for p in patterns):
            result['entities']['sectors'].append(sector)
            result['routing']['is_sector_specific'] = True

    # Detect energy queries -> add EIA (keeps FRED as primary for broader context)
    # Queries like "oil prices and inflation" get BOTH EIA oil data + FRED CPI
    energy_keywords = [
        'oil', 'crude', 'petroleum', 'gasoline', 'gas prices', 'diesel',
        'natural gas', 'henry hub', 'wti', 'brent', 'energy prices',
        'fuel', 'electricity', 'power prices', 'oil inventory', 'oil stocks',
        'crude stocks', 'oil production'
    ]
    if any(kw in query_lower for kw in energy_keywords):
        # Add EIA as secondary - FRED stays primary for related economic context
        if 'eia' not in result['routing']['secondary_sources']:
            result['routing']['secondary_sources'].append('eia')

    # Detect stock market queries -> add Alpha Vantage (keeps FRED for context)
    # Queries like "stock market and unemployment" get BOTH sources
    market_keywords = [
        'stock market', 'stocks', 's&p', 's&p 500', 'sp500', 'nasdaq',
        'dow jones', 'dow', 'djia', 'russell', 'small cap', 'spy', 'qqq',
        'vix', 'volatility index', 'stock index', 'equity market', 'equities'
    ]
    if any(kw in query_lower for kw in market_keywords):
        # Add Alpha Vantage as secondary - FRED has SP500, DJIA too
        if 'alphavantage' not in result['routing']['secondary_sources']:
            result['routing']['secondary_sources'].append('alphavantage')

    # Detect housing/rent queries -> add Zillow (FRED has CPI shelter, permits, etc.)
    housing_keywords = [
        'rent', 'rents', 'rental', 'market rent', 'actual rent', 'zillow',
        'home value', 'home price', 'house price', 'zori', 'zhvi'
    ]
    if any(kw in query_lower for kw in housing_keywords):
        if 'zillow' not in result['routing']['secondary_sources']:
            result['routing']['secondary_sources'].append('zillow')

    # Detect query type
    if any(kw in query_lower for kw in ['vs', 'versus', 'compared to', 'compare']):
        result['intent']['query_type'] = 'comparison'
        result['routing']['is_comparison'] = True
    elif any(kw in query_lower for kw in ['what is', 'what\'s the', 'current']):
        result['intent']['query_type'] = 'factual'
    elif any(kw in query_lower for kw in ['will', 'going to', 'coming', 'predict']):
        result['intent']['query_type'] = 'forecast'
        result['routing']['secondary_sources'].append('polymarket')

    return result


def validate_series_for_query(query_understanding: Dict, proposed_series: list) -> Dict:
    """
    Validate that proposed series match the query intent.

    This is the "gut check" layer - if Gemini detected demographics but
    the routing returned generic series, we override with correct ones.

    Args:
        query_understanding: The Gemini analysis of the query
        proposed_series: List of FRED series IDs from routing

    Returns:
        Dict with:
        - valid: bool - whether the series are appropriate
        - corrected_series: list - correct series if invalid
        - reason: str - explanation of why correction was needed
    """
    if not query_understanding:
        return {'valid': True, 'corrected_series': None, 'reason': None}

    routing = query_understanding.get('routing', {})
    entities = query_understanding.get('entities', {})
    demographics = entities.get('demographics', [])

    # If not demographic-specific, no validation needed
    if not routing.get('is_demographic_specific') and not demographics:
        return {'valid': True, 'corrected_series': None, 'reason': None}

    # Map demographics to their FRED series
    DEMOGRAPHIC_SERIES = {
        'women': {
            'unemployment': 'LNS14000002',
            'lfpr': 'LNS11300002',
            'epop': 'LNS12300002',
            'series': ['LNS14000002', 'LNS11300002', 'LNS12300002']
        },
        'female': {
            'unemployment': 'LNS14000002',
            'lfpr': 'LNS11300002',
            'epop': 'LNS12300002',
            'series': ['LNS14000002', 'LNS11300002', 'LNS12300002']
        },
        'men': {
            'unemployment': 'LNS14000001',
            'lfpr': 'LNS11300001',
            'epop': 'LNS12300001',
            'series': ['LNS14000001', 'LNS11300001', 'LNS12300001']
        },
        'male': {
            'unemployment': 'LNS14000001',
            'lfpr': 'LNS11300001',
            'epop': 'LNS12300001',
            'series': ['LNS14000001', 'LNS11300001', 'LNS12300001']
        },
        'black': {
            'unemployment': 'LNS14000006',
            'lfpr': 'LNS11300006',
            'epop': 'LNS12300006',
            'series': ['LNS14000006', 'LNS11300006', 'LNS12300006']
        },
        'african american': {
            'unemployment': 'LNS14000006',
            'lfpr': 'LNS11300006',
            'epop': 'LNS12300006',
            'series': ['LNS14000006', 'LNS11300006', 'LNS12300006']
        },
        'hispanic': {
            'unemployment': 'LNS14000009',
            'lfpr': 'LNS11300009',
            'epop': 'LNS12300009',
            'series': ['LNS14000009', 'LNS11300009', 'LNS12300009']
        },
        'latino': {
            'unemployment': 'LNS14000009',
            'lfpr': 'LNS11300009',
            'epop': 'LNS12300009',
            'series': ['LNS14000009', 'LNS11300009', 'LNS12300009']
        },
        'asian': {
            'unemployment': 'LNS14000004',
            'lfpr': 'LNS11300004',
            'epop': 'LNS12300004',
            'series': ['LNS14000004', 'LNS11300004', 'LNS12300004']
        },
        'youth': {
            'unemployment': 'LNS14000012',
            'lfpr': 'LNS11300012',
            'series': ['LNS14000012', 'LNS14000036']
        },
        'teen': {
            'unemployment': 'LNS14000012',
            'series': ['LNS14000012']
        },
        'veteran': {
            'unemployment': 'LNS14049526',
            'series': ['LNS14049526']
        }
    }

    # Generic series that should NOT be used for demographic queries
    GENERIC_SERIES = {'UNRATE', 'PAYEMS', 'LNS12300060', 'CIVPART', 'EMRATIO'}

    # Check if any detected demographic has appropriate series
    for demo in demographics:
        demo_lower = demo.lower()
        if demo_lower in DEMOGRAPHIC_SERIES:
            expected_series = set(DEMOGRAPHIC_SERIES[demo_lower]['series'])
            proposed_set = set(proposed_series)

            # Check if proposed series includes ANY demographic-specific series
            has_demographic_series = bool(expected_series & proposed_set)

            # Check if proposed series is mostly generic
            generic_count = len(proposed_set & GENERIC_SERIES)
            is_mostly_generic = generic_count > 0 and not has_demographic_series

            if is_mostly_generic or not has_demographic_series:
                return {
                    'valid': False,
                    'corrected_series': DEMOGRAPHIC_SERIES[demo_lower]['series'],
                    'reason': f"Query is about {demo} but routing returned generic series. Using {demo}-specific data instead.",
                    'demographic': demo
                }

    return {'valid': True, 'corrected_series': None, 'reason': None}


def get_routing_recommendation(understanding: Dict) -> Dict:
    """
    Based on the query understanding, recommend the routing path.

    This helps app.py decide:
    - Should we use pre-computed plans?
    - Should we use comparison routing?
    - Should we use international data?
    - Should we add supplementary sources?

    Returns:
        Dict with routing recommendations
    """
    routing = understanding.get('routing', {})
    entities = understanding.get('entities', {})
    intent = understanding.get('intent', {})

    recommendations = {
        # Primary routing decisions
        'use_comparison_router': routing.get('is_comparison', False),
        'use_international_data': routing.get('is_international', False),
        'require_demographic_filter': routing.get('is_demographic_specific', False),
        'require_sector_filter': routing.get('is_sector_specific', False),

        # Data sources to query
        'data_sources': {
            'primary': routing.get('primary_source', 'fred'),
            'secondary': routing.get('secondary_sources', [])
        },

        # Filters to apply
        'demographic_filter': entities.get('demographics', []),
        'sector_filter': entities.get('sectors', []),
        'region_filter': entities.get('regions', []),

        # Query metadata
        'query_type': intent.get('query_type', 'analytical'),
        'complexity': intent.get('complexity', 'moderate'),

        # Warnings
        'pitfalls': understanding.get('pitfalls', [])
    }

    return recommendations


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    test_queries = [
        "How are Black workers doing?",
        "US vs Eurozone GDP",
        "What is the Fed funds rate?",
        "Is a recession coming?",
        "How is the restaurant industry doing?",
        "Women's employment trends",
        "Compare China and US growth",
        "What's happening with market rents?",
    ]

    print("=" * 70)
    print("QUERY UNDERSTANDING TEST")
    print("=" * 70)

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print("-" * 40)

        understanding = understand_query(query, verbose=True)

        # Print key insights
        print(f"\nKey Insights:")
        print(f"  Query Type: {understanding.get('intent', {}).get('query_type')}")
        print(f"  Demographics: {understanding.get('entities', {}).get('demographics', [])}")
        print(f"  Regions: {understanding.get('entities', {}).get('regions', [])}")
        print(f"  Sectors: {understanding.get('entities', {}).get('sectors', [])}")
        print(f"  Is Comparison: {understanding.get('routing', {}).get('is_comparison')}")
        print(f"  Pitfalls: {understanding.get('pitfalls', [])[:2]}")
