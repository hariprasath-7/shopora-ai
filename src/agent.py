"""Shopora LangGraph agent with durable production checkpointing."""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from .config import settings
from .llm import get_llm
from .tools import tools

SYSTEM_PROMPT = """
You are Shopora, an AI shopping assistant.

Help users discover products, compare products, manage their cart, checkout,
view orders, track shipments, and answer shopping questions.

Rules:
- Use tools for real product/cart/order/payment/shipment information.
- The current user is authenticated; never ask for or invent another user identity.
- Never reveal another customer's cart, order, payment, or shipment information.
- Use answer_product_question when the user asks factual product/review questions so answers stay grounded in retrieved catalog evidence.
- Never invent catalog, order, payment, inventory, or shipment data.
- Resolve follow-up references from the conversation when unambiguous.
- For recommendations use recommend_products; for filters use filter_products;
  for broad searches use search_products; for comparisons use compare_products.
- Parse Indian budgets naturally: 80K means 80000 and ₹ means INR.
- Keep answers concise and useful. Do not use markdown tables for product lists.
- Never expose internal tool errors, stack traces, API keys, or implementation details.
"""


_checkpointer = None
_checkpointer_context = None
_agent = None


def _build_graph(checkpointer):
    agent_llm = get_llm().bind_tools(tools)

    def call_llm(state: MessagesState):
        response = agent_llm.invoke([("system", SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [response]}

    def should_continue(state: MessagesState):
        last_message = state["messages"][-1]
        return "tools" if getattr(last_message, "tool_calls", None) else END

    builder = StateGraph(MessagesState)
    builder.add_node("llm", call_llm)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "llm")
    builder.add_conditional_edges("llm", should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "llm")
    return builder.compile(checkpointer=checkpointer)


def initialize_agent():
    """Initialize the graph once during application startup."""
    global _checkpointer, _checkpointer_context, _agent
    if _agent is not None:
        return _agent

    if settings.langgraph_database_url:
        from langgraph.checkpoint.postgres import PostgresSaver

        _checkpointer_context = PostgresSaver.from_conn_string(settings.langgraph_database_url)
        _checkpointer = _checkpointer_context.__enter__()
        _checkpointer.setup()
    else:
        _checkpointer = MemorySaver()

    _agent = _build_graph(_checkpointer)
    return _agent


def shutdown_agent() -> None:
    global _checkpointer, _checkpointer_context, _agent
    if _checkpointer_context is not None:
        _checkpointer_context.__exit__(None, None, None)
    _checkpointer_context = None
    _checkpointer = None
    _agent = None


def get_agent():
    return _agent or initialize_agent()


# Compatibility: callers can still import `agent`.
class _AgentProxy:
    def __getattr__(self, name):
        return getattr(get_agent(), name)


agent = _AgentProxy()
