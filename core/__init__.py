# Core modules for EconStats
#
# This package contains the streamlined core components:
# - query_parser: Single LLM call for query understanding
# - series_catalog: Unified series metadata and query plans
# - data_fetcher: Unified data fetching interface (FRED + DBnomics)

from .series_catalog import (
    SERIES_CATALOG,
    QUERY_PLANS,
    SeriesMetadata,
    get_series_metadata,
    find_series_by_keyword,
    find_series_by_category,
    find_plan_for_query,
)

from .query_parser import (
    QueryIntent,
    parse_query,
)

from .data_fetcher import (
    DataFetcher,
    SeriesData,
    get_observations,
)

from .summary_generator import (
    generate_analytical_summary,
    generate_inflation_summary,
    generate_jobs_summary,
    generate_recession_summary,
    generate_fed_summary,
    ECONOMIC_FRAMEWORKS,
    TOPIC_PROMPTS,
)

from .temporal_intent import (
    TemporalIntent,
    detect_temporal_intent,
    get_reference_period_bounds,
    get_comparison_baseline_date,
    NAMED_PERIODS,
    COMPARISON_PATTERNS,
)

from .multi_period_fetcher import (
    MultiPeriodData,
    ComparisonMetric,
    fetch_multi_period_data,
    compute_comparison_metrics,
)

from .comparison_narrative import (
    generate_comparison_narrative,
    format_metric_narrative,
    format_comparison_insight,
)

from .intent_validator import (
    ValidationResult,
    ValidationIssue,
    validate_data_matches_intent,
    self_correct_if_needed,
)

from .indicator_context import (
    INDICATOR_CONTEXT,
    IndicatorContext,
    get_indicator_context,
    interpret_indicator,
    get_threshold_assessment,
    get_related_indicators,
    get_historical_context,
    get_caveats,
    format_indicator_explanation,
    # Quick access lists
    EMPLOYMENT_SERIES,
    INFLATION_SERIES,
    GDP_SERIES,
    FED_RATES_SERIES,
    CONSUMER_SERIES,
    HOUSING_SERIES,
    MARKET_SERIES,
)
