"""
Human-in-the-loop mapping reviewer — two-stage canonical model.

Stage 1: Reviews source_to_canonical.json  (source → canonical)
Stage 2: Reviews canonical_to_target.json  (canonical → target)

Auto-approves mappings with confidence >= AUTO_THRESHOLD.
Prompts human review for anything below the threshold.

Saves approved versions to:
  mapping/approved_source_to_canonical.json
  mapping/approved_canonical_to_target.json

Run: python mapping/reviewer.py
"""

import json
import sys
from copy import deepcopy
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box

MAPPING_DIR    = Path(__file__).parent
S2C_FILE       = MAPPING_DIR / "source_to_canonical.json"
C2T_FILE       = MAPPING_DIR / "canonical_to_target.json"
S2C_APPROVED   = MAPPING_DIR / "approved_source_to_canonical.json"
C2T_APPROVED   = MAPPING_DIR / "approved_canonical_to_target.json"

AUTO_THRESHOLD = 0.9

console = Console()


# ── helpers ───────────────────────────────────────────────────────────────────

def confidence_style(score: float) -> str:
    if score >= 0.9:
        return "green"
    if score >= 0.7:
        return "yellow"
    return "red"


def show_col(from_label: str, to_label: str, col: dict):
    score = col["confidence"]
    style = confidence_style(score)
    src   = col.get("source") or col.get("canonical", "?")
    tgt   = col.get("canonical") or col.get("target", "?")
    console.print(
        f"\n  [{from_label}] [cyan]{src}[/cyan]  →  "
        f"[{to_label}] [cyan]{tgt}[/cyan]  |  "
        f"transform: [magenta]{col['transform']}[/magenta]  |  "
        f"confidence: [{style}]{score:.2f}[/{style}]"
    )
    if col.get("notes"):
        console.print(f"  [dim]{col['notes']}[/dim]")


def review_col(col: dict, from_label: str, to_label: str) -> dict | None:
    show_col(from_label, to_label, col)
    tgt_key = "canonical" if "canonical" in col else "target"

    while True:
        choice = Prompt.ask(
            "  [bold]Action[/bold]",
            choices=["a", "e", "r", "?"],
            default="a",
            show_choices=False,
            show_default=False,
        ).lower()

        if choice == "?":
            console.print(
                "  [dim]a = approve as-is  |  "
                "e = edit target/transform  |  "
                "r = reject (exclude from migration)[/dim]"
            )
            continue

        if choice == "a":
            col["reviewed"] = True
            col["decision"] = "approved"
            return col

        if choice == "r":
            col["reviewed"] = True
            col["decision"] = "rejected"
            console.print("  [red]Rejected — column excluded from migration.[/red]")
            return None

        if choice == "e":
            new_tgt = Prompt.ask(
                f"  New {tgt_key} field [dim](current: {col[tgt_key]})[/dim]",
                default=col[tgt_key],
            )
            new_tx = Prompt.ask(
                f"  New transform    [dim](current: {col['transform']})[/dim]",
                default=col["transform"],
            )
            col[tgt_key]     = new_tgt
            col["transform"] = new_tx
            col["reviewed"]  = True
            col["decision"]  = "edited"
            console.print("  [green]Saved.[/green]")
            return col


def review_mapping(data: dict, from_label: str, to_label: str, stage_name: str) -> dict:
    """
    Walk through all mappings in a file, auto-approve high-confidence ones,
    and prompt for the rest. Returns the updated data dict.
    """
    approved   = deepcopy(data)
    total      = 0
    auto_count = 0
    flagged    = []

    for map_key, mapping in approved["mappings"].items():
        kept = []
        for col in mapping["columns"]:
            total += 1
            if col["confidence"] >= AUTO_THRESHOLD:
                col["reviewed"] = False
                col["decision"] = "auto-approved"
                auto_count += 1
                kept.append(col)
            else:
                flagged.append((map_key, col, kept))
        mapping["columns"] = kept  # will be rebuilt as we go

    console.print(Panel(
        f"[bold]{stage_name}[/bold]\n\n"
        f"Total mappings : {total}\n"
        f"Auto-approved  : [green]{auto_count}[/green]  (confidence ≥ {AUTO_THRESHOLD})\n"
        f"Needs review   : [yellow]{len(flagged)}[/yellow]  (confidence < {AUTO_THRESHOLD})",
        style="blue",
    ))

    if not flagged:
        console.print("[green]All mappings auto-approved — nothing to review.[/green]\n")
        return approved

    console.print(
        f"Review [yellow]{len(flagged)}[/yellow] low-confidence mappings.\n"
        "Commands:  [bold]a[/bold] approve  [bold]e[/bold] edit  "
        "[bold]r[/bold] reject  [bold]?[/bold] help\n"
    )

    for i, (map_key, col, kept_list) in enumerate(flagged, 1):
        console.print(f"[dim]─── {i}/{len(flagged)}  ({map_key}) ───[/dim]")
        result = review_col(col, from_label, to_label)
        if result is not None:
            kept_list.append(result)

    return approved


def summary_table(data: dict, col_key: str) -> Table:
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    t.add_column("Mapping")
    t.add_column("Columns")
    t.add_column("Auto")
    t.add_column("Reviewed")
    t.add_column("Rejected")

    for key, mapping in data["mappings"].items():
        cols     = mapping["columns"]
        auto     = sum(1 for c in cols if c.get("decision") == "auto-approved")
        reviewed = sum(1 for c in cols if c.get("decision") in ("approved", "edited"))
        rejected = sum(1 for c in cols if c.get("decision") == "rejected")
        t.add_row(
            key,
            str(len(cols) + rejected),
            str(auto),
            str(reviewed),
            f"[red]{rejected}[/red]" if rejected else "0",
        )
    return t


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    for path in (S2C_FILE, C2T_FILE):
        if not path.exists():
            console.print(f"[red]Missing:[/red] {path}")
            sys.exit(1)

    console.print(Panel(
        "[bold]Mapping Reviewer — Canonical Model[/bold]\n\n"
        "Stage 1: Source → Canonical\n"
        "Stage 2: Canonical → Target",
        style="bold blue",
    ))

    # ── Stage 1 ───────────────────────────────────────────────────────────────
    console.rule("[bold cyan]Stage 1 — Source → Canonical[/bold cyan]")
    with open(S2C_FILE, encoding="utf-8") as f:
        s2c = json.load(f)

    s2c_approved = review_mapping(s2c, "source", "canonical", "Source → Canonical")

    with open(S2C_APPROVED, "w", encoding="utf-8") as f:
        json.dump(s2c_approved, f, indent=2)

    console.print(summary_table(s2c_approved, "canonical"))
    console.print(f"[green]Saved:[/green] {S2C_APPROVED}\n")

    # ── Stage 2 ───────────────────────────────────────────────────────────────
    console.rule("[bold cyan]Stage 2 — Canonical → Target[/bold cyan]")
    with open(C2T_FILE, encoding="utf-8") as f:
        c2t = json.load(f)

    c2t_approved = review_mapping(c2t, "canonical", "target", "Canonical → Target")

    with open(C2T_APPROVED, "w", encoding="utf-8") as f:
        json.dump(c2t_approved, f, indent=2)

    console.print(summary_table(c2t_approved, "target"))
    console.print(f"[green]Saved:[/green] {C2T_APPROVED}\n")

    console.print(
        Panel(
            "[green]Review complete.[/green]\n\n"
            "Next step: [bold]python pipeline.py[/bold]",
            style="green",
        )
    )


if __name__ == "__main__":
    main()
