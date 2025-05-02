from datetime import date

import pytest
from pydantic import ValidationError

from infra.acquisition.models import DataFormat
from infra.acquisition.sec_fetcher import FilingRequest, FilingType


class TestFilingRequest:
    def test_valid_filing_request_cik_and_ticker(self):
        data = {
            "identifier": ["0000320193", "AAPL"],
            "filing_type": FilingType.ANNUAL_REPORT,
            "start_date": date(2023, 1, 1),
            "end_date": date(2023, 12, 31),
            "max_size": 5,
            "data_format": DataFormat.HTML,
        }
        req = FilingRequest(**data)
        assert req.identifier == ["0000320193", "AAPL"]
        assert (
            req.filing_type == FilingType.ANNUAL_REPORT.value
        )  # or "10-K" if use_enum_values=True
        assert req.start_date == date(2023, 1, 1)
        assert req.end_date == date(2023, 12, 31)
        assert req.max_size == 5
        assert req.data_format == DataFormat.HTML

    def test_valid_filing_request_only_cik(self):
        data = {"identifier": ["0000320193"], "max_size": 1}
        req = FilingRequest(**data)
        assert req.identifier == ["0000320193"]
        assert req.filing_type is None
        assert req.start_date is None
        assert req.end_date is None
        assert req.max_size == 1
        assert req.data_format == DataFormat.HTML  # Default

    def test_valid_filing_request_only_ticker(self):
        data = {"identifier": ["MSFT"]}
        req = FilingRequest(**data)
        assert req.identifier == ["MSFT"]
        assert req.max_size == 1  # Default
        assert req.data_format == DataFormat.HTML  # Default

    def test_filing_request_default_values(self):
        data = {"identifier": ["GOOGL"]}
        req = FilingRequest(**data)
        assert req.max_size == 1
        assert req.data_format == DataFormat.HTML
        assert req.filing_type is None
        assert req.start_date is None
        assert req.end_date is None

    def test_invalid_identifier_empty_list(self):
        with pytest.raises(ValidationError) as exc_info:
            FilingRequest(identifier=[])
        assert "Identifier cannot be empty" in str(exc_info.value)

    def test_invalid_identifier_cik_too_long(self):
        with pytest.raises(ValidationError) as exc_info:
            FilingRequest(identifier=["12345678901"])
        assert "CIK must be 1-10 digits: 12345678901" in str(exc_info.value)

    def test_invalid_identifier_cik_not_digit(self):
        # This case is handled by the ticker validation if not all digits
        # If we want a specific CIK error for non-digits, validator needs change
        # Current validator: if it's digits, checks length. If not digits, checks ticker rules.
        pass

    def test_invalid_identifier_ticker_too_long(self):
        with pytest.raises(ValidationError) as exc_info:
            FilingRequest(identifier=["ABCDEF"])
        assert "Ticker must be 1-5 alphanumeric characters: ABCDEF" in str(
            exc_info.value
        )

    def test_invalid_identifier_ticker_not_alnum(self):
        with pytest.raises(ValidationError) as exc_info:
            FilingRequest(identifier=["AB_CD"])
        assert "Ticker must be 1-5 alphanumeric characters: AB_CD" in str(
            exc_info.value
        )

    def test_invalid_identifier_mixed_valid_and_invalid(self):
        with pytest.raises(ValidationError) as exc_info:
            FilingRequest(identifier=["AAPL", "INVALIDTICKERTOOLONG"])
        assert (
            "Ticker must be 1-5 alphanumeric characters: INVALIDTICKERTOOLONG"
            in str(exc_info.value)
        )

    def test_filing_type_enum_value(self):
        req = FilingRequest(identifier=["TSLA"], filing_type="10-Q")
        assert req.filing_type == FilingType.QUARTERLY_REPORT.value

    def test_invalid_filing_type(self):
        with pytest.raises(ValidationError):
            FilingRequest(identifier=["TSLA"], filing_type="INVALID-TYPE")

    def test_date_conversion(self):
        req = FilingRequest(
            identifier=["IBM"], start_date="2023-01-01", end_date="2023-12-31"
        )
        assert req.start_date == date(2023, 1, 1)
        assert req.end_date == date(2023, 12, 31)

    def test_max_size_validation(self):
        # Pydantic handles type validation for int.
        # If we had custom rules (e.g. >0), we would test them.
        req = FilingRequest(identifier=["AMZN"], max_size=10)
        assert req.max_size == 10

    def test_data_format_enum_value(self):
        req = FilingRequest(identifier=["NFLX"], data_format="pdf")
        assert req.data_format == DataFormat.PDF

    def test_invalid_data_format(self):
        with pytest.raises(ValidationError):
            FilingRequest(identifier=["NFLX"], data_format="invalid_format")
