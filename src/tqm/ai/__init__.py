"""AI commentary engine — monthly business narrative powered by Claude."""

from .analyst import AIAnalyst, AICommentary, RootCauseAnalysis, RootCauseClaim, KeyFinding
from .snapshot import MonthlySnapshot, SnapshotComparison
from .review_gate import ReviewGate, ReviewBlockedError
from .cost_tracker import CostTracker
from .reconciler import NumberReconciler
from .volatility import VolatilityTracker, VolatilityProfile
from .sanitizer import PromptSanitizer, INJECTION_SYSTEM_GUARD
from .kpi_synonyms import SynonymTable, DEFAULT_SYNONYMS
from .mutations import run_mutations, MUTATIONS, MutationReport

__all__ = [
    "AIAnalyst", "AICommentary", "RootCauseAnalysis", "RootCauseClaim", "KeyFinding",
    "MonthlySnapshot", "SnapshotComparison",
    "ReviewGate", "ReviewBlockedError",
    "CostTracker",
    "NumberReconciler",
    "VolatilityTracker", "VolatilityProfile",
    "PromptSanitizer", "INJECTION_SYSTEM_GUARD",
    "SynonymTable", "DEFAULT_SYNONYMS",
    "run_mutations", "MUTATIONS", "MutationReport",
]
