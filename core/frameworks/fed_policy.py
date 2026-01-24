"""
Fed Policy Analysis Frameworks

Economic analysis tools for understanding Federal Reserve monetary policy stance.
These frameworks help answer: Is policy too tight? Too loose? What is the Fed watching?

Key Insight: The Fed has a dual mandate (maximum employment + stable prices at 2%).
These tools help assess whether current policy is appropriate for achieving those goals.

Frameworks:
1. TAYLOR_RULE - What rate SHOULD the Fed set based on inflation and employment?
2. FINANCIAL_CONDITIONS - How tight/loose are overall financial conditions?
3. FED_REACTION_FUNCTION - What indicators is the Fed focused on right now?
"""

from dataclasses import dataclass
from typing import Optional
import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.data_fetcher import DataFetcher


# =============================================================================
# TAYLOR RULE FRAMEWORK
# =============================================================================

@dataclass
class TaylorRuleResult:
    """Result of Taylor Rule calculation."""

    implied_rate: float  # What the rule says the rate should be
    actual_rate: float   # Current fed funds rate
    gap: float           # Implied - Actual (positive = Fed is loose)

    # Components
    r_star: float        # Neutral real rate assumption
    inflation: float     # Current inflation
    inflation_gap: float # Inflation - 2% target
    output_gap: float    # Output gap estimate

    # Metadata
    calculation_date: str
    inflation_source: str  # Which inflation measure used


def calculate_taylor_rule(
    inflation: float = None,
    output_gap: float = None,
    r_star: float = 2.5,
    inflation_target: float = 2.0,
    inflation_weight: float = 0.5,
    output_weight: float = 0.5,
    fetcher: DataFetcher = None
) -> TaylorRuleResult:
    """
    Calculate the Taylor Rule implied policy rate.

    The Taylor Rule (1993) is a monetary policy guideline suggesting how central
    banks should set interest rates based on economic conditions. It captures the
    intuition that the Fed should:
    - Raise rates when inflation exceeds target
    - Lower rates when the economy is underperforming

    Classic Formula:
        i = r* + pi + 0.5*(pi - pi*) + 0.5*(y - y*)

    Where:
        i   = nominal federal funds rate
        r*  = real neutral rate (long-run equilibrium rate)
        pi  = current inflation
        pi* = inflation target (2%)
        y   = actual output (GDP)
        y*  = potential output

    Economic Reasoning:
    - When inflation > target: Rule suggests higher rates to cool economy
    - When output < potential: Rule suggests lower rates to stimulate growth
    - The weights (0.5, 0.5) reflect Fed's dual mandate balance

    Args:
        inflation: Current inflation rate (%). If None, fetches Core PCE.
        output_gap: Output gap (%). If None, estimates from unemployment.
        r_star: Neutral real rate assumption. Default 2.5% (Fed's SEP longer-run).
        inflation_target: Fed's inflation target. Default 2.0%.
        inflation_weight: Weight on inflation gap. Default 0.5 (Taylor original).
        output_weight: Weight on output gap. Default 0.5 (Taylor original).
        fetcher: DataFetcher instance. Created if None.

    Returns:
        TaylorRuleResult with implied rate and components.

    Example:
        >>> result = calculate_taylor_rule()
        >>> print(f"Implied rate: {result.implied_rate:.2f}%")
        >>> print(f"Fed is {abs(result.gap)*100:.0f} bps {'loose' if result.gap > 0 else 'tight'}")
    """
    if fetcher is None:
        fetcher = DataFetcher()

    # Fetch current fed funds rate
    fed_funds_data = fetcher.fetch("FEDFUNDS", years=1)
    actual_rate = fed_funds_data.latest_value if fed_funds_data.latest_value else 5.25
    calc_date = fed_funds_data.latest_date or "unknown"

    # Get inflation if not provided (use Core PCE - Fed's preferred measure)
    inflation_source = "provided"
    if inflation is None:
        # Core PCE YoY - PCEPILFE is the index, need to calculate YoY
        pce_data = fetcher.fetch("PCEPILFE", years=2)
        if not pce_data.is_empty and len(pce_data.values) >= 12:
            # Calculate YoY change
            current = pce_data.values[-1]
            year_ago = pce_data.values[-12] if len(pce_data.values) >= 12 else pce_data.values[0]
            inflation = ((current / year_ago) - 1) * 100
            inflation_source = "Core PCE YoY"
        else:
            inflation = 2.8  # Fallback estimate
            inflation_source = "fallback estimate"

    # Estimate output gap if not provided
    # Use Okun's Law approximation: output gap ~ -2 * (unemployment - NAIRU)
    if output_gap is None:
        unemp_data = fetcher.fetch("UNRATE", years=1)
        if not unemp_data.is_empty:
            unemployment = unemp_data.latest_value
            nairu = 4.2  # Fed's current estimate of natural rate
            # Okun's Law: 1% above NAIRU ~ -2% output gap
            output_gap = -2.0 * (unemployment - nairu)
        else:
            output_gap = 0.0  # Assume at potential

    # Calculate inflation gap
    inflation_gap = inflation - inflation_target

    # Taylor Rule calculation
    implied_rate = (
        r_star
        + inflation
        + inflation_weight * inflation_gap
        + output_weight * output_gap
    )

    # Calculate gap (positive = Fed is running loose relative to rule)
    gap = implied_rate - actual_rate

    return TaylorRuleResult(
        implied_rate=implied_rate,
        actual_rate=actual_rate,
        gap=gap,
        r_star=r_star,
        inflation=inflation,
        inflation_gap=inflation_gap,
        output_gap=output_gap,
        calculation_date=calc_date,
        inflation_source=inflation_source
    )


def interpret_taylor_rule(result: TaylorRuleResult) -> str:
    """
    Interpret Taylor Rule results in plain English.

    Provides economic context for whether Fed policy appears appropriate,
    too tight, or too loose based on the Taylor Rule benchmark.

    Args:
        result: TaylorRuleResult from calculate_taylor_rule()

    Returns:
        Human-readable interpretation with economic reasoning.
    """
    gap_bps = result.gap * 100

    # Determine stance
    if abs(gap_bps) < 25:
        stance = "roughly neutral"
        stance_detail = "The Fed's current rate is close to what the Taylor Rule suggests."
    elif gap_bps > 0:
        stance = "loose"
        stance_detail = (
            f"The Fed is running {abs(gap_bps):.0f} basis points BELOW the Taylor Rule implied rate. "
            "This suggests policy may be more accommodative than the rule recommends."
        )
    else:
        stance = "tight"
        stance_detail = (
            f"The Fed is running {abs(gap_bps):.0f} basis points ABOVE the Taylor Rule implied rate. "
            "This suggests policy may be more restrictive than the rule recommends."
        )

    # Build interpretation
    lines = [
        f"TAYLOR RULE ANALYSIS (as of {result.calculation_date})",
        "=" * 50,
        "",
        f"Implied Policy Rate: {result.implied_rate:.2f}%",
        f"Actual Fed Funds:    {result.actual_rate:.2f}%",
        f"Gap:                 {gap_bps:+.0f} bps",
        "",
        f"Policy Stance: {stance.upper()}",
        stance_detail,
        "",
        "Components:",
        f"  - Neutral rate (r*):     {result.r_star:.1f}%",
        f"  - Current inflation:     {result.inflation:.2f}% ({result.inflation_source})",
        f"  - Inflation gap:         {result.inflation_gap:+.2f}% (vs 2% target)",
        f"  - Output gap:            {result.output_gap:+.2f}%",
        "",
        "Note: Taylor Rule is a guideline, not a precise target. The Fed considers",
        "many factors not captured here (financial stability, forward guidance, etc.)."
    ]

    return "\n".join(lines)


# =============================================================================
# FINANCIAL CONDITIONS FRAMEWORK
# =============================================================================

@dataclass
class FinancialConditionsResult:
    """Result of financial conditions assessment."""

    composite_score: float  # Standardized score (-2 to +2 typical range)
    stance: str             # "tight", "neutral", "loose"

    # Components (all normalized: positive = tighter conditions)
    real_rate: float        # Real fed funds rate
    credit_spread: float    # Corporate credit spreads
    equity_return: float    # Stock market YoY return (inverted)
    dollar_strength: float  # Trade-weighted dollar

    # Raw values
    raw_real_rate: float
    raw_credit_spread: float
    raw_equity_yoy: float
    raw_dollar_level: float

    calculation_date: str
    nfci_available: bool    # Whether we got actual NFCI


def calculate_financial_conditions(
    fetcher: DataFetcher = None,
    use_nfci: bool = True
) -> FinancialConditionsResult:
    """
    Assess overall financial conditions tightness.

    Financial conditions matter because monetary policy works through financial
    markets. Even if the Fed holds rates steady, conditions can tighten if:
    - Credit spreads widen (borrowing becomes harder)
    - Stock prices fall (wealth effect, cost of equity capital rises)
    - Dollar strengthens (exports become less competitive)

    This framework either uses the Chicago Fed's NFCI (if available) or
    constructs a proxy from available market data.

    Components (our proxy):
    1. Real Fed Funds Rate = FEDFUNDS - Core PCE inflation
       - Higher real rates = tighter policy
    2. Credit Spreads = BAA10Y or high yield spread
       - Wider spreads = tighter credit conditions
    3. Stock Market = S&P 500 YoY return
       - Lower returns = tighter conditions (inverted in score)
    4. Dollar Strength = Trade-weighted dollar index
       - Stronger dollar = tighter conditions

    Economic Reasoning:
    - The Fed controls short-term rates but financial conditions reflect
      the full transmission of policy to the real economy
    - Conditions can be tight even with low rates (2008) or loose even
      with high rates (strong risk appetite)
    - This helps assess whether policy is actually restrictive or accommodative

    Args:
        fetcher: DataFetcher instance. Created if None.
        use_nfci: Try to use Chicago Fed NFCI first. Default True.

    Returns:
        FinancialConditionsResult with composite score and components.
    """
    if fetcher is None:
        fetcher = DataFetcher()

    # Try to get Chicago Fed NFCI first
    nfci_available = False
    if use_nfci:
        nfci_data = fetcher.fetch("NFCI", years=1)
        if not nfci_data.is_empty:
            nfci_available = True
            # NFCI is already a composite - positive = tighter
            composite = nfci_data.latest_value
            calc_date = nfci_data.latest_date

            # Still fetch components for context
            # (we'll use rough estimates for the component breakdown)

    # Fetch component data
    fed_funds = fetcher.fetch("FEDFUNDS", years=2)
    pce = fetcher.fetch("PCEPILFE", years=2)

    # Credit spread - try BAA10Y (Moody's BAA - 10yr Treasury)
    credit_spread = fetcher.fetch("BAA10Y", years=2)
    if credit_spread.is_empty:
        # Fallback to high yield spread
        credit_spread = fetcher.fetch("BAMLH0A0HYM2", years=2)

    # S&P 500
    sp500 = fetcher.fetch("SP500", years=2)

    # Trade-weighted dollar
    dollar = fetcher.fetch("DTWEXBGS", years=2)

    # Calculate real rate
    if not fed_funds.is_empty and not pce.is_empty and len(pce.values) >= 12:
        current_pce = pce.values[-1]
        year_ago_pce = pce.values[-12] if len(pce.values) >= 12 else pce.values[0]
        inflation_yoy = ((current_pce / year_ago_pce) - 1) * 100
        raw_real_rate = fed_funds.latest_value - inflation_yoy
    else:
        raw_real_rate = 2.0  # Fallback estimate
        inflation_yoy = 2.8

    # Get credit spread
    raw_credit_spread = credit_spread.latest_value if not credit_spread.is_empty else 2.0

    # Calculate equity YoY
    if not sp500.is_empty and len(sp500.values) >= 252:  # ~1 year of daily data
        current_sp = sp500.values[-1]
        year_ago_sp = sp500.values[-252] if len(sp500.values) >= 252 else sp500.values[0]
        raw_equity_yoy = ((current_sp / year_ago_sp) - 1) * 100
    elif not sp500.is_empty and len(sp500.values) >= 12:
        # Monthly data
        current_sp = sp500.values[-1]
        year_ago_sp = sp500.values[-12]
        raw_equity_yoy = ((current_sp / year_ago_sp) - 1) * 100
    else:
        raw_equity_yoy = 10.0  # Fallback

    # Dollar level
    raw_dollar_level = dollar.latest_value if not dollar.is_empty else 100.0

    calc_date = fed_funds.latest_date or "unknown"

    # If we don't have NFCI, construct composite
    if not nfci_available:
        # Normalize each component to roughly -2 to +2 scale
        # Real rate: historical average ~1%, std ~2%
        real_rate_norm = (raw_real_rate - 1.0) / 2.0

        # Credit spread: historical average ~2%, std ~1%
        # Wider = tighter, so positive contribution
        credit_norm = (raw_credit_spread - 2.0) / 1.0

        # Equity return: higher returns = looser, so invert
        # Average ~10%, std ~15%
        equity_norm = -(raw_equity_yoy - 10.0) / 15.0

        # Dollar: average ~100, std ~10
        # Stronger = tighter
        dollar_norm = (raw_dollar_level - 100.0) / 10.0

        # Equal weight composite
        composite = (real_rate_norm + credit_norm + equity_norm + dollar_norm) / 4
    else:
        # Use NFCI as composite, estimate component contributions
        real_rate_norm = (raw_real_rate - 1.0) / 2.0
        credit_norm = (raw_credit_spread - 2.0) / 1.0
        equity_norm = -(raw_equity_yoy - 10.0) / 15.0
        dollar_norm = (raw_dollar_level - 100.0) / 10.0

    # Determine stance
    if composite > 0.5:
        stance = "tight"
    elif composite < -0.5:
        stance = "loose"
    else:
        stance = "neutral"

    return FinancialConditionsResult(
        composite_score=composite,
        stance=stance,
        real_rate=real_rate_norm,
        credit_spread=credit_norm,
        equity_return=equity_norm,
        dollar_strength=dollar_norm,
        raw_real_rate=raw_real_rate,
        raw_credit_spread=raw_credit_spread,
        raw_equity_yoy=raw_equity_yoy,
        raw_dollar_level=raw_dollar_level,
        calculation_date=calc_date,
        nfci_available=nfci_available
    )


def interpret_financial_conditions(result: FinancialConditionsResult) -> str:
    """
    Interpret financial conditions in plain English.

    Explains what tight or loose conditions mean for the economy and
    how different components are contributing.

    Args:
        result: FinancialConditionsResult from calculate_financial_conditions()

    Returns:
        Human-readable interpretation with economic context.
    """
    # Main assessment
    if result.stance == "tight":
        main_assessment = (
            "Financial conditions are TIGHT. This means the Fed's policy is effectively "
            "restrictive - borrowing is expensive, credit is harder to get, and/or asset "
            "prices are depressed. This should slow economic activity and inflation."
        )
    elif result.stance == "loose":
        main_assessment = (
            "Financial conditions are LOOSE. Despite the Fed's policy stance, financial "
            "markets are relatively accommodative - credit is flowing, asset prices are "
            "strong. This may support continued economic growth and could sustain inflation."
        )
    else:
        main_assessment = (
            "Financial conditions are roughly NEUTRAL. Neither particularly tight nor "
            "loose, suggesting policy is being transmitted as expected."
        )

    # Component contributions
    components = []

    if result.real_rate > 0.5:
        components.append(f"Real rates are restrictive at {result.raw_real_rate:.1f}%")
    elif result.real_rate < -0.5:
        components.append(f"Real rates remain accommodative at {result.raw_real_rate:.1f}%")

    if result.credit_spread > 0.5:
        components.append(f"Credit spreads are elevated ({result.raw_credit_spread:.2f}%), signaling stress")
    elif result.credit_spread < -0.5:
        components.append(f"Credit spreads are tight ({result.raw_credit_spread:.2f}%), showing strong risk appetite")

    if result.equity_return > 0.5:
        components.append(f"Weak equity returns ({result.raw_equity_yoy:+.1f}% YoY) tightening conditions")
    elif result.equity_return < -0.5:
        components.append(f"Strong equity gains ({result.raw_equity_yoy:+.1f}% YoY) loosening conditions")

    if result.dollar_strength > 0.5:
        components.append(f"Strong dollar ({result.raw_dollar_level:.1f}) tightening via trade channel")
    elif result.dollar_strength < -0.5:
        components.append(f"Weak dollar ({result.raw_dollar_level:.1f}) providing accommodation")

    # Build output
    source_note = "Chicago Fed NFCI" if result.nfci_available else "Proxy composite"

    lines = [
        f"FINANCIAL CONDITIONS ANALYSIS (as of {result.calculation_date})",
        "=" * 50,
        "",
        f"Composite Score: {result.composite_score:+.2f} ({source_note})",
        f"  (Positive = tighter, Negative = looser)",
        "",
        f"Overall Stance: {result.stance.upper()}",
        main_assessment,
        "",
        "Component Contributions:",
    ]

    if components:
        for comp in components:
            lines.append(f"  - {comp}")
    else:
        lines.append("  - All components near neutral")

    lines.extend([
        "",
        "Raw Values:",
        f"  - Real Fed Funds Rate:  {result.raw_real_rate:+.2f}%",
        f"  - Credit Spread:        {result.raw_credit_spread:.2f}%",
        f"  - S&P 500 YoY:          {result.raw_equity_yoy:+.1f}%",
        f"  - Dollar Index:         {result.raw_dollar_level:.1f}",
    ])

    return "\n".join(lines)


# =============================================================================
# FED REACTION FUNCTION FRAMEWORK
# =============================================================================

@dataclass
class FedReactionResult:
    """Result of Fed reaction function analysis."""

    likely_stance: str      # "hawkish", "dovish", "balanced"
    urgency: str            # "high", "moderate", "low"
    primary_concern: str    # What the Fed is most focused on

    # Key indicators
    core_pce: float         # Core PCE YoY
    core_pce_gap: float     # Distance from 2% target
    unemployment: float
    unemployment_gap: float # Distance from NAIRU
    inflation_expectations: float  # 5Y5Y breakeven
    expectations_anchored: bool

    # Assessment
    inflation_assessment: str
    employment_assessment: str
    expectations_assessment: str

    calculation_date: str


def calculate_fed_reaction(
    nairu: float = 4.2,
    inflation_target: float = 2.0,
    fetcher: DataFetcher = None
) -> FedReactionResult:
    """
    Analyze what the Fed is likely watching and their probable policy stance.

    The Fed's "reaction function" describes how they respond to economic data.
    While the Taylor Rule is mechanical, this framework tries to capture the
    Fed's actual decision-making process based on their communications.

    Key Inputs (What the Fed Watches):
    1. Core PCE Inflation - The Fed's official target measure
       - Target: 2% (since 2012)
       - Above 2%: Hawkish pressure
       - Below 2%: Dovish pressure

    2. Unemployment vs NAIRU - Labor market slack
       - NAIRU (Non-Accelerating Inflation Rate of Unemployment) ~ 4.2%
       - Below NAIRU: Economy running hot, inflation pressure
       - Above NAIRU: Labor market slack, room for accommodation

    3. Inflation Expectations (T5YIFR) - Are expectations anchored?
       - 5-Year, 5-Year Forward Inflation Expectation Rate
       - Should be ~2% if credibility is maintained
       - De-anchoring would be very concerning for the Fed

    Economic Reasoning:
    - Fed follows "flexible average inflation targeting" (FAIT)
    - They consider both current readings AND trajectory
    - Employment gets more weight when inflation is near target
    - Inflation expectations are a critical anchor

    Args:
        nairu: Non-accelerating inflation rate of unemployment. Default 4.2%.
        inflation_target: Fed's inflation target. Default 2.0%.
        fetcher: DataFetcher instance. Created if None.

    Returns:
        FedReactionResult with likely stance and key indicators.
    """
    if fetcher is None:
        fetcher = DataFetcher()

    # Fetch Core PCE (index, need to calculate YoY)
    pce_data = fetcher.fetch("PCEPILFE", years=2)
    if not pce_data.is_empty and len(pce_data.values) >= 12:
        current_pce = pce_data.values[-1]
        year_ago_pce = pce_data.values[-12]
        core_pce = ((current_pce / year_ago_pce) - 1) * 100
        calc_date = pce_data.latest_date
    else:
        core_pce = 2.8  # Fallback
        calc_date = "unknown"

    core_pce_gap = core_pce - inflation_target

    # Fetch unemployment
    unemp_data = fetcher.fetch("UNRATE", years=1)
    unemployment = unemp_data.latest_value if not unemp_data.is_empty else 4.0
    unemployment_gap = unemployment - nairu

    # Fetch inflation expectations (5Y5Y forward)
    expectations_data = fetcher.fetch("T5YIFR", years=1)
    inflation_expectations = expectations_data.latest_value if not expectations_data.is_empty else 2.3

    # Assess each dimension
    # Inflation assessment
    if core_pce_gap > 1.0:
        inflation_assessment = "significantly_above_target"
        inflation_concern = "high"
    elif core_pce_gap > 0.3:
        inflation_assessment = "moderately_above_target"
        inflation_concern = "moderate"
    elif core_pce_gap > -0.3:
        inflation_assessment = "near_target"
        inflation_concern = "low"
    else:
        inflation_assessment = "below_target"
        inflation_concern = "low"

    # Employment assessment
    if unemployment_gap < -0.5:
        employment_assessment = "tight_labor_market"
        employment_concern = "hawkish"  # Could add to inflation
    elif unemployment_gap < 0.3:
        employment_assessment = "near_full_employment"
        employment_concern = "neutral"
    elif unemployment_gap < 1.0:
        employment_assessment = "some_slack"
        employment_concern = "dovish"
    else:
        employment_assessment = "significant_slack"
        employment_concern = "dovish"

    # Expectations assessment
    if 1.8 <= inflation_expectations <= 2.5:
        expectations_anchored = True
        expectations_assessment = "well_anchored"
    elif inflation_expectations > 2.5:
        expectations_anchored = False
        expectations_assessment = "drifting_higher"
    else:
        expectations_anchored = True  # Low is okay
        expectations_assessment = "anchored_low"

    # Determine overall stance
    # Inflation is typically dominant when above target
    if core_pce_gap > 0.5:
        if employment_concern == "hawkish":
            likely_stance = "hawkish"
            urgency = "high"
            primary_concern = "Inflation above target with tight labor market"
        else:
            likely_stance = "hawkish"
            urgency = "moderate"
            primary_concern = "Inflation above target"
    elif core_pce_gap < -0.3:
        if employment_concern == "dovish":
            likely_stance = "dovish"
            urgency = "moderate"
            primary_concern = "Below-target inflation with labor slack"
        else:
            likely_stance = "balanced"
            urgency = "low"
            primary_concern = "Near mandate on both fronts"
    else:
        # Near target - employment becomes more important
        if employment_concern == "hawkish":
            likely_stance = "balanced"  # But watching inflation
            urgency = "low"
            primary_concern = "Monitoring tight labor market for inflation pressure"
        elif employment_concern == "dovish":
            likely_stance = "dovish"
            urgency = "moderate"
            primary_concern = "Supporting employment with inflation near target"
        else:
            likely_stance = "balanced"
            urgency = "low"
            primary_concern = "Both mandates near target"

    # Override for de-anchored expectations
    if not expectations_anchored and inflation_expectations > 2.5:
        likely_stance = "hawkish"
        urgency = "high"
        primary_concern = "Inflation expectations de-anchoring - credibility at risk"

    return FedReactionResult(
        likely_stance=likely_stance,
        urgency=urgency,
        primary_concern=primary_concern,
        core_pce=core_pce,
        core_pce_gap=core_pce_gap,
        unemployment=unemployment,
        unemployment_gap=unemployment_gap,
        inflation_expectations=inflation_expectations,
        expectations_anchored=expectations_anchored,
        inflation_assessment=inflation_assessment,
        employment_assessment=employment_assessment,
        expectations_assessment=expectations_assessment,
        calculation_date=calc_date
    )


def interpret_fed_reaction(result: FedReactionResult) -> str:
    """
    Interpret Fed reaction function analysis in plain English.

    Explains what the Fed is likely thinking based on current data
    and their historical reaction patterns.

    Args:
        result: FedReactionResult from calculate_fed_reaction()

    Returns:
        Human-readable interpretation with policy implications.
    """
    # Stance description
    if result.likely_stance == "hawkish":
        stance_desc = (
            "The Fed is likely in a HAWKISH posture, prioritizing inflation control. "
            "This means they're more inclined to keep rates higher for longer or "
            "even consider additional hikes if needed."
        )
    elif result.likely_stance == "dovish":
        stance_desc = (
            "The Fed is likely in a DOVISH posture, with room to ease policy. "
            "This means they may be looking for opportunities to cut rates "
            "or at minimum signal that cuts are coming."
        )
    else:
        stance_desc = (
            "The Fed is likely in a BALANCED posture, data-dependent with no "
            "strong bias in either direction. They'll be watching incoming data "
            "to determine the next move."
        )

    # Urgency context
    urgency_map = {
        "high": "Policy action may be imminent or strongly signaled.",
        "moderate": "The Fed is attentive but not in a rush to act.",
        "low": "No urgency to change policy in either direction."
    }

    # Assessment translations
    inflation_status = {
        "significantly_above_target": f"Core PCE at {result.core_pce:.2f}% is well above the 2% target",
        "moderately_above_target": f"Core PCE at {result.core_pce:.2f}% is modestly above target",
        "near_target": f"Core PCE at {result.core_pce:.2f}% is close to the 2% target",
        "below_target": f"Core PCE at {result.core_pce:.2f}% is below the 2% target"
    }

    employment_status = {
        "tight_labor_market": f"Unemployment at {result.unemployment:.1f}% is below NAIRU - labor market is tight",
        "near_full_employment": f"Unemployment at {result.unemployment:.1f}% is near full employment",
        "some_slack": f"Unemployment at {result.unemployment:.1f}% shows some labor market slack",
        "significant_slack": f"Unemployment at {result.unemployment:.1f}% indicates significant slack"
    }

    expectations_status = {
        "well_anchored": "Inflation expectations remain well-anchored near 2%",
        "drifting_higher": "WARNING: Inflation expectations are drifting higher",
        "anchored_low": "Inflation expectations anchored but on the low side"
    }

    lines = [
        f"FED REACTION FUNCTION ANALYSIS (as of {result.calculation_date})",
        "=" * 50,
        "",
        f"Likely Stance: {result.likely_stance.upper()}",
        f"Urgency: {result.urgency.upper()}",
        "",
        stance_desc,
        urgency_map.get(result.urgency, ""),
        "",
        f"Primary Concern: {result.primary_concern}",
        "",
        "Key Indicators the Fed is Watching:",
        f"  1. {inflation_status.get(result.inflation_assessment, '')}",
        f"  2. {employment_status.get(result.employment_assessment, '')}",
        f"  3. {expectations_status.get(result.expectations_assessment, '')}",
        "",
        "Data Summary:",
        f"  - Core PCE:                {result.core_pce:.2f}% (gap: {result.core_pce_gap:+.2f}%)",
        f"  - Unemployment:            {result.unemployment:.1f}% (gap: {result.unemployment_gap:+.1f}%)",
        f"  - 5Y5Y Inflation Expect:   {result.inflation_expectations:.2f}%",
        f"  - Expectations Anchored:   {'Yes' if result.expectations_anchored else 'NO - CONCERN'}",
        "",
        "Note: This analysis reflects typical Fed reaction patterns. Actual policy",
        "decisions also consider financial stability, global conditions, and forward",
        "guidance commitments."
    ]

    return "\n".join(lines)


# =============================================================================
# COMBINED ANALYSIS
# =============================================================================

def full_fed_policy_analysis(fetcher: DataFetcher = None) -> str:
    """
    Run all three Fed policy frameworks and provide a combined assessment.

    This gives a comprehensive view of:
    1. Where rates SHOULD be (Taylor Rule)
    2. How conditions FEEL (Financial Conditions)
    3. What the Fed is WATCHING (Reaction Function)

    Args:
        fetcher: DataFetcher instance. Created if None.

    Returns:
        Combined interpretation of all frameworks.
    """
    if fetcher is None:
        fetcher = DataFetcher()

    # Run all frameworks
    taylor = calculate_taylor_rule(fetcher=fetcher)
    conditions = calculate_financial_conditions(fetcher=fetcher)
    reaction = calculate_fed_reaction(fetcher=fetcher)

    # Build combined assessment
    lines = [
        "COMPREHENSIVE FED POLICY ANALYSIS",
        "=" * 60,
        "",
        "EXECUTIVE SUMMARY",
        "-" * 40,
    ]

    # Synthesize findings
    taylor_stance = "loose" if taylor.gap > 0.25 else "tight" if taylor.gap < -0.25 else "neutral"

    lines.extend([
        f"Taylor Rule:         Fed is {abs(taylor.gap)*100:.0f} bps {taylor_stance} vs implied rate",
        f"Financial Conditions: {conditions.stance.upper()} (score: {conditions.composite_score:+.2f})",
        f"Fed Likely Stance:   {reaction.likely_stance.upper()} (urgency: {reaction.urgency})",
        "",
    ])

    # Overall interpretation
    if taylor_stance == "loose" and conditions.stance == "loose":
        overall = (
            "Both Taylor Rule and financial conditions suggest policy is ACCOMMODATIVE. "
            "If inflation remains elevated, there may be pressure to tighten further."
        )
    elif taylor_stance == "tight" and conditions.stance == "tight":
        overall = (
            "Both Taylor Rule and financial conditions suggest policy is RESTRICTIVE. "
            "This should be putting downward pressure on inflation and economic activity."
        )
    elif conditions.stance == "tight" and taylor_stance != "tight":
        overall = (
            "Financial conditions are tighter than the Fed's rate alone suggests. "
            "Market forces (spreads, equity, dollar) are adding to restrictiveness."
        )
    elif conditions.stance == "loose" and taylor_stance != "loose":
        overall = (
            "Financial conditions are looser than the Fed's rate alone suggests. "
            "Strong risk appetite may be offsetting some of the Fed's tightening."
        )
    else:
        overall = (
            "Policy stance is roughly balanced. The Fed has flexibility to be "
            "data-dependent and adjust as conditions evolve."
        )

    lines.extend([
        "Overall Assessment:",
        overall,
        "",
        "-" * 60,
        "",
    ])

    # Add individual reports
    lines.append(interpret_taylor_rule(taylor))
    lines.append("")
    lines.append("-" * 60)
    lines.append("")
    lines.append(interpret_financial_conditions(conditions))
    lines.append("")
    lines.append("-" * 60)
    lines.append("")
    lines.append(interpret_fed_reaction(reaction))

    return "\n".join(lines)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("Testing Fed Policy Analysis Frameworks")
    print("=" * 60)

    # Initialize fetcher
    fetcher = DataFetcher()

    # Test Taylor Rule
    print("\n1. TAYLOR RULE")
    print("-" * 40)
    taylor_result = calculate_taylor_rule(fetcher=fetcher)
    print(interpret_taylor_rule(taylor_result))

    # Test Financial Conditions
    print("\n\n2. FINANCIAL CONDITIONS")
    print("-" * 40)
    fc_result = calculate_financial_conditions(fetcher=fetcher)
    print(interpret_financial_conditions(fc_result))

    # Test Fed Reaction Function
    print("\n\n3. FED REACTION FUNCTION")
    print("-" * 40)
    reaction_result = calculate_fed_reaction(fetcher=fetcher)
    print(interpret_fed_reaction(reaction_result))

    # Test Full Analysis
    print("\n\n4. FULL COMBINED ANALYSIS")
    print("-" * 40)
    full_analysis = full_fed_policy_analysis(fetcher=fetcher)
    print(full_analysis)
