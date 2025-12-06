"""ReAct pattern Agent implementation using LangGraph."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent  # type: ignore[attr-defined]

from oss_license_scan.agent.config import AgentConfig
from oss_license_scan.llm.provider import create_llm


def create_license_search_agent(
    tools: list[BaseTool],
    llm: BaseChatModel | None = None,
    model_name: str | None = None,
) -> Any:
    """
    Create a ReAct pattern Agent for license searching.

    Args:
        tools: List of LangChain tools (pypi_search, github_search, spdx_search)
        llm: Optional LLM to use. If None, uses ChatAnthropic with default settings.

    Returns:
        LangGraph compiled graph (Agent)
    """
    if llm is None:
        # Use shared create_llm() factory (respects LLM_PROVIDER env var)
        llm = create_llm(
            model_name=model_name,
            with_fallback=False,  # Agent does not need fallback
        )

    # Create ReAct Agent using LangGraph's prebuilt function
    agent = create_react_agent(llm, tools)  # type: ignore[misc]

    return agent


def run_agent_with_tools(
    query: str,
    tools: list[BaseTool],
    config: AgentConfig,
    llm: BaseChatModel | None = None,
) -> dict[str, Any]:
    """
    Run Agent with given tools and query.

    Args:
        query: User query/task for the Agent
        tools: List of LangChain tools to provide to the Agent
        config: Agent configuration (max_iterations, timeout, etc.)
        llm: Optional LLM to use

    Returns:
        Agent execution result with messages and tool calls

    Raises:
        GraphRecursionError: If Agent exceeds max_iterations
    """
    # Create Agent
    agent = create_license_search_agent(tools=tools, llm=llm, model_name=config.llm_model)

    # Calculate recursion_limit based on max_iterations
    # LangGraph counts each node execution, so we need:
    # - 1 for initial node
    # - 2 per iteration (agent node + tool node)
    # Formula: max_iterations * 2 + 1
    recursion_limit = config.max_iterations * 2 + 1

    # Prepare input messages
    input_messages = [HumanMessage(content=query)]

    # Run Agent with recursion limit
    result = agent.invoke(
        {"messages": input_messages},
        config={"recursion_limit": recursion_limit},
    )

    return result
