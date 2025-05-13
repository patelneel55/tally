import logging
from typing import Any, Dict, List, Optional, TypedDict, Union, cast

from langgraph_supervisor import create_supervisor

from infra.agents.interfaces import IAgent
from infra.tools.base import ITool


# Set up logging
logger = logging.getLogger(__name__)

# class ResearchAgent(IAgent):
#     def __init__(self):
#         pass

#     def add_tool(self, tool: ITool) -> None:
#         """
#         Add a tool to the agent's toolset.

#         Args:
#             tool: The tool to add
#         """
#         self.tools.append(tool)

#     def get_tools(self) -> List[ITool]:
#         """
#         Get all tools available to this agent.

#         Returns:
#             A list of tools available to the agent
#         """
#         return self.tools


class ResearchAgentSupervisor:
    def __init__(self):
        pass

    async def run(self):
        create_supervisor()
        pass


# User flow:
# research_agent = ResearchAgent()
# await research_agent.run("What is the PE ratio of AAPL 2024?")
# research supervisor
# agents:
# - math and financial modeling agent
# - database agent
# - researcher agent
#
# math and financial modeling agent:
# tools:
# - calculator tool
# - llm-math tool
# - financial calculator tools
# - <possibly> vector search formulas tool
#
#
# indexing agent (responsible for checking to see if data and needs to be indexed):
# - vectorsearch tool
# - Cache search tool
# - indexing pipeline tool
#
# researcher agent
# - vector search tool
# - web search tool
