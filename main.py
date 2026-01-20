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
    'PAYEMS': {'name': 'Nonfarm Payrolls', 'unit': 'Thousands of Persons', 'show_yoy': False, 'sa': True, 'source': 'U.S. Bureau of Labor Statistics'},
    'UNRATE': {'name': 'Unemployment Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': True, 'source': 'U.S. Bureau of Labor Statistics'},
    'A191RO1Q156NBEA': {'name': 'Real GDP Growth', 'unit': 'Percent Change', 'show_yoy': False, 'sa': True, 'source': 'U.S. Bureau of Economic Analysis'},
    'CPIAUCSL': {'name': 'Consumer Price Index', 'unit': 'Index 1982-84=100', 'show_yoy': True, 'sa': True, 'source': 'U.S. Bureau of Labor Statistics'},
    'FEDFUNDS': {'name': 'Federal Funds Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': False, 'source': 'Board of Governors of the Federal Reserve System'},
    'DGS10': {'name': '10-Year Treasury Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': False, 'source': 'Board of Governors of the Federal Reserve System'},
    'MORTGAGE30US': {'name': '30-Year Mortgage Rate', 'unit': 'Percent', 'show_yoy': False, 'sa': False, 'source': 'Freddie Mac'},
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
        # Keep FRED notes for AI context (already in info from API response)

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


def get_ai_summary(query: str, series_data: list, conversation_history: list = None) -> dict:
    """Get AI-generated summary, chart descriptions, and follow-up suggestions from Claude."""
    # Build series IDs list for default response
    series_ids = [sid for sid, dates, values, info in series_data if values]

    default_response = {
        "summary": "Economic data loaded successfully.",
        "suggestions": ["How is inflation trending?", "What's the unemployment rate?"],
        "chart_descriptions": {sid: "" for sid in series_ids}
    }

    if not ANTHROPIC_API_KEY:
        return default_response

    # Build context with current values
    context_parts = []
    for sid, dates, values, info in series_data:
        if values:
            latest = values[-1]
            latest_date = dates[-1]
            name = info.get('name', sid)
            unit = info.get('unit', '')
            context_parts.append(f"- {name} ({sid}): {latest:.2f} {unit} as of {latest_date}")

    context = "\n".join(context_parts)

    # Build background info from FRED notes
    background_parts = []
    for sid, dates, values, info in series_data:
        notes = info.get('notes', '')
        if notes:
            name = info.get('name', sid)
            # Truncate very long notes
            if len(notes) > 500:
                notes = notes[:500] + "..."
            background_parts.append(f"**{name} ({sid})**: {notes}")

    background = "\n\n".join(background_parts) if background_parts else ""

    # Build conversation context if this is a follow-up
    conv_context = ""
    if conversation_history:
        conv_parts = []
        for item in conversation_history[-3:]:  # Last 3 exchanges max
            conv_parts.append(f"User: {item.get('query', '')}")
            conv_parts.append(f"Assistant: {item.get('summary', '')}")
        conv_context = "Previous conversation:\n" + "\n".join(conv_parts) + "\n\n"

    # Build chart descriptions format hint
    chart_desc_format = ", ".join([f'"{sid}": "description"' for sid in series_ids])

    prompt = f"""You are an economist assistant helping users explore U.S. economic data.

{conv_context}User asked: "{query}"

Current data:
{context}

{"Background on these indicators (from FRED):" + chr(10) + background if background else ""}

Respond with JSON in exactly this format:
{{
  "summary": "Your 2-3 sentence summary answering their question with specific numbers and context.",
  "chart_descriptions": {{{chart_desc_format}}},
  "suggestions": ["First follow-up question?", "Second follow-up question?"]
}}

Guidelines:
- Summary: Be concise, avoid jargon, use flowing prose (no bullets). Directly answer their question.
- Chart descriptions: For EACH series, write 1-2 sentences explaining what this indicator measures and why it matters in the context of their question. Make it educational but accessible.
- Suggestions: Ask specific, relevant follow-ups (e.g., "How does this compare to pre-pandemic levels?" not "What is GDP?")

Return only valid JSON, no other text."""

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(response.content[0].text)
        return {
            "summary": result.get("summary", default_response["summary"]),
            "suggestions": result.get("suggestions", default_response["suggestions"])[:2],
            "chart_descriptions": result.get("chart_descriptions", default_response["chart_descriptions"])
        }
    except Exception as e:
        print(f"Claude error: {e}")
        return default_response


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

        # Special handling for PAYEMS - show monthly job gains, not level
        # PAYEMS is in thousands, so MoM change is jobs added in thousands
        display_value = latest
        display_unit = info.get('unit', '')
        is_job_change = False

        if sid == 'PAYEMS' and len(values) >= 2:
            mom_change = values[-1] - values[-2]  # Monthly change in thousands
            display_value = mom_change
            display_unit = 'Monthly Job Gains (Thousands)'
            is_job_change = True
            # Calculate 3-month average for context
            if len(values) >= 4:
                three_mo_avg = (values[-1] - values[-4]) / 3
            else:
                three_mo_avg = mom_change
        else:
            three_mo_avg = None

        # YoY change if enough data (skip for job change display)
        yoy_change = None
        if not is_job_change and len(values) >= 13:
            prev = values[-13]
            if prev != 0:
                yoy_change = ((latest - prev) / abs(prev)) * 100
        elif is_job_change and len(values) >= 13:
            # For payrolls, show YoY total jobs added
            yoy_jobs_added = values[-1] - values[-13]
            yoy_change = yoy_jobs_added  # Store as raw number, not percent

        # Get recessions for this date range
        recessions = get_recessions_in_range(dates[0], dates[-1]) if dates else []

        # Get source and seasonal adjustment info
        db_info = SERIES_DB.get(sid, {})
        source = db_info.get('source', 'FRED')
        sa = db_info.get('sa', False)

        # Get FRED notes for educational content
        notes = info.get('notes', '')
        # Clean up notes - take first 2-3 sentences for brevity
        if notes:
            sentences = notes.replace('\n', ' ').split('. ')
            notes = '. '.join(sentences[:3]) + ('.' if len(sentences) > 0 else '')

        charts.append({
            'series_id': sid,
            'name': info.get('name', sid),
            'unit': display_unit,
            'dates': dates,
            'values': values,
            'latest': display_value,  # For PAYEMS, this is MoM change
            'latest_date': latest_date,
            'yoy_change': yoy_change,
            'recessions': recessions,
            'source': source,
            'sa': sa,
            'notes': notes,
            'is_job_change': is_job_change,
            'three_mo_avg': three_mo_avg,
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
async def search(request: Request, query: str = Form(...), history: str = Form(default="")):
    """Handle search query - returns HTMX partial."""

    # Parse conversation history from JSON
    conversation_history = []
    if history:
        try:
            conversation_history = json.loads(history)
        except json.JSONDecodeError:
            pass

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

    # Get AI summary and suggestions
    ai_response = get_ai_summary(query, series_data, conversation_history)
    summary = ai_response["summary"]
    suggestions = ai_response["suggestions"]
    chart_descriptions = ai_response.get("chart_descriptions", {})

    # Format for frontend
    charts = format_chart_data(series_data)

    # Add Claude's descriptions to each chart
    for chart in charts:
        chart['description'] = chart_descriptions.get(chart['series_id'], '')

    # Update conversation history for next request
    new_history = conversation_history + [{"query": query, "summary": summary}]
    # Keep last 5 exchanges
    new_history = new_history[-5:]

    return templates.TemplateResponse("partials/results.html", {
        "request": request,
        "query": query,
        "summary": summary,
        "charts": charts,
        "suggestions": suggestions,
        "history": json.dumps(new_history),
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
