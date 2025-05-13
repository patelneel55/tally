import asyncio
import logging
import sys

import langchain
from langchain.callbacks.base import BaseCallbackHandler

from infra.collections.registry import get_schema_registry
from infra.embeddings.providers import OpenAIEmbeddingProvider
from infra.llm.providers import OpenAIProvider
from infra.pipelines.mem_walker import MemoryTreeNode, MemWalker


# from infra.vector_stores.weaviate import WeaviateVectorStore


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
    # langchain.debug = True

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

        # logging.basicConfig(level=logging.INFO)
        # import json

        # with open("cache/AAPL.json") as f:
        #     data = json.load(f)
        # mem_tree = MemoryTreeNode(**data)

        # mem_walker = MemWalker(llm_provider=OpenAIProvider())
        # context_output = await mem_walker.navigate_tree(
        #     # "How did Apple's net cash position change from September 28, 2024 to March 29, 2025, and what were the primary drivers of that change?",
        #     # "List all related information to Apple's liquidity strategy, including cash flow from operations, investing, and financing activities",
        #     # "Summarize Apple's liquidity strategy, including cash flow from operations, investing, and financing activities.",
        #     # "What were the year-over-year changes in EPS (basic and diluted)?",
        #     # "Compare the gross margins for Products vs. Services in Q2 2025",
        #     # "List the contingencies that the company has and list the new products for the second quarter",
        #     # "How much was the change in foreign currency translation, net of tax YoY?",
        #     # "List all the ongoing legal proceedings against the company",
        #     # "How much cash and cash equivalents were held in escrow?",
        #     # "What is the latest buyback authorization?",
        #     # "List all exhibits in the document",
        #     # "How many vendors represented 10% or more of vendor receivables?",
        #     # "What were the product updates announced this quarter?",
        #     # "As of December 28, 2024, the Company had two vendors that individually represented 10% or more of total vendor non-trade receivables, which accounted for 43% and 24%.",
        #     # "Give me all the details for all the ongoing legal proceedings against AAPL",
        #     # "What is the operating income for six month march 2025?",
        #     mem_tree,
        # )

        # with open("cache/collected_context.json", "w") as f:
        #     json.dump(
        #         [ob.model_dump() for ob in context_output.collected_context],
        #         f,
        #         indent=2,
        #     )

        # with open("cache/navigation.json", "w") as f:
        #     json.dump(
        #         [ob.model_dump() for ob in context_output.navigation_log], f, indent=2
        #     )

        logging.basicConfig(level=logging.DEBUG)
        collection = get_schema_registry().get_collection("SECFilings")
        collection.indexer.embedding_provider = OpenAIEmbeddingProvider()
        # collection.indexer.vector_store = WeaviateVectorStore(index_name="SECFilings")
        await collection.indexer.run(
            **{
                "identifier": ["JPM"],
                "filing_type": "10-Q",
            }
        )

    sys.exit(asyncio.run(run()))
