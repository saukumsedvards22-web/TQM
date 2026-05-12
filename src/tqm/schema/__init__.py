"""Schema detection and dimensional model builder."""

from .detector import SchemaDetector
from .model import DimensionalModel, DimTable, FactTable, Relationship

__all__ = ["SchemaDetector", "DimensionalModel", "DimTable", "FactTable", "Relationship"]
