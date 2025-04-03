import logging
from visual_block_extractor import VisualBlockExtractor
from xbrl_fact_extractor import XBRLFactExtractor
from markdown_renderer import MarkdownRenderer

logging.basicConfig(level=logging.DEBUG)

ixbrl_path = "sample_ixbrl.html"  # original file with tags
cleaned_path = "cleaned_sample_ixbrl.html"  # from IXBRLPreprocessor
output_path = "output.md"

def run_markdown_render_test():
    # Extract facts
    fact_extractor = XBRLFactExtractor(log_level=logging.DEBUG)
    assert fact_extractor.load_file(ixbrl_path), f"❌ Failed to load: {ixbrl_path}"
    facts = fact_extractor.extract_facts()
    assert facts, "❌ No XBRL facts extracted"

    # Extract visual blocks
    block_extractor = VisualBlockExtractor(log_level=logging.DEBUG)
    assert block_extractor.load_file(cleaned_path), f"❌ Failed to load: {cleaned_path}"
    blocks = block_extractor.extract_blocks()
    assert blocks, "❌ No visual blocks extracted"

    # Render Markdown
    renderer = MarkdownRenderer(blocks, facts, log_level=logging.DEBUG)
    md = renderer.render()
    assert md.startswith("#") or md.startswith("**"), "❌ Markdown doesn't start with expected heading/text"

    # Save and preview
    saved = renderer.save_to_file(output_path)
    assert saved, "❌ Failed to save Markdown file"
    
    preview = renderer.preview(12)
    print("\n✅ Markdown rendering complete")
    print(f"First 12 lines of Markdown:\n\n{preview}")

if __name__ == "__main__":
    run_markdown_render_test() 