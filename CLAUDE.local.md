# EconStats Project Memory

## Critical Rules (User-Specified)
- **DO NOT HALLUCINATE DATES** - Never make up or guess date ranges
- **PAYROLLS = CHANGES NOT LEVELS** - When using payroll data, focus on month-over-month or year-over-year changes, not absolute employment levels

## LLM Integration Patterns
- **LLMs hallucinate series IDs** - Never have LLMs generate FRED series IDs directly
- **Use topic discovery instead** - Have LLMs suggest dimensions/topics, then use FRED API to find valid series
- **Validate all series** - Use `validate_series_relevance()` to filter irrelevant/overly broad series
- **Claude API auth issues** - May get 401 errors; Gemini works as fallback in ensemble

## Architecture
- **RAG Catalog**: 115+ curated FRED series in `agents/series_rag.py` with semantic search
- **Pre-computed Plans**: 350+ query-to-series mappings across `agents/plans_*.json` files
- **Hybrid Approach**: Combine RAG + FRED API search for best coverage
- **Ensemble LLMs**: Claude + Gemini + GPT for improved query understanding

## Query Processing Flow
1. **Temporal extraction** - Extract date references ("in 2022", "pre-covid", "last year") from query
2. **Demographic extraction** - Extract demographic group (Black, Hispanic, women, etc.) BEFORE fuzzy matching
3. Check for holistic queries ("how is X doing?") needing multi-dimensional answers
4. Check pre-computed plans first (demographic-aware: only match within same demographic)
5. **Geographic detection** - Search FRED for state-specific series (TXUR, CAUR, etc.)
6. For holistic queries, augment with hybrid search (RAG + FRED)
7. Apply recency filter (reject series with no data after 2020)
8. Apply relevance filter (title must relate to query)
9. **STRICT LLM validation** - Always validate, including pre-computed plans
10. **Presentation validation** - AI determines stock/flow/rate for proper display
11. **Graceful no-data** - If validation rejects all series, show helpful guidance instead of wrong data

## Demographic Routing (CRITICAL)
The `extract_demographic_group()` function prevents cross-demographic confusion:
- "Black workers" → ONLY matches Black-specific plans (not women's data!)
- Demographic keywords: black, hispanic, latino, women, men, immigrant, youth, older

## Geographic Handling
The `detect_geographic_scope()` function detects state/regional queries:
- **Searches FRED** for state-specific series (e.g., TXUR, TXNA for Texas)
- Falls back to national data with warning if no state series found
- State series examples: {STATE}UR (unemployment), {STATE}NA (nonfarm payrolls), {STATE}RGSP (GDP)

## Temporal Query Handling (NEW)
The `extract_temporal_filter()` function handles time references in queries:
- **Specific years**: "inflation in 2022" → filters to 2022 data
- **Relative**: "last year", "this year", "past 3 years"
- **Periods**: "pre-covid" (through Feb 2020), "during covid" (Mar 2020 - Dec 2021), "post-covid" (2022+)
- **Recessions**: "great recession", "2008 crisis" → Dec 2007 - Jun 2009

## Presentation Validation (Stock vs Flow vs Rate)
The `validate_presentation()` function uses AI to determine how each series should be displayed:

| Category | Example | Display |
|----------|---------|---------|
| **STOCK** | Total Payrolls (159M) | Show as monthly CHANGE (+256K) |
| **FLOW** | Initial Claims (200K/week) | Show as LEVEL (already per-period) |
| **RATE** | Unemployment (4.4%) | Show as LEVEL (already a ratio) |

Key insight: Stocks are cumulative totals where the level is less meaningful than the change. Flows are already measured per-period, so the level IS meaningful.

## Synonym Handling
The `apply_synonyms()` function normalizes query terms using **word-boundary matching** to avoid substring corruption:
- Uses regex `\b...\b` to match whole words only
- Prevents "pay" → "wages" from corrupting "payrolls" → "wagesrolls"
- Sorts synonyms by length (longest first) for multi-word phrases

## Coverage Expansion (NEW)
Added series and plans for:
- **Small business**: BUSLOANS, DRTSCLCC (lending standards), NFIBOPTIMISM
- **Supply chain**: NAPMPMD (supplier deliveries), TSIFRGHT (freight), RAILFRTINTERMODAL
- **Industry sectors**: MANEMP, USCONS, USHCS, USLAH, USINFO, USTRADE, USGOVT
- **Veterans**: LNS14049526 (post-9/11 veteran unemployment)
- **Auto/vehicles**: TOTALSA, ALTSALES
- **Energy**: IPG211111CS (oil production), DCOILWTICO
- **Money supply**: M2SL, WALCL (Fed balance sheet)

## Polymarket Integration (Forward-Looking Data)
- `agents/polymarket.py` - Fetches prediction market data for forward-looking sentiment
- **Tracked markets**: recession odds, Fed rate expectations, GDP forecasts, tariff revenue
- **Display**: Shows relevant predictions below summary when query matches keywords
- **Keywords matched**: recession, fed, gdp, growth, economy, tariff, inflation, interest rate
- **Caching**: 15-minute TTL to avoid API spam
- **API**: Uses Polymarket Gamma API (https://gamma-api.polymarket.com)

## Key Files
- `app.py` - Main Streamlit app with query routing, temporal handling, geographic search
- `agents/agent_ensemble.py` - LLM ensemble for dimension discovery and validation
- `agents/series_rag.py` - RAG system with 115+ curated series
- `agents/polymarket.py` - Polymarket prediction market integration
- `agents/plans_*.json` - Pre-computed query plans by category:
  - `plans_employment.json` - Jobs, sectors, demographics
  - `plans_economy_overview.json` - Economy, small business, supply chain
  - `plans_demographics.json` - Race/ethnicity, gender, immigrants
  - `plans_gdp.json` - GDP, growth, production
  - `plans_inflation.json` - CPI, PCE, shelter, food, energy
  - `plans_housing.json` - Prices, starts, permits, mortgage
  - `plans_fed_rates.json` - Fed funds, treasuries, yields
  - `plans_consumer.json` - Sentiment, spending, retail
  - `plans_trade_markets.json` - Trade, stocks, commodities

## Recent Fixes (January 2026)
1. **Greedy synonym replacement** - Fixed substring corruption using word boundaries
2. **GDPC1 presentation** - Now shows YoY growth, not raw $28T level
3. **YoY calculation** - Fixed to handle quarterly data (4 obs/year), not just monthly
4. **Validation bypass** - Pre-computed plans now always validated
5. **Temporal queries** - Added extraction for year/period references
6. **Holistic patterns** - Expanded to catch "what about", "compare", industry queries
7. **Polymarket integration** - Added forward-looking prediction market data (recession, Fed, GDP)
