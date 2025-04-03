import logging
import json
from visual_block_extractor import VisualBlockExtractor
from xbrl_fact_extractor import XBRLFactExtractor
from markdown_renderer import MarkdownRenderer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """
    Demonstrate a complete pipeline:
    1. Extract facts from original iXBRL file
    2. Extract visual blocks from cleaned HTML
    3. Render both into a Markdown document with XBRL annotations
    """
    # File paths
    original_ixbrl_file = "sample_ixbrl.html"  # Original iXBRL with XBRL tags
    cleaned_html_file = "cleaned_sample_ixbrl.html"  # Cleaned HTML without XBRL tags
    output_markdown_file = "output_document.md"  # Output file
    
    # Step 1: Extract XBRL facts from the original iXBRL file
    logger.info("Step 1: Extracting XBRL facts")
    fact_extractor = XBRLFactExtractor()
    if fact_extractor.load_file(original_ixbrl_file):
        facts = fact_extractor.extract_facts()
        logger.info(f"Extracted {len(facts)} unique concept facts")
    else:
        logger.warning("Failed to load iXBRL file for fact extraction, proceeding without facts")
        facts = {}
    
    # Step 2: Extract visual blocks from the cleaned HTML file
    logger.info("Step 2: Extracting visual blocks")
    block_extractor = VisualBlockExtractor()
    if block_extractor.load_file(cleaned_html_file):
        blocks = block_extractor.extract_blocks()
        logger.info(f"Extracted {len(blocks)} visual blocks")
    else:
        logger.error("Failed to load HTML file for block extraction")
        return
    
    # Step 3: Render the blocks and facts to Markdown
    logger.info("Step 3: Rendering to Markdown")
    markdown_renderer = MarkdownRenderer(blocks, facts)
    markdown = markdown_renderer.render()
    
    # Save to file
    if markdown_renderer.save_to_file(output_markdown_file):
        logger.info(f"Markdown saved to {output_markdown_file}")
    else:
        logger.error("Failed to save Markdown to file")
    
    # Preview the output
    logger.info("Preview of generated Markdown:")
    preview = markdown_renderer.preview(15)  # Show first 15 lines
    
    # Optional: Save extracted data for reference
    with open("extracted_facts.json", "w") as f:
        json.dump(facts, f, indent=2)
    logger.info("Saved extracted facts to extracted_facts.json")
    
    with open("extracted_blocks.json", "w") as f:
        json.dump(blocks, f, indent=2)
    logger.info("Saved extracted blocks to extracted_blocks.json")


if __name__ == "__main__":
    main() 