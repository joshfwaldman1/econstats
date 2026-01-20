"""
LangGraph Economist Agent - Multi-step reasoning for economic analysis.
"""

import os
import json
from typing import Annotated, TypedDict, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from tools import (
    fetch_series,
    search_fred,
    calculate_stats,
    compare_periods,
    COMMON_QUERIES,
    SERIES_INFO
)


# === TOOLS (wrapped for LangGraph) ===

@tool
def get_economic_data(series_id: str, years: int = 10) -> str:
    """
    Fetch economic data from FRED.

    Args:
        series_id: FRED series ID (e.g., 'UNRATE' for unemployment, 'PAYEMS' for payrolls,
                   'CPIAUCSL' for CPI, 'GDPC1' for GDP, 'FEDFUNDS' for Fed rate)
        years: Years of history to fetch (default 10)

    Returns:
        JSON with dates, values, and basic stats
    """
    data = fetch_series(series_id, years)
    if 'error' not in data:
        stats = calculate_stats(data)
        # Don't return full arrays, just stats
        return json.dumps(stats, indent=2)
    return json.dumps(data)


@tool
def search_for_series(query: str) -> str:
    """
    Search FRED for economic data series.

    Args:
        query: Search terms (e.g., 'auto sales', 'restaurant employment', 'oil prices')

    Returns:
        List of matching series with IDs and descriptions
    """
    results = search_fred(query, limit=5)
    return json.dumps(results, indent=2)


@tool
def compare_time_periods(series_id: str, period1_start: str, period1_end: str,
                         period2_start: str, period2_end: str) -> str:
    """
    Compare economic data across two time periods.

    Args:
        series_id: FRED series ID
        period1_start: Start of first period (YYYY-MM-DD)
        period1_end: End of first period (YYYY-MM-DD)
        period2_start: Start of second period (YYYY-MM-DD)
        period2_end: End of second period (YYYY-MM-DD)

    Returns:
        Comparison statistics for both periods
    """
    data = fetch_series(series_id, years=20)
    if 'error' in data:
        return json.dumps(data)
    result = compare_periods(data, period1_start, period1_end, period2_start, period2_end)
    return json.dumps(result, indent=2)


@tool
def get_common_series(topic: str) -> str:
    """
    Get commonly used FRED series for a topic.

    Args:
        topic: Economic topic - one of: jobs, inflation, gdp, rates, housing, consumer, recession

    Returns:
        List of relevant series IDs with descriptions
    """
    topic = topic.lower()
    if topic in COMMON_QUERIES:
        series = COMMON_QUERIES[topic]
        result = []
        for s in series:
            result.append({
                'series_id': s,
                'description': SERIES_INFO.get(s, s)
            })
        return json.dumps(result, indent=2)
    return json.dumps({'error': f'Unknown topic. Available: {list(COMMON_QUERIES.keys())}'})


# All tools for the agent
TOOLS = [get_economic_data, search_for_series, compare_time_periods, get_common_series]


# === STATE ===

class AgentState(TypedDict):
    """State passed between nodes in the graph."""
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]
    query: str
    analysis_complete: bool


# === NODES ===

def create_agent(model_name: str = "claude-sonnet-4-20250514"):
    """Create the LangGraph agent."""

    # Initialize LLM with tools
    llm = ChatAnthropic(model=model_name, temperature=0)
    llm_with_tools = llm.bind_tools(TOOLS)

    # System prompt for the economist
    SYSTEM_PROMPT = """You are an expert economist analyzing US economic data. You have access to FRED (Federal Reserve Economic Data) through these tools:

1. get_economic_data(series_id, years) - Fetch data for a specific series
2. search_for_series(query) - Find relevant series for a topic
3. compare_time_periods(series_id, start1, end1, start2, end2) - Compare across periods
4. get_common_series(topic) - Get standard series for jobs/inflation/gdp/rates/housing/consumer/recession

## YOUR APPROACH
1. First, identify what data you need to answer the question
2. Fetch the relevant series (usually 2-4 for a complete picture)
3. Analyze the data - look at levels, trends, YoY changes
4. Synthesize into a clear, insightful answer

## KEY CONTEXT
- Economy needs ~100-150K jobs/month to keep pace with population
- Fed targets 2% inflation (Core PCE)
- Trend GDP growth is ~2% annually
- Inverted yield curve (T10Y2Y < 0) often precedes recessions
- Unemployment below 4% is historically tight

## RESPONSE STYLE
- Be direct and factual
- Cite specific numbers with dates
- Provide context (is this high/low historically?)
- If signals are mixed, say so honestly

Always fetch real data - don't guess at values."""

    def agent_node(state: AgentState):
        """Main agent reasoning node."""
        messages = state["messages"]

        # Add system prompt to first message if needed
        if not any(isinstance(m, AIMessage) for m in messages):
            response = llm_with_tools.invoke([
                {"role": "system", "content": SYSTEM_PROMPT},
                *messages
            ])
        else:
            response = llm_with_tools.invoke(messages)

        return {"messages": [response]}

    def should_continue(state: AgentState):
        """Decide whether to continue tool use or end."""
        last_message = state["messages"][-1]

        # If no tool calls, we're done
        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            return "end"

        return "tools"

    # Build the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(TOOLS))

    # Set entry point
    workflow.set_entry_point("agent")

    # Add edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile()


def run_query(query: str, verbose: bool = True) -> str:
    """
    Run an economic query through the agent.

    Args:
        query: The user's question
        verbose: Whether to print intermediate steps

    Returns:
        The agent's final analysis
    """
    agent = create_agent()

    initial_state = {
        "messages": [HumanMessage(content=query)],
        "query": query,
        "analysis_complete": False
    }

    if verbose:
        print(f"\n{'='*60}")
        print(f"QUERY: {query}")
        print('='*60)

    final_state = None
    for step in agent.stream(initial_state):
        if verbose:
            for node_name, node_state in step.items():
                if node_name == "agent":
                    msg = node_state["messages"][-1]
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        print(f"\n[Agent] Calling tools:")
                        for tc in msg.tool_calls:
                            print(f"  - {tc['name']}({tc['args']})")
                    elif hasattr(msg, 'content') and msg.content:
                        print(f"\n[Agent] Response:")
                        print(msg.content[:500] + "..." if len(msg.content) > 500 else msg.content)
                elif node_name == "tools":
                    print(f"\n[Tools] Executed")
        final_state = step

    # Extract final response
    if final_state:
        for node_state in final_state.values():
            last_msg = node_state["messages"][-1]
            if hasattr(last_msg, 'content'):
                return last_msg.content

    return "No response generated"


if __name__ == '__main__':
    # Test queries
    test_queries = [
        "What's the current state of the job market?",
        # "How does inflation compare to wage growth?",
        # "Are we heading into a recession?",
    ]

    for q in test_queries:
        result = run_query(q, verbose=True)
        print(f"\n{'='*60}")
        print("FINAL ANSWER:")
        print('='*60)
        print(result)
