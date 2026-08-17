"""Unit tests for scripts/build_grand_page.py (layout + slicer dedupe)."""
import build_grand_page as bgp


def _slicer(entity: str, prop: str, filters: list | None = None) -> dict:
    return {
        "name": f"{entity}.{prop}",
        "visual": {
            "visualType": "slicer",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [
                            {
                                "field": {
                                    "Column": {
                                        "Expression": {"SourceRef": {"Entity": entity}},
                                        "Property": prop,
                                    }
                                }
                            }
                        ]
                    }
                }
            },
        },
        "filterConfig": {"filters": filters or []},
    }


def test_slicer_key_distinguishes_fields():
    a = _slicer("gold dim_patch", "patch_name")
    b = _slicer("gold dim_league", "league_name")
    assert bgp.slicer_key(a) != bgp.slicer_key(b)


def test_slicer_key_same_field_same_config_equal():
    a = _slicer("gold dim_patch", "patch_name")
    b = _slicer("gold dim_patch", "patch_name")
    assert bgp.slicer_key(a) == bgp.slicer_key(b)


def test_slicer_key_keeps_fixed_filters_distinct():
    plain = _slicer("gold dim_hero", "hero_localized_name")
    radiant = _slicer(
        "gold dim_hero",
        "hero_localized_name",
        filters=[{"name": "x", "field": {"Measure": {"Expression": {"SourceRef": {"Entity": "gold dim_hero"}}, "Property": "Hero in Current Match"}}, "type": "Advanced"}],
    )
    assert bgp.slicer_key(plain) != bgp.slicer_key(radiant)


def test_slicer_key_missing_query_is_stable():
    assert bgp.slicer_key({"visual": {"visualType": "slicer"}}) == "field:<none>"


def _visual(w: float, h: float) -> dict:
    return {"name": "v", "visual": {"visualType": "card"}, "position": {"x": 0, "y": 0, "width": w, "height": h}}


def test_flow_wraps_into_columns():
    visuals = [_visual(bgp.COL_W, 200) for _ in range(4)]
    bottom = bgp.flow(visuals, 100.0)
    assert visuals[0]["position"]["y"] == 100.0
    assert visuals[3]["position"]["y"] > 100.0
    assert visuals[0]["position"]["x"] == bgp.MARGIN
    for v in visuals:
        pos = v["position"]
        assert pos["x"] + pos["width"] <= bgp.CANVAS_W - bgp.MARGIN + 1e-6
    assert bottom > visuals[3]["position"]["y"]


def test_flow_scales_oversized_visuals():
    wide = _visual(bgp.CANVAS_W, 400)
    bgp.flow([wide], 0.0)
    assert wide["position"]["width"] <= bgp.COL_W + 1e-6
    assert wide["position"]["height"] < 400


def test_fit_canvas_scales_down():
    visuals = [_visual(100, 100)]
    h, scale = bgp.fit_canvas(visuals, bgp.MAX_CANVAS_H * 2)
    assert scale < 1.0
    assert h == bgp.MAX_CANVAS_H
    assert visuals[0]["position"]["height"] < 100


def test_make_textbox_structure():
    tb = bgp.make_textbox("tb-1", [{"textRuns": [{"value": "hi"}]}], 10, 20, 300, 100)
    assert tb["name"] == "tb-1"
    assert tb["visual"]["visualType"] == "textbox"
    assert tb["position"] == {"x": 10, "y": 20, "z": 0, "height": 100, "width": 300, "tabOrder": 0}


def test_build_plan_covers_all_source_visuals():
    plan = bgp.build_plan()
    source_count = 0
    for pdir in sorted(bgp.PAGES_DIR.glob("*")):
        if not (pdir / "page.json").exists() or pdir.name == bgp.NEW_PAGE_ID:
            continue
        source_count += len(list((pdir / "visuals").glob("*/visual.json")))
    names = [v["name"] for v in plan["visuals"]]
    assert len(names) == len(set(names))
    assert len(plan["visuals"]) == source_count - 2 + 16
    assert plan["canvas"]["width"] == bgp.CANVAS_W
    assert plan["canvas"]["height"] <= bgp.MAX_CANVAS_H
    for v in plan["visuals"]:
        pos = v["position"]
        assert pos["x"] + pos["width"] <= plan["canvas"]["width"] + 1e-6
        assert pos["y"] + pos["height"] <= plan["canvas"]["height"] + 1e-6


def test_plan_bindings_resolve_in_semantic_model():
    plan = bgp.build_plan()
    refs = [ref for v in plan["visuals"] for ref in bgp.iter_visual_refs(v)]
    assert len(refs) > 400
    errors = bgp.verify_bindings(plan["visuals"])
    assert errors == []


def test_verify_bindings_catches_bad_property():
    bad = {
        "name": "bad-visual",
        "visual": {
            "visualType": "card",
            "query": {
                "queryState": {
                    "Y": {
                        "projections": [
                            {
                                "field": {
                                    "Measure": {
                                        "Expression": {"SourceRef": {"Entity": "gold fact_matches"}},
                                        "Property": "Definitely Not A Measure",
                                    }
                                }
                            }
                        ]
                    }
                }
            },
        },
    }
    errors = bgp.verify_bindings([bad])
    assert any("Definitely Not A Measure" in e for e in errors)


def test_verify_bindings_catches_unknown_entity():
    bad = {
        "name": "bad-visual",
        "visual": {
            "visualType": "card",
            "query": {
                "queryState": {
                    "Y": {
                        "projections": [
                            {
                                "field": {
                                    "Measure": {
                                        "Expression": {"SourceRef": {"Entity": "gold no_such_table"}},
                                        "Property": "Anything",
                                    }
                                }
                            }
                        ]
                    }
                }
            },
        },
    }
    errors = bgp.verify_bindings([bad])
    assert any("no_such_table" in e for e in errors)
