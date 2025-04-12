import abc
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator
from schema import And, Or, Schema, Use


class AcquisitionOutput(abc.ABC):
    """
    Abstract base class for acquisition outputs.
    """

    @abc.abstractmethod
    def get_uris(self) -> List[str]:
        """
        Abstract method to get the URIs from the acquisition output.
        """
        pass

    @abc.abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Abstract method to get the metadata from the acquisition output.
        """
        pass


class FilingType(str, Enum):
    """SEC filing types enumeration."""

    ANNUAL_REPORT = "10-K"
    QUARTERLY_REPORT = "10-Q"
    CURRENT_REPORT = "8-K"
    PROXY_STATEMENT = "DEF 14A"
    REGISTRATION_STATEMENT = "S-1"


class DataFormat(str, Enum):
    """Data format options for SEC filings."""

    HTML = "html"
    PDF = "pdf"


class SECFiling(BaseModel, AcquisitionOutput):
    """
    Represents an SEC filing document with associated metadata.

    This model is used to structure the data returned from the SEC API
    and provide a consistent interface for working with filing documents.
    """

    accessionNo: str = Field(..., description="SEC filing accession number")
    formType: str = Field(..., description="Type of SEC filing (e.g. 10-K, 10-Q)")
    filing_date: datetime = Field(
        ..., description="Date the filing was submitted", alias="filedAt"
    )
    company_name: str = Field(..., description="Name of the filing company")
    ticker: str = Field(..., description="Stock ticker symbol")
    cik: str = Field(..., description="SEC Central Index Key (CIK)")
    documentURL: Optional[str] = Field("", description="URL to the filing document")
    textURL: Optional[str] = Field(
        None, description="URL to the plain text version", alias="linkToTxt"
    )
    pdf_path: Optional[str] = Field(None, description="Local path to cached PDF file")
    html_path: Optional[str] = Field(None, description="Local path to cached HTML file")

    class Config:
        populate_by_name = True

    @field_validator("filing_date", mode="before")
    def parse_datetime(cls, value):
        """Convert ISO format string to datetime object."""
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value

    def get_uris(self) -> List[str]:
        """Return a list of URIs for the filing."""
        uris = []
        if self.documentURL:
            uri = self._convert_to_sec_gov_url(self.documentURL)
            uris.append(uri)
        return uris

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata for the filing."""
        return self.model_dump(exclude={"pdf_path", "html_path", "textURL"})

    def _convert_to_sec_gov_url(self, url: str) -> Optional[str]:
        """
        Convert an API URL to a SEC.gov URL format.

        The PDF Generator API requires URLs in the SEC.gov format.

        Args:
            url: The URL to convert

        Returns:
            SEC.gov formatted URL if conversion is successful, None otherwise
        """
        # If it's already a SEC.gov URL, return it as is
        if url.startswith("https://www.sec.gov/"):
            # Remove inline XBRL parameters if present
            return url.replace("/ix?doc=", "")

        # If it's a URL from the SEC API
        if "sec-api.io" in url:
            # Extract the path after /Archives/
            parts = url.split("/Archives/")
            if len(parts) > 1:
                return f"https://www.sec.gov/Archives/{parts[1]}"


sec_api_query_response_schema = Schema(
    [
        And(
            {
                "accessionNo": And(str, len),
                "formType": And(str, len),
                "cik": And(str, len),
                "companyName": And(str, len),
                "filedAt": And(str, len),
                "ticker": And(str, len),
                "documentFormatFiles": Or(
                    [
                        {
                            "type": And(str, len),
                            "documentUrl": And(str, len),
                        }
                    ],
                    None,
                    ignore_extra_keys=True,
                ),
            },
            Use(
                lambda x: SECFiling(
                    accessionNo=x["accessionNo"],
                    formType=x["formType"],
                    filing_date=x["filedAt"],
                    company_name=x["companyName"],
                    ticker=x["ticker"],
                    cik=x["cik"],
                    documentURL=next(
                        d["documentUrl"]
                        for d in x["documentFormatFiles"]
                        if d["type"] == x["formType"]
                    ),
                ),
            ),
            ignore_extra_keys=True,
        )
    ],
    ignore_extra_keys=True,
)
