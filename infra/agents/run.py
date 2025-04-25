import sys

import pysqlite3

sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

import asyncio
import logging
import os
import sys

from langgraph.graph.graph import CompiledGraph

from infra.agents.data_index_agent import DataIndexAgent
from infra.agents.math_agent import MathAgent
from infra.embeddings.providers import OpenAIEmbeddingProvider
from infra.llm.providers import OpenAIProvider
from infra.vector_stores.weaviate import WeaviateVectorStore

if __name__ == "__main__":

    async def run():
        vector_store = WeaviateVectorStore()
        embeddings = OpenAIEmbeddingProvider()
        llm_provider = OpenAIProvider()
        agent = DataIndexAgent(
            llm_provider=llm_provider,
            vector_store=vector_store,
            embedding_provider=embeddings,
        )
        # agent = MathAgent(llm_provider=OpenAIProvider())
        workflow: CompiledGraph = agent.build_agent()

        events = workflow.stream(
            {
                "messages": [
                    {
                        "role": "user",
                        # "content": "What were JPM's comment's about commercial real estate looking forward in 2024?",
                        "content": "Today's date is April 23rd 2025. What is the net income of Google (GOOG) in 2022?",
                    }
                ]
            },
            # {"messages": [{"role": "user", "content": "Sarah has 15 apples. She buys 8 more apples at the store. Then, she gives 5 apples to her friend Tom. How many apples does Sarah have left?"}]},
            stream_mode="values",
        )
        for event in events:
            event["messages"][-1].pretty_print()

    sys.exit(asyncio.run(run()))
