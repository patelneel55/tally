# import os
# import logging
# from typing import List, Dict, Any, Callable
# from pathlib import Path
# from langchain_core.documents import Document
# import sec_parser as sp
# from sec_parser.processing_engine.core import (
#     AbstractSemanticElementParser,
#     Edgar10KParser,
#     Edgar10QParser,
# )
# from sec_parser.processing_steps.top_section_manager import (
#     TopSectionManagerFor10K,
#     TopSectionManagerFor10Q,
# )
# from sec_parser.semantic_elements import (
#     AbstractSemanticElementParser,
#     AbstractProcessingStep,
#     AbstractSingleElementCheck,
#     NotYetClassifiedElement,
#     TableElement,
#     TextElement,
#     HighlightedTextElement
# )
# from sec_parser.processing_steps import (
#     IndividualSemanticElementExtractor,
#     ImageClassifier,
#     EmptyElementClassifier,
#     TableClassifier,
#     TableOfContentsClassifier,
#     IntroductorySectionElementClassifier,
#     TextClassifier,
#     HighlightedTextClassifier,
#     SupplementaryTextClassifier,
#     PageHeaderClassifier,
#     PageNumberClassifier,
#     TitleClassifier,
#     TextElementMerger
# )
# from sec_parser.processing_steps.individual_semantic_element_extractor.single_element_checks.image_check import (
#     ImageCheck,
# )
# from sec_parser.processing_steps.individual_semantic_element_extractor.single_element_checks.table_check import (
#     TableCheck,
# )
# from sec_parser.processing_steps.individual_semantic_element_extractor.single_element_checks.top_section_title_check import (
#     TopSectionTitleCheck,
# )
# from sec_parser.processing_steps.individual_semantic_element_extractor.single_element_checks.xbrl_tag_check import (
#     XbrlTagCheck,
# )
# from infra.core.interfaces import IParser

# logger = logging.getLogger(__name__)

# class EdgarParser(AbstractSemanticElementParser):
#     """
#     The Edgar10KParser class is responsible for parsing SEC EDGAR 10-K
#     quarterly reports. It transforms the HTML documents into a list
#     of elements. Each element in this list represents a part of
#     the visual structure of the original document.
#     """

#     def get_default_steps(
#         self,
#         get_checks: Callable[[], list[AbstractSingleElementCheck]] | None = None,
#     ) -> list[AbstractProcessingStep]:
#         return [
#             IndividualSemanticElementExtractor(
#                 get_checks=get_checks or self.get_default_single_element_checks,
#             ),
#             ImageClassifier(types_to_process={NotYetClassifiedElement}),
#             EmptyElementClassifier(types_to_process={NotYetClassifiedElement}),
#             TableClassifier(types_to_process={NotYetClassifiedElement}),
#             TableOfContentsClassifier(types_to_process={TableElement}),
#             TopSectionManagerFor10K(types_to_process={NotYetClassifiedElement}),
#             IntroductorySectionElementClassifier(),
#             TextClassifier(types_to_process={NotYetClassifiedElement}),
#             HighlightedTextClassifier(types_to_process={TextElement}),
#             SupplementaryTextClassifier(
#                 types_to_process={TextElement, HighlightedTextElement},
#             ),
#             PageHeaderClassifier(
#                 types_to_process={TextElement, HighlightedTextElement},
#             ),
#             PageNumberClassifier(
#                 types_to_process={TextElement, HighlightedTextElement},
#             ),
#             TitleClassifier(types_to_process={HighlightedTextElement}),
#             TextElementMerger(),
#         ]

#     def get_default_single_element_checks(self) -> list[AbstractSingleElementCheck]:
#         return [
#             TableCheck(),
#             XbrlTagCheck(),
#             ImageCheck(),
#             TopSectionTitleCheck(),
#         ]

# class SECParser(IParser):
#     """
#     Parser for SEC filings using the sec-parser library.
#     """

#     def __init__(self):
#         """Initialize the SEC parser."""
#         pass

#     def parse(self, file_path: str, output_format: IParser.SUPPORTED_FORMATS = "markdown") -> List[Document]:
#         if not os.path.exists(file_path):
#             raise FileNotFoundError(f"HTML file not found: {file_path}")
        
#         # Read the HTML content from the file
#         with open(file_path, 'r', encoding='utf-8') as file:
#             html_content = file.read()
            
#         # Log the file size for debugging purposes
#         logger.debug(f"Read {len(html_content)} bytes from {file_path}")
#         elements = EdgarParser().parse(html_content)
#         tree = sp.TreeBuilder.build(elements)
#         print(sp.render(tree))
#         return None
            