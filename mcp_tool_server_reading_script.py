"""
MCP Tool Server Reading Script

Use this file when explaining how normal Python functions become MCP tools.

Simple summary:
- FastMCP creates the MCP server.
- @mcp.tool() registers a Python function as an MCP tool.
- mcp.run(transport="stdio") starts the server.
- The LangGraph agent can connect to this server and call these tools.
"""

from mcp.server.fastmcp import FastMCP


# Read out:
# First, I import FastMCP. This is the simple MCP server class that lets me
# expose Python functions as MCP tools.

mcp = FastMCP("AI tool", log_level="ERROR")

# Read out:
# Here I create an MCP server and name it youtube-content-tools.
# I set the log level to ERROR so the terminal output stays clean during the demo.


@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers."""
    # Read out:
    # This decorator registers add_numbers as an MCP tool.
    # The tool accepts two numbers and returns their sum.
    return a + b


@mcp.tool()
def subtract_numbers(a: float, b: float) -> float:
    """Subtract the second number from the first number."""
    # Read out:
    # This creates a subtract tool. It takes two numbers and returns a minus b.
    return a - b


@mcp.tool()
def multiply_numbers(a: float, b: float) -> float:
    """Multiply two numbers."""
    # Read out:
    # This creates a multiply tool. It takes two numbers and returns their product.
    return a * b


@mcp.tool()
def divide_numbers(a: float, b: float) -> float:
    """Divide the first number by the second number."""
    # Read out:
    # This creates a divide tool. Before dividing, I check if the second number is
    # zero because division by zero is invalid.
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b


@mcp.tool()
def calculate_profit(cost_price: float, selling_price: float) -> str:
    """Calculate profit and profit percentage."""
    # Read out:
    # This creates a business tool called calculate_profit.
    # Profit is selling price minus cost price.
    # Profit percentage is profit divided by cost price, multiplied by 100.
    profit = selling_price - cost_price
    profit_percentage = (profit / cost_price) * 100
    return f"Profit: {profit}; Profit percentage: {profit_percentage}%"


if __name__ == "__main__":
    # Read out:
    # This starts the MCP server using standard input and output.
    # The agent can communicate with this MCP server through stdio, without
    # needing an HTTP server.
    mcp.run(transport="stdio")
