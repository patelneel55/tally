#!/usr/bin/env python3
# test_xbrl_fact_extractor.py

import logging
import json
from xbrl_fact_extractor import XBRLFactExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_extractor_test():
    """
    Test the XBRLFactExtractor with an iXBRL HTML file.
    """
    # Path to the iXBRL file
    input_file = "sample_ixbrl.html"
    
    # Create and configure the extractor
    extractor = XBRLFactExtractor(log_level=logging.INFO)
    
    # Load the iXBRL file
    if not extractor.load_file(input_file):
        logger.error(f"Failed to load file: {input_file}")
        return
    
    # Extract XBRL facts
    facts = extractor.extract_facts()
    
    if not facts:
        logger.warning("No facts were extracted from the file")
        return
    
    # Output statistics
    logger.info(f"Successfully extracted facts from {len(facts)} unique concepts")
    
    # Save facts to JSON for later use
    output_file = "xbrl_facts.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(facts, f, indent=2)
        logger.info(f"Saved extracted facts to {output_file}")
    except Exception as e:
        logger.error(f"Error saving facts to file: {str(e)}")
    
    # Demonstrate using get_facts_by_name for a specific concept
    # Try to find a revenue-related concept as an example
    for concept_name in facts.keys():
        if "revenue" in concept_name.lower():
            logger.info(f"Found revenue-related concept: {concept_name}")
            revenue_facts = extractor.get_facts_by_name(concept_name)
            logger.info(f"Revenue facts: {json.dumps(revenue_facts, indent=2)}")
            break

if __name__ == "__main__":
    logger.info("Starting XBRL Fact Extractor test...")
    run_extractor_test()
    logger.info("Test completed.") 