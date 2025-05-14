import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Tuple

from sqlalchemy.sql import ColumnExpressionArgument

from infra.acquisition.sec_fetcher import SECFiling
from infra.databases.cache import Cache
from infra.databases.engine import get_sqlalchemy_engine
from infra.databases.registry import TableNames
from infra.pipelines.mem_walker import MemoryTreeNode


logger = logging.getLogger(__name__)


class DataMiner(ABC):
    def __init__():
        pass

    @abstractmethod
    def nodes_for_mem_walk(filters: Dict[str, Any]) -> List[MemoryTreeNode]:
        pass


class SECSearch(DataMiner):
    def __init__(self):
        pass

    def nodes_for_mem_walk(self, filters) -> List[MemoryTreeNode]:
        # Convert filters to query the database
        hierarchy_table = Cache(
            get_sqlalchemy_engine(),
            TableNames.SECFilingHierarchy.value,
        )
        db_filters = self._db_filters_from_metadata(hierarchy_table, filters)
        with hierarchy_table.query_builder() as q:
            root_nodes = q.filter(*db_filters).all()
            return [
                MemoryTreeNode(**getattr(node, "document_structure"))
                for node in root_nodes
                if str(getattr(node, "status")) == "complete"
            ]

    def _db_filters_from_metadata(
        self, table: Cache, filters: Dict[str, Any]
    ) -> List[ColumnExpressionArgument[bool]]:
        filing_data = SECFiling.model_construct(**filters)
        exprs: List[ColumnExpressionArgument[bool]] = []
        if hasattr(filing_data, "ticker"):
            exprs.append(getattr(table.get_model(), "ticker") == filing_data.ticker)

        if hasattr(filing_data, "formType"):
            exprs.append(
                getattr(table.get_model(), "filing_type") == filing_data.formType
            )

        if hasattr(filing_data, "filing_date"):
            if hasattr(filing_data, "formType") and filing_data.formType == "10-Q":
                start, end = self._quarter_date_bounds(filing_data.filing_date)
            else:
                year = filing_data.filing_date.year
                tz = filing_data.filing_date.tzinfo
                start = datetime(year, 1, 1, tzinfo=tz)
                end = datetime(year + 1, 1, 1, tzinfo=tz)
            exprs.append(getattr(table.get_model(), "filing_date") >= start)
            exprs.append(getattr(table.get_model(), "filing_date") < end)

        return exprs

    @staticmethod
    def _quarter_date_bounds(dt: datetime) -> Tuple[datetime, datetime]:
        """
        Given any datetime, return the (inclusive) start and (exclusive) end
        of that quarter in the same timezone as `dt`.
        """
        # Q = 1–4
        quarter = (dt.month - 1) // 3 + 1
        # month where this quarter starts
        start_month = (quarter - 1) * 3 + 1

        # build start-of-quarter
        start = datetime(dt.year, start_month, 1, tzinfo=dt.tzinfo)

        # compute first day of NEXT quarter
        if start_month + 3 > 12:
            end = datetime(dt.year + 1, 1, 1, tzinfo=dt.tzinfo)
        else:
            end = datetime(dt.year, start_month + 3, 1, tzinfo=dt.tzinfo)

        return start, end
