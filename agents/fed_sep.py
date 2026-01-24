"""
Federal Reserve Summary of Economic Projections (SEP) Integration.

Fetches and parses FOMC economic projections from the Fed's website.
SEP is released quarterly (March, June, September, December meetings).

Data includes median and range projections for:
- Real GDP growth
- Unemployment rate
- PCE inflation
- Core PCE inflation
- Federal funds rate
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser

# =============================================================================
# SEP MEETING DATES (updated quarterly)
# =============================================================================

# FOMC meetings with SEP releases (month/day format)
# SEP is released at March, June, September, December meetings
SEP_MEETINGS = [
    (3, 19),   # March
    (6, 18),   # June
    (9, 17),   # September
    (12, 18),  # December
]

# Cache for SEP data (refreshed daily max)
_sep_cache: Dict = {}
_sep_cache_time: Optional[datetime] = None
SEP_CACHE_TTL = timedelta(hours=24)


# =============================================================================
# HTML PARSER FOR SEP TABLES
# =============================================================================

class SEPTableParser(HTMLParser):
    """Parse SEP projection tables from Fed HTML."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_row = []
        self.tables = []
        self.current_table = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
            self.current_table = []
        elif tag == 'tr' and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ('td', 'th') and self.in_row:
            self.in_cell = True

    def handle_endtag(self, tag):
        if tag == 'table':
            if self.current_table:
                self.tables.append(self.current_table)
            self.in_table = False
            self.current_table = []
        elif tag == 'tr':
            if self.current_row:
                self.current_table.append(self.current_row)
            self.in_row = False
            self.current_row = []
        elif tag in ('td', 'th'):
            self.in_cell = False

    def handle_data(self, data):
        if self.in_cell:
            text = data.strip()
            if text:
                self.current_row.append(text)


# =============================================================================
# SEP DATA FETCHING
# =============================================================================

def get_latest_sep_url() -> Tuple[str, str]:
    """
    Get URL for most recent SEP release.

    Returns:
        (url, meeting_date) tuple
    """
    now = datetime.now()

    # Build list of candidate dates going back 2 years
    candidates = []
    for year in [now.year, now.year - 1, now.year - 2]:
        for month, day in SEP_MEETINGS:
            meeting_date = datetime(year, month, day)
            if meeting_date <= now:
                candidates.append(meeting_date)

    # Sort by most recent first
    candidates.sort(reverse=True)

    # Try each candidate URL until one works
    for meeting_date in candidates[:4]:  # Only try last 4 meetings
        date_str = meeting_date.strftime('%Y%m%d')
        url = f"https://www.federalreserve.gov/monetarypolicy/fomcprojtabl{date_str}.htm"

        # Quick check if URL exists
        try:
            req = Request(url, method='HEAD', headers={
                'User-Agent': 'Mozilla/5.0 (compatible; EconStats/1.0)',
            })
            with urlopen(req, timeout=5) as response:
                if response.status == 200:
                    return url, meeting_date.strftime('%B %Y')
        except:
            continue

    # Fallback to known good URL (December 2024)
    return "https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20241218.htm", "December 2024"


def fetch_sep_html(url: str) -> Optional[str]:
    """Fetch SEP HTML from Fed website."""
    try:
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; EconStats/1.0)',
            'Accept': 'text/html',
        })
        with urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8')
    except (HTTPError, URLError) as e:
        print(f"[SEP] Error fetching {url}: {e}")
        return None


def parse_sep_tables(html: str) -> Dict:
    """
    Parse SEP HTML into structured data.

    Returns dict with projections for each variable.
    """
    parser = SEPTableParser()
    parser.feed(html)

    projections = {
        'gdp': {},
        'unemployment': {},
        'pce_inflation': {},
        'core_pce': {},
        'fed_funds': {},
    }

    # Map table headers to our keys
    variable_map = {
        'change in real gdp': 'gdp',
        'real gdp': 'gdp',
        'unemployment rate': 'unemployment',
        'pce inflation': 'pce_inflation',
        'core pce inflation': 'core_pce',
        'core pce': 'core_pce',
        'federal funds rate': 'fed_funds',
    }

    for table in parser.tables:
        if not table:
            continue

        # Try to identify which variable this table is for
        current_var = None
        years = []

        for row in table:
            row_text = ' '.join(row).lower()

            # Check if this row identifies the variable
            for key_phrase, var_name in variable_map.items():
                if key_phrase in row_text:
                    current_var = var_name
                    break

            # Look for year headers
            year_pattern = re.findall(r'\b(202\d|longer\s*run)\b', row_text, re.IGNORECASE)
            if year_pattern and len(year_pattern) >= 3:
                years = [y.lower().replace(' ', '_') for y in year_pattern]

            # Look for median projections
            if current_var and years and 'median' in row_text:
                # Extract numeric values
                values = []
                for cell in row:
                    # Match numbers like 2.5, 4.2, etc.
                    match = re.search(r'(\d+\.?\d*)', cell)
                    if match:
                        values.append(float(match.group(1)))

                # Map values to years
                if values:
                    for i, year in enumerate(years):
                        if i < len(values):
                            projections[current_var][year] = {
                                'median': values[i],
                            }

    return projections


def get_sep_data(force_refresh: bool = False) -> Dict:
    """
    Get current SEP projections.

    Returns structured projection data with caching.
    """
    global _sep_cache, _sep_cache_time

    # Check cache
    if not force_refresh and _sep_cache and _sep_cache_time:
        if datetime.now() - _sep_cache_time < SEP_CACHE_TTL:
            return _sep_cache

    url, meeting_date = get_latest_sep_url()
    html = fetch_sep_html(url)

    if not html:
        # Return hardcoded fallback (December 2024 SEP)
        return get_fallback_sep()

    projections = parse_sep_tables(html)

    # If parsing failed, use fallback
    if not any(projections[k] for k in projections):
        return get_fallback_sep()

    result = {
        'meeting_date': meeting_date,
        'source_url': url,
        'projections': projections,
        'fetched_at': datetime.now().isoformat(),
    }

    # Cache it
    _sep_cache = result
    _sep_cache_time = datetime.now()

    return result


def get_fallback_sep() -> Dict:
    """
    Hardcoded SEP data as fallback when scraping fails.
    Updated from December 2024 FOMC meeting.
    """
    return {
        'meeting_date': 'December 2024',
        'source_url': 'https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20241218.htm',
        'projections': {
            'gdp': {
                '2024': {'median': 2.5, 'range': (2.3, 2.7)},
                '2025': {'median': 2.1, 'range': (1.6, 2.5)},
                '2026': {'median': 2.0, 'range': (1.4, 2.5)},
                '2027': {'median': 1.9, 'range': (1.5, 2.5)},
                'longer_run': {'median': 1.8, 'range': (1.7, 2.5)},
            },
            'unemployment': {
                '2024': {'median': 4.2, 'range': (4.2, 4.2)},
                '2025': {'median': 4.3, 'range': (4.2, 4.5)},
                '2026': {'median': 4.3, 'range': (3.9, 4.6)},
                '2027': {'median': 4.3, 'range': (3.8, 4.5)},
                'longer_run': {'median': 4.2, 'range': (3.5, 4.5)},
            },
            'pce_inflation': {
                '2024': {'median': 2.4, 'range': (2.4, 2.7)},
                '2025': {'median': 2.5, 'range': (2.1, 2.9)},
                '2026': {'median': 2.1, 'range': (2.0, 2.6)},
                '2027': {'median': 2.0, 'range': (2.0, 2.4)},
                'longer_run': {'median': 2.0, 'range': (2.0, 2.0)},
            },
            'core_pce': {
                '2024': {'median': 2.8, 'range': (2.8, 2.9)},
                '2025': {'median': 2.5, 'range': (2.1, 3.2)},
                '2026': {'median': 2.2, 'range': (2.0, 2.7)},
                '2027': {'median': 2.0, 'range': (2.0, 2.6)},
            },
            'fed_funds': {
                '2024': {'median': 4.4, 'range': (4.4, 4.6)},
                '2025': {'median': 3.9, 'range': (3.1, 4.4)},
                '2026': {'median': 3.4, 'range': (2.4, 3.9)},
                '2027': {'median': 3.1, 'range': (2.4, 3.9)},
                'longer_run': {'median': 3.0, 'range': (2.4, 3.9)},
            },
        },
        'is_fallback': True,
    }


# =============================================================================
# QUERY INTERFACE
# =============================================================================

def is_sep_query(query: str) -> bool:
    """Check if query is asking about Fed projections/SEP."""
    query_lower = query.lower()

    sep_keywords = [
        'fed project', 'fed forecast', 'fed expect', 'fed predict',
        'fomc project', 'fomc forecast', 'fomc expect',
        'sep', 'summary of economic projections',
        'dot plot', 'rate path', 'rate projection',
        'where does the fed see', 'what does the fed expect',
        'fed outlook', 'fed\'s outlook', 'fed median',
        'how many rate cuts', 'how many cuts',
        'terminal rate', 'neutral rate',
        'inflation outlook', 'gdp outlook', 'economic outlook',
        'rate outlook', 'unemployment outlook',
    ]

    return any(kw in query_lower for kw in sep_keywords)


def get_sep_for_query(query: str) -> Optional[Dict]:
    """
    Get relevant SEP data based on query.

    Returns formatted data for display.
    """
    if not is_sep_query(query):
        return None

    sep_data = get_sep_data()
    query_lower = query.lower()

    # Determine which projections are relevant
    relevant_vars = []

    if any(w in query_lower for w in ['gdp', 'growth', 'economy', 'output']):
        relevant_vars.append('gdp')
    if any(w in query_lower for w in ['unemployment', 'jobs', 'labor']):
        relevant_vars.append('unemployment')
    if any(w in query_lower for w in ['inflation', 'pce', 'prices', 'cpi']):
        relevant_vars.extend(['pce_inflation', 'core_pce'])
    if any(w in query_lower for w in ['rate', 'fed funds', 'interest', 'cut', 'hike', 'dot plot', 'terminal', 'neutral']):
        relevant_vars.append('fed_funds')

    # If no specific variable mentioned, return all
    if not relevant_vars:
        relevant_vars = ['gdp', 'unemployment', 'pce_inflation', 'fed_funds']

    # Remove duplicates while preserving order
    relevant_vars = list(dict.fromkeys(relevant_vars))

    return {
        'meeting_date': sep_data['meeting_date'],
        'source_url': sep_data.get('source_url', ''),
        'projections': {k: sep_data['projections'].get(k, {}) for k in relevant_vars},
        'is_fallback': sep_data.get('is_fallback', False),
    }


def format_sep_for_display(sep_data: Dict) -> str:
    """
    Format SEP data for display in the UI.

    Returns a narrative explanation of Fed projections.
    """
    if not sep_data:
        return ""

    projections = sep_data.get('projections', {})
    meeting = sep_data.get('meeting_date', 'recent')

    sentences = []

    # GDP narrative
    if 'gdp' in projections:
        gdp = projections['gdp']
        gdp_2025 = gdp.get('2025', {}).get('median')
        gdp_lr = gdp.get('longer_run', {}).get('median')
        if gdp_2025:
            if gdp_lr and gdp_2025 > gdp_lr:
                sentences.append(f"FOMC participants expect GDP growth of {gdp_2025}% in 2025, gradually slowing toward the {gdp_lr}% long-run trend.")
            else:
                sentences.append(f"FOMC participants expect GDP growth of {gdp_2025}% in 2025.")

    # Unemployment narrative
    if 'unemployment' in projections:
        unemp = projections['unemployment']
        unemp_2025 = unemp.get('2025', {}).get('median')
        unemp_lr = unemp.get('longer_run', {}).get('median')
        if unemp_2025:
            if unemp_lr:
                diff = unemp_2025 - unemp_lr
                if abs(diff) < 0.2:
                    sentences.append(f"Unemployment is projected to hold steady around {unemp_2025}%, near the {unemp_lr}% long-run level.")
                elif diff > 0:
                    sentences.append(f"Unemployment is projected at {unemp_2025}% in 2025, slightly above the {unemp_lr}% long-run estimate.")
                else:
                    sentences.append(f"Unemployment is projected at {unemp_2025}% in 2025.")

    # Inflation narrative
    if 'pce_inflation' in projections or 'core_pce' in projections:
        pce = projections.get('pce_inflation', {})
        core = projections.get('core_pce', {})
        pce_2025 = pce.get('2025', {}).get('median')
        pce_2027 = pce.get('2027', {}).get('median')
        core_2025 = core.get('2025', {}).get('median')

        if pce_2025 and pce_2027:
            if pce_2025 > 2.0 and pce_2027 <= 2.0:
                sentences.append(f"Inflation is expected to remain elevated at {pce_2025}% in 2025 before returning to the 2% target by 2027.")
            elif pce_2025 > 2.0:
                sentences.append(f"Inflation is projected at {pce_2025}% in 2025, still above the 2% target.")
            else:
                sentences.append(f"Inflation is projected at {pce_2025}% in 2025.")
        elif core_2025:
            sentences.append(f"Core PCE inflation is projected at {core_2025}% in 2025.")

    # Fed funds narrative (most important for "dot plot" queries)
    if 'fed_funds' in projections:
        ff = projections['fed_funds']
        ff_2025 = ff.get('2025', {}).get('median')
        ff_2026 = ff.get('2026', {}).get('median')
        ff_lr = ff.get('longer_run', {}).get('median')

        if ff_2025 and ff_2026:
            cuts_2025 = round((4.4 - ff_2025) / 0.25)  # Assuming 4.4% current
            cuts_2026 = round((ff_2025 - ff_2026) / 0.25)

            if cuts_2025 > 0 and cuts_2026 > 0:
                sentences.append(f"The median dot plot shows the fed funds rate falling to {ff_2025}% by end of 2025 and {ff_2026}% by end of 2026—implying roughly {int(cuts_2025 + cuts_2026)} quarter-point cuts over two years.")
            elif ff_lr:
                sentences.append(f"The median fed funds rate projection is {ff_2025}% for 2025, with a long-run neutral rate of {ff_lr}%.")
            else:
                sentences.append(f"The median fed funds rate projection is {ff_2025}% for 2025.")
        elif ff_lr:
            sentences.append(f"The long-run neutral rate estimate is {ff_lr}%.")

    if not sentences:
        return ""

    # Combine into narrative
    narrative = " ".join(sentences)

    # Add source note
    if sep_data.get('is_fallback'):
        narrative += f" *(Based on {meeting} FOMC projections; more recent data may be available.)*"
    else:
        narrative += f" *({meeting} FOMC)*"

    return narrative


def get_sep_series_data(variable: str) -> Tuple[List[str], List[float], Dict]:
    """
    Get SEP projection as time series data (for charting).

    Args:
        variable: One of 'gdp', 'unemployment', 'pce_inflation', 'core_pce', 'fed_funds'

    Returns:
        (dates, values, info) tuple compatible with chart builder
    """
    sep_data = get_sep_data()
    projections = sep_data['projections'].get(variable, {})

    if not projections:
        return [], [], {'error': f'No SEP data for {variable}'}

    var_names = {
        'gdp': 'Real GDP Growth',
        'unemployment': 'Unemployment Rate',
        'pce_inflation': 'PCE Inflation',
        'core_pce': 'Core PCE Inflation',
        'fed_funds': 'Federal Funds Rate',
    }

    dates = []
    values = []

    # Convert year keys to dates (use Q4 of each year)
    year_order = ['2024', '2025', '2026', '2027', 'longer_run']

    for year in year_order:
        if year in projections:
            median = projections[year].get('median')
            if median is not None:
                if year == 'longer_run':
                    # Use 2030 as proxy for long run
                    dates.append('2030-12-31')
                else:
                    dates.append(f'{year}-12-31')
                values.append(median)

    info = {
        'id': f'sep_{variable}',
        'title': f'FOMC Projection: {var_names.get(variable, variable)}',
        'description': f'Median FOMC participant projection for {var_names.get(variable, variable).lower()}',
        'units': 'percent',
        'frequency': 'annual',
        'source': 'Federal Reserve',
        'source_url': sep_data.get('source_url', ''),
        'meeting_date': sep_data.get('meeting_date', ''),
        'is_projection': True,
    }

    return dates, values, info


# =============================================================================
# SERIES CATALOG ENTRIES
# =============================================================================

SEP_SERIES = {
    'sep_gdp': {
        'name': 'FOMC GDP Growth Projection',
        'variable': 'gdp',
        'description': 'Median FOMC projection for real GDP growth',
        'keywords': ['gdp projection', 'fed gdp forecast', 'growth outlook'],
    },
    'sep_unemployment': {
        'name': 'FOMC Unemployment Projection',
        'variable': 'unemployment',
        'description': 'Median FOMC projection for unemployment rate',
        'keywords': ['unemployment projection', 'fed jobs forecast'],
    },
    'sep_pce_inflation': {
        'name': 'FOMC PCE Inflation Projection',
        'variable': 'pce_inflation',
        'description': 'Median FOMC projection for PCE inflation',
        'keywords': ['inflation projection', 'fed inflation forecast'],
    },
    'sep_core_pce': {
        'name': 'FOMC Core PCE Projection',
        'variable': 'core_pce',
        'description': 'Median FOMC projection for core PCE inflation',
        'keywords': ['core inflation projection', 'fed core pce forecast'],
    },
    'sep_fed_funds': {
        'name': 'FOMC Fed Funds Rate Projection',
        'variable': 'fed_funds',
        'description': 'Median FOMC projection for federal funds rate (dot plot)',
        'keywords': ['dot plot', 'rate path', 'fed funds projection', 'terminal rate'],
    },
}


def search_sep_series(query: str) -> List[str]:
    """
    Search for SEP series matching a query.

    Returns list of matching series keys.
    """
    query_lower = query.lower()
    matches = []

    for key, info in SEP_SERIES.items():
        # Check keywords
        if any(kw in query_lower for kw in info['keywords']):
            matches.append(key)
            continue
        # Check name
        if any(word in info['name'].lower() for word in query_lower.split()):
            matches.append(key)

    return matches


# =============================================================================
# TEST
# =============================================================================

if __name__ == '__main__':
    print("Testing SEP integration...\n")

    # Test fetching data
    sep = get_sep_data()
    print(f"Meeting: {sep['meeting_date']}")
    print(f"Source: {sep.get('source_url', 'fallback')}")
    print(f"Is fallback: {sep.get('is_fallback', False)}")
    print()

    # Print projections
    for var, data in sep['projections'].items():
        if data:
            print(f"{var}:")
            for year, proj in sorted(data.items()):
                median = proj.get('median', 'N/A')
                print(f"  {year}: {median}%")
            print()

    # Test query matching
    test_queries = [
        "what does the fed expect for gdp",
        "dot plot",
        "fed rate projections",
        "how many rate cuts in 2025",
        "inflation outlook",
    ]

    print("Query matching:")
    for q in test_queries:
        is_sep = is_sep_query(q)
        print(f"  '{q}' -> {is_sep}")

    # Test formatted output
    print("\nFormatted output:")
    result = get_sep_for_query("what does the fed expect")
    print(format_sep_for_display(result))
