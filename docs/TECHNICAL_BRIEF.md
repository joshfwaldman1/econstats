# EconStats Technical Brief

*For Jules - feel free to start over, but here's what exists and why.*

---

## Architecture Overview

```
User Query ("How are Black workers doing?")
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  1. QUERY UNDERSTANDING (agents/query_understanding.py)      │
│     - Gemini analyzes intent, entities, demographics         │
│     - Output: structured JSON with routing hints             │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  2. ROUTING LAYER                                            │
│     a) Pre-computed plans (agents/plans_*.json) - fast path  │
│     b) Comparison router (US vs Eurozone, X vs Y)            │
│     c) Judgment layer - triggers expert search               │
│     d) Dynamic series selection - Gemini picks from catalog  │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  3. VALIDATION LAYER (query_understanding.py)                │
│     - "Gut check" - does proposed series match query?        │
│     - Override: Black workers query got UNRATE? → LNS14000006│
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  4. DATA FETCHING (parallel)                                 │
│     - FRED API (most series)                                 │
│     - Alpha Vantage (stocks, forex, fundamentals)            │
│     - DBnomics (international)                               │
│     - Zillow (housing)                                       │
│     - EIA (energy)                                           │
│     - Polymarket (prediction markets)                        │
│     - Fed website scraping (dot plots, SEP)                  │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  5. ANALYSIS & SYNTHESIS                                     │
│     - Economist analysis (core/economist_analysis.py)        │
│     - Recession scorecard (agents/recession_scorecard.py)    │
│     - Fed guidance (agents/fed_sep.py)                       │
│     - Expert research via Gemini grounded search             │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  6. PRESENTATION (app.py - Streamlit)                        │
│     - Charts (Plotly, Economist-style)                       │
│     - Callout boxes (recession dashboard, Fed guidance)      │
│     - Attribution and sources                                │
└──────────────────────────────────────────────────────────────┘
```

---

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `app.py` | Main Streamlit app, orchestrates everything | ~800 |
| `agents/query_understanding.py` | Gemini query analysis, validation layer, dynamic series | ~600 |
| `agents/query_router.py` | Comparison routing (domestic + international) | ~400 |
| `agents/judgment_layer.py` | Detects opinion queries, triggers expert search | ~300 |
| `agents/series_rag.py` | RAG over 115 curated FRED series | ~200 |
| `agents/alphavantage.py` | Stocks, forex, commodities, P/E ratios | ~300 |
| `agents/dbnomics.py` | International data (Eurozone, UK, China, etc.) | ~250 |
| `agents/fed_sep.py` | Fed dot plots, FOMC statement summaries | ~200 |
| `agents/recession_scorecard.py` | Recession dashboard (Sahm, yield curve, etc.) | ~150 |
| `agents/polymarket.py` | Prediction market odds | ~100 |
| `core/economist_analysis.py` | AI synthesis into narrative | ~200 |
| `agents/plans_*.json` | 460+ pre-computed query→series mappings | ~3000 total |

---

## Data Flow Example

**Query**: "How are Black workers doing?"

1. **Query Understanding** (Gemini)
   ```json
   {
     "intent": "analytical",
     "entities": {"demographics": ["black"]},
     "routing": {"is_demographic_specific": true},
     "pitfalls": ["Do NOT use UNRATE - use LNS14000006"]
   }
   ```

2. **Plan Lookup** - finds `plans_demographics.json` entry for "black workers"
   ```json
   {
     "series": ["LNS14000006", "LNS14000009"],
     "title": "Black Worker Employment"
   }
   ```

3. **Validation Layer** - confirms series match demographic (pass)

4. **Data Fetch** - FRED API for LNS14000006, LNS14000009

5. **Analysis** - "Black unemployment at 5.8%, down from 6.2% YoY..."

6. **Render** - Chart + narrative + comparison to overall rate

---

## The Hard Problems (And Current Solutions)

### 1. Query→Series Mapping
**Problem**: 800,000 FRED series. User says "jobs" - which one?
**Solution**:
- Pre-computed plans for common queries (fast, reliable)
- RAG over curated 115-series catalog (semantic search)
- Dynamic Gemini selection for novel queries (flexible but slower)
- Validation layer as safety net

### 2. Demographic/Sector Confusion
**Problem**: "Black workers" returns women's data; "healthcare stocks" returns employment
**Solution**:
- Query understanding extracts entities upfront
- Validation layer overrides misroutes
- Explicit demographic/sector→series mappings

### 3. Data Transformation
**Problem**: FRED gives raw levels (GDP = $28T). User wants "GDP growth"
**Solution**:
- Series metadata: `transform: "yoy_pct"`, `change_type: "yoy"`
- `validate_presentation()` determines stock/flow/rate
- Explicit rules: payrolls = changes, unemployment = levels

### 4. Judgment Questions
**Problem**: "Are we in an AI bubble?" needs opinion, not just data
**Solution**:
- Regex patterns detect judgment keywords (bubble, overvalued, sustainable)
- Triggers Gemini with Google grounding
- Searches for Wall Street analysts (Hatzius, Kostin, Dalio)
- Returns attributed expert views alongside data

### 5. International Comparisons
**Problem**: Comparing US (FRED) to Eurozone (DBnomics) - different formats
**Solution**:
- Normalize to common format (dates, values, metadata)
- Match measure types (YoY vs YoY, real vs real)
- Query router detects "US vs X" patterns

---

## API Keys Required

| Service | Env Var | Free Tier | Used For |
|---------|---------|-----------|----------|
| FRED | `FRED_API_KEY` | Unlimited | Primary data source |
| Alpha Vantage | `ALPHAVANTAGE_API_KEY` | 25/day (fundamentals), 500/day (prices) | Stocks, forex, P/E ratios |
| Gemini | `GOOGLE_API_KEY` | 60 req/min | Query understanding, expert search |
| EIA | `EIA_API_KEY` | Unlimited | Energy data (optional) |
| Claude | `ANTHROPIC_API_KEY` | Paid | Economist analysis |

---

## What's Working Well

1. **Pre-computed plans** - Fast, reliable for common queries
2. **Validation layer** - Catches most misroutes
3. **Recession scorecard** - Clean dashboard for recession queries
4. **Fed guidance integration** - Dot plots + FOMC summaries
5. **Comparison router** - US vs Eurozone works smoothly
6. **Gemini grounded search** - Gets real expert quotes

---

## What's Fragile / Needs Work

1. **Query understanding is slow** - Gemini call adds ~2s latency
2. **Pre-computed plans don't scale** - 460 plans, can't cover everything
3. **Dynamic series selection is hit-or-miss** - Gemini sometimes picks wrong series
4. **No caching layer** - Same query hits APIs repeatedly
5. **Fed scraping is brittle** - HTML changes break it; using hardcoded fallbacks
6. **International data gaps** - DBnomics has lag, limited granularity
7. **No user state** - Can't track "show me this over time" or alerts
8. **Streamlit limitations** - Single-threaded, no real async, refresh clears state

---

## If Starting Over, Consider

1. **Typed schema for series catalog** - Pydantic models for series metadata
2. **SQLite or Postgres for plans** - Instead of JSON files
3. **Redis for caching** - API responses, query→series mappings
4. **Background workers** - Pre-warm common queries, scheduled data refresh
5. **Separate API layer** - FastAPI backend, any frontend
6. **Embeddings for series search** - Better than keyword RAG
7. **User accounts** - Save queries, watchlists, alerts
8. **Rate limit handling** - Queue system for Alpha Vantage limits

---

## Running Locally

```bash
cd /tmp/econstats
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set API keys
export FRED_API_KEY=xxx
export ALPHAVANTAGE_API_KEY=xxx
export GOOGLE_API_KEY=xxx
export ANTHROPIC_API_KEY=xxx

# Run
streamlit run app.py
```

---

## Summary

It's a prototype that works for demos but has scaling issues. The core insight is sound: combine real data + AI interpretation + expert research. The implementation is a patchwork of JSON files, regex patterns, and API calls held together by a validation layer that catches mistakes.

A rewrite could be cleaner, but the hard-won knowledge is:
- Which FRED series actually answer which questions
- How to transform data correctly (levels vs changes)
- When to show data vs when to show expert opinion
- How to avoid demographic/sector confusion

That knowledge is encoded in `CLAUDE.local.md` and the `plans_*.json` files.
