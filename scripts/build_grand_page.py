"""Build the "Grand Report" page: every report page merged into one canvas.

Scans every page of the PBIP report and re-emits all visuals onto a single,
much larger page (3-column flow layout) with a story-rich narrative layer:

  - the 40 per-page slicers are deduplicated into a unified filter bar at the
    top (one slicer per unique field + filter configuration);
  - every remaining visual is copied unchanged (queries, formatting, filter
    configs) into a chapter per source page, in report page order;
  - each chapter gets a generated textbox header with a story paragraph;
  - a hero intro and a closing footer frame the whole canvas.

The builder is idempotent: it deletes and regenerates the Grand Report page,
so it can be re-run after the report changes.

Usage:
    python scripts/build_grand_page.py            # write the page
    python scripts/build_grand_page.py --dry-run  # print the layout only
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Iterable

BASE = Path(__file__).resolve().parent.parent
PAGES_DIR = BASE / ".pbip" / "dota pipeline.Report" / "definition" / "pages"
PAGES_META = PAGES_DIR / "pages.json"

NEW_PAGE_ID = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
NEW_PAGE_NAME = "Grand Report"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.11.0/schema.json"

CANVAS_W = 3840.0
COLUMNS = 3
MARGIN = 28.0
GUTTER = 28.0
COL_W = (CANVAS_W - 2 * MARGIN - (COLUMNS - 1) * GUTTER) / COLUMNS
SLICER_COL_W = 380.0
SECTION_GAP = 56.0
HEADER_H = 122.0
INTRO_H = 230.0
MAX_CANVAS_H = 16000.0

CHERRY = "#B03A2E"
NAVY = "#1B4F72"
INK = "#333333"
GREY = "#666666"


def slicer_key(visual: dict) -> str:
    """Canonical identity of a slicer: bound field + fixed filter config.

    Two slicers are the same only if they filter the same field with the same
    fixed filters, so side-specific slicers (e.g. "Hero - Radiant" vs
    "Hero - Dire", which share a field but differ in their filter config) are
    kept distinct.
    """
    projections = (
        visual.get("visual", {}).get("query", {}).get("queryState", {}).get("Values", {}).get("projections", [])
    )
    field = projections[0]["field"] if projections else None
    if not field:
        return "field:<none>"
    ref = field["Column" if "Column" in field else "Measure"]["Expression"]["SourceRef"]["Entity"]
    prop = field["Column" if "Column" in field else "Measure"]["Property"]
    field_key = f"{ref}.{prop}"
    filters = visual.get("filterConfig", {}).get("filters", [])
    config_key = json.dumps(filters, sort_keys=True, ensure_ascii=False)
    return f"{field_key}|{config_key}"


def make_paragraph(runs: list[dict]) -> dict:
    return {"textRuns": runs}


def run(value: str, *, size: str = "11pt", weight: str = "normal", color: str = INK) -> dict:
    text_style: dict = {"fontFamily": "Segoe UI", "fontSize": size, "fontWeight": weight}
    if color != INK:
        text_style["color"] = color
    return {"value": value, "textStyle": text_style}


def make_textbox(
    name: str,
    paragraphs: list[dict],
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    border: bool = True,
) -> dict:
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": 0, "height": height, "width": width, "tabOrder": 0},
        "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
            "visualContainerObjects": {
                "title": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
                "background": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
                "dropShadow": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
                "border": [{"properties": {"show": {"expr": {"Literal": {"Value": "true" if border else "false"}}}}}],
            },
        },
    }


def section_header(name: str, chapter: str | None, title: str, story: str, source_page: str | None, width: float) -> dict:
    paragraphs = [make_paragraph([run(f"{chapter} - {title}", size="24pt", weight="600", color=CHERRY)])]
    paragraphs.append(make_paragraph([run(story, size="11.5pt", color=INK)]))
    if source_page:
        paragraphs.append(make_paragraph([run(f"Consolidated from the '{source_page}' page of the report.", size="9pt", color=GREY)]))
    return make_textbox(name, paragraphs, MARGIN, 0, width, HEADER_H)


def flow(visuals: Iterable[dict], y: float, *, col_w: float = COL_W) -> float:
    """Place visuals left-to-right in `col_w` columns, wrapping; return bottom y."""
    x = MARGIN
    row_h = 0.0
    for v in visuals:
        pos = v["position"]
        w, h = pos["width"], pos["height"]
        if w > col_w:
            scale = col_w / w
            w, h = col_w, h * scale
        if x > MARGIN and x + w > CANVAS_W - MARGIN + 1e-6:
            x = MARGIN
            y += row_h + GUTTER
            row_h = 0.0
        pos.update({"x": x, "y": y, "width": w, "height": h})
        x += w + GUTTER
        row_h = max(row_h, h)
    return y + row_h


def fit_canvas(visuals: list[dict], canvas_h: float) -> tuple[float, float]:
    """Scale all visuals down if the layout exceeds MAX_CANVAS_H; return (h, scale)."""
    if canvas_h <= MAX_CANVAS_H:
        return canvas_h, 1.0
    scale = MAX_CANVAS_H / canvas_h
    for v in visuals:
        pos = v["position"]
        pos["x"] *= scale
        pos["y"] *= scale
        pos["width"] *= scale
        pos["height"] *= scale
    return MAX_CANVAS_H, scale


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


CHAPTERS = {
    "Overview": (
        "The battlefield at a glance. Total matches, leagues, patches, regions, lobbies and game modes - the raw shape "
        "of the dataset this report is built on. This chapter sets the stage and calibrates everything that follows."
    ),
    "Hero Meta": (
        "The meta is a living thing, and here it is measured: which heroes are picked most, which are banned out of "
        "fear, and who actually wins when it matters. Cross pick and ban numbers with win rates to see who truly rules "
        "the patch."
    ),
    "Players": (
        "Behind every hero is a player. This chapter profiles the professionals - their performance, their habits, "
        "their favourite heroes. Use the hero filter to see who makes a hero their own."
    ),
    "Teams": (
        "No hero fights alone. Team records, head-to-head histories and line-up compositions - who teams up with whom, "
        "and how those partnerships have fared over time."
    ),
    "Matches": (
        "The games themselves: when they were played, how long they ran, in which mode and lobby, and under which "
        "patch. The raw timeline of the professional scene."
    ),
    "Combat": (
        "When steel meets steel. Teamfights, kills, damage dealt and taken, and the heroes who turned the fight. This "
        "is where matches are won and lost in a matter of seconds."
    ),
    "Economy": (
        "Gold is the true scoreboard. Net worth, GPM, item purchases and the economic race between the lanes. Watch "
        "the money to understand why a fight went the way it did."
    ),
    "Draft": (
        "Victory is decided before the horn sounds. Picks and bans reveal the strategy of both teams before a single "
        "creep spawns - what was contested, what was respected, and what was stolen."
    ),
    "Match Detail": (
        "Zoom in on a single game. Every player, every hero, every item, every teamfight, minute by minute. The "
        "closest possible look at how a match actually unfolded."
    ),
    "Match Breakdown": (
        "The autopsy. Runes, kills, wards and damage over time - the fine-grained events that explain why a match "
        "turned. For when the scoreboard alone is not enough."
    ),
    "Progression": (
        "The arc of the season. How matches, teams and stats evolve over time - momentum, form, and the long road "
        "from patch to patch."
    ),
    "About & Glossary": (
        "The map legend. Definitions of every term used across this report, plus notes on how the data was collected "
        "and what each chapter offers."
    ),
}


def collect_page_visuals(page_dir: Path) -> list[tuple[str, dict]]:
    visuals = []
    for vdir in sorted((page_dir / "visuals").glob("*")):
        path = vdir / "visual.json"
        if path.exists():
            visuals.append((path.stem, read_json(path)))
    visuals.sort(key=lambda item: item[1]["position"]["z"])
    return visuals


def build_plan() -> dict:
    """Compute the full layout plan for the Grand Report page (no writes)."""
    pages_meta = read_json(PAGES_META)
    page_order = pages_meta["pageOrder"]

    interactions: list[dict] = []
    section_visuals: list[tuple[str, list[dict]]] = []
    for pid in page_order:
        if pid == NEW_PAGE_ID:
            continue
        page_dir = PAGES_DIR / pid
        page = read_json(page_dir / "page.json")
        interactions.extend(page.get("visualInteractions", []))
        section_visuals.append((page["displayName"], [v for _, v in collect_page_visuals(page_dir)]))

    unique_slicers: list[dict] = []
    seen: set[str] = set()
    stripped: list[tuple[str, list[dict]]] = []
    for name, visuals in section_visuals:
        kept = []
        for v in visuals:
            if v["visual"]["visualType"] == "slicer":
                key = slicer_key(v)
                if key not in seen:
                    seen.add(key)
                    unique_slicers.append(v)
            else:
                kept.append(v)
        stripped.append((name, kept))
    section_visuals = stripped

    placed: list[dict] = []
    y = MARGIN

    intro_title = make_textbox(
        f"{NEW_PAGE_ID}-intro-title",
        [
            make_paragraph([run("THE GRAND REPORT", size="44pt", weight="700", color=CHERRY)]),
            make_paragraph([run("One canvas. Every match. The whole story of professional Dota 2.", size="16pt", weight="600", color=NAVY)]),
        ],
        MARGIN,
        y,
        CANVAS_W - 2 * MARGIN,
        120,
        border=False,
    )
    intro_guide = make_textbox(
        f"{NEW_PAGE_ID}-intro-guide",
        [
            make_paragraph([
                run("HOW TO READ THIS CANVAS", size="11pt", weight="700", color=NAVY),
            ]),
            make_paragraph([
                run(
                    "Twelve chapters flow top to bottom, uniting every page of the report: set the stage with the overview, "
                    "study the heroes who define the meta, meet the players and teams, then descend into matches, drafts, "
                    "combat, economy and the minute-by-minute detail of individual games. The filter bar directly below "
                    "drives the entire story - every visual answers to the same filters, so what you select here is told "
                    "consistently everywhere else. Scroll freely: the story is long, but every detail is here.",
                    size="11pt",
                )
            ]),
        ],
        MARGIN,
        y + 140,
        CANVAS_W - 2 * MARGIN,
        INTRO_H - 140,
    )
    placed += [intro_title, intro_guide]
    y += INTRO_H

    bar_header = make_textbox(
        f"{NEW_PAGE_ID}-filter-bar",
        [
            make_paragraph([run("Global Filters", size="22pt", weight="600", color=NAVY)]),
            make_paragraph([
                run(
                    f"One filter bar replaces the per-page slicers: {len(unique_slicers)} unique controls (deduplicated "
                    "from 40) govern every chapter below. Change a filter and the whole canvas answers.",
                    size="10.5pt",
                    color=INK,
                )
            ]),
        ],
        MARGIN,
        y,
        CANVAS_W - 2 * MARGIN,
        100,
        border=False,
    )
    placed.append(bar_header)
    y += 108
    y = flow(unique_slicers, y, col_w=SLICER_COL_W)
    placed.extend(unique_slicers)
    y += SECTION_GAP

    for idx, (display_name, visuals) in enumerate(section_visuals, start=1):
        header = section_header(
            f"{NEW_PAGE_ID}-chapter-{idx:02d}",
            f"Chapter {idx:02d}",
            display_name,
            CHAPTERS.get(display_name, "Part of the story of professional Dota 2."),
            display_name,
            CANVAS_W - 2 * MARGIN,
        )
        header["position"]["y"] = y
        placed.append(header)
        y += HEADER_H + 12
        y = flow(visuals, y)
        placed.extend(visuals)
        y += SECTION_GAP

    footer = make_textbox(
        f"{NEW_PAGE_ID}-footer",
        [
            make_paragraph([run("END OF THE GRAND REPORT", size="18pt", weight="700", color=CHERRY)]),
            make_paragraph([
                run(
                    "Every chapter of the Dota 2 Intelligence Report, on one canvas. The data behind it flows from a full "
                    "pipeline: scraped from the OpenDota API, stored, transformed and modelled for analysis. Filter, scroll "
                    "and explore - the whole war is on this one page.",
                    size="11pt",
                )
            ]),
        ],
        MARGIN,
        y,
        CANVAS_W - 2 * MARGIN,
        130,
    )
    placed.append(footer)
    y += 150

    canvas_h, scale = fit_canvas(placed, y)
    for i, v in enumerate(placed, start=1):
        v["position"]["z"] = i
        v["position"]["tabOrder"] = i

    copied = {v["name"] for v in placed}
    kept_interactions = []
    seen_pairs: set[tuple[str, str, str]] = set()
    for item in interactions:
        pair = (item["source"], item["target"], item["type"])
        if item["source"] in copied and item["target"] in copied and pair not in seen_pairs:
            seen_pairs.add(pair)
            kept_interactions.append(item)

    return {
        "page_order": page_order,
        "canvas": {"width": CANVAS_W, "height": round(canvas_h)},
        "scale": scale,
        "visuals": placed,
        "sections": [(name, len(visuals)) for name, visuals in section_visuals],
        "slicers": {"total": 40, "unique": len(unique_slicers)},
        "interactions": kept_interactions,
    }


def render_page(plan: dict) -> dict:
    return {
        "$schema": PAGE_SCHEMA,
        "name": NEW_PAGE_ID,
        "displayName": NEW_PAGE_NAME,
        "displayOption": "FitToWidth",
        "height": plan["canvas"]["height"],
        "width": plan["canvas"]["width"],
        "visualInteractions": plan["interactions"],
    }


def write_page(plan: dict) -> None:
    page_dir = PAGES_DIR / NEW_PAGE_ID
    if page_dir.exists():
        shutil.rmtree(page_dir)
    for v in plan["visuals"]:
        write_json(page_dir / "visuals" / v["name"] / "visual.json", v)
    write_json(page_dir / "page.json", render_page(plan))

    pages_meta = read_json(PAGES_META)
    if NEW_PAGE_ID not in pages_meta["pageOrder"]:
        pages_meta["pageOrder"].insert(0, NEW_PAGE_ID)
    pages_meta["activePageName"] = NEW_PAGE_ID
    pages_meta["landingPageName"] = NEW_PAGE_ID
    write_json(PAGES_META, pages_meta)


MODEL_DIR = BASE / ".pbip" / "dota pipeline.SemanticModel" / "definition" / "tables"
_TMDL_NAME = re.compile(r"^\s*(table|column|measure)\s+(?:'([^']+)'|(\S+))(?:\s*=.*)?$")


def model_schema() -> dict[str, tuple[set[str], set[str]]]:
    """Parse the semantic model TMDL into {entity: (columns, measures)}."""
    schema: dict[str, tuple[set[str], set[str]]] = {}
    for path in sorted(MODEL_DIR.glob("*.tmdl")):
        entity = None
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _TMDL_NAME.match(line)
            if not m:
                continue
            kind, quoted, bare = m.group(1), m.group(2), m.group(3)
            name = quoted if quoted is not None else bare
            if kind == "table":
                schema.setdefault(name, (set(), set()))
                entity = name
            elif entity is not None:
                schema[entity][0 if kind == "column" else 1].add(name)
    return schema


def _field_ref(field: dict) -> tuple[str, str, str] | None:
    if "Column" in field:
        col = field["Column"]
        return "column", col["Expression"]["SourceRef"]["Entity"], col["Property"]
    if "Measure" in field:
        m = field["Measure"]
        return "measure", m["Expression"]["SourceRef"]["Entity"], m["Property"]
    return None


def _iter_field_refs(node: dict, out: list[tuple[str, str, str]]) -> None:
    ref = _field_ref(node)
    if ref is not None:
        out.append(ref)
        return
    for value in node.values():
        if isinstance(value, dict):
            _iter_field_refs(value, out)


def iter_visual_refs(visual: dict) -> list[tuple[str, str, str]]:
    """All (kind, entity, property) field references of one visual."""
    out: list[tuple[str, str, str]] = []
    query_state = visual.get("visual", {}).get("query", {}).get("queryState", {})
    for role in query_state.values():
        for proj in role.get("projections", []):
            _iter_field_refs(proj.get("field", {}), out)
    for filt in visual.get("filterConfig", {}).get("filters", []):
        _iter_field_refs(filt.get("field", {}), out)
        if "filter" in filt:
            _iter_field_refs(filt["filter"], out)
    return out


def verify_bindings(visuals: list[dict]) -> list[str]:
    """Check that every field reference resolves in the semantic model."""
    schema = model_schema()
    errors: list[str] = []
    for v in visuals:
        for kind, entity, prop in iter_visual_refs(v):
            if entity not in schema:
                errors.append(f"{v['name']}: unknown entity '{entity}'")
            elif prop not in schema[entity][0 if kind == "column" else 1]:
                errors.append(f"{v['name']}: '{entity}.{prop}' is not a {kind} in the model")
    return errors


def print_plan(plan: dict) -> None:
    print(f"Grand Report page: {plan['canvas']['width']} x {plan['canvas']['height']}px (scale {plan['scale']:.3f})")
    print(f"Visuals placed: {len(plan['visuals'])}  (slicers: {plan['slicers']['unique']} unique of {plan['slicers']['total']} total)")
    print(f"Cross-visual interactions preserved: {len(plan['interactions'])}")
    for name, count in plan["sections"]:
        print(f"  - {name:<20} {count} visuals")
    print(f"Target: {PAGES_DIR / NEW_PAGE_ID}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print the layout plan without writing files")
    parser.add_argument("--verify", action="store_true", help="check every field reference against the semantic model")
    args = parser.parse_args()

    plan = build_plan()
    print_plan(plan)
    if args.verify:
        errors = verify_bindings(plan["visuals"])
        if errors:
            for e in errors:
                print(f"ERROR: {e}")
            return 1
        refs = sum(len(iter_visual_refs(v)) for v in plan["visuals"])
        print(f"Verified {refs} field references against the semantic model: all resolve.")
    if args.dry_run:
        return 0
    write_page(plan)
    print("Wrote Grand Report page and updated pages.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
