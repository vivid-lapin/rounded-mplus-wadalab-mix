#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTCollection, TTFont
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

from arib_charset import arib_b24_b62_codepoints, codepoint_summary


ROOT = Path(__file__).resolve().parents[1]
REGULAR = ROOT / "rounded-mplus-1m-regular.ttf"
WADA = ROOT / "wlcmaru2004aribu.ttf"
HIRAGINO_PRON = Path("/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc")
DIST = ROOT / "dist"
ANALYSIS = ROOT / "analysis"
PROJECT_VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
    "project"
]["version"]


@dataclass(frozen=True)
class BuildPlan:
    mode: str
    output: Path
    family_name: str
    full_name: str
    ps_name: str
    regular_codepoints: set[int]
    wada_codepoints: set[int]
    unavailable_codepoints: set[int]
    out_of_scope_codepoints: set[int]
    notes: list[str]


def load_font(path: Path, font_number: int | None = None) -> TTFont:
    if path.suffix.lower() == ".ttc":
        if font_number is None:
            raise ValueError(f"TTC font number is required for {path}")
        return TTCollection(path).fonts[font_number]
    return TTFont(path)


def cmap_codepoints(font: TTFont) -> set[int]:
    codepoints: set[int] = set()
    for subtable in font["cmap"].tables:
        if subtable.isUnicode():
            codepoints.update(subtable.cmap)
    return codepoints


def format_cp(cp: int) -> str:
    return f"U+{cp:04X}"


def range_strings(codepoints: set[int]) -> list[str]:
    values = sorted(codepoints)
    if not values:
        return []
    result: list[str] = []
    first = prev = values[0]
    for cp in values[1:]:
        if cp == prev + 1:
            prev = cp
        else:
            result.append(format_range(first, prev))
            first = prev = cp
    result.append(format_range(first, prev))
    return result


def format_range(first: int, last: int) -> str:
    if first == last:
        return format_cp(first)
    return f"{format_cp(first)}-{format_cp(last)} ({last - first + 1})"


def subset_font(path: Path, codepoints: set[int]) -> TTFont:
    font = TTFont(path)
    options = Options()
    options.hinting = False
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.name_languages = ["*"]

    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes=sorted(codepoints))
    subsetter.subset(font)

    # Save and reload so fontTools drops unsupported source-specific tables and
    # normalizes table internals before we append glyphs manually.
    with tempfile.NamedTemporaryFile(suffix=".ttf") as tmp:
        font.save(tmp.name)
        normalized = TTFont(tmp.name)

    # The source fonts do not have compatible vertical metric tables
    # (wlcmaru2004aribu.ttf has vhea but no vmtx). The generated fonts are
    # intended as horizontal fallback fonts, so drop vertical metrics instead of
    # carrying an inconsistent partial table set through the manual merge.
    for tag in ("vhea", "vmtx"):
        if tag in normalized:
            del normalized[tag]
    return normalized


def subset_scaled_wada(codepoints: set[int], units_per_em: int) -> TTFont:
    font = subset_font(WADA, codepoints)
    if font["head"].unitsPerEm != units_per_em:
        scale_upem(font, units_per_em)
        with tempfile.NamedTemporaryFile(suffix=".ttf") as tmp:
            font.save(tmp.name)
            font = TTFont(tmp.name)
    return font


def ensure_format_12_cmap(font: TTFont) -> None:
    cmap_table = font["cmap"]
    for subtable in cmap_table.tables:
        if (
            subtable.platformID == 3
            and subtable.platEncID == 10
            and subtable.format == 12
        ):
            return
    existing: dict[int, str] = {}
    for existing_subtable in cmap_table.tables:
        if existing_subtable.isUnicode():
            existing.update(existing_subtable.cmap)
    subtable = CmapSubtable.newSubtable(12)
    subtable.platformID = 3
    subtable.platEncID = 10
    subtable.language = 0
    subtable.cmap = existing
    cmap_table.tables.append(subtable)


def add_cmap_entries(font: TTFont, entries: dict[int, str]) -> None:
    ensure_format_12_cmap(font)
    for subtable in font["cmap"].tables:
        if not subtable.isUnicode():
            continue
        if subtable.format == 4:
            subtable.cmap.update(
                {cp: name for cp, name in entries.items() if cp <= 0xFFFF}
            )
        elif subtable.format in (12, 13):
            subtable.cmap.update(entries)


def append_wada_glyphs(base: TTFont, wada: TTFont, wada_codepoints: set[int]) -> None:
    base_order = base.getGlyphOrder()
    base_names = set(base_order)
    wada_order = wada.getGlyphOrder()
    wada_cmap = wada.getBestCmap() or {}

    mapping: dict[str, str] = {".notdef": ".notdef"}
    for old_name in wada_order:
        if old_name == ".notdef":
            continue
        new_name = f"wlc.{old_name}"
        suffix = 1
        while new_name in base_names or new_name in mapping.values():
            suffix += 1
            new_name = f"wlc.{old_name}.{suffix}"
        mapping[old_name] = new_name

    glyf = base["glyf"]
    hmtx = base["hmtx"]
    appended_names: list[str] = []
    for old_name in wada_order:
        if old_name == ".notdef":
            continue
        new_name = mapping[old_name]
        glyph = copy.deepcopy(wada["glyf"][old_name])
        if glyph.isComposite():
            for component in glyph.components:
                component.glyphName = mapping.get(
                    component.glyphName, component.glyphName
                )
        glyf.glyphs[new_name] = glyph
        hmtx.metrics[new_name] = wada["hmtx"].metrics[old_name]
        appended_names.append(new_name)

    new_order = base_order + appended_names
    base.setGlyphOrder(new_order)
    base["maxp"].numGlyphs = len(new_order)
    base["hhea"].numberOfHMetrics = len(new_order)

    if "vmtx" in base:
        vmtx = base["vmtx"]
        advance_height = base["head"].unitsPerEm
        v_ascent = getattr(base.get("vhea"), "ascent", advance_height)
        for new_name in appended_names:
            glyph = glyf[new_name]
            y_max = getattr(glyph, "yMax", v_ascent)
            vmtx.metrics[new_name] = (advance_height, v_ascent - y_max)
        if "vhea" in base:
            base["vhea"].numberOfVMetrics = len(new_order)

    new_cmap_entries = {
        cp: mapping[wada_cmap[cp]]
        for cp in sorted(wada_codepoints)
        if cp in wada_cmap and wada_cmap[cp] in mapping
    }
    add_cmap_entries(base, new_cmap_entries)


def set_font_names(
    font: TTFont, family_name: str, full_name: str, ps_name: str
) -> None:
    name_table = font["name"]
    subfamily = "Regular"
    version_text = f"Version {PROJECT_VERSION}"
    unique = f"{ps_name}; {version_text}"
    public_domain = "Public domain"
    values = {
        0: public_domain,
        1: family_name,
        2: subfamily,
        3: unique,
        4: full_name,
        5: version_text,
        6: ps_name,
        13: public_domain,
        16: family_name,
        17: subfamily,
    }
    name_table.names = []
    for name_id, value in values.items():
        name_table.setName(value, name_id, 3, 1, 0x409)
        name_table.setName(value, name_id, 3, 1, 0x411)
        name_table.setName(value, name_id, 1, 0, 0)


def recalc_metadata(font: TTFont, fs_type: int) -> None:
    os2 = font["OS/2"]
    os2.fsType = fs_type
    os2.recalcUnicodeRanges(font, pruneOnly=False)
    os2.recalcCodePageRanges(font, pruneOnly=False)
    os2.recalcAvgCharWidth(font)
    codepoints = sorted(cmap_codepoints(font))
    bmp_codepoints = [cp for cp in codepoints if cp <= 0xFFFF]
    if bmp_codepoints:
        os2.usFirstCharIndex = min(bmp_codepoints)
        os2.usLastCharIndex = max(bmp_codepoints)


def build_font(plan: BuildPlan, fs_type: int) -> dict[str, object]:
    plan.output.parent.mkdir(exist_ok=True)
    base = subset_font(REGULAR, plan.regular_codepoints)
    if plan.wada_codepoints:
        wada = subset_scaled_wada(plan.wada_codepoints, base["head"].unitsPerEm)
        append_wada_glyphs(base, wada, plan.wada_codepoints)

    set_font_names(base, plan.family_name, plan.full_name, plan.ps_name)
    recalc_metadata(base, fs_type=fs_type)
    base.save(plan.output)

    built = TTFont(plan.output)
    actual = cmap_codepoints(built)
    expected = plan.regular_codepoints | plan.wada_codepoints
    report = {
        "mode": plan.mode,
        "output": str(plan.output.relative_to(ROOT)),
        "family_name": plan.family_name,
        "full_name": plan.full_name,
        "postscript_name": plan.ps_name,
        "units_per_em": built["head"].unitsPerEm,
        "glyph_count": len(built.getGlyphOrder()),
        "cmap_count": len(actual),
        "regular_codepoint_count": len(plan.regular_codepoints),
        "wada_codepoint_count": len(plan.wada_codepoints),
        "unavailable_codepoint_count": len(plan.unavailable_codepoints),
        "unavailable_codepoints": [
            format_cp(cp) for cp in sorted(plan.unavailable_codepoints)
        ],
        "out_of_scope_codepoint_count": len(plan.out_of_scope_codepoints),
        "included_codepoint_summary": (
            codepoint_summary(expected) if plan.out_of_scope_codepoints else {}
        ),
        "expected_codepoint_count": len(expected),
        "missing_after_build": [format_cp(cp) for cp in sorted(expected - actual)],
        "extra_after_build": [format_cp(cp) for cp in sorted(actual - expected)],
        "notes": plan.notes,
    }
    return report


def make_plans() -> list[BuildPlan]:
    regular = load_font(REGULAR)
    wada = load_font(WADA)
    hiragino = load_font(HIRAGINO_PRON, font_number=1)

    regular_cps = cmap_codepoints(regular)
    wada_cps = cmap_codepoints(wada)
    hiragino_cps = cmap_codepoints(hiragino)

    hiragino_regular_raw = regular_cps - hiragino_cps
    hiragino_wada_raw = (wada_cps - hiragino_cps) - regular_cps
    hiragino_raw = hiragino_regular_raw | hiragino_wada_raw
    arib_profile = arib_b24_b62_codepoints(wada_cps)
    hiragino_included = hiragino_raw & arib_profile
    hiragino_out_of_scope = hiragino_raw - hiragino_included
    hiragino_regular = hiragino_regular_raw & hiragino_included
    hiragino_wada = hiragino_wada_raw & hiragino_included

    return [
        BuildPlan(
            mode="mix",
            output=DIST / "rounded-mplus-1m-wadalab-mix.ttf",
            family_name="Rounded M+ 1m WadaLab mix",
            full_name="Rounded M+ 1m WadaLab mix Regular",
            ps_name="RoundedMplus1mWadaLabMix-Regular",
            regular_codepoints=regular_cps,
            wada_codepoints=wada_cps - regular_cps,
            unavailable_codepoints=set(),
            out_of_scope_codepoints=set(),
            notes=[
                "Rounded M+ 1m regular を優先して使用します。",
                "wlcmaru2004aribu.ttf のうち、Rounded M+ に無いコードポイントをすべて補完します。",
            ],
        ),
        BuildPlan(
            mode="arib",
            output=DIST / "rounded-mplus-1m-wadalab-comp-arib.ttf",
            family_name="Rounded M+ 1m WadaLab comp ARIB",
            full_name="Rounded M+ 1m WadaLab comp ARIB Regular",
            ps_name="RoundedMplus1mWadaLabCompARIB-Regular",
            regular_codepoints=hiragino_regular,
            wada_codepoints=hiragino_wada,
            unavailable_codepoints=set(),
            out_of_scope_codepoints=hiragino_out_of_scope,
            notes=[
                "Hiragino Maru Gothic ProN W4 に無いコードポイントだけを含みます。",
                "採用順は、Rounded M+ 1m regular、wlcmaru2004aribu.ttf の順です。",
                "ARIB STD-B24 と ARIB STD-B62 相当の文字集合だけを採用します。",
            ],
        ),
    ]


def write_reports(reports: list[dict[str, object]]) -> None:
    ANALYSIS.mkdir(exist_ok=True)
    (ANALYSIS / "build-report.json").write_text(
        json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = ["# 生成レポート", ""]
    for report in reports:
        lines.extend(
            [
                f"## {report['mode']}",
                f"- 出力先: `{report['output']}`",
                f"- フルネーム: {report['full_name']}",
                f"- UPM: {report['units_per_em']}",
                f"- グリフ数: {report['glyph_count']}",
                f"- cmap: {report['cmap_count']}",
                f"- Rounded M+ 由来コードポイント数: {report['regular_codepoint_count']}",
                f"- WadaLab 由来コードポイント数: {report['wada_codepoint_count']}",
                f"- 入力元に無いコードポイント数: {report['unavailable_codepoint_count']}",
                f"- 採用範囲外の候補数: {report['out_of_scope_codepoint_count']}",
                f"- 生成後の不足数: {len(report['missing_after_build'])}",
                f"- 生成後の余分なコードポイント数: {len(report['extra_after_build'])}",
            ]
        )
        if report["unavailable_codepoints"]:
            lines.append(
                f"- 入力元に無いコードポイント: {', '.join(report['unavailable_codepoints'])}"
            )
        if report["included_codepoint_summary"]:
            summary = ", ".join(
                f"{label}: {count}"
                for label, count in report["included_codepoint_summary"].items()
            )
            lines.append(f"- 採用内訳: {summary}")
        for note in report["notes"]:
            lines.append(f"- メモ: {note}")
        lines.append("")
    (ANALYSIS / "build-report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["all", "mix", "arib"],
        default="all",
    )
    parser.add_argument(
        "--fs-type",
        type=lambda value: int(value, 0),
        default=0,
        help="OS/2 fsType for generated fonts. Default: 0.",
    )
    args = parser.parse_args()

    plans = make_plans()
    if args.mode != "all":
        plans = [plan for plan in plans if plan.mode == args.mode]
    reports = [build_font(plan, fs_type=args.fs_type) for plan in plans]
    write_reports(reports)
    for report in reports:
        print(f"{report['mode']}: {report['output']}")


if __name__ == "__main__":
    main()
