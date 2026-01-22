#!/usr/bin/env python3
"""
RAG-based FRED series retrieval.

Architecture:
1. Embed descriptions of FRED series
2. User query → embed → find similar series via cosine similarity
3. LLM picks best 2-4 from candidates

This approach reduces prompt complexity and lets the LLM focus on
selection rather than recall.
"""

import json
import os
import numpy as np
from pathlib import Path
from urllib.request import urlopen, Request
from typing import List, Dict, Optional, Tuple

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# =============================================================================
# FRED SERIES CATALOG
# Curated list of important series with semantic descriptions
# =============================================================================

FRED_SERIES_CATALOG = [
    # === EMPLOYMENT - GENERAL ===
    {"id": "PAYEMS", "name": "Total Nonfarm Payrolls",
     "description": "Total number of jobs in the US economy excluding farm workers. The headline jobs number reported monthly. Shows how many jobs were added or lost."},
    {"id": "UNRATE", "name": "Unemployment Rate (U-3)",
     "description": "Percentage of the labor force that is unemployed and actively seeking work. The headline unemployment rate."},
    {"id": "U6RATE", "name": "Unemployment Rate (U-6)",
     "description": "Broader unemployment rate including discouraged workers and those working part-time for economic reasons."},
    {"id": "CIVPART", "name": "Labor Force Participation Rate",
     "description": "Percentage of working-age population either employed or actively looking for work."},
    {"id": "LNS12300060", "name": "Prime-Age Employment-Population Ratio",
     "description": "Percentage of people aged 25-54 who are employed. Best measure of labor market health, avoids retirement effects."},
    {"id": "JTSJOL", "name": "Job Openings (JOLTS)",
     "description": "Number of job openings available. Measures labor demand and how many positions employers are trying to fill."},
    {"id": "JTSQUR", "name": "Quits Rate",
     "description": "Rate at which workers voluntarily quit their jobs. High quits signal worker confidence in finding new jobs."},
    {"id": "ICSA", "name": "Initial Jobless Claims",
     "description": "Weekly count of new unemployment insurance claims. Most timely indicator of layoffs and labor market stress."},
    {"id": "CCSA", "name": "Continuing Jobless Claims",
     "description": "Number of people continuing to receive unemployment benefits. Shows how long people stay unemployed."},

    # === EMPLOYMENT - BY GENDER ===
    {"id": "LNS14000001", "name": "Unemployment Rate - Men",
     "description": "Unemployment rate for men. Male-specific labor market indicator."},
    {"id": "LNS14000002", "name": "Unemployment Rate - Women",
     "description": "Unemployment rate for women. Female-specific labor market indicator."},
    {"id": "LNS12300061", "name": "Prime-Age Employment Ratio - Men",
     "description": "Employment-population ratio for men aged 25-54. Best measure of men's labor market health."},
    {"id": "LNS12300062", "name": "Prime-Age Employment Ratio - Women",
     "description": "Employment-population ratio for women aged 25-54. Best measure of women's labor market health."},
    {"id": "LNS11300001", "name": "Labor Force Participation - Men",
     "description": "Labor force participation rate for men. Share of men working or looking for work."},
    {"id": "LNS11300002", "name": "Labor Force Participation - Women",
     "description": "Labor force participation rate for women. Share of women working or looking for work."},

    # === EMPLOYMENT - BY RACE ===
    {"id": "LNS14000003", "name": "Unemployment Rate - White",
     "description": "Unemployment rate for White workers. White-specific labor market indicator."},
    {"id": "LNS14000006", "name": "Unemployment Rate - Black",
     "description": "Unemployment rate for Black or African American workers. Black-specific labor market indicator."},
    {"id": "LNS14000009", "name": "Unemployment Rate - Hispanic",
     "description": "Unemployment rate for Hispanic or Latino workers. Hispanic-specific labor market indicator."},
    {"id": "LNS14032183", "name": "Unemployment Rate - Asian",
     "description": "Unemployment rate for Asian workers. Asian-specific labor market indicator."},

    # === EMPLOYMENT - IMMIGRANTS / FOREIGN-BORN ===
    {"id": "LNU04073395", "name": "Unemployment Rate - Foreign Born",
     "description": "Unemployment rate for foreign-born workers, immigrants. Immigrant-specific labor market indicator."},
    {"id": "LNU02073395", "name": "Employment Level - Foreign Born",
     "description": "Number of employed foreign-born workers, immigrants. Total immigrant employment."},
    {"id": "LNU01373395", "name": "Labor Force - Foreign Born",
     "description": "Foreign-born labor force, immigrants in workforce. Total immigrants working or seeking work."},
    {"id": "LNU04073413", "name": "Unemployment Rate - Native Born",
     "description": "Unemployment rate for native-born workers. US-born labor market indicator for comparison with immigrants."},
    {"id": "LNU02073413", "name": "Employment Level - Native Born",
     "description": "Number of employed native-born workers. US-born employment for comparison."},

    # === EMPLOYMENT - BY AGE ===
    {"id": "LNS14000012", "name": "Unemployment Rate - 16-19 years",
     "description": "Unemployment rate for teenagers aged 16-19. Youth labor market indicator."},
    {"id": "LNS14000036", "name": "Unemployment Rate - 20-24 years",
     "description": "Unemployment rate for young adults aged 20-24. Young worker labor market."},
    {"id": "LNS14000089", "name": "Unemployment Rate - 25-54 years",
     "description": "Unemployment rate for prime-age workers 25-54. Core working-age labor market."},
    {"id": "LNS14000091", "name": "Unemployment Rate - 55 and over",
     "description": "Unemployment rate for older workers 55+. Older worker labor market indicator."},

    # === EMPLOYMENT - BY SECTOR ===
    {"id": "MANEMP", "name": "Manufacturing Employment",
     "description": "Total employment in manufacturing sector. Factory jobs, industrial employment."},
    {"id": "USCONS", "name": "Construction Employment",
     "description": "Total employment in construction sector. Building, infrastructure jobs."},
    {"id": "USTRADE", "name": "Retail Trade Employment",
     "description": "Total employment in retail trade. Store workers, retail jobs."},
    {"id": "USFIRE", "name": "Financial Services Employment",
     "description": "Employment in finance, insurance, real estate. Banking, financial sector jobs."},
    {"id": "USEHS", "name": "Education and Health Services Employment",
     "description": "Employment in education and healthcare. Teachers, nurses, hospital workers."},
    {"id": "USLAH", "name": "Leisure and Hospitality Employment",
     "description": "Employment in leisure and hospitality. Hotels, restaurants, entertainment, tourism jobs."},
    {"id": "USINFO", "name": "Information Sector Employment",
     "description": "Employment in information sector. Tech, media, telecommunications jobs."},
    {"id": "USPBS", "name": "Professional and Business Services Employment",
     "description": "Employment in professional services. Consulting, legal, accounting, business services."},
    {"id": "USGOVT", "name": "Government Employment",
     "description": "Total government employment. Federal, state, local government workers."},
    {"id": "CES3133440001", "name": "Semiconductor Manufacturing Employment",
     "description": "Employment in semiconductor and electronic component manufacturing. Chip makers, electronics manufacturing jobs."},

    # === WAGES AND EARNINGS ===
    {"id": "CES0500000003", "name": "Average Hourly Earnings",
     "description": "Average hourly earnings for all private employees. Wage growth, pay levels."},
    {"id": "AHETPI", "name": "Average Hourly Earnings - Production Workers",
     "description": "Average hourly earnings for production and nonsupervisory workers. Blue-collar wages."},
    {"id": "LES1252881600Q", "name": "Median Weekly Earnings",
     "description": "Real median weekly earnings for full-time workers. Inflation-adjusted middle-class wages."},
    {"id": "MEPAINUSA672N", "name": "Median Personal Income",
     "description": "Median personal income in the US. Middle-class income levels."},

    # === INFLATION AND PRICES ===
    {"id": "CPIAUCSL", "name": "Consumer Price Index (CPI)",
     "description": "Consumer price index for all urban consumers. Headline inflation, cost of living."},
    {"id": "CPILFESL", "name": "Core CPI",
     "description": "CPI excluding food and energy. Core inflation, underlying price pressures."},
    {"id": "PCEPI", "name": "PCE Price Index",
     "description": "Personal consumption expenditures price index. Fed's preferred inflation measure."},
    {"id": "PCEPILFE", "name": "Core PCE",
     "description": "Core PCE excluding food and energy. The Fed's 2% inflation target measure."},
    {"id": "CUSR0000SAH1", "name": "CPI - Shelter",
     "description": "Consumer price index for shelter, housing costs. Rent and housing inflation."},
    {"id": "CUSR0000SAF11", "name": "CPI - Food at Home",
     "description": "Consumer price index for groceries. Food prices, grocery inflation."},
    {"id": "CUSR0000SEFV", "name": "CPI - Food Away from Home",
     "description": "Consumer price index for restaurants and dining out. Restaurant prices, eating out costs."},
    {"id": "CUSR0000SETB01", "name": "CPI - Gasoline",
     "description": "Consumer price index for gasoline. Gas prices, fuel costs."},
    {"id": "GASREGW", "name": "Regular Gas Price",
     "description": "Average price of regular gasoline per gallon. Pump prices, fuel costs."},

    # === GDP AND ECONOMIC GROWTH ===
    {"id": "GDPC1", "name": "Real GDP",
     "description": "Real gross domestic product. Total economic output, size of the economy."},
    {"id": "A191RL1Q225SBEA", "name": "Real GDP Growth (Quarterly)",
     "description": "Quarterly GDP growth rate, annualized. Economic growth, expansion or contraction."},
    {"id": "A191RO1Q156NBEA", "name": "Real GDP Growth (Year-over-Year)",
     "description": "GDP growth compared to same quarter last year. Annual economic growth rate."},
    {"id": "INDPRO", "name": "Industrial Production Index",
     "description": "Industrial production index. Manufacturing output, factory production."},
    {"id": "TCU", "name": "Capacity Utilization",
     "description": "Total capacity utilization rate. How much of productive capacity is being used."},

    # === INTEREST RATES ===
    {"id": "FEDFUNDS", "name": "Federal Funds Rate",
     "description": "Federal funds effective rate. The Fed's policy interest rate, overnight lending rate."},
    {"id": "DGS10", "name": "10-Year Treasury Yield",
     "description": "10-year Treasury constant maturity rate. Long-term interest rates, bond yields."},
    {"id": "DGS2", "name": "2-Year Treasury Yield",
     "description": "2-year Treasury constant maturity rate. Short-term rates, Fed policy expectations."},
    {"id": "T10Y2Y", "name": "10Y-2Y Treasury Spread",
     "description": "Spread between 10-year and 2-year Treasury yields. Yield curve, recession indicator when inverted."},
    {"id": "MORTGAGE30US", "name": "30-Year Mortgage Rate",
     "description": "30-year fixed mortgage rate. Home loan rates, housing affordability."},
    {"id": "MORTGAGE15US", "name": "15-Year Mortgage Rate",
     "description": "15-year fixed mortgage rate. Shorter-term home loan rates."},

    # === HOUSING ===
    {"id": "CSUSHPINSA", "name": "Case-Shiller Home Price Index",
     "description": "S&P/Case-Shiller national home price index. House prices, real estate values."},
    {"id": "MSPUS", "name": "Median Home Sales Price",
     "description": "Median sales price of houses sold. Typical home price, housing costs."},
    {"id": "HOUST", "name": "Housing Starts",
     "description": "New residential construction starts. Home building activity, new housing supply."},
    {"id": "PERMIT", "name": "Building Permits",
     "description": "New private housing units authorized by permits. Future construction pipeline."},
    {"id": "EXHOSLUSM495S", "name": "Existing Home Sales",
     "description": "Existing home sales. Housing market activity, home buying volume."},
    {"id": "NHSUSSPT", "name": "New Home Sales",
     "description": "New single-family home sales. New construction sales volume."},
    {"id": "RRVRUSQ156N", "name": "Rental Vacancy Rate",
     "description": "Rental vacancy rate. Empty rental units, rental market tightness."},

    # === CONSUMER ===
    {"id": "UMCSENT", "name": "Consumer Sentiment",
     "description": "University of Michigan consumer sentiment index. Consumer confidence, economic optimism."},
    {"id": "PCE", "name": "Personal Consumption Expenditures",
     "description": "Total personal consumption expenditures. Consumer spending, household purchases."},
    {"id": "RSAFS", "name": "Retail Sales",
     "description": "Advance retail sales. Consumer spending at stores, shopping activity."},
    {"id": "PSAVERT", "name": "Personal Saving Rate",
     "description": "Personal saving rate as percentage of income. How much households save."},
    {"id": "TOTALSL", "name": "Consumer Credit",
     "description": "Total consumer credit outstanding. Consumer debt, borrowing levels."},
    {"id": "DSPIC96", "name": "Real Disposable Income",
     "description": "Real disposable personal income. Inflation-adjusted income after taxes."},

    # === TRADE AND INTERNATIONAL ===
    {"id": "BOPGSTB", "name": "Trade Balance",
     "description": "US trade balance in goods and services. Exports minus imports, trade deficit."},
    {"id": "EXPGS", "name": "Exports",
     "description": "US exports of goods and services. What America sells abroad."},
    {"id": "IMPGS", "name": "Imports",
     "description": "US imports of goods and services. What America buys from abroad."},
    {"id": "DTWEXBGS", "name": "Dollar Index",
     "description": "Trade-weighted US dollar index. Dollar strength against trading partners."},

    # === FINANCIAL MARKETS ===
    {"id": "SP500", "name": "S&P 500",
     "description": "S&P 500 stock market index. Stock prices, equity market performance."},
    {"id": "NASDAQCOM", "name": "NASDAQ Composite",
     "description": "NASDAQ composite index. Tech stocks, technology sector performance."},
    {"id": "DJIA", "name": "Dow Jones Industrial Average",
     "description": "Dow Jones Industrial Average. Blue-chip stocks, industrial companies."},
    {"id": "VIXCLS", "name": "VIX Volatility Index",
     "description": "CBOE volatility index, the fear gauge. Market uncertainty, expected volatility."},

    # === RECESSION INDICATORS ===
    {"id": "SAHMREALTIME", "name": "Sahm Rule Recession Indicator",
     "description": "Sahm rule recession indicator. Signals recession when unemployment rises quickly."},
    {"id": "BBKMLEIX", "name": "Chicago Fed Leading Index",
     "description": "Brave-Butters-Kelley leading index. Forecasts future economic growth."},
    {"id": "USREC", "name": "NBER Recession Indicator",
     "description": "NBER recession indicator. Official recession dating, economic contractions."},
    {"id": "T10Y3M", "name": "10Y-3M Treasury Spread",
     "description": "Spread between 10-year Treasury and 3-month bill. Yield curve inversion, recession predictor."},

    # === COMMODITIES ===
    {"id": "DCOILWTICO", "name": "Crude Oil Price (WTI)",
     "description": "West Texas Intermediate crude oil price. Oil prices, energy costs."},
    {"id": "DCOILBRENTEU", "name": "Crude Oil Price (Brent)",
     "description": "Brent crude oil price. International oil benchmark."},
    {"id": "GOLDAMGBD228NLBM", "name": "Gold Price",
     "description": "Gold price per troy ounce. Gold prices, precious metals, safe haven."},

    # === GOVERNMENT AND DEBT ===
    {"id": "GFDEBTN", "name": "Federal Debt",
     "description": "Total federal government debt. National debt, government borrowing."},
    {"id": "FYFSD", "name": "Federal Surplus/Deficit",
     "description": "Federal government budget surplus or deficit. Government spending vs revenue."},
    {"id": "FGEXPND", "name": "Federal Government Spending",
     "description": "Total federal government expenditures. Government spending levels."},
    {"id": "FGRECPT", "name": "Federal Government Revenue",
     "description": "Total federal government receipts. Tax revenue, government income."},
]

# =============================================================================
# EMBEDDING FUNCTIONS
# =============================================================================

_embeddings_cache = {}
_catalog_embeddings = None

def get_embedding(text: str) -> np.ndarray:
    """Get embedding for a text string using OpenAI's API."""
    if text in _embeddings_cache:
        return _embeddings_cache[text]

    url = 'https://api.openai.com/v1/embeddings'
    payload = {
        'model': 'text-embedding-3-small',
        'input': text
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }

    try:
        req = Request(url, data=json.dumps(payload).encode('utf-8'),
                     headers=headers, method='POST')
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            embedding = np.array(result['data'][0]['embedding'])
            _embeddings_cache[text] = embedding
            return embedding
    except Exception as e:
        print(f"Embedding error: {e}")
        return None


def get_batch_embeddings(texts: List[str]) -> List[np.ndarray]:
    """Get embeddings for multiple texts in one API call."""
    url = 'https://api.openai.com/v1/embeddings'
    payload = {
        'model': 'text-embedding-3-small',
        'input': texts
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }

    try:
        req = Request(url, data=json.dumps(payload).encode('utf-8'),
                     headers=headers, method='POST')
        with urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            embeddings = [np.array(d['embedding']) for d in result['data']]
            return embeddings
    except Exception as e:
        print(f"Batch embedding error: {e}")
        return None


def build_catalog_embeddings():
    """Build embeddings for all series in the catalog."""
    global _catalog_embeddings

    if _catalog_embeddings is not None:
        return _catalog_embeddings

    # Check if cached embeddings exist
    cache_path = Path(__file__).parent / 'series_embeddings.json'
    if cache_path.exists():
        with open(cache_path) as f:
            cached = json.load(f)
            _catalog_embeddings = {
                item['id']: np.array(item['embedding'])
                for item in cached
            }
            return _catalog_embeddings

    print("Building embeddings for FRED series catalog...")

    # Create search text for each series
    texts = []
    for series in FRED_SERIES_CATALOG:
        search_text = f"{series['name']}. {series['description']}"
        texts.append(search_text)

    # Get embeddings in batch
    embeddings = get_batch_embeddings(texts)

    if embeddings:
        _catalog_embeddings = {}
        cache_data = []
        for series, embedding in zip(FRED_SERIES_CATALOG, embeddings):
            _catalog_embeddings[series['id']] = embedding
            cache_data.append({
                'id': series['id'],
                'embedding': embedding.tolist()
            })

        # Cache to file
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f)

        print(f"Built embeddings for {len(_catalog_embeddings)} series")

    return _catalog_embeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


# =============================================================================
# RAG RETRIEVAL
# =============================================================================

def retrieve_relevant_series(query: str, top_k: int = 15) -> List[Dict]:
    """
    Retrieve the most relevant FRED series for a query using semantic search.

    Args:
        query: User's question
        top_k: Number of candidates to return

    Returns:
        List of series dicts with similarity scores
    """
    # Ensure catalog embeddings are built
    catalog_embeddings = build_catalog_embeddings()
    if not catalog_embeddings:
        return []

    # Get query embedding
    query_embedding = get_embedding(query)
    if query_embedding is None:
        return []

    # Compute similarities
    similarities = []
    for series in FRED_SERIES_CATALOG:
        series_embedding = catalog_embeddings.get(series['id'])
        if series_embedding is not None:
            sim = cosine_similarity(query_embedding, series_embedding)
            similarities.append({
                **series,
                'similarity': sim
            })

    # Sort by similarity and return top-k
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    return similarities[:top_k]


# =============================================================================
# LLM SELECTION FROM CANDIDATES
# =============================================================================

def select_best_series(query: str, candidates: List[Dict], num_series: int = 4) -> Dict:
    """
    Have an LLM select the best series from retrieved candidates.

    Args:
        query: User's original question
        candidates: List of candidate series from retrieval
        num_series: Target number of series to select

    Returns:
        Dict with selected series and explanation
    """
    # Format candidates for the prompt
    candidate_text = "\n".join([
        f"- {c['id']}: {c['name']} - {c['description']}"
        for c in candidates
    ])

    prompt = f"""You are an expert economist. A user asked: "{query}"

Here are relevant FRED series candidates (retrieved by semantic search):

{candidate_text}

Select the {num_series} BEST series that directly answer the user's question.

CRITICAL RULES:
1. For demographic questions (immigrants, women, Black workers, etc.), ONLY use demographic-specific series. DO NOT use aggregate series like UNRATE or PAYEMS.
2. For "how is X doing?" questions, cover multiple dimensions: employment + wages + relevant prices if applicable.
3. Each series should add unique insight - no redundant measures.

Return JSON only:
{{
    "series": ["ID1", "ID2", "ID3", "ID4"],
    "explanation": "Brief explanation of why these series answer the question",
    "show_yoy": false,
    "combine_chart": false
}}"""

    # Use GPT-4 for selection (good at following instructions)
    url = 'https://api.openai.com/v1/chat/completions'
    payload = {
        'model': 'gpt-4o',
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 500,
        'temperature': 0.3
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }

    try:
        req = Request(url, data=json.dumps(payload).encode('utf-8'),
                     headers=headers, method='POST')
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            content = result['choices'][0]['message']['content']

            # Extract JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]

            return json.loads(content.strip())
    except Exception as e:
        print(f"Selection error: {e}")
        # Fallback: return top candidates
        return {
            'series': [c['id'] for c in candidates[:num_series]],
            'explanation': f"Top matches for: {query}",
            'show_yoy': False,
            'combine_chart': False
        }


# =============================================================================
# MAIN RAG FUNCTION
# =============================================================================

def rag_query_plan(query: str, verbose: bool = False) -> Dict:
    """
    Generate a query plan using RAG: retrieve relevant series, then select best ones.

    Args:
        query: User's question
        verbose: Whether to print progress

    Returns:
        Query plan dict with series, explanation, etc.
    """
    if verbose:
        print(f"RAG query plan for: {query}")

    # Step 1: Retrieve candidates via semantic search
    if verbose:
        print("  Retrieving candidates...")
    candidates = retrieve_relevant_series(query, top_k=15)

    if verbose:
        print(f"  Found {len(candidates)} candidates:")
        for c in candidates[:5]:
            print(f"    {c['id']}: {c['name']} (sim: {c['similarity']:.3f})")

    if not candidates:
        return {
            'series': [],
            'search_terms': [query],
            'explanation': 'No matching series found',
            'show_yoy': False,
            'combine_chart': False
        }

    # Step 2: Have LLM select best series from candidates
    if verbose:
        print("  Selecting best series...")
    result = select_best_series(query, candidates)

    if verbose:
        print(f"  Selected: {result.get('series', [])}")

    # Ensure all expected fields exist
    result.setdefault('search_terms', [])
    result.setdefault('show_yoy', False)
    result.setdefault('show_mom', False)
    result.setdefault('show_avg_annual', False)
    result.setdefault('combine_chart', False)
    result.setdefault('is_followup', False)
    result.setdefault('add_to_previous', False)
    result.setdefault('keep_previous_series', False)

    return result


# =============================================================================
# TEST
# =============================================================================

def test_rag():
    """Test RAG retrieval with sample queries."""
    test_queries = [
        "How is the economy for immigrants?",
        "How are restaurants doing?",
        "What's happening with women in the labor market?",
        "Is inflation coming down?",
        "Are we heading into a recession?",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print('='*60)
        result = rag_query_plan(query, verbose=True)
        print(f"\nFinal plan:")
        print(f"  Series: {result['series']}")
        print(f"  Explanation: {result['explanation']}")


if __name__ == "__main__":
    test_rag()
