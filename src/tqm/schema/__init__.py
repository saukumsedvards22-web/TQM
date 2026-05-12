"""Schema detection and dimensional model builder."""

from .detector import SchemaDetector
from .model import DimensionalModel, DimTable, FactTable, Relationship
from .drift import SchemaDriftDetector, DriftReport
from .date_validator import DateColumnValidator, DateValidationResult

__all__ = [
    "SchemaDetector", "DimensionalModel", "DimTable", "FactTable", "Relationship",
    "SchemaDriftDetector", "DriftReport",
    "DateColumnValidator", "DateValidationResult",
]
