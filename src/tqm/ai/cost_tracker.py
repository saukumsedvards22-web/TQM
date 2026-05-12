"""Token usage and cost tracking per report run.

Prices as of Claude Sonnet 4.6 (update when models change):
  Input:             $3.00 / 1M tokens
  Output:            $15.00 / 1M tokens
  Cache write:       $3.75 / 1M tokens
  Cache read:        $0.30 / 1M tokens  ← ~90% cheaper than input

Persists a JSONL log at .tqm_costs.jsonl for monthly billing review.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Prices in USD per million tokens
_PRICES = {
    "input": 3.00,
    "output": 15.00,
    "cache_write": 3.75,
    "cache_read": 0.30,
}

# EUR/USD — update monthly or pull from an FX API
_EUR_USD = 1.08


@dataclass
class RunCost:
    client_name: str
    period: str
    step: str                     # "dax_generation" | "ai_commentary"
    model: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    usd: float
    eur: float
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def summary(self) -> str:
        saving = self.cache_read_tokens * (_PRICES["input"] - _PRICES["cache_read"]) / 1_000_000
        return (
            f"[{self.step}] {self.input_tokens:,} in / {self.output_tokens:,} out / "
            f"{self.cache_read_tokens:,} cached → €{self.eur:.4f} (saved €{saving * _EUR_USD:.4f} via cache)"
        )


class CostTracker:
    """Track and log Claude API costs for every report run."""

    def __init__(self, log_path: Path = Path(".tqm_costs.jsonl")) -> None:
        self.log_path = log_path
        self._runs: list[RunCost] = []

    def record(
        self,
        client_name: str,
        period: str,
        step: str,
        model: str,
        usage: Any,           # anthropic.types.Usage
    ) -> RunCost:
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0

        usd = (
            (input_tokens * _PRICES["input"] / 1_000_000)
            + (output_tokens * _PRICES["output"] / 1_000_000)
            + (cache_write * _PRICES["cache_write"] / 1_000_000)
            + (cache_read * _PRICES["cache_read"] / 1_000_000)
        )
        eur = usd / _EUR_USD

        run = RunCost(
            client_name=client_name,
            period=period,
            step=step,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_write_tokens=cache_write,
            cache_read_tokens=cache_read,
            usd=usd,
            eur=eur,
        )
        self._runs.append(run)
        self._append_to_log(run)
        log.info(run.summary())
        return run

    def session_total(self) -> tuple[float, float]:
        """Return (total_usd, total_eur) for this session."""
        total_usd = sum(r.usd for r in self._runs)
        return total_usd, total_usd / _EUR_USD

    def print_session_summary(self) -> None:
        usd, eur = self.session_total()
        log.info("Session cost: $%.4f USD / €%.4f EUR across %d API calls", usd, eur, len(self._runs))

    def monthly_summary(self, client_name: str | None = None) -> dict:
        """Read the JSONL log and summarise costs for the current month."""
        if not self.log_path.exists():
            return {}

        month = datetime.utcnow().strftime("%Y-%m")
        total_eur = 0.0
        by_step: dict[str, float] = {}

        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not row.get("timestamp", "").startswith(month):
                continue
            if client_name and row.get("client_name") != client_name:
                continue
            total_eur += row.get("eur", 0.0)
            step = row.get("step", "unknown")
            by_step[step] = by_step.get(step, 0.0) + row.get("eur", 0.0)

        return {"month": month, "total_eur": round(total_eur, 4), "by_step": by_step}

    def _append_to_log(self, run: RunCost) -> None:
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(run), ensure_ascii=False) + "\n")
