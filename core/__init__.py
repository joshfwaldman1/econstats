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
