# EconStats Pre-Computed Query Plans

**Total: 314 queries**

Use this document to review and edit the pre-computed responses. Each query shows:
- The exact user input that triggers it
- Which FRED series will be displayed
- Whether to show year-over-year transformation
- The explanation shown to users

---

## ECONOMY OVERVIEW (22 queries)

| Query | Series | YoY | Notes |
|-------|--------|-----|-------|
| "how is the economy" | A191RL1Q225SBEA, UNRATE, CPIAUCSL | CPI only | GDP growth + unemployment + inflation |
| "how is the economy doing" | A191RL1Q225SBEA, UNRATE, CPIAUCSL | CPI only | GDP growth + unemployment + inflation |
| "economic overview" | A191RL1Q225SBEA, UNRATE, CPIAUCSL | CPI only | GDP growth + unemployment + inflation |
| "state of the economy" | A191RL1Q225SBEA, UNRATE, CPIAUCSL | CPI only | GDP growth + unemployment + inflation |
| "is the economy good" | A191RL1Q225SBEA, UNRATE, CPIAUCSL | CPI only | |
| "is the economy bad" | A191RL1Q225SBEA, UNRATE, CPIAUCSL | CPI only | |
| "economy today" | A191RL1Q225SBEA, UNRATE, CPIAUCSL | CPI only | |
| "us economy" | A191RL1Q225SBEA, UNRATE, CPIAUCSL | CPI only | |
| "american economy" | A191RL1Q225SBEA, UNRATE, CPIAUCSL | CPI only | |
| "economic outlook" | USSLIND, A191RL1Q225SBEA, UNRATE | No | Leading index + GDP + unemployment |
| "economic forecast" | USSLIND, A191RL1Q225SBEA | No | Leading index |
| "is there a recession" | A191RL1Q225SBEA, T10Y2Y, UNRATE | No | GDP growth + yield curve + unemployment |
| "are we in a recession" | A191RL1Q225SBEA, T10Y2Y, UNRATE | No | |
| "recession risk" | T10Y2Y, A191RL1Q225SBEA, UNRATE | No | Yield curve first (recession indicator) |
| "recession indicators" | T10Y2Y, SAHMREALTIME, A191RL1Q225SBEA | No | Yield curve + Sahm rule |

---

## EMPLOYMENT & JOBS (40 queries)

| Query | Series | YoY | Notes |
|-------|--------|-----|-------|
| "jobs" | PAYEMS, UNRATE | No | Simple: payrolls + unemployment |
| "job market" | PAYEMS, UNRATE | No | |
| "employment" | PAYEMS, UNRATE | No | |
| "unemployment" | UNRATE | No | Just the headline rate |
| "unemployment rate" | UNRATE, U6RATE | No | Adds U-6 for context |
| "how is the job market" | PAYEMS, UNRATE, LNS12300060 | No | Adds prime-age emp ratio |
| "labor market" | PAYEMS, UNRATE | No | |
| "hiring" | JTSJOL, JTSHIR, PAYEMS | No | JOLTS data |
| "job growth" | PAYEMS | No | Just payrolls |
| "job openings" | JTSJOL | No | JOLTS openings |
| "jolts" | JTSJOL, JTSQUR, JTSHIR | No | Full JOLTS picture |
| "payrolls" | PAYEMS | No | |
| "nonfarm payrolls" | PAYEMS | No | |
| "jobs report" | PAYEMS, UNRATE | No | |
| "weekly jobless claims" | ICSA, CCSA | No | Initial + continuing |
| "initial claims" | ICSA | No | |
| "continuing claims" | CCSA | No | |
| "labor force participation" | LNS11300060, LNS11300000 | No | Prime-age + overall |
| "participation rate" | LNS11300000, LNS11300060 | No | |
| "prime age employment" | LNS12300060 | No | THE best measure |
| "employment to population ratio" | LNS12300060, EMRATIO | No | |
| "is the labor market tight" | LNS12300060, JTSJOL, UNRATE | No | Prime-age + openings + unemployment |
| "underemployment" | U6RATE, UNRATE | No | U-6 vs U-3 |
| "u6 unemployment" | U6RATE | No | |
| "long term unemployment" | LNS13023621 | No | 27+ weeks |
| "job quits" | JTSQUR | No | Quits rate |
| "quit rate" | JTSQUR | No | |
| "layoffs" | JTSLDL | No | JOLTS layoffs |

---

## INFLATION & PRICES (41 queries)

| Query | Series | YoY | Notes |
|-------|--------|-----|-------|
| "inflation" | CPIAUCSL, CPILFESL | **Yes** | Headline + core CPI |
| "cpi" | CPIAUCSL | **Yes** | |
| "consumer price index" | CPIAUCSL, CPILFESL | **Yes** | |
| "core inflation" | CPILFESL | **Yes** | |
| "core cpi" | CPILFESL | **Yes** | |
| "pce" | PCEPI, PCEPILFE | **Yes** | Fed's preferred measure |
| "pce inflation" | PCEPI | **Yes** | |
| "core pce" | PCEPILFE | **Yes** | THE Fed target |
| "what does the fed target" | PCEPILFE | **Yes** | Core PCE = 2% target |
| "fed inflation target" | PCEPILFE | **Yes** | |
| "price increases" | CPIAUCSL | **Yes** | |
| "cost of living" | CPIAUCSL | **Yes** | |
| "prices" | CPIAUCSL | **Yes** | |
| "inflation rate" | CPIAUCSL, CPILFESL | **Yes** | |
| "is inflation high" | CPIAUCSL, CPILFESL, PCEPILFE | **Yes** | All three measures |
| "is inflation coming down" | CPIAUCSL, CPILFESL | **Yes** | |
| "deflation" | CPIAUCSL | **Yes** | |
| "disinflation" | CPIAUCSL, CPILFESL | **Yes** | |
| "food prices" | CUSR0000SAF11 | **Yes** | Food at home CPI |
| "grocery prices" | CUSR0000SAF11 | **Yes** | |
| "gas prices" | GASREGW | No | Actual price, not index |
| "gasoline prices" | GASREGW | No | |
| "energy prices" | CUSR0000SEHF | **Yes** | Energy CPI component |
| "oil prices" | DCOILWTICO | No | WTI price per barrel |
| "rent inflation" | CUSR0000SEHA | **Yes** | Rent CPI |
| "shelter inflation" | CUSR0000SAH1 | **Yes** | Shelter CPI (includes OER) |
| "housing inflation" | CUSR0000SAH1 | **Yes** | |
| "services inflation" | CUSR0000SAS | **Yes** | Services CPI |
| "goods inflation" | CUSR0000SAC | **Yes** | Commodities CPI |

---

## INTEREST RATES & FED (40 queries)

| Query | Series | YoY | Notes |
|-------|--------|-----|-------|
| "interest rates" | FEDFUNDS, DGS10 | No | Short + long rates |
| "rates" | FEDFUNDS, DGS10 | No | |
| "fed" | FEDFUNDS | No | |
| "federal reserve" | FEDFUNDS | No | |
| "fed funds rate" | FEDFUNDS | No | |
| "federal funds rate" | FEDFUNDS | No | |
| "fed policy" | FEDFUNDS | No | |
| "monetary policy" | FEDFUNDS, DGS2 | No | Policy rate + 2yr (expectations) |
| "rate hikes" | FEDFUNDS | No | |
| "rate cuts" | FEDFUNDS | No | |
| "will the fed cut rates" | FEDFUNDS, DGS2 | No | Current + market expectations |
| "treasury yields" | DGS2, DGS10, DGS30 | No | Short, medium, long |
| "10 year treasury" | DGS10 | No | |
| "2 year treasury" | DGS2 | No | |
| "yield curve" | T10Y2Y | No | 10yr - 2yr spread |
| "inverted yield curve" | T10Y2Y | No | |
| "yield curve inversion" | T10Y2Y, DGS10, DGS2 | No | Spread + underlying |
| "bond yields" | DGS10, DGS2 | No | |
| "mortgage rates" | MORTGAGE30US | No | |
| "30 year mortgage" | MORTGAGE30US | No | |
| "prime rate" | DPRIME | No | Bank prime |
| "credit card rates" | TERMCBCCALLNS | No | |

---

## HOUSING (30 queries)

| Query | Series | YoY | Notes |
|-------|--------|-----|-------|
| "housing" | CSUSHPINSA, HOUST, CUSR0000SEHA | No | Prices + starts + rent CPI |
| "housing market" | CSUSHPINSA, MORTGAGE30US, CUSR0000SEHA | No | Prices + rates + rent |
| "home prices" | CSUSHPINSA | No | Case-Shiller |
| "house prices" | CSUSHPINSA | No | |
| "real estate" | CSUSHPINSA, EXHOSLUSM495S | No | Prices + sales |
| "home sales" | EXHOSLUSM495S | No | Existing home sales |
| "existing home sales" | EXHOSLUSM495S | No | |
| "new home sales" | HSN1F | No | |
| "housing starts" | HOUST | No | |
| "building permits" | PERMIT | No | Leading indicator |
| "housing affordability" | MORTGAGE30US, CSUSHPINSA | No | Rates + prices |
| "rent prices" | CUSR0000SEHA | **Yes** | Rent CPI |
| "case shiller" | CSUSHPINSA | No | |
| "housing inventory" | MSACSR | No | Months supply |
| "housing supply" | HOUST, PERMIT | No | Starts + permits |

---

## GDP & GROWTH (30 queries)

| Query | Series | YoY | Notes |
|-------|--------|-----|-------|
| "gdp" | A191RL1Q225SBEA | No | Growth rate (already annualized) |
| "gdp growth" | A191RL1Q225SBEA | No | |
| "economic growth" | A191RL1Q225SBEA | No | |
| "real gdp" | GDPC1 | No | Level |
| "gdp report" | A191RL1Q225SBEA | No | |
| "quarterly gdp" | A191RL1Q225SBEA | No | |
| "growth rate" | A191RL1Q225SBEA | No | |
| "output" | INDPRO | No | Industrial production |
| "production" | INDPRO | No | |
| "industrial production" | INDPRO | No | |
| "manufacturing" | IPMAN, MANEMP | No | Production + employment |
| "factory output" | IPMAN | No | |
| "capacity utilization" | TCU | No | |
| "productivity" | OPHNFB | No | Output per hour |
| "durable goods" | DGORDER | No | |

---

## DEMOGRAPHICS - WOMEN (15 queries)

**NOTE: These queries NEVER use aggregate series like PAYEMS or UNRATE**

| Query | Series | YoY | Notes |
|-------|--------|-----|-------|
| "women" | LNS14000002, LNS12300062, LNS11300002 | No | Unemployment + prime-age emp + LFPR |
| "women employment" | LNS12300062, LNS14000002, LNS11300002 | No | |
| "women unemployment" | LNS14000002, LNS14000026, LNS12300062 | No | Overall + prime-age |
| "women in the workforce" | LNS12300062, LNS11300002, LNS14000002 | No | |
| "women labor force" | LNS12300062, LNS11300002, LNS14000002 | No | |
| "female employment" | LNS12300062, LNS14000002 | No | |
| "female unemployment" | LNS14000002 | No | |
| "women's jobs" | LNS12300062, LNS14000002 | No | |
| "working women" | LNS12300062, LNS11300002 | No | |
| "gender employment gap" | LNS12300062, LNS12300061 | No | Women vs men prime-age |
| "how are women doing in the economy" | LNS14000002, LNS12300062, LNS11300002 | No | |
| "women's labor force participation" | LNS11300002 | No | |

---

## DEMOGRAPHICS - OTHER (20 queries)

| Query | Series | YoY | Notes |
|-------|--------|-----|-------|
| "men employment" | LNS12300061, LNS14000001 | No | Prime-age + unemployment |
| "men unemployment" | LNS14000001 | No | |
| "black unemployment" | LNS14000006 | No | |
| "african american unemployment" | LNS14000006 | No | |
| "black employment" | LNS12300006, LNS14000006 | No | |
| "hispanic unemployment" | LNS14000009 | No | |
| "latino unemployment" | LNS14000009 | No | |
| "white unemployment" | LNS14000003 | No | |
| "youth unemployment" | LNS14000012 | No | 16-19 years |
| "teen unemployment" | LNS14000012 | No | |
| "older workers" | LNS14000095, LNS14000097 | No | 55-64 + 65+ |
| "racial unemployment gap" | LNS14000006, LNS14000003, LNS14000009 | No | Black, White, Hispanic |

---

## CONSUMER (30 queries)

| Query | Series | YoY | Notes |
|-------|--------|-----|-------|
| "consumer spending" | RSXFS | No | Retail sales ex food services |
| "retail sales" | RSXFS | No | |
| "consumer sentiment" | UMCSENT | No | Michigan index |
| "consumer confidence" | UMCSENT | No | |
| "spending" | RSXFS, PCE | No | Retail + PCE |
| "consumption" | PCEC96 | No | Real PCE |
| "personal spending" | PCE | No | |
| "consumer" | RSXFS, UMCSENT | No | Sales + sentiment |
| "michigan consumer sentiment" | UMCSENT | No | |
| "savings rate" | PSAVERT | No | |
| "personal savings" | PSAVERT | No | |
| "consumer debt" | TOTALSL | No | Total consumer credit |
| "household debt" | TOTALSL | No | |
| "credit card debt" | REVOLSL | No | Revolving credit |
| "personal income" | PI | No | |
| "disposable income" | DSPIC96 | No | Real disposable |

---

## TRADE & MARKETS (35 queries)

| Query | Series | YoY | Notes |
|-------|--------|-----|-------|
| "trade" | BOPGSTB | No | Trade balance |
| "trade deficit" | BOPGSTB | No | |
| "trade balance" | BOPGSTB | No | |
| "imports" | IMPGS | No | Total imports |
| "exports" | EXPGS | No | Total exports |
| "china trade" | IMPCH | No | Imports from China |
| "dollar" | DTWEXBGS | No | Trade-weighted index |
| "us dollar" | DTWEXBGS | No | |
| "exchange rate" | DTWEXBGS | No | |
| "stock market" | SP500 | No | |
| "stocks" | SP500 | No | |
| "s&p 500" | SP500 | No | |
| "sp500" | SP500 | No | |
| "dow jones" | SP500 | No | (SP500 is better measure) |
| "nasdaq" | NASDAQCOM | No | |
| "market volatility" | VIXCLS | No | VIX |
| "vix" | VIXCLS | No | |
| "oil" | DCOILWTICO | No | WTI crude |
| "crude oil" | DCOILWTICO | No | |
| "gold price" | GOLDAMGBD228NLBM | No | |
| "commodities" | PPIACO | No | PPI commodities |

---

## SERIES REFERENCE

| Series ID | Name |
|-----------|------|
| A191RL1Q225SBEA | Real GDP Growth Rate (quarterly, annualized) |
| GDPC1 | Real GDP Level |
| UNRATE | Unemployment Rate (U-3) |
| U6RATE | Unemployment Rate (U-6, includes underemployed) |
| PAYEMS | Total Nonfarm Payrolls |
| LNS12300060 | Prime-Age (25-54) Employment-Population Ratio |
| LNS11300000 | Labor Force Participation Rate |
| CPIAUCSL | Consumer Price Index (All Items) |
| CPILFESL | Core CPI (Less Food & Energy) |
| PCEPILFE | Core PCE (Fed's target measure) |
| FEDFUNDS | Federal Funds Rate |
| DGS10 | 10-Year Treasury Yield |
| DGS2 | 2-Year Treasury Yield |
| T10Y2Y | 10Y-2Y Treasury Spread (yield curve) |
| MORTGAGE30US | 30-Year Mortgage Rate |
| CSUSHPINSA | Case-Shiller Home Price Index |
| HOUST | Housing Starts |
| CUSR0000SEHA | CPI: Rent of Primary Residence |
| RSXFS | Retail Sales (ex food services) |
| UMCSENT | U. of Michigan Consumer Sentiment |
| SP500 | S&P 500 Index |
| JTSJOL | Job Openings (JOLTS) |
| LNS14000002 | Unemployment Rate - Women |
| LNS12300062 | Prime-Age Employment Ratio - Women |
| LNS14000006 | Unemployment Rate - Black |

---

*Generated by 9 specialized AI economist agents*
