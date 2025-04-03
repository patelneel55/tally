import unittest
import logging
import json
import os
from markdown_renderer import MarkdownRenderer


class TestMarkdownRenderer(unittest.TestCase):
    """Test cases for the MarkdownRenderer class"""
    
    def setUp(self):
        """Set up test fixtures before each test method is run"""
        # Configure logging to capture log output
        logging.basicConfig(level=logging.INFO)
        
        # Sample blocks that mimics output from VisualBlockExtractor
        self.sample_blocks = [
            {
                "type": "heading",
                "tag": "h1",
                "text": "Annual Report 2023",
                "font_size": 26,
                "is_bold": True,
                "is_italic": False,
                "is_underlined": False,
                "line_number": 1
            },
            {
                "type": "heading",
                "tag": "h2",
                "text": "Financial Highlights",
                "font_size": 22,
                "is_bold": True,
                "is_italic": False,
                "is_underlined": False,
                "line_number": 2
            },
            {
                "type": "paragraph",
                "tag": "p",
                "text": "Revenue: $10,500,000",
                "font_size": 12,
                "is_bold": False,
                "is_italic": False,
                "is_underlined": False,
                "line_number": 3
            },
            {
                "type": "paragraph",
                "tag": "p",
                "text": "Net Income: $5,000,000",
                "font_size": 12,
                "is_bold": False,
                "is_italic": False,
                "is_underlined": False,
                "line_number": 4
            },
            {
                "type": "heading",
                "tag": "h3",
                "text": "Management Discussion",
                "font_size": 20,
                "is_bold": False,
                "is_italic": False,
                "is_underlined": False,
                "line_number": 5
            },
            {
                "type": "paragraph",
                "tag": "p",
                "text": "This was a strong year for our operations despite market challenges.",
                "font_size": 12,
                "is_bold": False,
                "is_italic": True,
                "is_underlined": False,
                "line_number": 6
            },
            {
                "type": "table",
                "tag": "table",
                "text": "<table><tr><th>Quarter</th><th>Revenue</th></tr><tr><td>Q1</td><td>$2,500,000</td></tr></table>",
                "font_size": 12,
                "is_bold": False,
                "is_italic": False,
                "is_underlined": False,
                "line_number": 7
            }
        ]
        
        # Sample XBRL facts
        self.sample_facts = {
            "us-gaap:Revenue": [
                {"value": "10500000", "contextRef": "FY2023", "unitRef": "USD"}
            ],
            "us-gaap:NetIncomeLoss": [
                {"value": "5000000", "contextRef": "FY2023", "unitRef": "USD"}
            ]
        }
        
    def test_initialization(self):
        """Test MarkdownRenderer initialization"""
        renderer = MarkdownRenderer(self.sample_blocks)
        self.assertEqual(len(renderer.blocks), 7)
        self.assertEqual(len(renderer.facts), 0)
        
        renderer_with_facts = MarkdownRenderer(self.sample_blocks, self.sample_facts)
        self.assertEqual(len(renderer_with_facts.facts), 2)
    
    def test_render_without_facts(self):
        """Test rendering blocks without XBRL facts"""
        renderer = MarkdownRenderer(self.sample_blocks)
        markdown = renderer.render()
        
        # Check basic structure
        self.assertIn("# **Annual Report 2023**", markdown)
        self.assertIn("## **Financial Highlights**", markdown)
        self.assertIn("### Management Discussion", markdown)
        self.assertIn("Revenue: $10,500,000", markdown)
        self.assertIn("*This was a strong year for our operations despite market challenges.*", markdown)
        
        # Check that there are no footnotes
        self.assertNotIn("## Footnotes", markdown)
        
        # Check for table
        self.assertIn("<div class='table-container'>", markdown)
        self.assertIn("<table><tr><th>Quarter</th><th>Revenue</th></tr>", markdown)
    
    def test_render_with_facts(self):
        """Test rendering blocks with XBRL facts"""
        renderer = MarkdownRenderer(self.sample_blocks, self.sample_facts)
        markdown = renderer.render()
        
        # Check that facts were linked - with the correct format our implementation uses
        self.assertIn("Revenue[^", markdown)
        self.assertIn("Net Income[^", markdown)
        
        # Check for footnotes section
        self.assertIn("## Footnotes", markdown)
        self.assertIn("[^1]:", markdown)
        self.assertIn("us-gaap:Revenue | Context: FY2023 | Unit: USD", markdown)
    
    def test_save_to_file(self):
        """Test saving the rendered Markdown to a file"""
        renderer = MarkdownRenderer(self.sample_blocks, self.sample_facts)
        temp_file = "temp_test_output.md"
        
        # Save to file
        result = renderer.save_to_file(temp_file)
        self.assertTrue(result)
        
        # Check that file exists and has content
        self.assertTrue(os.path.exists(temp_file))
        with open(temp_file, 'r') as f:
            content = f.read()
            self.assertIn("# **Annual Report 2023**", content)
            self.assertIn("## Footnotes", content)
        
        # Clean up
        os.remove(temp_file)
    
    def test_preview(self):
        """Test previewing the first n lines of rendered Markdown"""
        renderer = MarkdownRenderer(self.sample_blocks)
        preview = renderer.preview(3)
        
        # Should contain the first heading but not everything
        self.assertIn("# **Annual Report 2023**", preview)
        self.assertLess(len(preview.split('\n')), 10)  # Should be limited
    
    def test_heading_level_mapping(self):
        """Test mapping of font sizes to heading levels"""
        renderer = MarkdownRenderer(self.sample_blocks)
        
        # Test various font sizes
        self.assertEqual(renderer._get_heading_level(26), "#")
        self.assertEqual(renderer._get_heading_level(24), "#")
        self.assertEqual(renderer._get_heading_level(23), "##")
        self.assertEqual(renderer._get_heading_level(22), "##")
        self.assertEqual(renderer._get_heading_level(20), "###")
        self.assertEqual(renderer._get_heading_level(18), "####")
        self.assertEqual(renderer._get_heading_level(16), "#####")
        self.assertEqual(renderer._get_heading_level(14), "######")
        self.assertEqual(renderer._get_heading_level(12), "")  # Not a heading
    
    def test_styling(self):
        """Test application of text styling (bold, italic, underline)"""
        # Create blocks with different styling
        styled_blocks = [
            {
                "type": "paragraph",
                "text": "Bold text",
                "font_size": 12,
                "is_bold": True,
                "is_italic": False,
                "is_underlined": False,
                "line_number": 1
            },
            {
                "type": "paragraph",
                "text": "Italic text",
                "font_size": 12,
                "is_bold": False,
                "is_italic": True,
                "is_underlined": False,
                "line_number": 2
            },
            {
                "type": "paragraph",
                "text": "Underlined text",
                "font_size": 12,
                "is_bold": False,
                "is_italic": False,
                "is_underlined": True,
                "line_number": 3
            },
            {
                "type": "paragraph",
                "text": "Bold and italic",
                "font_size": 12,
                "is_bold": True,
                "is_italic": True,
                "is_underlined": False,
                "line_number": 4
            }
        ]
        
        renderer = MarkdownRenderer(styled_blocks)
        markdown = renderer.render()
        
        self.assertIn("**Bold text**", markdown)
        self.assertIn("*Italic text*", markdown)
        self.assertIn("<u>Underlined text</u>", markdown)
        self.assertIn("***Bold and italic***", markdown)


if __name__ == '__main__':
    unittest.main() 