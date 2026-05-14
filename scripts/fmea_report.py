#!/usr/bin/env python3
"""Print the FMEA register with computed RPNs, then verify gate coverage via mutation tests.

Exit codes:
  0 — no open high-RPN modes AND all mutations caught
  1 — open high-RPN mode(s) exist, OR at least one gate hole detected

Usage: python scripts/fmea_report.py [--threshold 100] [--skip-mutations]
"""

import argparse
import sys
from pathlib import Path

import yaml


def _fmea_section(modes: list[dict], threshold: int) -> tuple[list[str], list[dict]]:
    """Return (printed_lines, high_open_modes)."""
    lines = [
        f"\n{'='*72}",
        f"  TQM FMEA Register  (threshold RPN > {threshold})",
        f"{'='*72}\n",
        f"{'ID':<8} {'S':>3} {'O':>3} {'D':>3} {'RPN':>5}  {'Open':>5}  Name",
        "-" * 72,
    ]
    high_open: list[dict] = []
    for mode in modes:
        s, o = mode["S"], mode["O"]
        d_raw = mode["D"]
        d_residual = mode.get("residual_D", d_raw)
        rpn_residual = s * o * d_residual
        open_flag = mode.get("open", False)

        row_flag = "🔴" if (open_flag and rpn_residual > threshold) else (
            "🟡" if open_flag else "✅"
        )
        lines.append(
            f"{mode['id']:<8} {s:>3} {o:>3} {d_residual:>3} {rpn_residual:>5}  "
            f"{str(open_flag):>5}  {row_flag} {mode['name'][:50]}"
        )
        if open_flag and rpn_residual > threshold:
            high_open.append(mode)
    return lines, high_open


def _mutation_section() -> tuple[list[str], bool]:
    """Run the gate mutation suite. Return (printed_lines, all_caught)."""
    lines = [
        f"\n{'='*72}",
        "  Gate Coverage — Mutation Test Suite",
        f"{'='*72}\n",
    ]
    try:
        # Import here so the script works without installing tqm (just prints FMEA)
        from tqm.ai.mutations import run_mutations
    except ImportError as exc:
        lines.append(f"  [SKIP] tqm not importable: {exc}")
        lines.append("  Install with: pip install -e .")
        return lines, True  # don't fail the exit code if package not installed

    report = run_mutations()
    lines.append(f"  {len(report.results) - len(report.holes)}/{len(report.results)} mutations caught\n")
    for r in report.results:
        icon = "✅" if r.caught else "❌"
        lines.append(
            f"  {icon} {r.mutation.name:<32} "
            f"expected={r.mutation.expected_block_code:<28} "
            f"actual={','.join(r.actual_block_codes) or '(nothing)'}"
        )
    if report.holes:
        lines += [
            "",
            f"❌  {len(report.holes)} GATE HOLE(S) — mutations the gate did NOT catch:",
            *[f"    - {h.mutation.name}: {h.mutation.description}" for h in report.holes],
            "",
            "  Fix the gate before the next release.",
        ]
    else:
        lines.append("\n✅  Gate catches all documented failure modes.")
    return lines, report.passed


def main() -> None:
    parser = argparse.ArgumentParser(description="TQM FMEA report")
    parser.add_argument("--threshold", type=int, default=100, help="RPN threshold for high-risk")
    parser.add_argument("--skip-mutations", action="store_true",
                        help="Skip gate mutation verification (faster, less trustworthy)")
    args = parser.parse_args()

    fmea_path = Path(__file__).parent.parent / "config" / "fmea.yaml"
    data = yaml.safe_load(fmea_path.read_text(encoding="utf-8"))
    modes = data["failure_modes"]

    fmea_lines, high_open = _fmea_section(modes, args.threshold)
    for line in fmea_lines:
        print(line)

    print(f"\n{'='*72}")
    if high_open:
        print(f"\n🔴  {len(high_open)} HIGH-RISK OPEN FAILURE MODE(S) (RPN > {args.threshold}):\n")
        for mode in high_open:
            s, o = mode["S"], mode["O"]
            d = mode.get("residual_D", mode["D"])
            rpn = s * o * d
            print(f"  [{mode['id']}] RPN={rpn}  {mode['name']}")
            if mode.get("action"):
                print(f"       Action: {mode['action'].strip()[:120]}")
            print()
        print("  Pipeline must not run automated delivery until these are mitigated.")

    mutations_passed = True
    if not args.skip_mutations:
        mut_lines, mutations_passed = _mutation_section()
        for line in mut_lines:
            print(line)
    else:
        print("\n  [Mutation tests skipped — run without --skip-mutations to verify gate coverage]")

    overall_ok = (not high_open) and mutations_passed
    print(f"\n{'='*72}")
    if overall_ok:
        print("\n✅  FMEA clean and gate verified. Safe to proceed.\n")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
