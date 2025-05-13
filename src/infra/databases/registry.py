from enum import Enum

from sqlalchemy import JSON, DateTime, Integer, LargeBinary, PickleType, UnicodeText
from sqlalchemy.orm import mapped_column

from infra.databases.cache import Cache


class TableNames(str, Enum):
    SECFilings = "sec_filings"
    SECFilingHierarchy = "sec_filing_hierarchy"
    SECFilingSummary = "sec_filing_summary"

    WebLoader = "web_loader"
    PDFLoder = "pdf_loader"


TABLE_SCHEMAS = {
    TableNames.SECFilings: {
        "value": mapped_column(PickleType, nullable=False),
    },
    TableNames.WebLoader: {
        "headers": mapped_column(PickleType, nullable=False),
        "status_code": mapped_column(Integer, nullable=False),
        "body": mapped_column(UnicodeText, nullable=True),
    },
    TableNames.SECFilingHierarchy: {
        "ticker": mapped_column(UnicodeText, nullable=False),
        "filing_type": mapped_column(UnicodeText, nullable=False),
        "filing_date": mapped_column(DateTime(timezone=True), nullable=False),
        # "status": mapped_column(UnicodeText, nullable=False),
        "document_structure": mapped_column(JSON, nullable=True),
    },
    TableNames.SECFilingSummary: {
        "ticker": mapped_column(UnicodeText, nullable=False),
        "filing_type": mapped_column(UnicodeText, nullable=False),
        "filing_date": mapped_column(DateTime(timezone=True), nullable=False),
        "original_text": mapped_column(UnicodeText, nullable=False),
        "summary": mapped_column(UnicodeText, nullable=False),
    },
}


def init_table_schemas():
    for table_name, column_mapping in TABLE_SCHEMAS.items():
        Cache._get_or_create_cache_model(
            table_name.value, column_mapping=column_mapping
        )
