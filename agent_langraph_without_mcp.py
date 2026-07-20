import os
from pprint import pprint
from typing import Literal

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from typing_extensions import TypedDict


# 1. Groq setup

load_dotenv("path of the env file")


# 2. Tools available to the agents


@tool
def add_numbers(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@tool
def subtract_numbers(a: float, b: float) -> float:
    """Subtract the second number from the first number."""
    return a - b


@tool
def multiply_numbers(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@tool
def divide_numbers(a: float, b: float) -> float:
    """Divide the first number by the second number."""
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b


@tool
def calculate_profit(cost_price: float, selling_price: float) -> str:
    """Calculate profit and profit percentage."""
    profit = selling_price - cost_price
    profit_percentage = (profit / cost_price) * 100
    return f"Profit: {profit}; Profit percentage: {profit_percentage}%"


CALCULATOR_TOOLS = {
    "add": add_numbers,
    "subtract": subtract_numbers,
    "multiply": multiply_numbers,
    "divide": divide_numbers,
}


# 3. Supervisor agent


class CalculatorTask(BaseModel):
    operation: Literal["add", "subtract", "multiply", "divide"]
    a: float
    b: float


class ProfitTask(BaseModel):
    cost_price: float
    selling_price: float


class SupervisorPlan(BaseModel):
    calculator_tasks: list[CalculatorTask] = []
    profit_task: ProfitTask | None = None


class AgentDemoState(TypedDict, total=False):
    request: str
    selected_agents: list[str]
    calculator_tasks: list[dict]
    profit_task: dict | None
    calculator_result: str
    business_result: str
    final: str


SUPERVISOR_PROMPT = """
You are the supervisor.

You can send work to two agents:
1. calculator_agent - handles add, subtract, multiply, and divide tasks.
2. business_agent - calculates profit from cost price and selling price.

Rules:
- Return JSON that matches the SupervisorPlan schema.
- Extract every arithmetic instruction into calculator_tasks.
- If the user asks for two calculations, return two calculator_tasks.
- Do not stop after the first arithmetic instruction. Scan the full user query.
- Only create a calculator_task when the user gives a clear math operation and two explicit numbers.
- Never invent numbers. Never use 0 and 0 as placeholders.
- Create profit_task only when the user asks for profit and gives both cost price and selling price.
- Do not turn a profit question into basic subtract calculator_tasks.
- Sentence boundaries do not matter. For example:
  "multiply 12 and 8. Add 8 and 1" means two tasks:
  multiply(12, 8) and add(8, 1).
- A request can use calculator_agent, business_agent, both, or neither.

Example:
User query: give me the multiplication of 12 and 8. Add 8 and 1
calculator_tasks:
- operation: multiply, a: 12, b: 8
- operation: add, a: 8, b: 1
profit_task: null

Example:
User query: I bought an item for 100 and sold it for 125. Calculate profit.
calculator_tasks: []
profit_task:
  cost_price: 100
  selling_price: 125
""".strip()


def supervisor_node(state: AgentDemoState):
    request = state["request"]
    supervisor_llm = ChatGroq(
        model=os.getenv("GROQ_MODEL"),
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
        max_retries=2,
    ).with_structured_output(
        SupervisorPlan,
        method="json_mode",
    )
    plan = supervisor_llm.invoke(
        [
            ("system", SUPERVISOR_PROMPT),
            ("human", f"User query: {request}"),
        ]
    )

    calculator_tasks = [task.model_dump() for task in plan.calculator_tasks]
    profit_task = plan.profit_task.model_dump() if plan.profit_task else None

    selected_agents = []
    if calculator_tasks:
        selected_agents.append("calculator_agent")
    if profit_task:
        selected_agents.append("business_agent")

    return {
        "selected_agents": selected_agents,
        "calculator_tasks": calculator_tasks,
        "profit_task": profit_task,
    }


# 4. Worker agents


def calculator_agent_node(state: AgentDemoState):
    result_parts = []

    for task in state["calculator_tasks"]:
        operation = task["operation"]
        a = task["a"]
        b = task["b"]
        tool = CALCULATOR_TOOLS[operation]
        result = tool.invoke({"a": a, "b": b})

        result_parts.append(
            f"{operation.title()} result: {a} and {b} = {result}"
        )

    calculator_result = "; ".join(result_parts)
    return {"calculator_result": calculator_result}


def business_agent_node(state: AgentDemoState):
    result = calculate_profit.invoke(state["profit_task"])
    return {"business_result": result}


# 5. Routing decisions


def route_from_supervisor(
    state: AgentDemoState,
) -> Literal["calculator_agent", "business_agent", "supervisor_response"]:
    if "calculator_agent" in state.get("selected_agents", []):
        return "calculator_agent"
    if "business_agent" in state.get("selected_agents", []):
        return "business_agent"
    return "supervisor_response"


def route_after_calculator(
    state: AgentDemoState,
) -> Literal["business_agent", "supervisor_response"]:
    if "business_agent" in state.get("selected_agents", []):
        return "business_agent"
    return "supervisor_response"


def supervisor_response_node(state: AgentDemoState):
    parts = []
    if state.get("calculator_result"):
        parts.append(state["calculator_result"])
    if state.get("business_result"):
        parts.append(state["business_result"])

    final = " | ".join(parts) if parts else "No supported task found."
    return {"final": final}


# 6. LangGraph wiring


def build_graph():
    builder = StateGraph(AgentDemoState)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("calculator_agent", calculator_agent_node)
    builder.add_node("business_agent", business_agent_node)
    builder.add_node("supervisor_response", supervisor_response_node)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "calculator_agent": "calculator_agent",
            "business_agent": "business_agent",
            "supervisor_response": "supervisor_response",
        },
    )
    builder.add_conditional_edges(
        "calculator_agent",
        route_after_calculator,
        {
            "business_agent": "business_agent",
            "supervisor_response": "supervisor_response",
        },
    )
    builder.add_edge("business_agent", "supervisor_response")
    builder.add_edge("supervisor_response", END)
    return builder.compile()


# 7. Invoke demo


DEMO_REQUESTS = [
    "give me the multiplication of 12 and 8. Add 8 and 1. I bought an item for 100 and sold it for 125. Calculate profit"
]


def run_invoke_demo(request: str) -> None:
    graph = build_graph()
    state = {"request": request}

    final_state = graph.invoke(state)

    print("\nFINAL STATE")
    pprint(final_state, sort_dicts=False)

    print("\nFINAL OUTPUT")
    print(final_state.get("final", "No final response was produced."))


def main() -> None:
    for request in DEMO_REQUESTS:
        run_invoke_demo(request)


if __name__ == "__main__":
    main()
