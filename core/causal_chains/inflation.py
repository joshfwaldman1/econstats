"""
Causal Chain Models for Inflation Dynamics.

This module provides structured representations of how inflation transmits through
the economy. Each chain models a different inflation driver with:
- Defined stages with typical lags
- Relevant economic series for each stage
- Detection functions to identify current position
- Interpretation functions to explain the dynamics

Key insight: Inflation is not monolithic. Understanding WHICH type of inflation
is occurring (demand-pull vs cost-push) is crucial for policy response and forecasting.

Current context (as of early 2026):
- Headline inflation falling toward 2% target
- Shelter inflation sticky but should decline (market rents already fell)
- Goods in outright deflation
- Services ex-shelter normalizing
- Labor market cooling but not collapsing
"""

from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum


# =============================================================================
# CHAIN STAGE DEFINITIONS
# =============================================================================

class ChainStatus(Enum):
    """Status of a causal chain stage."""
    NOT_TRIGGERED = "not_triggered"
    EARLY = "early"
    ACTIVE = "active"
    PEAK = "peak"
    REVERSING = "reversing"
    NORMALIZED = "normalized"


@dataclass
class ChainStage:
    """A single stage in a causal chain."""
    name: str
    description: str
    series: list[str]  # FRED series IDs to monitor
    lag_months: tuple[int, int]  # (min_lag, max_lag) from previous stage
    threshold_rising: Optional[float] = None  # Threshold for "triggered"
    threshold_falling: Optional[float] = None  # Threshold for "reversing"

    def __post_init__(self):
        if self.series is None:
            self.series = []


@dataclass
class CausalChain:
    """A complete causal chain with stages and detection logic."""
    name: str
    description: str
    stages: list[ChainStage]
    key_insight: str
    policy_relevance: str

    def get_stage_names(self) -> list[str]:
        """Get list of stage names in order."""
        return [stage.name for stage in self.stages]

    def get_all_series(self) -> list[str]:
        """Get all series IDs used across all stages."""
        all_series = []
        for stage in self.stages:
            all_series.extend(stage.series)
        return list(set(all_series))


# =============================================================================
# DEMAND-PULL INFLATION CHAIN
# =============================================================================

DEMAND_PULL = CausalChain(
    name="DEMAND_PULL",
    description="""
    Classic demand-pull inflation: Strong aggregate demand exceeds productive capacity,
    giving firms pricing power and workers bargaining power.

    Transmission: Demand -> Capacity -> Prices -> Wages -> Unit Labor Costs -> Services

    Historical examples:
    - 1960s Great Inflation (guns + butter)
    - 2021-2022 post-COVID reopening surge
    """,
    stages=[
        ChainStage(
            name="Strong Demand",
            description="Aggregate demand rises faster than potential output",
            series=[
                "GDPC1",           # Real GDP
                "PCEC96",          # Real Personal Consumption
                "RSXFS",           # Retail Sales (ex food services)
                "UMCSENT",         # Consumer Sentiment
            ],
            lag_months=(0, 0),
            threshold_rising=3.0,  # GDP growth > 3% signals strong demand
        ),
        ChainStage(
            name="Capacity Utilization Rises",
            description="Firms approach production limits, slack disappears",
            series=[
                "TCU",             # Total Capacity Utilization
                "UNRATE",          # Unemployment Rate (inverse of labor slack)
                "JTSJOL",          # Job Openings (labor demand)
            ],
            lag_months=(0, 3),
            threshold_rising=80.0,  # Capacity util > 80% is tight
            threshold_falling=75.0,
        ),
        ChainStage(
            name="Pricing Power",
            description="Firms can raise prices without losing sales",
            series=[
                "PPIFIS",          # PPI Final Demand
                "CPIAUCSL",        # CPI All Items
                "CUSR0000SAC",     # CPI Commodities
            ],
            lag_months=(1, 4),
            threshold_rising=3.0,  # YoY > 3%
        ),
        ChainStage(
            name="Wage Pressure",
            description="Tight labor market drives wage gains above productivity",
            series=[
                "CES0500000003",   # Avg Hourly Earnings (Private)
                "ECIWAG",          # ECI Wages and Salaries
                "AHETPI",          # Avg Hourly Earnings (Production)
            ],
            lag_months=(3, 6),
            threshold_rising=4.0,  # Wage growth > 4% with 1-2% productivity
        ),
        ChainStage(
            name="Unit Labor Costs",
            description="Labor costs per unit of output rise (wages > productivity)",
            series=[
                "ULCNFB",          # Unit Labor Cost (Nonfarm Business)
                "OPHNFB",          # Output per Hour (Nonfarm Business)
                "COMPNFB",         # Compensation per Hour
            ],
            lag_months=(0, 2),
            threshold_rising=3.0,  # ULC > 3% is concerning
        ),
        ChainStage(
            name="Core Services Inflation",
            description="Sustained services inflation (most labor-intensive)",
            series=[
                "CUSR0000SAS",     # CPI Services
                "CUSR0000SASLE",   # CPI Services Less Energy
                "PCEPILFE",        # Core PCE (Fed's target)
            ],
            lag_months=(3, 6),
            threshold_rising=3.5,  # Services > 3.5% is above target
        ),
    ],
    key_insight="""
    Demand-pull inflation is the "good" kind in moderation - it signals a strong economy.
    The key risk is overheating: if the Fed doesn't tighten in time, inflation expectations
    can become unanchored, requiring painful disinflation later.
    """,
    policy_relevance="""
    Fed response: Raise rates to cool demand, reduce capacity pressures.
    Fiscal response: Avoid pro-cyclical stimulus when economy is already hot.
    The "soft landing" challenge: cool demand just enough without recession.
    """,
)


# =============================================================================
# COST-PUSH INFLATION CHAIN
# =============================================================================

COST_PUSH = CausalChain(
    name="COST_PUSH",
    description="""
    Supply-side inflation: External shocks raise input costs, which pass through
    to consumer prices. Unlike demand-pull, this is stagflationary - inflation
    rises while output falls.

    Transmission: Supply Shock -> Input Costs -> PPI -> CPI (with pass-through)

    Historical examples:
    - 1973-74 Oil Embargo
    - 2021-2022 Supply Chain Crisis
    - 2022 Energy Spike (Ukraine war)
    """,
    stages=[
        ChainStage(
            name="Supply Shock",
            description="External event disrupts supply (oil, shipping, materials)",
            series=[
                "DCOILWTICO",      # WTI Crude Oil
                "DCOILBRENTEU",    # Brent Crude
                "PPIACO",          # PPI All Commodities
                "WPU101",          # PPI Metals
            ],
            lag_months=(0, 0),
            threshold_rising=20.0,  # Oil +20% YoY is a shock
        ),
        ChainStage(
            name="Input Costs Rise",
            description="Producer input costs increase across sectors",
            series=[
                "PPIITM",          # PPI Intermediate Materials
                "PCUOMFGOMFG",     # PPI Manufacturing
                "WPU0561",         # PPI Industrial Chemicals
            ],
            lag_months=(0, 2),
            threshold_rising=5.0,
        ),
        ChainStage(
            name="PPI Increases",
            description="Producer prices rise as firms face higher costs",
            series=[
                "PPIFIS",          # PPI Final Demand
                "PPIFGS",          # PPI Finished Goods
                "WPSFD4111",       # PPI Finished Consumer Goods
            ],
            lag_months=(1, 3),
            threshold_rising=4.0,
        ),
        ChainStage(
            name="CPI Pass-Through",
            description="Firms pass costs to consumers (partial, 3-6mo delay)",
            series=[
                "CPIAUCSL",        # CPI All Items
                "CUSR0000SAC",     # CPI Commodities
                "CUSR0000SETA02",  # CPI Used Vehicles
            ],
            lag_months=(3, 6),
            threshold_rising=3.0,
        ),
        ChainStage(
            name="Second-Round Effects",
            description="If expectations shift, cost shock becomes persistent",
            series=[
                "MICH",            # Michigan Inflation Expectations (1yr)
                "T5YIFR",          # 5yr 5yr Forward Inflation Expectations
                "EXPINF1YR",       # Cleveland Fed 1yr Inflation Expectations
            ],
            lag_months=(3, 12),
            threshold_rising=3.5,  # Expectations above target
        ),
    ],
    key_insight="""
    Cost-push inflation is transitory IF expectations stay anchored. The 1970s error
    was letting supply shocks feed into expectations. The Fed's credibility prevents
    one-time price jumps from becoming ongoing inflation.

    Pass-through is typically partial (50-70%) and delayed (3-6 months).
    Goods prices are more affected than services.
    """,
    policy_relevance="""
    Fed dilemma: Tightening hurts output when economy is already hit by supply shock.
    The "look-through" strategy works IF expectations stay anchored.
    If expectations rise, Fed must act despite output costs (Volcker 1979).
    """,
)


# =============================================================================
# SHELTER INFLATION CHAIN (Critical for Current Environment)
# =============================================================================

SHELTER_INFLATION = CausalChain(
    name="SHELTER_INFLATION",
    description="""
    Housing costs transmission to CPI Shelter. This is THE key to understanding
    2023-2025 inflation dynamics. CPI Shelter is a LAGGING indicator because:

    1. It measures existing rent contracts, not new leases
    2. It includes Owner's Equivalent Rent (OER), which is imputed
    3. It updates slowly as leases roll over

    Market rents (Zillow, Apartment List) LEAD CPI Shelter by 12-18 months.

    Current situation (2026): Market rents have cooled, CPI Shelter still elevated
    but should decline through 2026 as old leases roll off.
    """,
    stages=[
        ChainStage(
            name="Interest Rate Shock",
            description="Fed rate changes alter mortgage affordability",
            series=[
                "FEDFUNDS",        # Fed Funds Rate
                "MORTGAGE30US",    # 30-Year Mortgage Rate
                "MORTGAGE15US",    # 15-Year Mortgage Rate
            ],
            lag_months=(0, 0),
            threshold_rising=5.0,  # Mortgage rates > 5% slow housing
            threshold_falling=4.0,
        ),
        ChainStage(
            name="Home Buying Surge/Decline",
            description="Transaction volume responds to rates",
            series=[
                "EXHOSLUSM495S",   # Existing Home Sales
                "HSN1F",           # New Single Family Homes Sold
                "HOUST1F",         # Single Family Housing Starts
            ],
            lag_months=(1, 3),
        ),
        ChainStage(
            name="Home Prices",
            description="Case-Shiller and other home price indices react",
            series=[
                "CSUSHPINSA",      # Case-Shiller US National
                "MSPUS",           # Median Sales Price
                "ASPUS",           # Average Sales Price
                "zillow_zhvi_national",  # Zillow Home Value Index
            ],
            lag_months=(3, 9),
            threshold_rising=5.0,  # YoY > 5% is strong appreciation
        ),
        ChainStage(
            name="Market Rents",
            description="New lease rents adjust (Zillow ZORI is real-time)",
            series=[
                "zillow_zori_national",  # Zillow Observed Rent Index (LEADING)
                "zillow_rent_yoy",       # Zillow Rent YoY Change
            ],
            lag_months=(3, 12),
            threshold_rising=5.0,
        ),
        ChainStage(
            name="CPI Shelter",
            description="CPI rent/OER rises (12-18mo lag from market rents)",
            series=[
                "CUSR0000SAH1",    # CPI Shelter (headline)
                "CUSR0000SEHA",    # CPI Rent of Primary Residence
                "CUSR0000SEHC",    # CPI Owner's Equivalent Rent
            ],
            lag_months=(12, 18),
            threshold_rising=4.0,  # Above 3% is elevated
        ),
        ChainStage(
            name="Rate Reversal (if applicable)",
            description="When rates rise, the chain reverses with same lags",
            series=[
                "MORTGAGE30US",    # Mortgage rates
                "CUSR0000SAH1",    # CPI Shelter (will eventually fall)
            ],
            lag_months=(12, 24),
        ),
    ],
    key_insight="""
    CPI Shelter is BACKWARD-LOOKING. Market rents (Zillow ZORI) lead by 12+ months.

    This explains the 2023-2025 inflation puzzle:
    - 2021-2022: Low rates -> home buying surge -> home prices spike -> rents rise
    - 2023-2024: Fed hikes -> market rents cool -> but CPI Shelter stays elevated
    - 2025-2026: Old high-rent leases finally roll off -> CPI Shelter declines

    Shelter is 1/3 of CPI. This lag is why disinflation took so long despite
    Fed's aggressive hiking cycle.
    """,
    policy_relevance="""
    Fed challenge: They know shelter is lagged, but can't ignore 1/3 of CPI.
    The "supercore" focus (services ex-housing) helps isolate demand-driven inflation.
    Rent futures or real-time rent indices could improve policy decisions.
    """,
)


# =============================================================================
# WAGE-PRICE SPIRAL CHAIN
# =============================================================================

WAGE_PRICE_SPIRAL = CausalChain(
    name="WAGE_PRICE_SPIRAL",
    description="""
    The feared feedback loop: wages and prices chase each other upward.

    Key condition: Only happens if inflation EXPECTATIONS become unanchored.
    If workers believe prices will keep rising, they demand higher wages.
    If firms believe costs will keep rising, they raise prices preemptively.

    Historical examples:
    - 1970s stagflation (expectations unanchored after oil shocks)
    - NOT 2021-2023 (expectations remained anchored despite high inflation)

    The 2021-2023 period is notable: despite high inflation, expectations stayed
    anchored around 2-3%, preventing a true spiral. This is the Fed's credibility.
    """,
    stages=[
        ChainStage(
            name="Tight Labor Market",
            description="Low unemployment gives workers bargaining power",
            series=[
                "UNRATE",          # Unemployment Rate
                "JTSJOL",          # Job Openings
                "JTSQUR",          # Quits Rate (confidence to quit)
                "LNS12300060",     # Prime-Age EPOP
            ],
            lag_months=(0, 0),
            threshold_rising=0.0,  # UNRATE < 4% is tight
        ),
        ChainStage(
            name="Wage Growth Exceeds Productivity",
            description="Nominal wages rise faster than output per worker",
            series=[
                "CES0500000003",   # Avg Hourly Earnings
                "ECIWAG",          # ECI Wages
                "OPHNFB",          # Productivity (to compare)
            ],
            lag_months=(3, 6),
            threshold_rising=4.0,  # Wages > 4% with ~1% productivity = trouble
        ),
        ChainStage(
            name="Unit Labor Costs Rise",
            description="Cost per unit of output increases",
            series=[
                "ULCNFB",          # Unit Labor Cost (Nonfarm Business)
            ],
            lag_months=(0, 2),
            threshold_rising=3.0,
        ),
        ChainStage(
            name="Firms Raise Prices",
            description="Firms pass labor costs to consumers",
            series=[
                "CUSR0000SAS",     # CPI Services (labor-intensive)
                "CUSR0000SASLE",   # CPI Services Less Energy
                "PCEPILFE",        # Core PCE
            ],
            lag_months=(2, 4),
            threshold_rising=3.5,
        ),
        ChainStage(
            name="Expectations Shift (KEY TEST)",
            description="If workers expect higher future inflation, they demand more",
            series=[
                "MICH",            # Michigan 1yr Expectations
                "T5YIFR",          # 5yr 5yr Forward
                "EXPINF1YR",       # Cleveland Fed Expectations
            ],
            lag_months=(0, 6),
            threshold_rising=3.5,  # Expectations above 3% signals de-anchoring
        ),
        ChainStage(
            name="Spiral Continues (or Not)",
            description="If expectations anchored, spiral breaks. If not, repeat.",
            series=[
                "CES0500000003",   # Wage growth (does it accelerate?)
                "PCEPILFE",        # Core inflation (does it persist?)
            ],
            lag_months=(6, 12),
        ),
    ],
    key_insight="""
    The wage-price spiral is NOT automatic. It requires EXPECTATIONS to de-anchor.

    2021-2023 showed this: despite 9% inflation, long-run expectations (5yr 5yr)
    stayed near 2%. Workers got one-time wage bumps, not accelerating demands.

    This is the value of Fed credibility built over 40 years of inflation targeting.
    The 1970s Fed had no such credibility after abandoning the gold standard.
    """,
    policy_relevance="""
    Fed must maintain credibility above all. "Whatever it takes" to prevent de-anchoring.
    Pre-emptive tightening is preferable to post-facto crisis response.
    Communication and forward guidance are as important as rate moves.
    """,
)


# =============================================================================
# DETECTION FUNCTIONS
# =============================================================================

@dataclass
class ChainPosition:
    """Current position within a causal chain."""
    chain_name: str
    current_stage: Optional[str]
    stage_status: ChainStatus
    confidence: float  # 0-1
    evidence: list[str]
    next_expected: Optional[str]
    estimated_lag: Optional[tuple[int, int]]


def detect_chain_position(
    chain: CausalChain,
    data: dict[str, dict],
) -> ChainPosition:
    """
    Detect current position in a causal chain based on economic data.

    Args:
        chain: The causal chain to analyze
        data: Dict of series_id -> {value, yoy_change, mom_change, trend}

    Returns:
        ChainPosition with current stage and status
    """
    evidence = []
    active_stage = None
    stage_status = ChainStatus.NOT_TRIGGERED

    # Walk through stages looking for activity
    for i, stage in enumerate(chain.stages):
        stage_active = False
        stage_evidence = []

        for series_id in stage.series:
            if series_id not in data:
                continue

            series_data = data[series_id]
            yoy = series_data.get("yoy_change")
            trend = series_data.get("trend", "stable")

            if yoy is None:
                continue

            # Check thresholds
            if stage.threshold_rising and yoy > stage.threshold_rising:
                stage_active = True
                stage_evidence.append(
                    f"{series_id} at {yoy:.1f}% YoY (above {stage.threshold_rising}% threshold)"
                )
            elif stage.threshold_falling and yoy < stage.threshold_falling:
                stage_evidence.append(
                    f"{series_id} at {yoy:.1f}% YoY (below {stage.threshold_falling}%, reversing)"
                )
                if active_stage == stage.name:
                    stage_status = ChainStatus.REVERSING

        if stage_active:
            active_stage = stage.name
            evidence.extend(stage_evidence)

            # Determine status based on trend
            if series_data.get("trend") == "accelerating":
                stage_status = ChainStatus.EARLY
            elif series_data.get("trend") == "decelerating":
                stage_status = ChainStatus.PEAK
            else:
                stage_status = ChainStatus.ACTIVE

    # Determine next expected stage
    next_stage = None
    estimated_lag = None
    if active_stage:
        stage_names = chain.get_stage_names()
        try:
            current_idx = stage_names.index(active_stage)
            if current_idx < len(chain.stages) - 1:
                next_stage_obj = chain.stages[current_idx + 1]
                next_stage = next_stage_obj.name
                estimated_lag = next_stage_obj.lag_months
        except ValueError:
            pass

    return ChainPosition(
        chain_name=chain.name,
        current_stage=active_stage,
        stage_status=stage_status,
        confidence=min(len(evidence) * 0.2, 0.9),  # More evidence = higher confidence
        evidence=evidence,
        next_expected=next_stage,
        estimated_lag=estimated_lag,
    )


# =============================================================================
# INTERPRETATION FUNCTIONS
# =============================================================================

def interpret_demand_pull(position: ChainPosition, data: dict) -> str:
    """Interpret demand-pull inflation position."""
    if position.stage_status == ChainStatus.NOT_TRIGGERED:
        return """
        Demand-pull inflation is NOT currently active.

        Evidence: Capacity utilization is below tight levels, GDP growth is moderate,
        and there are no signs of demand overheating. This is consistent with a
        balanced economy operating near potential without excess demand pressure.
        """

    if position.current_stage == "Strong Demand":
        return f"""
        EARLY STAGE: Strong demand building.

        {chr(10).join('- ' + e for e in position.evidence)}

        What to watch: Capacity utilization (TCU), job openings vs unemployed (JTSJOL/UNEMPLOY).
        If capacity tightens, firms will gain pricing power in 1-3 months.
        """

    if position.current_stage == "Core Services Inflation":
        if position.stage_status == ChainStatus.REVERSING:
            return f"""
            LATE STAGE: Demand-pull inflation is cooling.

            Core services inflation has peaked and is decelerating. This suggests:
            1. Fed tightening is working
            2. Labor market is rebalancing (quits falling, wage growth moderating)
            3. Unit labor cost pressures easing

            Expected: Continued disinflation as wage-price dynamics normalize.
            """
        else:
            return f"""
            PEAK STAGE: Demand-pull inflation fully manifested in services.

            {chr(10).join('- ' + e for e in position.evidence)}

            Policy implication: Fed must maintain restrictive stance until services
            inflation convincingly returns to target. This typically requires
            labor market softening (higher unemployment, fewer job openings).
            """

    return f"""
    Demand-pull inflation in stage: {position.current_stage}
    Status: {position.stage_status.value}

    {chr(10).join('- ' + e for e in position.evidence)}

    Next expected: {position.next_expected or 'Terminal stage'}
    Typical lag: {position.estimated_lag[0]}-{position.estimated_lag[1]} months
    """ if position.estimated_lag else ""


def interpret_cost_push(position: ChainPosition, data: dict) -> str:
    """Interpret cost-push inflation position."""
    if position.stage_status == ChainStatus.NOT_TRIGGERED:
        return """
        No active cost-push inflation.

        Supply chains are stable, commodity prices are not spiking, and input costs
        are contained. This is favorable for disinflation as there are no external
        cost pressures to pass through.
        """

    if "Second-Round Effects" in str(position.current_stage):
        return f"""
        CRITICAL JUNCTURE: Second-round effects being tested.

        {chr(10).join('- ' + e for e in position.evidence)}

        The key question: Are inflation expectations de-anchoring?

        If 5yr5yr forward (T5YIFR) stays near 2%: Supply shock is transitory.
        If expectations rise above 3%: Risk of persistent inflation.

        This is where the 1970s went wrong - supply shocks became embedded expectations.
        """

    if position.stage_status == ChainStatus.REVERSING:
        return f"""
        Cost-push inflation is REVERSING.

        Input costs are falling back, reducing pass-through pressure. Watch for:
        - PPI falling faster than CPI (retailers absorbing cost cuts)
        - Goods prices deflating
        - Energy prices stabilizing

        This typically supports faster disinflation in headline vs core.
        """

    return f"""
    Cost-push inflation in stage: {position.current_stage}
    Status: {position.stage_status.value}

    {chr(10).join('- ' + e for e in position.evidence)}

    Key watch: Are expectations staying anchored? Check T5YIFR and Michigan 5yr.
    """


def interpret_shelter(position: ChainPosition, data: dict) -> str:
    """Interpret shelter inflation dynamics."""

    # Get key data points if available
    cpi_shelter_yoy = data.get("CUSR0000SAH1", {}).get("yoy_change")
    market_rent_yoy = data.get("zillow_rent_yoy", {}).get("value")
    mortgage_rate = data.get("MORTGAGE30US", {}).get("value")

    if position.stage_status == ChainStatus.NOT_TRIGGERED:
        return """
        Shelter inflation dynamics are stable.

        No significant rate shock or housing market dislocation is occurring.
        CPI Shelter is evolving normally based on existing lease rollovers.
        """

    # The critical case: market rents leading CPI shelter down
    if market_rent_yoy is not None and cpi_shelter_yoy is not None:
        if market_rent_yoy < cpi_shelter_yoy:
            gap = cpi_shelter_yoy - market_rent_yoy
            return f"""
            KEY INSIGHT: Market rents are LEADING CPI Shelter down.

            Current readings:
            - CPI Shelter: {cpi_shelter_yoy:.1f}% YoY (lagging indicator)
            - Market Rents (Zillow): {market_rent_yoy:.1f}% YoY (leading indicator)
            - Gap: {gap:.1f} percentage points

            What this means:
            CPI Shelter measures existing leases, which were signed 6-18 months ago
            at higher rents. As these leases roll over, CPI Shelter will decline.

            Estimated timing: Based on typical lease lengths (12mo) and BLS methodology,
            CPI Shelter should decline toward market rents over the next 6-12 months.

            Implication for headline inflation: Shelter is ~33% of CPI. As it normalizes,
            headline and core CPI should continue falling even if other components are stable.
            """

    if position.current_stage == "CPI Shelter":
        return f"""
        CPI Shelter is the active stage.

        {chr(10).join('- ' + e for e in position.evidence)}

        Remember: This is a LAGGING indicator. To forecast shelter inflation:
        1. Look at market rents (Zillow ZORI, Apartment List)
        2. Look at new lease CPI (if available)
        3. Apply 12-18 month lag

        Current mortgage rates: {mortgage_rate:.1f}% (affects future home prices/rents)
        """ if mortgage_rate else f"""
        CPI Shelter is the active stage.

        {chr(10).join('- ' + e for e in position.evidence)}

        Check Zillow ZORI for leading indicator of where CPI Shelter is heading.
        """

    return f"""
    Shelter chain in stage: {position.current_stage}

    {chr(10).join('- ' + e for e in position.evidence)}

    The 12-18 month lag between market rents and CPI Shelter is crucial for
    understanding inflation dynamics.
    """


def interpret_wage_spiral(position: ChainPosition, data: dict) -> str:
    """Interpret wage-price spiral risk."""

    # Get expectations data
    mich_1yr = data.get("MICH", {}).get("value")
    t5yifr = data.get("T5YIFR", {}).get("value")
    wage_growth = data.get("CES0500000003", {}).get("yoy_change")

    if position.stage_status == ChainStatus.NOT_TRIGGERED:
        spiral_status = "NOT occurring"
        if t5yifr and t5yifr < 2.5:
            return f"""
            Wage-price spiral: {spiral_status}

            EXPECTATIONS ARE ANCHORED.

            5yr 5yr Forward Inflation: {t5yifr:.2f}% (well-anchored near 2%)

            This is the KEY test for a wage-price spiral. Despite elevated inflation,
            markets and consumers expect the Fed to bring inflation back to target.

            As long as expectations stay anchored, wage gains are one-time catch-ups,
            not the beginning of a self-reinforcing spiral.
            """

    if "Expectations Shift" in str(position.current_stage):
        if t5yifr and t5yifr > 3.0:
            return f"""
            WARNING: Inflation expectations showing stress.

            5yr 5yr Forward: {t5yifr:.2f}% (above comfort zone)
            1yr Michigan: {mich_1yr:.1f}% (if available)

            This is the critical juncture. If expectations de-anchor:
            - Workers will demand higher wages expecting future inflation
            - Firms will raise prices expecting future cost increases
            - A true spiral can develop

            Fed response required: Aggressive communication and/or additional tightening
            to re-anchor expectations before they become self-fulfilling.
            """
        else:
            return f"""
            Wage-price dynamics active, but expectations ANCHORED.

            5yr 5yr Forward: {t5yifr:.2f}% (still near target)
            Wage Growth: {wage_growth:.1f}% (elevated but not accelerating)

            This is NOT a 1970s-style spiral because:
            1. Long-run expectations remain anchored
            2. Fed has credibility from decades of inflation targeting
            3. Wage gains appear to be one-time catch-ups, not persistent acceleration

            The 2021-2023 period demonstrated this - high inflation without a spiral
            because expectations stayed anchored.
            """

    return f"""
    Wage-price dynamics in stage: {position.current_stage}
    Status: {position.stage_status.value}

    {chr(10).join('- ' + e for e in position.evidence)}

    Key test: Are inflation expectations (T5YIFR) staying near 2%?
    If yes: No spiral. If rising above 3%: Spiral risk.
    """


def interpret_inflation_dynamics(
    chain: CausalChain,
    position: ChainPosition,
    data: dict,
) -> str:
    """
    Route to appropriate interpretation function based on chain.
    """
    interpreters = {
        "DEMAND_PULL": interpret_demand_pull,
        "COST_PUSH": interpret_cost_push,
        "SHELTER_INFLATION": interpret_shelter,
        "WAGE_PRICE_SPIRAL": interpret_wage_spiral,
    }

    interpreter = interpreters.get(chain.name)
    if interpreter:
        return interpreter(position, data)

    return f"""
    Chain: {chain.name}
    Current stage: {position.current_stage}
    Status: {position.stage_status.value}
    Evidence: {position.evidence}
    """


# =============================================================================
# UNIFIED NARRATIVE FUNCTION
# =============================================================================

def get_current_inflation_narrative(data: dict) -> str:
    """
    Generate a complete narrative of current inflation dynamics.

    This function analyzes all four causal chains and synthesizes
    a coherent explanation of where we are and where we're headed.

    Args:
        data: Dict of series_id -> {value, yoy_change, mom_change, trend}

    Returns:
        Comprehensive narrative string
    """
    chains = [DEMAND_PULL, COST_PUSH, SHELTER_INFLATION, WAGE_PRICE_SPIRAL]
    positions = []
    interpretations = []

    for chain in chains:
        position = detect_chain_position(chain, data)
        positions.append((chain.name, position))
        interpretation = interpret_inflation_dynamics(chain, position, data)
        interpretations.append((chain.name, interpretation))

    # Build narrative
    narrative = """
================================================================================
INFLATION DYNAMICS ANALYSIS
================================================================================

"""

    for chain_name, interp in interpretations:
        narrative += f"""
--- {chain_name} ---
{interp}
"""

    # Add synthesis
    narrative += """
================================================================================
SYNTHESIS: Where Are We?
================================================================================

"""

    # Check key indicators for synthesis
    core_pce = data.get("PCEPILFE", {}).get("yoy_change")
    cpi_shelter = data.get("CUSR0000SAH1", {}).get("yoy_change")
    cpi_goods = data.get("CUSR0000SAC", {}).get("yoy_change")
    t5yifr = data.get("T5YIFR", {}).get("value")

    if core_pce is not None:
        if core_pce < 3.0:
            narrative += f"""
Core PCE at {core_pce:.1f}% - approaching target range.

"""
        elif core_pce > 4.0:
            narrative += f"""
Core PCE at {core_pce:.1f}% - still elevated, work remains.

"""
        else:
            narrative += f"""
Core PCE at {core_pce:.1f}% - progress but not yet at target.

"""

    if cpi_shelter and cpi_goods:
        if cpi_goods < 0 and cpi_shelter > 3:
            narrative += f"""
KEY DYNAMIC: Goods deflation ({cpi_goods:.1f}%) offset by sticky shelter ({cpi_shelter:.1f}%).

This is the mechanical story of 2024-2026 disinflation:
- Goods prices fell as supply chains normalized and demand cooled
- Shelter remains elevated due to 12-18 month lag from prior rent increases
- Services ex-shelter (the "supercore") is the true test of underlying inflation

As shelter catches up to market rents, core inflation should continue declining.
"""

    if t5yifr:
        if t5yifr < 2.5:
            narrative += f"""
ANCHORED EXPECTATIONS: 5yr5yr forward at {t5yifr:.2f}%.

This is the most important single number. Expectations near 2% mean:
- Wage-price spiral risk is minimal
- One-time price shocks don't become persistent inflation
- Fed has credibility to achieve soft landing
"""
        elif t5yifr > 3.0:
            narrative += f"""
WARNING: Expectations elevated at {t5yifr:.2f}%.

This requires close monitoring. If expectations de-anchor, the Fed
may need to tighten further even if the economy is slowing.
"""

    return narrative


# =============================================================================
# TEST WITH SIMULATED CURRENT CONDITIONS
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("TESTING INFLATION CAUSAL CHAINS")
    print("=" * 80)

    # Simulate current conditions (early 2026):
    # - Inflation falling, approaching target
    # - Shelter sticky but should decline
    # - Goods deflating
    # - Expectations anchored

    simulated_data = {
        # Core inflation measures
        "PCEPILFE": {"value": 2.6, "yoy_change": 2.6, "trend": "decelerating"},
        "CPILFESL": {"value": None, "yoy_change": 2.8, "trend": "decelerating"},

        # Shelter - still elevated but should fall
        "CUSR0000SAH1": {"value": None, "yoy_change": 4.2, "trend": "decelerating"},
        "CUSR0000SEHA": {"value": None, "yoy_change": 4.0, "trend": "stable"},

        # Market rents - leading indicator, already cooled
        "zillow_rent_yoy": {"value": 2.5, "yoy_change": None, "trend": "stable"},

        # Goods - deflating
        "CUSR0000SAC": {"value": None, "yoy_change": -1.5, "trend": "stable"},

        # Labor market - cooling but solid
        "UNRATE": {"value": 4.2, "yoy_change": None, "trend": "rising"},
        "CES0500000003": {"value": None, "yoy_change": 3.8, "trend": "decelerating"},
        "JTSJOL": {"value": 7.5, "yoy_change": -15.0, "trend": "falling"},

        # Capacity
        "TCU": {"value": 77.5, "yoy_change": -1.2, "trend": "stable"},

        # Expectations - well anchored
        "T5YIFR": {"value": 2.25, "yoy_change": None, "trend": "stable"},
        "MICH": {"value": 2.9, "yoy_change": None, "trend": "stable"},

        # Energy - stable
        "DCOILWTICO": {"value": 72, "yoy_change": -5.0, "trend": "stable"},

        # Mortgage rates
        "MORTGAGE30US": {"value": 6.5, "yoy_change": None, "trend": "stable"},
    }

    print("\n" + "=" * 80)
    print("SIMULATED CONDITIONS (Early 2026)")
    print("=" * 80)
    print("""
    Core PCE: 2.6% (approaching target)
    CPI Shelter: 4.2% (elevated but lagging)
    Market Rents (Zillow): 2.5% (already cooled)
    Goods CPI: -1.5% (deflating)
    Unemployment: 4.2% (normalized)
    5yr5yr Forward: 2.25% (anchored)
    """)

    # Generate full narrative
    narrative = get_current_inflation_narrative(simulated_data)
    print(narrative)

    # Test individual chain detection
    print("\n" + "=" * 80)
    print("INDIVIDUAL CHAIN ANALYSIS")
    print("=" * 80)

    for chain in [DEMAND_PULL, COST_PUSH, SHELTER_INFLATION, WAGE_PRICE_SPIRAL]:
        print(f"\n--- {chain.name} ---")
        position = detect_chain_position(chain, simulated_data)
        print(f"Stage: {position.current_stage}")
        print(f"Status: {position.stage_status.value}")
        print(f"Confidence: {position.confidence:.1%}")
        if position.evidence:
            print("Evidence:")
            for e in position.evidence:
                print(f"  - {e}")
        if position.next_expected:
            print(f"Next: {position.next_expected} ({position.estimated_lag[0]}-{position.estimated_lag[1]}mo)")

    print("\n" + "=" * 80)
    print("CHAIN METADATA")
    print("=" * 80)

    for chain in [DEMAND_PULL, COST_PUSH, SHELTER_INFLATION, WAGE_PRICE_SPIRAL]:
        print(f"\n{chain.name}:")
        print(f"  Stages: {' -> '.join(chain.get_stage_names())}")
        print(f"  Series count: {len(chain.get_all_series())}")
        print(f"  Key insight: {chain.key_insight.strip()[:100]}...")
