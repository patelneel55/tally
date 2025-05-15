import asyncio
import json
import logging
import sys
import time

import langchain
from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks import FileCallbackHandler, StdOutCallbackHandler

from infra.collections.registry import get_schema_registry
from infra.embeddings.providers import OpenAIEmbeddingProvider
from infra.llm.providers import OpenAIProvider
from infra.pipelines.mem_walker import MemoryTreeNode, MemWalker
from infra.tools.database_search import DatabaseSearchTool, VectorSearchQuery
from infra.utils import ProgressTracker
from infra.agents.retrieval_agent import RetrievalAgent

from infra.vector_stores.weaviate import WeaviateVectorStore
from langgraph.graph.graph import CompiledGraph


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
                ("What were JPM's comment's about commercial real estate looking forward in 2024?", None)
                # ("What business segments contributed most to noninterest revenue?", None),
            ],
        }
        
        vector_store = WeaviateVectorStore()
        embeddings = OpenAIEmbeddingProvider()
        agent = RetrievalAgent(
            llm_provider=OpenAIProvider(),
            vector_store=vector_store,
            embedding_provider=embeddings,
        )
        workflow: CompiledGraph = agent.build_agent()
        callback = StdOutCallbackHandler()
        

        async def run_case(ticker, case, answer, tracker):
            start = time.perf_counter()
            await workflow.ainvoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": case,
                        }
                    ]
                },
                config={"callbacks": [FileCallbackHandler(filename=f"cache/{ticker}_{hash(case)}")]},
            )
            end = time.perf_counter()
            await tracker.step()
            return case, f"{end - start:.4f}"

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

        with open("cache/retrieval_metrics.json", "w") as f:
            for case, duration in results:
                f.write(f"Case: {case}\n")
                f.write(f"Duration: {duration}")

    sys.exit(asyncio.run(run()))
