#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import math
import struct
import unicodedata
from collections import defaultdict
from pathlib import Path

from arib_charset import arib_b24_b62_codepoints, codepoint_summary


ROOT = Path(__file__).resolve().parents[1]
REGULAR = ROOT / "rounded-mplus-1m-regular.ttf"
ARIB = ROOT / "rounded-mplus-1m-arib.ttf"
WADA_ARIB = ROOT / "wlcmaru2004aribu.ttf"
HIRAGINO = Path("/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc")
OUT = ROOT / "analysis"
REPORT_FONT_LABELS = {
    "regular": "Rounded M+ regular",
    "reference_font": "参考フォント",
    "hiragino_pron": "Hiragino Maru Gothic ProN",
    "wlcmaru2004aribu": "WadaLab (wlcmaru2004aribu.ttf)",
}


class Font:
    def __init__(self, path: Path, index: int = 0) -> None:
        self.path = path
        self.index = index
        self.data = path.read_bytes()
        self.base = 0
        self.ttc_count = 1
        if self.data[:4] == b"ttcf":
            self.ttc_count = struct.unpack_from(">I", self.data, 8)[0]
            self.base = struct.unpack_from(">I", self.data, 12 + 4 * index)[0]

        table_count = struct.unpack_from(">H", self.data, self.base + 4)[0]
        self.tables: dict[str, tuple[int, int, int]] = {}
        for i in range(table_count):
            tag, checksum, offset, length = struct.unpack_from(
                ">4sIII", self.data, self.base + 12 + i * 16
            )
            self.tables[tag.decode("latin1")] = (offset, length, checksum)

    def _table(self, tag: str) -> tuple[int, int]:
        offset, length, _ = self.tables[tag]
        return offset, length

    @property
    def units_per_em(self) -> int | None:
        if "head" not in self.tables:
            return None
        offset, _ = self._table("head")
        return struct.unpack_from(">H", self.data, offset + 18)[0]

    @property
    def glyph_count(self) -> int | None:
        if "maxp" not in self.tables:
            return None
        offset, _ = self._table("maxp")
        return struct.unpack_from(">H", self.data, offset + 4)[0]

    @property
    def horizontal_metric_count(self) -> int | None:
        if "hhea" not in self.tables:
            return None
        offset, _ = self._table("hhea")
        return struct.unpack_from(">H", self.data, offset + 34)[0]

    @property
    def fs_type(self) -> int | None:
        if "OS/2" not in self.tables:
            return None
        offset, _ = self._table("OS/2")
        return struct.unpack_from(">H", self.data, offset + 8)[0]

    @property
    def head_dates(self) -> tuple[str, str] | None:
        if "head" not in self.tables:
            return None
        offset, _ = self._table("head")
        created, modified = struct.unpack_from(">QQ", self.data, offset + 20)
        epoch = dt.datetime(1904, 1, 1)
        return (
            str(epoch + dt.timedelta(seconds=created)),
            str(epoch + dt.timedelta(seconds=modified)),
        )

    def names(self) -> dict[int, list[str]]:
        if "name" not in self.tables:
            return {}
        offset, _ = self._table("name")
        _, count, string_offset = struct.unpack_from(">HHH", self.data, offset)
        result: dict[int, list[str]] = defaultdict(list)
        for i in range(count):
            rec = offset + 6 + i * 12
            platform, _, _, name_id, length, rel = struct.unpack_from(
                ">HHHHHH", self.data, rec
            )
            raw = self.data[offset + string_offset + rel : offset + string_offset + rel + length]
            encoding = "utf-16-be" if platform in (0, 3) else "macroman"
            result[name_id].append(raw.decode(encoding, errors="replace"))
        return result

    def best_name(self, name_id: int) -> str:
        values = self.names().get(name_id, [])
        return values[0] if values else ""

    def cmap(self) -> dict[int, int]:
        offset, _ = self._table("cmap")
        _, count = struct.unpack_from(">HH", self.data, offset)
        subtables: list[tuple[int, int, int, dict[int, int]]] = []
        for i in range(count):
            platform, encoding, rel = struct.unpack_from(">HHI", self.data, offset + 4 + i * 8)
            fmt, cmap = self._parse_cmap_subtable(offset + rel)
            subtables.append((platform, encoding, fmt, cmap))

        # Prefer a full Unicode cmap, then the largest available cmap.
        _, _, _, cmap = max(
            subtables,
            key=lambda row: (row[2] == 12, row[0] == 3 and row[1] == 10, len(row[3])),
        )
        return cmap

    def _parse_cmap_subtable(self, offset: int) -> tuple[int, dict[int, int]]:
        fmt = struct.unpack_from(">H", self.data, offset)[0]
        cmap: dict[int, int] = {}
        if fmt == 4:
            length, _, seg_count_x2 = struct.unpack_from(">HHH", self.data, offset + 2)
            seg_count = seg_count_x2 // 2
            pos = offset + 14
            end = list(struct.unpack_from(">" + "H" * seg_count, self.data, pos))
            pos += seg_count * 2 + 2
            start = list(struct.unpack_from(">" + "H" * seg_count, self.data, pos))
            pos += seg_count * 2
            delta = list(struct.unpack_from(">" + "h" * seg_count, self.data, pos))
            pos += seg_count * 2
            range_offset_pos = pos
            range_offset = list(struct.unpack_from(">" + "H" * seg_count, self.data, pos))

            for i, (first, last) in enumerate(zip(start, end)):
                if first == 0xFFFF and last == 0xFFFF:
                    continue
                for cp in range(first, last + 1):
                    if range_offset[i] == 0:
                        gid = (cp + delta[i]) & 0xFFFF
                    else:
                        gid_pos = range_offset_pos + 2 * i + range_offset[i] + 2 * (cp - first)
                        if gid_pos + 2 > offset + length:
                            continue
                        gid = struct.unpack_from(">H", self.data, gid_pos)[0]
                        if gid:
                            gid = (gid + delta[i]) & 0xFFFF
                    if gid:
                        cmap[cp] = gid
        elif fmt == 12:
            group_count = struct.unpack_from(">I", self.data, offset + 12)[0]
            for i in range(group_count):
                first, last, first_gid = struct.unpack_from(">III", self.data, offset + 16 + i * 12)
                for cp in range(first, last + 1):
                    cmap[cp] = first_gid + cp - first
        return fmt, cmap

    def hmetric(self, glyph_id: int) -> tuple[int, int] | None:
        metric_count = self.horizontal_metric_count
        glyph_count = self.glyph_count
        if "hmtx" not in self.tables or metric_count is None or glyph_count is None:
            return None
        offset, _ = self._table("hmtx")
        if glyph_id < metric_count:
            return struct.unpack_from(">Hh", self.data, offset + glyph_id * 4)
        advance = struct.unpack_from(">H", self.data, offset + (metric_count - 1) * 4)[0]
        lsb_offset = offset + metric_count * 4 + (glyph_id - metric_count) * 2
        return advance, struct.unpack_from(">h", self.data, lsb_offset)[0]


def ranges(codepoints: set[int]) -> list[tuple[int, int]]:
    if not codepoints:
        return []
    values = sorted(codepoints)
    result: list[tuple[int, int]] = []
    first = prev = values[0]
    for cp in values[1:]:
        if cp == prev + 1:
            prev = cp
        else:
            result.append((first, prev))
            first = prev = cp
    result.append((first, prev))
    return result


def format_ranges(codepoints: set[int], limit: int | None = None) -> str:
    items = ranges(codepoints)
    shown = items if limit is None else items[:limit]
    parts = [
        f"U+{first:04X}" if first == last else f"U+{first:04X}-U+{last:04X} ({last - first + 1})"
        for first, last in shown
    ]
    if limit is not None and len(items) > limit:
        parts.append(f"... +{len(items) - limit} ranges")
    return ", ".join(parts)


def label(cp: int) -> str:
    char = chr(cp)
    name = unicodedata.name(char, "")
    return f"U+{cp:04X}\t{char}\t{name}"


def round_half_away(value: float) -> int:
    return int(math.floor(value + 0.5)) if value >= 0 else int(math.ceil(value - 0.5))


def scaled_hmetric_match_count(source: Font, dest: Font) -> tuple[int, int]:
    scale = (dest.units_per_em or 1) / (source.units_per_em or 1)
    source_cmap = source.cmap()
    dest_cmap = dest.cmap()
    total = 0
    matches = 0
    for cp in sorted(set(source_cmap) & set(dest_cmap)):
        source_metric = source.hmetric(source_cmap[cp])
        dest_metric = dest.hmetric(dest_cmap[cp])
        if source_metric is None or dest_metric is None:
            continue
        total += 1
        expected = (
            round_half_away(source_metric[0] * scale),
            round_half_away(source_metric[1] * scale),
        )
        if expected == dest_metric:
            matches += 1
    return matches, total


def write_codepoints(path: Path, codepoints: set[int]) -> None:
    path.write_text("\n".join(label(cp) for cp in sorted(codepoints)) + "\n", encoding="utf-8")


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def summary(font: Font) -> dict[str, object]:
    created, modified = font.head_dates or ("", "")
    cmap = font.cmap()
    return {
        "path": display_path(font.path),
        "index": font.index,
        "family": font.best_name(1),
        "full_name": font.best_name(4),
        "version": font.best_name(5),
        "postscript_name": font.best_name(6),
        "copyright": font.best_name(0),
        "units_per_em": font.units_per_em,
        "glyph_count": font.glyph_count,
        "cmap_count": len(cmap),
        "fs_type": font.fs_type,
        "created": created,
        "modified": modified,
        "tables": sorted(font.tables),
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)
    regular = Font(REGULAR)
    arib = Font(ARIB) if ARIB.exists() else None
    wada_arib = Font(WADA_ARIB) if WADA_ARIB.exists() else None
    hiragino_pron = Font(HIRAGINO, 1)

    reg = set(regular.cmap())
    ari = set(arib.cmap()) if arib else set()
    hira = set(hiragino_pron.cmap())
    wada = set(wada_arib.cmap()) if wada_arib else set()
    arib_raw = (reg | wada) - hira
    arib_profile = arib_b24_b62_codepoints(wada)
    arib_filtered = arib_raw & arib_profile
    arib_out_of_scope = arib_raw - arib_filtered

    sets = {
        "wadalab_only_vs_regular": wada - reg,
        "regular_plus_wadalab": reg | wada,
        "regular_missing_in_hiragino_pron": reg - hira,
        "regular_plus_wadalab_missing_in_hiragino_pron_raw": arib_raw,
        "regular_plus_wadalab_missing_in_hiragino_pron": arib_filtered,
        "arib_out_of_scope": arib_out_of_scope,
        "needs_wadalab_after_regular": ((wada - hira) - reg) & arib_filtered,
    }
    if arib:
        sets.update(
            {
                "reference_font_only_vs_regular": ari - reg,
                "regular_only_vs_reference_font": reg - ari,
                "reference_font_missing_in_hiragino_pron": ari - hira,
                "reference_font_only_missing_in_hiragino_pron": (ari - reg) - hira,
                "regular_plus_reference_font_missing_in_hiragino_pron": (reg | ari) - hira,
                "needs_reference_font_after_regular": ((reg | ari) - hira) - reg,
                "reference_font_unavailable_from_regular_plus_wadalab": ari - (reg | wada),
            }
        )

    write_codepoints(OUT / "wadalab-only-vs-regular.txt", sets["wadalab_only_vs_regular"])
    write_codepoints(OUT / "regular-plus-wadalab.txt", sets["regular_plus_wadalab"])
    write_codepoints(OUT / "hiragino-pron-missing-from-regular.txt", sets["regular_missing_in_hiragino_pron"])
    write_codepoints(
        OUT / "hiragino-pron-arib-needs-wadalab-after-regular.txt",
        sets["needs_wadalab_after_regular"],
    )
    write_codepoints(OUT / "hiragino-pron-arib-out-of-scope.txt", sets["arib_out_of_scope"])
    if arib:
        write_codepoints(OUT / "reference-font-only-vs-regular.txt", sets["reference_font_only_vs_regular"])
        write_codepoints(OUT / "regular-only-vs-reference-font.txt", sets["regular_only_vs_reference_font"])
        write_codepoints(OUT / "hiragino-pron-missing-from-reference-font.txt", sets["reference_font_missing_in_hiragino_pron"])
        write_codepoints(
            OUT / "hiragino-pron-missing-from-reference-font-only.txt",
            sets["reference_font_only_missing_in_hiragino_pron"],
        )
        write_codepoints(
            OUT / "hiragino-pron-arib-needs-reference-font-after-regular.txt",
            sets["needs_reference_font_after_regular"],
        )
        write_codepoints(
            OUT / "reference-font-unavailable-from-regular-plus-wadalab.txt",
            sets["reference_font_unavailable_from_regular_plus_wadalab"],
        )

    payload = {
        "fonts": {
            "regular": summary(regular),
            "reference_font": summary(arib) if arib else None,
            "hiragino_pron": summary(hiragino_pron),
            "wlcmaru2004aribu": summary(wada_arib) if wada_arib else None,
        },
        "counts": {name: len(values) for name, values in sets.items()},
        "ranges": {name: format_ranges(values) for name, values in sets.items()},
        "arib_included_summary": codepoint_summary(arib_filtered),
        "wlcmaru2004aribu_coverage": {
            "count": len(wada),
            "ranges": format_ranges(wada),
            "codepoints_added_after_regular": len(wada - reg),
        },
    }
    if arib:
        matching, checked = scaled_hmetric_match_count(regular, arib)
        payload["regular_to_reference_font_metric_scale"] = {
            "scale": (arib.units_per_em or 1) / (regular.units_per_em or 1),
            "matching_common_codepoints": matching,
            "common_codepoints_checked": checked,
        }
    (OUT / "font-audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = [
        "# フォント監査",
        "",
        "## 対象フォント",
    ]
    for key, value in payload["fonts"].items():
        if value is None:
            continue
        label_name = REPORT_FONT_LABELS.get(key, key)
        report.extend(
            [
                f"- {label_name}: {value['full_name']} / {value['version']}",
                f"  - ファイル: `{value['path']}`",
                f"  - index: {value['index']}, UPM: {value['units_per_em']}, グリフ数: {value['glyph_count']}, cmap: {value['cmap_count']}, fsType: 0x{value['fs_type']:X}",
                f"  - 著作権/name 0: {value['copyright']}",
                f"  - 作成日時: {value['created']}, 更新日時: {value['modified']}",
            ]
        )
    report.extend(
        [
            "",
            "## 件数",
            f"- WadaLab (wlcmaru2004aribu.ttf) の収録コードポイント数: {len(wada)}",
            f"- Rounded M+ regular に無く、WadaLab から補うコードポイント数: {len(sets['wadalab_only_vs_regular'])}",
            f"- Rounded M+ + WadaLab の合計コードポイント数: {len(sets['regular_plus_wadalab'])}",
            f"- Rounded M+ regular のうち Hiragino Maru Gothic ProN に無いコードポイント数: {len(sets['regular_missing_in_hiragino_pron'])}",
            f"- Rounded M+ を優先し、WadaLab 全体で補う場合の Hiragino ARIB 対象数: {len(sets['regular_plus_wadalab_missing_in_hiragino_pron'])}",
            f"- 採用範囲外の Hiragino ARIB 候補数: {len(sets['arib_out_of_scope'])}",
            f"- そのうち WadaLab から取るコードポイント数: {len(sets['needs_wadalab_after_regular'])}",
            "",
            "## 重要な範囲",
            f"- Rounded M+ 優先後、WadaLab から補う範囲: {format_ranges(sets['wadalab_only_vs_regular'], 80)}",
            f"- Rounded M+ 優先後、WadaLab 全体から補う必要がある範囲: {format_ranges(sets['needs_wadalab_after_regular'], 80)}",
        ]
    )
    if arib_filtered:
        included_summary_text = ", ".join(
            f"{label_name}: {count}" for label_name, count in codepoint_summary(arib_filtered).items()
        )
        report.append(f"- 採用範囲: {included_summary_text}")
    if arib:
        metric = payload["regular_to_reference_font_metric_scale"]
        report.extend(
            [
                "",
                "## 参考フォントとの比較",
                f"- Rounded M+ regular に無く、参考フォントにだけあるコードポイント数: {len(sets['reference_font_only_vs_regular'])}",
                f"- 参考フォントに無く、Rounded M+ regular にだけあるコードポイント数: {len(sets['regular_only_vs_reference_font'])}",
                f"- 参考フォントのうち Hiragino Maru Gothic ProN に無いコードポイント数: {len(sets['reference_font_missing_in_hiragino_pron'])}",
                f"- 参考フォントのうち、Rounded M+ + WadaLab でも用意できないコードポイント数: {len(sets['reference_font_unavailable_from_regular_plus_wadalab'])}",
                f"- Rounded M+ regular→参考フォントの共通 hmtx が 1000→1024 スケールと一致した数: {metric['matching_common_codepoints']} / {metric['common_codepoints_checked']}",
                f"- Rounded M+ + WadaLab でも用意できない参考フォント範囲: {format_ranges(sets['reference_font_unavailable_from_regular_plus_wadalab'], 80)}",
            ]
        )
    else:
        report.extend(
            [
                "",
                "## 参考フォントとの比較",
                "- `rounded-mplus-1m-arib.ttf` が無いため、参考フォントとの比較はスキップしました。",
            ]
        )
    (OUT / "font-audit.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(display_path(OUT / "font-audit.md"))


if __name__ == "__main__":
    main()
