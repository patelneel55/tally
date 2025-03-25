#!/usr/bin/env python
"""
Test the updated planner with the new supported metrics.
"""
import json
from planner_llm import plan_tool_call
from tool_registry import run_tool

def test_planner():
    """Test the planner with various queries and print the results."""
    
    print("\n=== TESTING PLANNER WITH UPDATED METRICS ===\n")
    
    # Test cases with both supported and unsupported metrics
    test_cases = [
        # Supported metrics
        {"query": "What is the company name for Apple?", "expected_metric": "name"},
        {"query": "What is the market cap of JPMorgan?", "expected_metric": "market_cap"},
        {"query": "What's the net income for Amazon?", "expected_metric": "net_income"},
        {"query": "What is Microsoft's P/E ratio?", "expected_metric": "pe_ratio"},
        {"query": "What is the ROE for Netflix?", "expected_metric": "roe"},
        
        # Unsupported metrics
        {"query": "What is the CET1 ratio for JPMorgan?", "expected_error": True},
        {"query": "What's the dividend yield for Verizon?", "expected_error": True},
        {"query": "Explain how to calculate ROE", "expected_error": True},
    ]
    
    # Run each test case
    for i, case in enumerate(test_cases, 1):
        query = case["query"]
        print(f"\nTest {i}: {query}")
        
        # Get plan from planner
        plan = plan_tool_call(query)
        print(f"Plan: {json.dumps(plan, indent=2)}")
        
        # Verify if the plan matches expectations
        if "expected_metric" in case:
            if plan.get("tool") == "get_financial_metric" and \
               plan.get("args", {}).get("metric") == case["expected_metric"]:
                print(f"✅ Successfully planned for {case['expected_metric']}")
            else:
                print(f"❌ Failed to correctly plan for {case['expected_metric']}")
        
        if "expected_error" in case and case["expected_error"]:
            if plan.get("tool") == "error":
                print(f"✅ Correctly returned error for unsupported metric")
            else:
                print(f"❌ Failed to return error for unsupported metric")
    
    print("\n=== TESTING COMPLETE ===\n")

if __name__ == "__main__":
    test_planner() 