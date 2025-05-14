import asyncio
import json
import logging
import sys
import time

import langchain
from langchain.callbacks.base import BaseCallbackHandler

from infra.collections.registry import get_schema_registry
from infra.embeddings.providers import OpenAIEmbeddingProvider
from infra.llm.providers import OpenAIProvider
from infra.pipelines.mem_walker import MemoryTreeNode, MemWalker
from infra.tools.vector_search import DatabaseSearchTool, VectorSearchQuery
from infra.utils import ProgressTracker


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
        search_tool = DatabaseSearchTool(llm_provider=OpenAIProvider())

        async def run_case(ticker, case, answer, tracker):
            start = time.perf_counter()
            output_str = await search_tool.execute(
                **VectorSearchQuery(
                    query=case,
                    justification="Why not?",
                    collection="SECFilings",
                    filters={
                        "ticker": ticker,
                        "formType": "10-Q",
                    },
                ).model_dump()
            )
            end = time.perf_counter()
            await tracker.step()
            output = json.loads(output_str)
            output["case"] = case
            output["duration"] = f"{end - start:.4f}"
            # if not answer:
            #     return output

            # # Verify whether the response matches the answer
            # context = output["collected_context"]

            return output

        test_cases = {
            "AAPL": [
                ("What is the operating income for six month ended march 2025?", None),
                # ("How did Apple's net cash position change from September 28, 2024 to March 29, 2025, and what were the primary drivers of that change?", None),
                # ("List all related information to Apple's liquidity strategy, including cash flow from operations, investing, and financing activities",None),
                # ("Summarize Apple's liquidity strategy, including cash flow from operations, investing, and financing activities.",None),
                (
                    "What were the year-over-year changes in EPS (basic and diluted)?",
                    None,
                ),
                (
                    "Compare the gross margins for Products vs. Services in Q2 2025",
                    None,
                ),
                (
                    "List the contingencies that the company has and list the new products for the second quarter",
                    None,
                ),
                (
                    "How much was the change in foreign currency translation, net of tax YoY?",
                    None,
                ),
                ("List all the ongoing legal proceedings against the company", None),
                ("How much cash and cash equivalents were held in escrow?", None),
                ("What is the latest buyback authorization?", None),
                ("List all exhibits in the document", None),
                (
                    "How many vendors represented 10% or more of vendor receivables?",
                    None,
                ),
                ("What were the product updates announced this quarter?", None),
            ],
            "JPM": [
                # ("What business segments contributed most to noninterest revenue?", None),
            ],
        }

        flattened = [
            (ticker, case, answer)
            for ticker, cases in test_cases.items()
            for case, answer in cases
        ]
        async with ProgressTracker(len(flattened)) as tracker:
            tasks = [
                run_case(ticker, case, answer, tracker)
                for ticker, case, answer in flattened
            ]
            results = await asyncio.gather(*tasks)

        with open("cache/retrieval_testing.json", "w") as f:
            json.dump(results, f, indent=2)

        logging.basicConfig(level=logging.INFO)
        search_tool = DatabaseSearchTool(llm_provider=OpenAIProvider())
        output_str = await search_tool.execute(
            **VectorSearchQuery(
                query="What is the latest buyback authorization?",
                justification="Why not?",
                collection="SECFilings",
                filters={
                    "ticker": "AAPL",
                    "formType": "10-Q",
                },
            ).model_dump()
        )
        with open("cache/output.json", "w") as f:
            f.write(output_str)

        # logging.basicConfig(level=logging.DEBUG)
        # collection = get_schema_registry().get_collection("SECFilings")
        # collection.indexer.embedding_provider = OpenAIEmbeddingProvider()
        # # collection.indexer.vector_store = WeaviateVectorStore(index_name="SECFilings")
        # await collection.indexer.run(
        #     **{
        #         "identifier": ["AAPL"],
        #         "filing_type": "10-Q",
        #     }
        # )

    sys.exit(asyncio.run(run()))
