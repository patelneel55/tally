# test_diagnostics_xbrl_facts.py

import logging
from xbrl_fact_extractor import XBRLFactExtractor

logging.basicConfig(level=logging.DEBUG)

ixbrl_file_path = "sample_ixbrl.html"  # This must be the original, uncleaned iXBRL

def run_fact_extraction_test():
    extractor = XBRLFactExtractor(log_level=logging.DEBUG)

    success = extractor.load_file(ixbrl_file_path)
    assert success, f"❌ Failed to load iXBRL file: {ixbrl_file_path}"

    facts = extractor.extract_facts()
    assert isinstance(facts, dict), "❌ extract_facts() did not return a dict"
    assert len(facts) > 0, "❌ No facts extracted — check tag parsing or file structure"

    print("\n✅ Fact extraction complete")
    print(f"Total unique concepts extracted: {len(facts)}")
    total_instances = sum(len(v) for v in facts.values())
    print(f"Total fact instances extracted: {total_instances}")

    # Print a few samples
    print("\nSample extracted facts:")
    for name, instances in list(facts.items())[:5]:
        print(f"- {name}:")
        for fact in instances[:2]:  # limit to 2 facts per concept
            print(f"    value: {fact['value']} | tag: {fact['tag']} | ctx: {fact.get('contextRef')} | unit: {fact.get('unitRef')}")
        print()

    # Spot-check one specific fact if you know it exists
    sample_tag = "us-gaap:NetIncomeLoss"
    if sample_tag in facts:
        print(f"✔️ Found {sample_tag}: {facts[sample_tag][0]}")
    else:
        print(f"⚠️ Did not find {sample_tag} — may not exist in this sample")

if __name__ == "__main__":
    run_fact_extraction_test() 