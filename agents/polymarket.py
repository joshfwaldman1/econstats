"""
Polymarket prediction market integration for EconStats.

Fetches economic prediction market data (recession odds, Fed rate expectations, GDP forecasts)
to complement FRED historical data with forward-looking market sentiment.
"""

import requests
from datetime import datetime, timedelta
from typing import Optional
import json

# Cache to avoid excessive API calls
_cache: dict = {}
_cache_ttl = timedelta(minutes=15)

GAMMA_API_BASE = "https://gamma-api.polymarket.com"

# Curated list of economic event slugs to track
ECONOMIC_EVENTS = {
    # Recession/GDP
    "us-recession-by-end-of-2026": {
        "category": "recession",
        "display_name": "US Recession by End of 2026",
        "keywords": ["recession", "economic downturn", "contraction"],
    },
    "negative-gdp-growth-in-2025": {
        "category": "gdp",
        "display_name": "Negative GDP Growth in 2025",
        "keywords": ["gdp", "growth", "economy"],
    },
    "gdp-growth-in-2025": {
        "category": "gdp",
        "display_name": "GDP Growth in 2025",
        "keywords": ["gdp", "growth", "economy"],
    },
    "us-gdp-growth-in-q4-2025": {
        "category": "gdp",
        "display_name": "US GDP Growth Q4 2025",
        "keywords": ["gdp", "growth", "quarterly"],
    },
    # Fed/Rates
    "fed-decision-in-january": {
        "category": "fed",
        "display_name": "Fed Decision in January",
        "keywords": ["fed", "federal reserve", "interest rate", "fomc"],
    },
    "fed-decision-in-march-885": {
        "category": "fed",
        "display_name": "Fed Decision in March",
        "keywords": ["fed", "federal reserve", "interest rate", "fomc"],
    },
    "how-many-fed-rate-cuts-in-2026": {
        "category": "fed",
        "display_name": "Fed Rate Cuts in 2026",
        "keywords": ["fed", "rate cut", "monetary policy", "fomc"],
    },
    "who-will-trump-nominate-as-fed-chair": {
        "category": "fed",
        "display_name": "Next Fed Chair Nominee",
        "keywords": ["fed chair", "federal reserve", "powell"],
    },
    # Fiscal/Policy
    "how-much-revenue-will-the-us-raise-from-tariffs-in-2025": {
        "category": "tariffs",
        "display_name": "US Tariff Revenue 2025",
        "keywords": ["tariffs", "trade", "revenue"],
    },
    "will-tariffs-generate-250b-in-2025": {
        "category": "tariffs",
        "display_name": "Tariffs >$250B in 2025",
        "keywords": ["tariffs", "trade"],
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


def fetch_event(slug: str) -> Optional[dict]:
    """
    Fetch a single event by slug from Polymarket.

    Returns event data with markets, or None on error.
    """
    cache_key = f"event_{slug}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        # Get events list and find by slug
        resp = requests.get(
            f"{GAMMA_API_BASE}/events",
            params={"closed": "false", "limit": 500},
            timeout=10
        )
        resp.raise_for_status()
        events = resp.json()

        for event in events:
            if event.get("slug") == slug:
                _set_cache(cache_key, event)
                return event

        return None
    except Exception as e:
        print(f"[Polymarket] Error fetching event {slug}: {e}")
        return None


def fetch_all_economic_events() -> list[dict]:
    """
    Fetch all tracked economic events from Polymarket.

    Returns list of event data with parsed probabilities.
    """
    cache_key = "all_economic_events"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    results = []

    try:
        # Fetch all events in one call
        resp = requests.get(
            f"{GAMMA_API_BASE}/events",
            params={"closed": "false", "limit": 500},
            timeout=10
        )
        resp.raise_for_status()
        all_events = resp.json()

        # Index by slug
        events_by_slug = {e.get("slug"): e for e in all_events}

        # Process tracked events
        for slug, meta in ECONOMIC_EVENTS.items():
            event = events_by_slug.get(slug)
            if not event:
                continue

            parsed = parse_event(event, meta)
            if parsed:
                results.append(parsed)

        _set_cache(cache_key, results)
        return results

    except Exception as e:
        print(f"[Polymarket] Error fetching events: {e}")
        return []


def parse_event(event: dict, meta: dict) -> Optional[dict]:
    """
    Parse event data into a standardized format.

    Returns:
        {
            "slug": "us-recession-by-end-of-2026",
            "title": "US Recession by End of 2026",
            "category": "recession",
            "volume": 170265,
            "markets": [
                {"outcome": "Yes", "probability": 0.225},
                {"outcome": "No", "probability": 0.775}
            ],
            "last_updated": "2026-01-23T21:45:05Z"
        }
    """
    try:
        markets = event.get("markets", [])
        if not markets:
            return None

        parsed_markets = []
        for m in markets:
            outcomes = json.loads(m.get("outcomes", "[]"))
            prices = json.loads(m.get("outcomePrices", "[]"))

            if len(outcomes) == len(prices):
                for outcome, price in zip(outcomes, prices):
                    try:
                        prob = float(price)
                        parsed_markets.append({
                            "outcome": outcome,
                            "probability": prob,
                            "question": m.get("question", ""),
                        })
                    except (ValueError, TypeError):
                        continue

        if not parsed_markets:
            return None

        return {
            "slug": event.get("slug"),
            "title": meta.get("display_name", event.get("title")),
            "category": meta.get("category"),
            "keywords": meta.get("keywords", []),
            "volume": event.get("volume", 0),
            "liquidity": event.get("liquidity", 0),
            "markets": parsed_markets,
            "end_date": event.get("endDate"),
            "last_updated": event.get("updatedAt"),
            "url": f"https://polymarket.com/event/{event.get('slug')}",
        }

    except Exception as e:
        print(f"[Polymarket] Error parsing event: {e}")
        return None


def get_recession_odds() -> Optional[dict]:
    """
    Get current recession probability from Polymarket.

    Returns:
        {
            "probability": 0.225,
            "volume": 170265,
            "title": "US Recession by End of 2026",
            "url": "https://polymarket.com/event/..."
        }
    """
    events = fetch_all_economic_events()
    for event in events:
        if event.get("category") == "recession":
            # Find the "Yes" probability
            for market in event.get("markets", []):
                if market.get("outcome") == "Yes":
                    return {
                        "probability": market["probability"],
                        "volume": event.get("volume", 0),
                        "title": event.get("title"),
                        "url": event.get("url"),
                        "end_date": event.get("end_date"),
                    }
    return None


def get_fed_rate_expectations() -> list[dict]:
    """
    Get Fed rate cut expectations from Polymarket.

    Returns list of markets related to Fed decisions.
    """
    events = fetch_all_economic_events()
    fed_events = [e for e in events if e.get("category") == "fed"]
    return fed_events


def get_gdp_expectations() -> list[dict]:
    """
    Get GDP growth expectations from Polymarket.
    """
    events = fetch_all_economic_events()
    gdp_events = [e for e in events if e.get("category") == "gdp"]
    return gdp_events


def find_relevant_predictions(query: str) -> list[dict]:
    """
    Find prediction markets relevant to a user query.

    Args:
        query: User's question (e.g., "will there be a recession?")

    Returns:
        List of relevant prediction market data
    """
    query_lower = query.lower()
    events = fetch_all_economic_events()

    relevant = []
    for event in events:
        # Check if query matches any keywords
        keywords = event.get("keywords", [])
        title = event.get("title", "").lower()

        score = 0
        for kw in keywords:
            if kw in query_lower:
                score += 2

        # Also check title words
        for word in query_lower.split():
            if len(word) > 3 and word in title:
                score += 1

        if score > 0:
            event["relevance_score"] = score
            relevant.append(event)

    # Sort by relevance then volume
    relevant.sort(key=lambda x: (-x.get("relevance_score", 0), -x.get("volume", 0)))
    return relevant


def format_prediction_for_display(prediction: dict) -> str:
    """
    Format a prediction market for display in the app.

    Returns a formatted string like:
    "Recession by 2026: 22.5% (Polymarket, $170K volume)"
    """
    title = prediction.get("title", "Unknown")
    markets = prediction.get("markets", [])
    volume = prediction.get("volume", 0)

    # Find primary probability (usually "Yes" for binary markets)
    prob = None
    for m in markets:
        if m.get("outcome") in ("Yes", "1", "True"):
            prob = m.get("probability")
            break

    if prob is None and markets:
        prob = markets[0].get("probability")

    if prob is not None:
        prob_pct = prob * 100
        vol_str = f"${volume/1000:.0f}K" if volume >= 1000 else f"${volume:.0f}"
        return f"{title}: {prob_pct:.1f}% ({vol_str} volume)"

    return f"{title}: No probability data"


# Quick test
if __name__ == "__main__":
    print("Testing Polymarket integration...\n")

    # Test recession odds
    recession = get_recession_odds()
    if recession:
        print(f"Recession odds: {recession['probability']*100:.1f}%")
        print(f"  Volume: ${recession['volume']:,.0f}")
        print(f"  Market: {recession['title']}")
        print(f"  URL: {recession['url']}\n")

    # Test Fed expectations
    fed = get_fed_rate_expectations()
    print(f"Found {len(fed)} Fed-related markets:")
    for event in fed[:3]:
        print(f"  - {format_prediction_for_display(event)}")

    print("\n" + "="*50)

    # Test query matching
    test_queries = [
        "will there be a recession?",
        "what will the fed do?",
        "gdp growth outlook",
    ]

    for q in test_queries:
        print(f"\nQuery: '{q}'")
        relevant = find_relevant_predictions(q)
        for r in relevant[:2]:
            print(f"  → {format_prediction_for_display(r)}")
