# EconStats Product Overview

## 1. Potential Users

**Primary audience**: People who need economic data + interpretation, but don't have time to navigate FRED, read Fed statements, or parse Wall Street research.

- **Journalists** covering the economy who need quick, accurate data with context
- **Small business owners** wondering "should I hire now?" or "is a recession coming?"
- **Policy staff** at think tanks, congressional offices, or state governments
- **Individual investors** trying to understand macro trends beyond "stocks go up/down"
- **Students/educators** learning economics who want real data, not textbook examples
- **Financial advisors** who need to explain economic context to clients

**What they have in common**: They can ask questions in plain English, but don't know (or care about) FRED series IDs like `LNS14000006` or `A191RL1Q225SBEA`.

---

## 2. Baseline Questions We Can Answer Now

### Employment & Labor Market
- "How is the job market doing?"
- "What's the unemployment rate for Black workers?"
- "How are women doing in the labor market?"
- "What sectors are hiring? Which are laying off?"
- "How is manufacturing employment trending?"

### Inflation & Prices
- "What's inflation right now?"
- "Is inflation coming down?"
- "What's happening with rent prices?"
- "Core vs headline inflation?"

### GDP & Growth
- "How fast is the economy growing?"
- "Are we in a recession?"
- "What are the recession odds?"

### Fed & Interest Rates
- "What's the Fed doing with rates?"
- "When will the Fed cut rates?"
- "What does the dot plot show?"

### Markets & Stocks
- "How is the stock market doing?"
- "How are tech stocks performing?"
- "What's happening with oil prices?"

### International
- "How does US growth compare to Eurozone?"
- "US vs China GDP growth?"

---

## 3. How We Differ from Google / ChatGPT

| Dimension | Google | ChatGPT | EconStats |
|-----------|--------|---------|-----------|
| **Data freshness** | Links to sources (you do the work) | Knowledge cutoff (stale) | Live data from FRED, Alpha Vantage, Zillow, DBnomics |
| **Data accuracy** | No verification | Hallucinated numbers common | Real series IDs, validated sources |
| **Interpretation** | None (just search results) | Generic "on one hand..." hedging | Economist-style analysis: headline, narrative, risks/opportunities |
| **Forward-looking** | News articles (backward) | Speculation | Fed dot plots, Polymarket odds, Wall Street research via Gemini |
| **Expert opinions** | Manual search required | Made-up quotes | Grounded web search prioritizing Jan Hatzius, Powell, etc. |
| **Visualizations** | None | Can't show charts | Purpose-built charts with annotations, The Economist style |

**The core difference**: We connect data + interpretation. A user asks "are we in a recession?" and gets:
1. Actual recession scorecard (Sahm Rule, yield curve, sentiment, claims)
2. Color-coded risk levels (green/yellow/red)
3. Polymarket forward-looking odds
4. Wall Street economist opinions via grounded search
5. Charts showing the indicators over time

ChatGPT would give you a definition of recession and hedge. Google would give you 10 links.

---

## 4. Really Hard Questions

These are queries where the user expects insight, not just data:

### Judgment/Interpretation Questions
- "Are we in an AI bubble?"
- "Is the stock market overvalued?"
- "Will the Fed pivot?"
- "Is inflation really coming down, or is it sticky?"
- "Are wages keeping up with inflation?"

### Causal/Analytical Questions
- "Why is unemployment so low but people feel bad about the economy?"
- "What's driving inflation - supply or demand?"
- "How do tariffs affect prices?"
- "Why does the yield curve matter?"

### Predictive Questions
- "Will there be a recession in 2026?"
- "Where will rates be in a year?"
- "Is now a good time to buy a house?"

### Cross-Domain Questions
- "How does immigration affect wages?"
- "What's the relationship between oil prices and inflation?"
- "How does the strong dollar affect trade?"

---

## 5. How We Would Want to Answer Hard Questions

### Architecture for Judgment Questions

```
Query: "Are we in an AI bubble?"
                    │
                    ▼
┌─────────────────────────────────────┐
│  1. Query Understanding (Gemini)    │
│  - Detects: bubble/valuation topic  │
│  - Routes to: judgment layer        │
└─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────┐
│  2. Data Layer (parallel)           │
│  - Market data: QQQ, Mag7 stocks    │
│  - P/E ratios: Alpha Vantage        │
│  - Historical: dot-com comparison   │
└─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────┐
│  3. Judgment Layer (Gemini + Web)   │
│  - Google grounded search for:      │
│    • Jan Hatzius / Goldman views    │
│    • David Kostin on valuations     │
│    • Robert Shiller on bubbles      │
│  - Extract: bull case, bear case    │
└─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────┐
│  4. Synthesis & Presentation        │
│  - Headline: one-sentence answer    │
│  - Data: P/E ratios, price charts   │
│  - Expert views: attributed quotes  │
│  - Risks/opportunities: both sides  │
└─────────────────────────────────────┘
```

### Key Principles for Hard Questions

1. **Show your work** - Don't just say "maybe." Show the P/E ratio is 28 vs historical 17, then let experts contextualize.

2. **Attribution over assertion** - "Goldman's Jan Hatzius argues X" is better than "the consensus is X."

3. **Data-grounded opinions** - Every claim should connect to a real indicator. "Labor market is strong" → unemployment 4.1%, payrolls +200K.

4. **Present both sides** - Judgment questions have reasonable disagreement. Show bull case and bear case.

5. **Explicit uncertainty** - "Confidence: Medium" badge. Don't pretend to know what we don't.

---

## 6. What Is NOT Under the Purview of This Model

### Out of Scope

| Category | Examples | Why Not |
|----------|----------|---------|
| **Individual stock picks** | "Should I buy NVDA?" | Not financial advice; regulatory risk |
| **Personal finance** | "Should I refinance my mortgage?" | Requires individual circumstances |
| **Political predictions** | "Who will win the election?" | Political, not economic |
| **Breaking news** | "What did Powell say today?" (within hours) | Data lag; not a news service |
| **Proprietary data** | Hedge fund positioning, Bloomberg terminal data | Paywalled; no access |
| **Micro-level data** | "What's the unemployment rate in Omaha?" | FRED coverage gaps at local level |
| **Non-US deep dives** | "Detailed China provincial data" | Limited international granularity |
| **Tax/legal advice** | "How do tariffs affect my import business?" | Requires professional advice |

### Guardrails

- We do not provide financial advice (always disclaim)
- We do not make confident predictions about markets
- We do not claim real-time data when we have lagged data (transparent about freshness)
- We do not generate synthetic data or fill gaps with hallucinations

---

## 7. Current Technical Stack

### Data Sources
- **FRED** (Federal Reserve Economic Data) - 800,000+ series, primary source
- **Alpha Vantage** - Real-time stocks, forex, commodities, fundamentals (P/E ratios)
- **DBnomics** - International data (Eurozone, UK, China, Japan via IMF/Eurostat)
- **Zillow** - Housing data (rents, home values)
- **EIA** - Energy data (oil, gas, electricity prices)
- **Polymarket** - Prediction market odds (recession, Fed, GDP)
- **Fed website** - SEP/dot plots, FOMC statements

### AI/LLM Layer
- **Gemini** - Query understanding, dynamic series selection, expert research (Google grounded)
- **Claude** - Premium economist analysis, synthesis

### Key Capabilities
- Pre-computed query plans (460+) for fast common queries
- RAG over 115 curated FRED series
- Dynamic series selection for unexpected queries
- Validation layer ensuring demographics/sectors route correctly
- Recession scorecard dashboard
- Fed guidance integration
- The Economist-style charting

---

## 8. What Would Make This Better (Technical Wishlist)

1. **Historical P/E time series** - Currently only get point-in-time; want 30-year chart
2. **Faster international data** - DBnomics has lag; want real-time Eurozone
3. **Local/regional data** - BLS has metro data; need integration
4. **Earnings data** - For "are earnings supporting valuations?" questions
5. **Sentiment data** - Twitter/news NLP for real-time sentiment
6. **User accounts** - Save queries, track indicators over time
7. **Alerts** - "Tell me when unemployment crosses 4.5%"
8. **API** - Let others build on top of this

---

## Summary

EconStats answers "how's the economy?" questions by combining:
1. **Real data** from authoritative sources (not hallucinated)
2. **Economist-quality interpretation** (not hedge-everything GPT answers)
3. **Expert opinions** grounded in actual Wall Street research
4. **Clear visualizations** that tell a story

The hard part isn't getting data (FRED is free). The hard part is:
- Knowing which of 800,000 series to use
- Transforming data correctly (levels vs changes, YoY vs QoQ)
- Connecting multiple indicators into a coherent story
- Knowing when data alone isn't enough and expert judgment matters
