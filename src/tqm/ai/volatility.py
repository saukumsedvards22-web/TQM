"""Volatility-based delta threshold — per-client, per-KPI, grounded in history.

The fixed 40% threshold was indefensible. A business with stable 2% monthly
revenue variance should be reviewed at ±8%. A seasonal company might swing 60%
legitimately. The threshold must come from the data, not from a guess.

Algorithm:
  - Maintain a rolling window of historical KPI snapshots (persisted as JSONL).
  - Compute per-KPI threshold as median + N × MAD (median absolute deviation).
    MAD is robust to outliers; mean+σ is not. Revenue/COGS monthly deltas are
    fat-tailed and right-skewed — one bad month inflates σ and widens the
    threshold precisely when it should stay tight.
  - MAD converted to σ-equivalent via the standard consistency factor 1.4826
    so that N=2.5 gives the same ~1.2% flag rate on a normal distribution, but
    a single outlier in 12 months no longer dominates the threshold.
  - On first run (no history), use a conservative static fallback (15%).
  - Expose the computed thresholds so they appear in the audit log.

Conservative defaults matter more than sophisticated defaults.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

_STATIC_FALLBACK_PCT = 15.0   # used when fewer than MIN_HISTORY snapshots exist
_MIN_HISTORY = 3               # minimum snapshots before volatility-based threshold kicks in
_DEFAULT_N_SIGMA = 2.5


_MAD_CONSISTENCY_FACTOR = 1.4826  # makes MAD a consistent estimator of σ under normality


@dataclass
class KPIThreshold:
    kpi: str
    threshold_pct: float
    method: str          # "volatility_mad" | "static_fallback"
    history_count: int
    median_pct: float = 0.0
    mad_pct: float = 0.0


@dataclass
class VolatilityProfile:
    client_name: str
    thresholds: dict[str, KPIThreshold] = field(default_factory=dict)

    def get_threshold(self, kpi: str) -> KPIThreshold:
        return self.thresholds.get(
            kpi,
            KPIThreshold(
                kpi=kpi,
                threshold_pct=_STATIC_FALLBACK_PCT,
                method="static_fallback",
                history_count=0,
            ),
        )

    def summary(self) -> str:
        if not self.thresholds:
            return f"No history — using static fallback {_STATIC_FALLBACK_PCT}% for all KPIs"
        lines = [f"Volatility thresholds for {self.client_name}:"]
        for kpi, t in self.thresholds.items():
            lines.append(
                f"  {kpi}: ±{t.threshold_pct:.1f}%  "
                f"(method={t.method}, n={t.history_count}, "
                f"median={t.median_pct:.1f}%, mad={t.mad_pct:.1f}%)"
            )
        return "\n".join(lines)


class VolatilityTracker:
    """Persist monthly KPI delta history and compute per-KPI thresholds."""

    def __init__(
        self,
        history_dir: Path = Path(".tqm_history"),
        n_sigma: float = _DEFAULT_N_SIGMA,
        min_history: int = _MIN_HISTORY,
        static_fallback_pct: float = _STATIC_FALLBACK_PCT,
    ) -> None:
        self.history_dir = history_dir
        self.n_sigma = n_sigma
        self.min_history = min_history
        self.static_fallback_pct = static_fallback_pct
        self.history_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, client_name: str, period: str, kpi_deltas: dict[str, dict]) -> None:
        """Append this month's deltas to the history file."""
        path = self._path(client_name)
        record = {
            "period": period,
            "deltas": {kpi: delta["pct"] for kpi, delta in kpi_deltas.items()},
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        log.debug("Recorded %d KPI deltas for %s / %s", len(kpi_deltas), client_name, period)

    def compute_profile(self, client_name: str) -> VolatilityProfile:
        """Return per-KPI thresholds based on stored history."""
        history = self._load(client_name)
        if len(history) < self.min_history:
            log.info(
                "Only %d history points for %s — using static fallback %.0f%%",
                len(history), client_name, self.static_fallback_pct,
            )
            return VolatilityProfile(client_name=client_name)

        # Collect per-KPI delta series
        by_kpi: dict[str, list[float]] = {}
        for record in history:
            for kpi, pct in record.get("deltas", {}).items():
                by_kpi.setdefault(kpi, []).append(pct)

        thresholds: dict[str, KPIThreshold] = {}
        for kpi, deltas in by_kpi.items():
            if len(deltas) < self.min_history:
                thresholds[kpi] = KPIThreshold(
                    kpi=kpi,
                    threshold_pct=self.static_fallback_pct,
                    method="static_fallback",
                    history_count=len(deltas),
                )
                continue

            sorted_deltas = sorted(deltas)
            n = len(sorted_deltas)
            mid = n // 2
            median = (sorted_deltas[mid] if n % 2 else
                      (sorted_deltas[mid - 1] + sorted_deltas[mid]) / 2.0)
            abs_devs = sorted(abs(d - median) for d in deltas)
            mad_raw = (abs_devs[n // 2] if n % 2 else
                       (abs_devs[n // 2 - 1] + abs_devs[n // 2]) / 2.0)
            # Scale MAD to σ-equivalent so n_sigma has consistent meaning
            mad_sigma = mad_raw * _MAD_CONSISTENCY_FACTOR

            # Never set threshold below 5% regardless of how stable the history is
            computed = max(abs(median) + self.n_sigma * mad_sigma, 5.0)

            thresholds[kpi] = KPIThreshold(
                kpi=kpi,
                threshold_pct=round(computed, 1),
                method="volatility_mad",
                history_count=len(deltas),
                median_pct=round(median, 2),
                mad_pct=round(mad_sigma, 2),
            )

        log.info(VolatilityProfile(client_name=client_name, thresholds=thresholds).summary())
        return VolatilityProfile(client_name=client_name, thresholds=thresholds)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _path(self, client_name: str) -> Path:
        safe = client_name.lower().replace(" ", "_").replace("/", "_")
        return self.history_dir / f"{safe}_history.jsonl"

    def _load(self, client_name: str) -> list[dict]:
        path = self._path(client_name)
        if not path.exists():
            return []
        records: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records
