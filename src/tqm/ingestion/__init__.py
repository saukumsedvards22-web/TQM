"""Data ingestion: Excel workbooks and SAP flat-file exports."""

from .excel import ExcelIngester
from .sap import SAPIngester
from .base import IngestionResult, RawTable

__all__ = ["ExcelIngester", "SAPIngester", "IngestionResult", "RawTable"]
