"""
Tool Registry for Analyst AI.

This module serves as a central registry for all tools available in the Analyst AI system.
It provides a mechanism to look up and execute tools by their string names.
"""
from typing import Dict, Any, Callable

# Import tools
from tools.get_financial_metric import get_financial_metric


# Registry mapping tool names to their function implementations
tool_registry: Dict[str, Callable] = {
    "get_financial_metric": get_financial_metric
}


def run_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool by its name with the provided arguments.
    
    Args:
        tool_name (str): The name of the tool to execute
        args (dict): Dictionary of arguments to pass to the tool
        
    Returns:
        dict: The result from the tool execution
        
    Raises:
        ValueError: If the tool_name is not found in the registry
        
    Example:
        >>> run_tool("get_financial_metric", {"ticker": "AAPL", "metric": "name"})
        {'value': 'Apple Inc.', 'ticker': 'AAPL', 'metric': 'name'}
    """
    try:
        # Look up the function from the registry
        if tool_name not in tool_registry:
            return {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(tool_registry.keys())
            }
        
        # Get the function and call it with unpacked arguments
        tool_function = tool_registry[tool_name]
        result = tool_function(**args)
        
        return result
    
    except TypeError as e:
        # Handle the case where arguments don't match the function signature
        return {
            "error": f"Invalid arguments for tool {tool_name}: {str(e)}",
            "tool_name": tool_name
        }
    except Exception as e:
        # Handle any other unexpected errors
        return {
            "error": f"Error executing tool {tool_name}: {str(e)}",
            "tool_name": tool_name
        }


if __name__ == "__main__":
    # Example usage with the updated metrics
    result1 = run_tool("get_financial_metric", {"ticker": "AAPL", "metric": "name"})
    print(result1)
    
    result2 = run_tool("get_financial_metric", {"ticker": "JPM", "metric": "market_cap"})
    print(result2)
    
    result3 = run_tool("get_financial_metric", {"ticker": "MSFT", "metric": "total_employees"})
    print(result3)
    
    # Error cases
    result4 = run_tool("unknown_tool", {"some_arg": "value"})
    print(result4)
    
    result5 = run_tool("get_financial_metric", {"invalid_arg": "value"})
    print(result5) 