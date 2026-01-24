# EconStats Project Memory

## Critical Rules (User-Specified)
- **MAKE NO MISTAKES** - Be thorough. Test edge cases. Think about how users actually type queries.
- **DO NOT HALLUCINATE DATES** - Never make up or guess date ranges
- **PAYROLLS = CHANGES NOT LEVELS** - When using payroll data, focus on month-over-month or year-over-year changes, not absolute employment levels

## Comparison Query Detection (query_router.py)
**Comparison keywords must be exhaustive:**
- "vs", "versus", "compared to", "compare", "than", "against", "relative to", "between", "and"

**Region aliases must cover all common spellings:**
- US: "us", "usa", "u.s.", "u.s", "america", "american", "united states"
- Eurozone: "eurozone", "euro area", "euro zone", "eu", "europe", "european"

**When a user asks X vs Y, ALWAYS return data for BOTH X and Y.**

## Economic Comparison Fundamentals (CRITICAL)
**NEVER compare apples to oranges. All comparisons must be equivalent:**

| Dimension | Rule | Example Violation |
|-----------|------|-------------------|
| **YoY vs QoQ** | NEVER mix year-over-year with quarter-over-quarter | US GDP 2.3% YoY vs Eurozone 0.6% QoQ = WRONG |
| **Real vs Nominal** | ALWAYS compare real with real (inflation-adjusted) | Real GDP vs Nominal GDP = WRONG |
| **Same periodicity** | Match monthly/quarterly/annual data appropriately | Annual IMF data vs Monthly FRED = Be careful |

**Series metadata in `dbnomics.py` and `query_router.py`:**
- `measure_type`: "real", "nominal", "rate", "index"
- `change_type`: "yoy", "qoq", "mom", "level"
- `transform`: What to apply to raw FRED data (e.g., "yoy_pct")

**FRED series that need transformation:**
- GDPC1 (Real GDP): Level → must calculate YoY % change
- CPIAUCSL (CPI): Index → must calculate YoY % change
- UNRATE, FEDFUNDS: Already rates, display as-is

## LLM Integration Patterns
- **LLMs hallucinate series IDs** - Never have LLMs generate FRED series IDs directly
- **Use topic discovery instead** - Have LLMs suggest dimensions/topics, then use FRED API to find valid series
- **Validate all series** - Use `validate_series_relevance()` to filter irrelevant/overly broad series
- **Claude API auth issues** - May get 401 errors; Gemini works as fallback in ensemble

## Architecture
- **Economist Reasoning (PRIMARY)**: `core/economist_reasoning.py` - AI reasons about what indicators an economist would need, then searches FRED
- **RAG Catalog**: 115+ curated FRED series in `agents/series_rag.py` with semantic search
- **Pre-computed Plans**: 460+ query-to-series mappings across `agents/plans_*.json` files (fast-path backstop)
- **Hybrid Fallback**: Combine RAG + FRED API search when reasoning fails

## Query Processing Flow (NEW - AI-First)
1. **Pre-computed plan check** - Exact match only (fast path for known queries)
2. **Economist Reasoning** (PRIMARY) - AI thinks: "To answer this, an economist would need X, Y, Z..."
3. **FRED Search** - Search for each concept the AI identified
4. **Relevance Filter** - Skip series that don't match the intended concept
5. **Fallback** - If reasoning fails, use hybrid RAG + FRED search

The key insight: We ask the AI to REASON about what's needed, not to recall series IDs from memory.
This keeps the system "on its toes" rather than just string-matching against pre-computed patterns.

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

## Stock Market Integration
- `agents/stocks.py` - Query plans for stock market data (uses FRED, not external APIs)
- **Series**: SP500, DJIA, NASDAQCOM, VIXCLS, T10Y2Y, BAMLH0A0HYM2, GOLDAMGBD228NLBM, DCOILWTICO
- **Queries handled**: "stock market", "s&p 500", "dow jones", "nasdaq", "vix", "yield curve", "gold price", "oil price"
- **Integration**: Falls back to stock plans if no precomputed economic plan matches

## Zillow Integration (Market Rents & Home Values)
- `agents/zillow.py` - Fetches actual market rents and home values from Zillow Research
- **No API key required** - Uses free public CSV downloads
- **Series**:
  - `zillow_zori_national` - Zillow Observed Rent Index (actual market rents)
  - `zillow_zhvi_national` - Zillow Home Value Index
  - `zillow_rent_yoy` - Rent growth year-over-year
  - `zillow_home_value_yoy` - Home value growth year-over-year
- **Queries handled**: "zillow rent", "market rent", "actual rents", "zhvi", "zori"
- **Better than FRED for**: Real-time rent data (CPI rent lags by months)

## EIA Integration (Energy Data)
- `agents/eia.py` - Detailed energy data from US Energy Information Administration
- **Requires**: `EIA_API_KEY` env var (free at https://www.eia.gov/opendata/register.php)
- **Series**:
  - `eia_wti_crude` - WTI crude oil spot price
  - `eia_brent_crude` - Brent crude oil price
  - `eia_gasoline_retail` - Retail gasoline prices
  - `eia_diesel_retail` - Diesel fuel prices
  - `eia_natural_gas_henry_hub` - Henry Hub natural gas
  - `eia_crude_stocks` - US crude oil inventories
  - `eia_crude_production` - US oil production
  - `eia_electricity_residential` - Residential electricity prices
- **Better than FRED for**: More granular energy data, weekly updates

## Alpha Vantage Integration (Real-Time Markets)
- `agents/alphavantage.py` - Daily market data for stocks, forex, commodities
- **Requires**: `ALPHAVANTAGE_API_KEY` env var (free at https://www.alphavantage.co/support/#api-key)
- **Series**:
  - Stocks: `av_spy`, `av_qqq`, `av_dia`, `av_iwm` (ETFs tracking indices)
  - Treasuries: `av_treasury_10y`, `av_treasury_2y`, `av_treasury_30y`, `av_treasury_3m`
  - Forex: `av_eurusd`, `av_usdjpy`, `av_gbpusd`, `av_dollar_index`
  - Commodities: `av_crude_oil`, `av_brent`, `av_natural_gas`
  - Economic: `av_real_gdp`, `av_cpi`, `av_unemployment`, `av_fed_funds`
- **Better than FRED for**: Daily data (FRED indices are delayed), forex rates

## DBnomics Integration (International Data)
- `agents/dbnomics.py` - International economic data from IMF, Eurostat, ECB, BOE
- **API**: https://api.db.nomics.world/v22/
- **Coverage**:
  - Eurozone: GDP, inflation (HICP), unemployment
  - UK: GDP, CPI, Bank of England rate
  - Japan: GDP, inflation (IMF)
  - China: GDP, inflation (IMF)
  - Germany: GDP, unemployment
  - Canada, Mexico, India, Brazil: GDP (IMF)
  - ECB main refinancing rate
- **Queries handled**: "eurozone economy", "how is china doing", "uk inflation", "ecb rate"
- **Data format**: Converted to FRED-compatible (dates, values, info) for seamless integration

## Smart Query Router (Comparison Queries)
- `agents/query_router.py` - Handles multi-source queries
- **Comparison detection**: "vs", "compared to", "compare", multiple regions mentioned
- **Region extraction**: US, Eurozone, UK, Japan, China, Germany, Canada, Mexico, India, Brazil
- **Indicator extraction**: GDP/growth, inflation/CPI, unemployment, rates
- **Multi-source fetch**: Combines FRED (US) + DBnomics (international) for comparisons
- **Example queries**:
  - "US vs Eurozone GDP" → FRED:GDPC1 + DBnomics:eurozone_gdp
  - "Compare US and China growth" → FRED:GDPC1 + DBnomics:china_gdp
  - "UK inflation vs US" → FRED:CPIAUCSL + DBnomics:uk_inflation

## Key Files
- `app.py` - Main Streamlit app with query routing, temporal handling, geographic search
- `agents/agent_ensemble.py` - LLM ensemble for dimension discovery and validation
- `agents/series_rag.py` - RAG system with 115+ curated series
- `agents/polymarket.py` - Polymarket prediction market integration
- `agents/zillow.py` - Zillow housing data (no API key needed)
- `agents/eia.py` - EIA energy data (requires EIA_API_KEY)
- `agents/alphavantage.py` - Alpha Vantage market data (requires ALPHAVANTAGE_API_KEY)
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

## Chart Design Principles (The Economist Style)
1. **Minimal but Informative** - Use simple charts (line, bar, scatter). Complex issues need simple visuals.
2. **Purpose-Driven** - Each chart answers ONE question. Ask "What insight do readers take away?"
3. **Clear Hierarchy** - Title (attention), subtitle (context/what we see), source (grayed out)
4. **Annotations** - Mark key events/turning points. Explain "why", not just "what"
5. **Restraint** - Show less to communicate more. Use color purposefully, not decoratively.
6. **Small Multiples** - Break complex comparisons into related smaller charts

## Recent Fixes (January 2026)
1. **Greedy synonym replacement** - Fixed substring corruption using word boundaries
2. **GDPC1 presentation** - Now shows YoY growth, not raw $28T level
3. **YoY calculation** - Fixed to handle quarterly data (4 obs/year), not just monthly
4. **Validation bypass** - Pre-computed plans now always validated
5. **Temporal queries** - Added extraction for year/period references
6. **Holistic patterns** - Expanded to catch "what about", "compare", industry queries
7. **Polymarket integration** - Added forward-looking prediction market data (recession, Fed, GDP)
8. **Eurozone GDP YoY fix** - Changed from QoQ (CLV_PCH_PRE) to YoY (CLV_PCH_SM) for proper US comparison
9. **Comparison metadata** - Added measure_type/change_type to all DBnomics and FRED comparison series
