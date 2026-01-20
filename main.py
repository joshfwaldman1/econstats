"""
EconStats - FastAPI + HTMX + Tailwind version
A clean, modern frontend for economic data exploration.
"""

import os
import json
import httpx
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from anthropic import Anthropic

# Initialize
app = FastAPI(title="EconStats")
templates = Jinja2Templates(directory="templates")

# API Keys
FRED_API_KEY = os.environ.get('FRED_API_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

# Load query plans from existing JSON files
def load_query_plans():
    plans = {}
    plan_files = [
        'agents/plans_economy_overview.json',
        'agents/plans_inflation.json',
        'agents/plans_employment.json',
        'agents/plans_gdp.json',
        'agents/plans_housing.json',
    ]
    for pf in plan_files:
        if os.path.exists(pf):
            with open(pf) as f:
                plans.update(json.load(f))
    return plans

QUERY_PLANS = load_query_plans()

# NBER Recession dates (for chart shading)
RECESSIONS = [
    ('1948-11-01', '1949-10-01'),
    ('1953-07-01', '1954-05-01'),
    ('1957-08-01', '1958-04-01'),
    ('1960-04-01', '1961-02-01'),
    ('1969-12-01', '1970-11-01'),
    ('1973-11-01', '1975-03-01'),
    ('1980-01-01', '1980-07-01'),
    ('1981-07-01', '1982-11-01'),
    ('1990-07-01', '1991-03-01'),
    ('2001-03-01', '2001-11-01'),
    ('2007-12-01', '2009-06-01'),
    ('2020-02-01', '2020-04-01'),
]

# Series metadata (subset for prototype)
SERIES_DB = {
    'PAYEMS': {'name': 'Total Nonfarm Payrolls', 'unit': 'Thousands of Persons', 'show_yoy': False},
    'UNRATE': {'name': 'Unemployment Rate', 'unit': 'Percent', 'show_yoy': False},
    'A191RO1Q156NBEA': {'name': 'Real GDP Growth', 'unit': 'Percent Change', 'show_yoy': False},
    'CPIAUCSL': {'name': 'Consumer Price Index', 'unit': 'Index 1982-84=100', 'show_yoy': True},
    'FEDFUNDS': {'name': 'Federal Funds Rate', 'unit': 'Percent', 'show_yoy': False},
    'DGS10': {'name': '10-Year Treasury Rate', 'unit': 'Percent', 'show_yoy': False},
    'MORTGAGE30US': {'name': '30-Year Mortgage Rate', 'unit': 'Percent', 'show_yoy': False},
}


def normalize_query(query: str) -> str:
    """Normalize query for matching."""
    import re
    q = query.lower().strip()
    fillers = [
        r'^what is\s+', r'^what are\s+', r'^show me\s+', r'^show\s+',
        r'^tell me about\s+', r'^how is\s+', r'^how are\s+',
        r'^what\'s\s+', r'^whats\s+', r'^give me\s+',
        r'\?$', r'\.+$', r'\s+the\s+', r'^the\s+'
    ]
    for filler in fillers:
        q = re.sub(filler, ' ', q)
    q = ' '.join(q.split()).strip()
    return q


def find_query_plan(query: str):
    """Find matching query plan."""
    normalized = normalize_query(query)
    original_lower = query.lower().strip()

    if original_lower in QUERY_PLANS:
        return QUERY_PLANS[original_lower]
    if normalized in QUERY_PLANS:
        return QUERY_PLANS[normalized]

    # Fuzzy match
    import difflib
    matches = difflib.get_close_matches(normalized, list(QUERY_PLANS.keys()), n=1, cutoff=0.6)
    if matches:
        return QUERY_PLANS[matches[0]]

    return None


def get_fred_data(series_id: str, years: int = None) -> tuple:
    """Fetch data from FRED API."""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        'series_id': series_id,
        'api_key': FRED_API_KEY,
        'file_type': 'json',
        'sort_order': 'asc',
    }

    if years:
        start = datetime.now() - timedelta(days=years * 365)
        params['observation_start'] = start.strftime('%Y-%m-%d')

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
            data = resp.json()

        observations = data.get('observations', [])
        dates = []
        values = []
        for obs in observations:
            if obs['value'] != '.':
                dates.append(obs['date'])
                values.append(float(obs['value']))

        # Get series info
        info_url = "https://api.stlouisfed.org/fred/series"
        info_params = {'series_id': series_id, 'api_key': FRED_API_KEY, 'file_type': 'json'}
        with httpx.Client(timeout=10) as client:
            info_resp = client.get(info_url, params=info_params)
            info_data = info_resp.json()

        info = info_data.get('seriess', [{}])[0]
        db_info = SERIES_DB.get(series_id, {})
        info['name'] = db_info.get('name', info.get('title', series_id))
        info['unit'] = db_info.get('unit', info.get('units', ''))

        return dates, values, info
    except Exception as e:
        print(f"FRED error for {series_id}: {e}")
        return [], [], {}


def calculate_yoy(dates: list, values: list) -> tuple:
    """Calculate year-over-year percent change."""
    if len(dates) < 13:
        return dates, values

    yoy_dates = []
    yoy_values = []
    for i in range(12, len(values)):
        if values[i - 12] != 0:
            pct = ((values[i] - values[i - 12]) / abs(values[i - 12])) * 100
            yoy_dates.append(dates[i])
            yoy_values.append(round(pct, 2))
    return yoy_dates, yoy_values


def get_ai_summary(query: str, series_data: list) -> str:
    """Get AI-generated summary from Claude."""
    if not ANTHROPIC_API_KEY:
        return "Economic data loaded successfully."

    # Build context
    context_parts = []
    for sid, dates, values, info in series_data:
        if values:
            latest = values[-1]
            latest_date = dates[-1]
            name = info.get('name', sid)
            unit = info.get('unit', '')
            context_parts.append(f"- {name} ({sid}): {latest:.2f} {unit} as of {latest_date}")

    context = "\n".join(context_parts)

    prompt = f"""You are an economist writing a brief summary for a general audience.

User asked: "{query}"

Current data:
{context}

Write a 2-3 sentence summary that:
1. Directly answers their question
2. Mentions specific numbers
3. Provides context (is this good/bad, up/down from last year)

Be concise and avoid jargon. No bullet points - just flowing prose."""

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        print(f"Claude error: {e}")
        return "Economic data loaded successfully."


def get_recessions_in_range(min_date: str, max_date: str) -> list:
    """Get recession periods that overlap with the date range."""
    recessions = []
    for start, end in RECESSIONS:
        if end >= min_date and start <= max_date:
            recessions.append({
                'start': max(start, min_date),
                'end': min(end, max_date),
            })
    return recessions


def format_chart_data(series_data: list) -> list:
    """Format series data for Plotly.js on the frontend."""
    charts = []
    for sid, dates, values, info in series_data:
        if not values:
            continue

        # Calculate latest value and change
        latest = values[-1]
        latest_date = dates[-1]

        # YoY change if enough data
        yoy_change = None
        if len(values) >= 13:
            prev = values[-13]
            if prev != 0:
                yoy_change = ((latest - prev) / abs(prev)) * 100

        # Get recessions for this date range
        recessions = get_recessions_in_range(dates[0], dates[-1]) if dates else []

        charts.append({
            'series_id': sid,
            'name': info.get('name', sid),
            'unit': info.get('unit', ''),
            'dates': dates,
            'values': values,
            'latest': latest,
            'latest_date': latest_date,
            'yoy_change': yoy_change,
            'recessions': recessions,
        })

    return charts


# Routes

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Landing page."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "examples": [
            "How is the economy?",
            "What's the unemployment rate?",
            "Is inflation coming down?",
            "Are we in a recession?",
        ]
    })


@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, query: str = Form(...)):
    """Handle search query - returns HTMX partial."""

    # Find query plan
    plan = find_query_plan(query)

    if plan:
        series_ids = plan.get('series', [])[:4]
        show_yoy = plan.get('show_yoy', False)
    else:
        # Default to economy overview
        series_ids = ['PAYEMS', 'UNRATE', 'A191RO1Q156NBEA', 'CPIAUCSL']
        show_yoy = [False, False, False, True]

    # Fetch data
    series_data = []
    for i, sid in enumerate(series_ids):
        dates, values, info = get_fred_data(sid)
        if dates and values:
            # Apply YoY if needed
            apply_yoy = False
            if isinstance(show_yoy, list) and i < len(show_yoy):
                apply_yoy = show_yoy[i]
            elif isinstance(show_yoy, bool):
                apply_yoy = show_yoy
            elif SERIES_DB.get(sid, {}).get('show_yoy', False):
                apply_yoy = True

            if apply_yoy and len(dates) > 12:
                dates, values = calculate_yoy(dates, values)
                info['name'] = info.get('name', sid) + ' (YoY %)'
                info['unit'] = '% Change YoY'

            series_data.append((sid, dates, values, info))

    # Get AI summary
    summary = get_ai_summary(query, series_data)

    # Format for frontend
    charts = format_chart_data(series_data)

    # Related questions based on context
    query_lower = query.lower()
    if 'job' in query_lower or 'employ' in query_lower or 'economy' in query_lower:
        related = [("Recession risk?", "recession risk"), ("Wages vs inflation?", "wages vs inflation")]
    elif 'inflation' in query_lower or 'cpi' in query_lower:
        related = [("Are wages keeping up?", "wages vs inflation"), ("Fed funds rate?", "fed funds rate")]
    elif 'gdp' in query_lower or 'growth' in query_lower:
        related = [("Is a recession coming?", "recession risk"), ("Job market?", "job market")]
    else:
        related = [("How is the economy?", "how is the economy"), ("Inflation?", "inflation")]

    return templates.TemplateResponse("partials/results.html", {
        "request": request,
        "query": query,
        "summary": summary,
        "charts": charts,
        "related": related,
    })


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    """About page."""
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
