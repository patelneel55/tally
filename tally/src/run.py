import asyncio
import logging
import os
import sys

import langchain
from langchain.callbacks import StdOutCallbackHandler
from langchain.callbacks.base import BaseCallbackHandler
from langgraph.graph.graph import CompiledGraph

# from langgraph.tracing import trace_graph

from infra.agents.data_index_agent import DataIndexAgent

# from infra.agents.math_agent import MathAgent

from infra.embeddings.providers import OpenAIEmbeddingProvider
from infra.llm.providers import OpenAIProvider


# import pysqlite3

# sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")


from infra.vector_stores.weaviate import WeaviateVectorStore
from infra.collections.registry import get_schema_registry


class CaptureFullPromptHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        print("\n=== 🚨 PROMPT PAYLOAD ===")
        for p in prompts:
            print(p)
        print("\n=== 🚨 Function specs ===")
        # print(kwargs)
        if "tools" in kwargs.get("invocation_params", {}):
            for f in kwargs.get("invocation_params").get("tools"):
                print(f)


if __name__ == "__main__":
    langchain.debug = True

    async def run():
        # vector_store = WeaviateVectorStore()
        # embeddings = OpenAIEmbeddingProvider()
        # agent = DataIndexAgent(
        #     llm_provider=OpenAIProvider(),
        #     vector_store=vector_store,
        #     embedding_provider=embeddings,
        # )
        # # agent = MathAgent(llm_provider=OpenAIProvider())
        # workflow: CompiledGraph = agent.build_agent()
        # callback = StdOutCallbackHandler()

        # result = workflow.invoke(
        #     {
        #         "messages": [
        #             {
        #                 "role": "user",
        #                 "content": "What were JPM's comment's about commercial real estate looking forward in 2024?",
        #                 # "content": "Today's date is April 23rd 2025. What is the net income of Google (GOOG) in 2022?",
        #                 # "content": "Sarah has 15 apples. She buys 8 more apples at the store. Then, she gives 5 apples to her friend Tom. How many apples does Sarah have left?",
        #             }
        #         ]
        #     },
        #     # config={"configurable": {"thread_id": 42}}
        #     # {"messages": [{"role": "user", "content": "Sarah has 15 apples. She buys 8 more apples at the store. Then, she gives 5 apples to her friend Tom. How many apples does Sarah have left?"}]},
        #     # config={"callbacks": [CaptureFullPromptHandler(), callback]},
        # )
        # print(result)
        logging.basicConfig(level=logging.DEBUG)
        collection = get_schema_registry().get_collection("SECFilings")
        collection.indexer.embedding_provider = OpenAIEmbeddingProvider()
        collection.indexer.vector_store = WeaviateVectorStore(index_name="SECFilings")
        await collection.indexer.run(
            **{
                "identifier": ["AAPL"],
                "filing_type": "10-Q",
            }
        )

    sys.exit(asyncio.run(run()))
