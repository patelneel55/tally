import asyncio
import logging
import os
import sys
from infra.agents.math_agent import MathAgent
from langgraph.graph.graph import CompiledGraph
from infra.llm.providers import OpenAIProvider

if __name__ == "__main__":
    async def run():
        agent = MathAgent(llm_provider=OpenAIProvider())
        workflow: CompiledGraph = agent.build_agent()

        events = workflow.stream(
            {
                "messages": [
                    {"role": "user", "content": "If I invest $1000 at an annual interest rate of 5%, compounded annually, how much will I have after 3 years?"}
                ]
            },
            # {"messages": [{"role": "user", "content": "Sarah has 15 apples. She buys 8 more apples at the store. Then, she gives 5 apples to her friend Tom. How many apples does Sarah have left?"}]},

            stream_mode="values",
        )
        for event in events:
            event["messages"][-1].pretty_print()
    sys.exit(asyncio.run(run()))
