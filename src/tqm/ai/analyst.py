"""AI analyst — generates monthly business commentary using Claude.

Uses prompt caching on the system prompt (domain knowledge + client profile)
so repeated monthly calls are fast and cheap.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import anthropic

from .snapshot import SnapshotComparison

log = logging.getLogger(__name__)

# Cached system prompt — injected once per session, cached by Anthropic
_ANALYST_SYSTEM_PROMPT = """\
You are a senior financial analyst and business intelligence consultant \
specialising in Latvian SMEs. You've been preparing monthly management \
reports for manufacturing, wholesale, and logistics companies for 10+ years.

## Your Role
You receive month-over-month KPI data and write a concise, insightful \
monthly commentary that a non-technical CEO or CFO can act on.

## Output Format
Return structured JSON with exactly these keys:
{
  "headline": "One sentence capturing the single most important thing this month",
  "executive_summary": "2-3 sentences. What changed and why it matters.",
  "key_findings": [
    "Finding 1 — specific, numbers included",
    "Finding 2",
    "Finding 3 (max 5)"
  ],
  "root_cause_analysis": "1-2 paragraphs. WHY things changed — seasonality, market, ops?",
  "risks": ["Risk 1", "Risk 2"],
  "opportunities": ["Opportunity 1", "Opportunity 2"],
  "recommended_actions": [
    {"action": "Do X", "owner": "CFO/CEO/Sales", "deadline": "next 30 days"}
  ],
  "outlook": "One sentence forecast for next month."
}

## Rules
- Always cite specific numbers (e.g. "Revenue grew 12.4% to €847k").
- Never make up numbers not present in the data.
- Write in plain English. No jargon. No buzzwords.
- Be direct and confident. CEOs don't want hedged non-answers.
- If a change is within ±3% and there's no pattern, say it's stable.
- Flag anything over ±15% as significant regardless of direction.
"""


@dataclass
class AICommentary:
    headline: str
    executive_summary: str
    key_findings: list[str]
    root_cause_analysis: str
    risks: list[str]
    opportunities: list[str]
    recommended_actions: list[dict]
    outlook: str
    period_label: str
    raw_json: str = ""

    def to_markdown(self) -> str:
        lines = [
            f"# Monthly Commentary — {self.period_label}",
            f"\n> **{self.headline}**",
            f"\n## Executive Summary\n{self.executive_summary}",
            "\n## Key Findings",
        ]
        for finding in self.key_findings:
            lines.append(f"- {finding}")
        lines.append(f"\n## Root Cause Analysis\n{self.root_cause_analysis}")
        if self.risks:
            lines.append("\n## Risks")
            for r in self.risks:
                lines.append(f"- {r}")
        if self.opportunities:
            lines.append("\n## Opportunities")
            for o in self.opportunities:
                lines.append(f"- {o}")
        if self.recommended_actions:
            lines.append("\n## Recommended Actions")
            for a in self.recommended_actions:
                lines.append(f"- **{a.get('action', '')}** — {a.get('owner', '')} / {a.get('deadline', '')}")
        lines.append(f"\n## Outlook\n{self.outlook}")
        return "\n".join(lines)


class AIAnalyst:
    """Generate monthly business commentary from a SnapshotComparison."""

    MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str | None = None, client_profile: str = "") -> None:
        self.client = anthropic.Anthropic(api_key=api_key)
        self.client_profile = client_profile

    def analyse(self, comparison: SnapshotComparison) -> AICommentary:
        system_blocks: list[dict] = [
            {
                "type": "text",
                "text": _ANALYST_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        if self.client_profile:
            system_blocks.append(
                {
                    "type": "text",
                    "text": f"## Client Profile\n{self.client_profile}",
                    "cache_control": {"type": "ephemeral"},
                }
            )

        user_message = (
            f"Analyse the following month-over-month data and write the commentary.\n\n"
            f"```json\n{comparison.to_prompt_context()}\n```"
        )

        log.info("Generating AI commentary for %s…", comparison.period_label)
        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=2048,
            system=system_blocks,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = response.content[0].text  # type: ignore[union-attr]
        log.debug("Cache tokens: %s", getattr(response.usage, "cache_read_input_tokens", "n/a"))

        return self._parse(raw, comparison.period_label)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self, raw: str, period_label: str) -> AICommentary:
        import json
        import re

        raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                # Fallback — treat whole response as executive summary
                data = {"executive_summary": raw}

        return AICommentary(
            headline=data.get("headline", ""),
            executive_summary=data.get("executive_summary", ""),
            key_findings=data.get("key_findings", []),
            root_cause_analysis=data.get("root_cause_analysis", ""),
            risks=data.get("risks", []),
            opportunities=data.get("opportunities", []),
            recommended_actions=data.get("recommended_actions", []),
            outlook=data.get("outlook", ""),
            period_label=period_label,
            raw_json=raw,
        )
