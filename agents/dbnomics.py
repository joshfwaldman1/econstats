"""
DBnomics integration for EconStats - International economic data.

DBnomics aggregates data from 80+ providers including IMF, Eurostat, ECB, OECD, World Bank.
This adds international coverage that FRED doesn't have.

API: https://api.db.nomics.world/v22/
"""

import json
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from datetime import datetime, timedelta
from typing import Optional

# Cache to avoid excessive API calls
_cache: dict = {}
_cache_ttl = timedelta(minutes=30)

DBNOMICS_API = "https://api.db.nomics.world/v22"

# Curated international series with full DBnomics IDs
# Format: provider/dataset/series_code
INTERNATIONAL_SERIES = {
    # === EUROZONE ===
    "eurozone_gdp": {
        "id": "Eurostat/namq_10_gdp/Q.CLV_PCH_PRE.SCA.B1GQ.EA20",
        "name": "Eurozone GDP Growth (QoQ)",
        "description": "Euro area quarterly GDP growth rate",
        "keywords": ["eurozone", "euro area", "europe", "gdp", "eu"],
        "provider": "Eurostat",
    },
    "eurozone_inflation": {
        "id": "Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA",
        "name": "Eurozone Inflation (HICP)",
        "description": "Euro area harmonized CPI annual change",
        "keywords": ["eurozone", "euro", "inflation", "hicp", "cpi", "europe"],
        "provider": "Eurostat",
    },
    "eurozone_unemployment": {
        "id": "Eurostat/une_rt_m/M.SA.TOTAL.PC_ACT.T.EA20",
        "name": "Eurozone Unemployment Rate",
        "description": "Euro area unemployment rate, seasonally adjusted",
        "keywords": ["eurozone", "unemployment", "europe", "jobs"],
        "provider": "Eurostat",
    },
    # === UK ===
    "uk_gdp": {
        "id": "BOE/GDP/IHYR.Q",
        "name": "UK GDP Growth",
        "description": "UK quarterly real GDP growth",
        "keywords": ["uk", "britain", "british", "gdp", "england"],
        "provider": "Bank of England",
    },
    "uk_inflation": {
        "id": "BOE/CPI/D7G7.M",
        "name": "UK Inflation (CPI)",
        "description": "UK Consumer Price Index annual rate",
        "keywords": ["uk", "britain", "inflation", "cpi"],
        "provider": "Bank of England",
    },
    "uk_bank_rate": {
        "id": "BOE/BANKRATE/IUMABEDR.D",
        "name": "Bank of England Rate",
        "description": "Bank of England official bank rate",
        "keywords": ["uk", "boe", "bank rate", "interest rate", "britain"],
        "provider": "Bank of England",
    },
    # === JAPAN ===
    "japan_gdp": {
        "id": "IMF/WEO:2024-10/JPN.NGDP_RPCH.pcent_change",
        "name": "Japan GDP Growth",
        "description": "Japan annual real GDP growth (IMF)",
        "keywords": ["japan", "japanese", "gdp", "asia"],
        "provider": "IMF",
    },
    "japan_inflation": {
        "id": "IMF/WEO:2024-10/JPN.PCPIPCH.pcent_change",
        "name": "Japan Inflation",
        "description": "Japan inflation rate (IMF)",
        "keywords": ["japan", "inflation", "cpi"],
        "provider": "IMF",
    },
    # === CHINA ===
    "china_gdp": {
        "id": "IMF/WEO:2024-10/CHN.NGDP_RPCH.pcent_change",
        "name": "China GDP Growth",
        "description": "China annual real GDP growth (IMF)",
        "keywords": ["china", "chinese", "gdp", "asia"],
        "provider": "IMF",
    },
    "china_inflation": {
        "id": "IMF/WEO:2024-10/CHN.PCPIPCH.pcent_change",
        "name": "China Inflation",
        "description": "China inflation rate (IMF)",
        "keywords": ["china", "inflation", "cpi"],
        "provider": "IMF",
    },
    # === GERMANY ===
    "germany_gdp": {
        "id": "IMF/WEO:2024-10/DEU.NGDP_RPCH.pcent_change",
        "name": "Germany GDP Growth",
        "description": "Germany annual real GDP growth",
        "keywords": ["germany", "german", "gdp", "europe"],
        "provider": "IMF",
    },
    "germany_unemployment": {
        "id": "Eurostat/une_rt_m/M.SA.TOTAL.PC_ACT.T.DE",
        "name": "Germany Unemployment Rate",
        "description": "Germany unemployment rate",
        "keywords": ["germany", "unemployment", "jobs"],
        "provider": "Eurostat",
    },
    # === CANADA ===
    "canada_gdp": {
        "id": "IMF/WEO:2024-10/CAN.NGDP_RPCH.pcent_change",
        "name": "Canada GDP Growth",
        "description": "Canada annual real GDP growth",
        "keywords": ["canada", "canadian", "gdp"],
        "provider": "IMF",
    },
    # === MEXICO ===
    "mexico_gdp": {
        "id": "IMF/WEO:2024-10/MEX.NGDP_RPCH.pcent_change",
        "name": "Mexico GDP Growth",
        "description": "Mexico annual real GDP growth",
        "keywords": ["mexico", "mexican", "gdp"],
        "provider": "IMF",
    },
    # === INDIA ===
    "india_gdp": {
        "id": "IMF/WEO:2024-10/IND.NGDP_RPCH.pcent_change",
        "name": "India GDP Growth",
        "description": "India annual real GDP growth",
        "keywords": ["india", "indian", "gdp"],
        "provider": "IMF",
    },
    # === BRAZIL ===
    "brazil_gdp": {
        "id": "IMF/WEO:2024-10/BRA.NGDP_RPCH.pcent_change",
        "name": "Brazil GDP Growth",
        "description": "Brazil annual real GDP growth",
        "keywords": ["brazil", "brazilian", "gdp"],
        "provider": "IMF",
    },
    # === ECB ===
    "ecb_rate": {
        "id": "ECB/FM/D.U2.EUR.4F.KR.MRR_FR.LEV",
        "name": "ECB Main Refinancing Rate",
        "description": "European Central Bank main policy rate",
        "keywords": ["ecb", "euro", "rate", "europe", "interest"],
        "provider": "ECB",
    },
}

# Query plans for international queries
INTERNATIONAL_QUERY_PLANS = {
    "eurozone economy": {
        "series": ["eurozone_gdp", "eurozone_inflation", "eurozone_unemployment"],
        "explanation": "Key Eurozone economic indicators.",
    },
    "how is europe doing": {
        "series": ["eurozone_gdp", "eurozone_inflation", "germany_gdp"],
        "explanation": "European economic indicators.",
    },
    "europe economy": {
        "series": ["eurozone_gdp", "eurozone_inflation", "germany_gdp"],
        "explanation": "European economic indicators.",
    },
    "uk economy": {
        "series": ["uk_gdp", "uk_inflation", "uk_bank_rate"],
        "explanation": "UK economic indicators.",
    },
    "how is the uk doing": {
        "series": ["uk_gdp", "uk_inflation", "uk_bank_rate"],
        "explanation": "UK economic indicators.",
    },
    "japan economy": {
        "series": ["japan_gdp", "japan_inflation"],
        "explanation": "Japan economic indicators from IMF.",
    },
    "how is japan doing": {
        "series": ["japan_gdp", "japan_inflation"],
        "explanation": "Japan economic indicators from IMF.",
    },
    "china economy": {
        "series": ["china_gdp", "china_inflation"],
        "explanation": "China economic indicators from IMF.",
    },
    "how is china doing": {
        "series": ["china_gdp", "china_inflation"],
        "explanation": "China economic indicators from IMF.",
    },
    "germany economy": {
        "series": ["germany_gdp", "germany_unemployment"],
        "explanation": "Germany economic indicators.",
    },
    "ecb rate": {
        "series": ["ecb_rate"],
        "explanation": "ECB main refinancing rate.",
    },
    "eurozone inflation": {
        "series": ["eurozone_inflation"],
        "explanation": "Eurozone HICP inflation.",
    },
    "canada economy": {
        "series": ["canada_gdp"],
        "explanation": "Canada GDP growth from IMF.",
    },
    "mexico economy": {
        "series": ["mexico_gdp"],
        "explanation": "Mexico GDP growth from IMF.",
    },
    "india economy": {
        "series": ["india_gdp"],
        "explanation": "India GDP growth from IMF.",
    },
    "brazil economy": {
        "series": ["brazil_gdp"],
        "explanation": "Brazil GDP growth from IMF.",
    },
}


def _get_cached(key: str) -> Optional[dict]:
    """Get cached result if still valid."""
    if key in _cache:
        data, timestamp = _cache[key]
        if datetime.now() - timestamp < _cache_ttl:
            return data
    return None


def _set_cache(key: str, data: dict) -> None:
    """Cache result with timestamp."""
    _cache[key] = (data, datetime.now())


def fetch_series(series_key: str) -> Optional[dict]:
    """
    Fetch a series from DBnomics.

    Args:
        series_key: Key from INTERNATIONAL_SERIES (e.g., "eurozone_gdp")

    Returns:
        Dict with dates, values, and metadata, or None on error.
    """
    if series_key not in INTERNATIONAL_SERIES:
        return None

    cache_key = f"dbnomics_{series_key}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    series_info = INTERNATIONAL_SERIES[series_key]
    series_id = series_info["id"]

    try:
        url = f"{DBNOMICS_API}/series/{series_id}?observations=1"
        req = Request(url, headers={"Accept": "application/json"})
        resp = urlopen(req, timeout=10)
        data = json.loads(resp.read())

        docs = data.get("series", {}).get("docs", [])
        if not docs:
            return None

        series_data = docs[0]
        periods = series_data.get("period", [])
        values = series_data.get("value", [])

        # Filter out None values
        clean_periods = []
        clean_values = []
        for p, v in zip(periods, values):
            if v is not None:
                clean_periods.append(p)
                clean_values.append(v)

        result = {
            "id": series_key,
            "dbnomics_id": series_id,
            "name": series_info["name"],
            "description": series_info["description"],
            "provider": series_info["provider"],
            "dates": clean_periods,
            "values": clean_values,
            "frequency": series_data.get("@frequency", "unknown"),
            "unit": series_data.get("unit", ""),
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        print(f"[DBnomics] Error fetching {series_key}: {e}")
        return None


def get_observations_dbnomics(series_key: str) -> tuple:
    """
    Get observations in FRED-compatible format.

    Returns:
        Tuple of (dates, values, info) for compatibility with app.py
    """
    data = fetch_series(series_key)
    if not data:
        return None, None, None

    # Convert periods to FRED-style dates (YYYY-MM-DD)
    dates = []
    for p in data["dates"]:
        if "Q" in p:
            # Quarterly: 2024-Q1 -> 2024-03-31
            year, q = p.split("-Q")
            month = {"1": "03", "2": "06", "3": "09", "4": "12"}[q]
            dates.append(f"{year}-{month}-01")
        elif len(p) == 4:
            # Annual: 2024 -> 2024-12-31
            dates.append(f"{p}-12-31")
        elif len(p) == 7:
            # Monthly: 2024-01 -> 2024-01-01
            dates.append(f"{p}-01")
        else:
            dates.append(p)

    info = {
        "id": data["dbnomics_id"],
        "name": data["name"],
        "title": data["name"],
        "units": data.get("unit", ""),
        "frequency": data["frequency"],
        "source": f"DBnomics ({data['provider']})",
    }

    return dates, data["values"], info


def find_international_plan(query: str) -> Optional[dict]:
    """
    Find a query plan for international data.

    Returns dict with 'series' and 'explanation' if found.
    """
    query_lower = query.lower().strip()

    # Exact/partial match on plans first
    for plan_query, plan in INTERNATIONAL_QUERY_PLANS.items():
        if plan_query in query_lower or query_lower in plan_query:
            return {**plan, "source": "dbnomics"}

    # Score-based keyword matching on series
    matches = []
    for series_key, meta in INTERNATIONAL_SERIES.items():
        keywords = meta.get("keywords", [])
        score = 0
        for kw in keywords:
            if kw in query_lower:
                # Longer keyword matches score higher
                score += len(kw)
        if score > 0:
            matches.append((series_key, meta, score))

    # Return highest scoring match
    if matches:
        matches.sort(key=lambda x: -x[2])
        best_key, best_meta, _ = matches[0]
        return {
            "series": [best_key],
            "explanation": best_meta.get("description"),
            "source": "dbnomics",
        }

    return None


def is_international_query(query: str) -> bool:
    """Check if query asks about international/non-US data."""
    query_lower = query.lower()
    intl_keywords = [
        "eurozone", "euro area", "europe", "european", "eu",
        "uk", "britain", "british", "england",
        "japan", "japanese",
        "china", "chinese",
        "germany", "german",
        "global", "world",
        "ecb", "boe", "boj",
        "emerging", "advanced economies",
    ]
    return any(kw in query_lower for kw in intl_keywords)


# Quick test
if __name__ == "__main__":
    print("Testing DBnomics integration...\n")

    test_series = ["eurozone_gdp", "china_gdp", "uk_gdp"]
    for key in test_series:
        print(f"Fetching {key}...")
        dates, values, info = get_observations_dbnomics(key)
        if dates:
            print(f"  {info['name']}")
            print(f"  Source: {info['source']}")
            print(f"  Latest: {dates[-1]} = {values[-1]}")
            print()
        else:
            print(f"  Failed to fetch\n")

    print("=" * 50)
    print("\nQuery matching tests:\n")

    test_queries = [
        "how is the eurozone doing?",
        "china gdp growth",
        "uk economy",
        "global economic outlook",
    ]

    for q in test_queries:
        plan = find_international_plan(q)
        if plan:
            print(f"Query: '{q}'")
            print(f"  Series: {plan['series']}")
        else:
            print(f"Query: '{q}' - No plan found")
        print()
