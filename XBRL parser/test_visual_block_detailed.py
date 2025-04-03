import logging
from visual_block_extractor import VisualBlockExtractor

logging.basicConfig(level=logging.DEBUG)

input_path = "cleaned_sample_ixbrl.html"

def run_visual_block_test():
    extractor = VisualBlockExtractor(log_level=logging.DEBUG)
    
    # Load the cleaned HTML file
    success = extractor.load_file(input_path)
    assert success, f"❌ Failed to load HTML from {input_path}"

    # Extract the visual blocks
    blocks = extractor.extract_blocks()
    assert isinstance(blocks, list), "❌ Output is not a list"
    assert len(blocks) > 0, "❌ No blocks were extracted — check preprocessing or tag filtering"

    # Log a summary of block types
    print("\n✅ Visual block extraction complete")
    print(f"Total blocks extracted: {len(blocks)}")

    type_counts = {}
    for block in blocks:
        btype = block["type"]
        type_counts[btype] = type_counts.get(btype, 0) + 1

    print("\nBlock type counts:")
    for t, c in type_counts.items():
        print(f"- {t}: {c}")

    # Show first few blocks
    print("\nSample blocks:\n")
    for b in blocks[:5]:
        print(f"[{b['line_number']}] <{b['tag']}> {b['type']} | size: {b['font_size']}, bold: {b['is_bold']}, italic: {b['is_italic']}, underlined: {b['is_underlined']}")
        print(f"   → {b['text'][:100]}...\n")

if __name__ == "__main__":
    run_visual_block_test() 