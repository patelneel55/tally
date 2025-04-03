# test_diagnostics_preprocessor.py

import logging
from ixbrl_preprocessor import IXBRLPreprocessor

logging.basicConfig(level=logging.DEBUG)

# Assume this is a real iXBRL file provided externally
input_path = "sample_ixbrl.html"
output_path = "cleaned_sample_ixbrl.html"

def run_preprocessor_test():
    pre = IXBRLPreprocessor(log_level=logging.DEBUG)
    
    success = pre.load_file(input_path)
    assert success, f"Failed to load file: {input_path}"

    html = pre.process()
    assert html is not None, "Processing returned None"
    assert "<html" in html or "<body" in html, "HTML structure missing from output"
    assert pre.xbrl_tag_count > 0, "No XBRL tags removed — unexpected!"

    save_success = pre.save_to_file(output_path)
    assert save_success, f"Failed to save output to {output_path}"

    print("\n✅ Preprocessing complete")
    print(f"Tags removed: {pre.xbrl_tag_count}")
    print("\nPreview of cleaned HTML:\n")
    for line in html.splitlines()[:20]:
        print(line)

if __name__ == "__main__":
    run_preprocessor_test() 