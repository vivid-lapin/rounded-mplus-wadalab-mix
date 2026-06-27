from __future__ import annotations

from functools import lru_cache


def hex_codepoints(text: str) -> frozenset[int]:
    return frozenset(int(token, 16) for token in text.split())


# ARIB STD-B24 Table 7-19 "Code Values for Added Symbols Set".
ARIB_B24_ADDITIONAL_CODEPOINTS = hex_codepoints(
    """
    00B2 00B3 00BC 00BD 00BE 0FD6 203C 2049 2113 2116 2121 213B
    2150 2151 2152 2153 2154 2155 2156 2157 2158 2159 215A 215B
    2160 2161 2162 2163 2164 2165 2166 2167 2168 2169 216A 216B
    2189 2460 2461 2462 2463 2464 2465 2466 2467 2468 2469 246A
    246B 246C 246D 246E 246F 2470 2471 2472 2473 2474 2475 2476
    2477 2478 2479 247A 247B 247C 247D 247E 247F 2488 2489 248A
    248B 248C 248D 248E 248F 2490 2491 2492 2493 24B9 24C8 24EB
    24EC 25B6 25C0 2600 2601 2602 2603 260E 2613 2614 2616 2617
    2660 2663 2665 2666 2668 266C 2693 269E 269F 26A1 26BE 26BF
    26C4 26C5 26C6 26C7 26C8 26C9 26CA 26CB 26CC 26CD 26CF 26D0
    26D1 26D2 26D3 26D4 26D5 26D6 26D7 26D8 26D9 26DA 26DB 26DC
    26DD 26DE 26DF 26E0 26E1 26E3 26E8 26E9 26EA 26EB 26EC 26ED
    26EE 26EF 26F0 26F1 26F2 26F3 26F4 26F5 26F6 26F7 26F8 26F9
    26FA 26FB 26FC 26FD 26FE 26FF 2708 2757 2776 2777 2778 2779
    277A 277B 277C 277D 277E 277F 27A1 27D0 2A00 2B05 2B06 2B07
    2B1B 2B24 2B2E 2B2F 2B55 2B56 2B57 2B58 2B59 3016 3017 3036
    322A 322B 322C 322D 322E 322F 3230 3231 3232 3233 3236 3237
    3239 3244 3245 3246 3247 3248 3249 324A 324B 324C 324D 324E
    324F 3251 3252 3253 3254 3255 3256 3257 3258 3259 325A 325B
    328B 3299 3371 337B 337C 337D 337E 338F 3390 339D 339E 33A0
    33A1 33A2 33A4 33A5 33CA 3402 351F 37E2 3EDA 4093 4103 4264
    4EFD 4EFF 4F9A 4FC9 509C 511E 51BC 5307 5361 536C 544D 5496
    549C 54A9 550E 554A 5672 56E4 5733 5734 5880 59E4 5A23 5A55
    5BEC 5EAC 5F34 5F45 5FB7 6017 6130 6624 66C8 66D9 66FA 66FB
    6852 6911 693B 6A45 6A91 6ADB 6BF1 6CE0 6D2E 6DBF 6DCA 6DF8
    6F5E 6FF9 7064 7147 71C1 7200 739F 73A8 73C9 73D6 741B 7421
    7426 742A 742C 7439 744B 7575 7581 7772 78C8 78E0 7947 79AE
    79DA 7A1E 7B7F 7C31 7D8B 7FA1 8118 813A 82AE 845B 84DC 84EC
    8559 85CE 8755 87EC 880B 88F5 89D2 8A79 8AF6 8DCE 8FBB 8FF6
    90DD 9127 912D 91B2 9233 9288 9321 9348 9592 96DE 9903 9940
    9AD9 9BD6 9DD7 9EB4 9EB5 9FC4 9FC5 9FC6 E081 E084 E08A E08B
    E08C E08E E0D8 E0D9 E0F8 E0F9 E0FA E0FB E0FC E0FD E0FE E0FF
    E180 E181 E182 E183 E184 E185 E186 E187 E18A E18B E18C E18D
    E18E E190 E191 E192 E193 E194 E195 E196 E197 E198 E199 E19A
    E19C E1AE E1C3 E1C7 E1C8 E1C9 E1CA E1CB E1D0 E1D6 E28B E28C
    E28D E28E E28F E290 E291 E292 E293 E294 E295 E296 E297 E298
    E299 E29A E29B E29C E29D E29E E29F E2A4 E2A5 E2A6 E2A7 E2A8
    E2A9 E2AA E2AB E2AC E2AD E2AE E2AF E2B0 E2B1 E2B2 E2B3 E2B4
    E2B5 E2B6 E2B7 E2B8 E2B9 E2BA E2BB E2BC E2BD E2BE E2BF E2C0
    E2C1 E2C2 E2C4 E2C5 E2CD E2CE E2CF E2D0 E2D1 E2D2 E2D3 E2D4
    E2D5 E2D6 E2D7 E2D8 E2D9 E2DA E2DB E2DC E2DD E2DE E2DF E2E0
    E2E1 E2E2 E2FB E383 E384 E385 E386 E387 E388 E389 E38A E38B
    E38C E38D E38E E38F E390 E391 E392 E393 E394 E395 E396 E397
    E398 E399 E39A E39B E39C E3A7 E3A8 FA10 FA11 FA45 FA46 FA4A
    FA6B FA6C FA6D
    """
)

# ARIB STD-B62 Volume 1 Part 2, Section 5.2 / Description 1. This keeps the
# official B62 additions explicit and adds the BS4K/8K symbols implemented in
# wlcmaru2004aribu.ttf but not present in the older English B62 PDF text.
ARIB_B62_ADDITIONAL_CODEPOINTS = hex_codepoints(
    """
    1F100 1F101 1F102 1F103 1F104 1F105 1F106 1F107 1F108 1F109
    1F10A 1F110 1F112 1F113 1F114 1F115 1F116 1F117 1F118 1F119
    1F11A 1F11B 1F11C 1F11D 1F11E 1F11F 1F120 1F121 1F122 1F123
    1F124 1F125 1F126 1F127 1F128 1F129 1F12A 1F12B 1F12C 1F12D
    1F131 1F13D 1F13F 1F142 1F146 1F14A 1F14B 1F14C 1F14D 1F14E
    1F15F 1F179 1F17B 1F17C 1F17F 1F18A 1F18B 1F18C 1F18D 1F190
    1F19B 1F19C 1F19D 1F19E 1F19F 1F1A0 1F1A1 1F1A2 1F1A3 1F1A4
    1F1A5 1F1A6 1F1A7 1F1A8 1F1A9 1F1AA 1F1AB 1F1AC 1F200 1F210
    1F211 1F212 1F213 1F214 1F215 1F216 1F217 1F218 1F219 1F21A
    1F21B 1F21C 1F21D 1F21E 1F21F 1F220 1F221 1F222 1F223 1F224
    1F225 1F226 1F227 1F228 1F229 1F22B 1F22C 1F22D 1F22E 1F22F
    1F230 1F231 1F23B 1F240 1F241 1F242 1F243 1F244 1F245 1F246
    1F247 1F248 20158 233CC 233FE 235C4 242EE
    """
)

ARIB_PUA_RANGES = (
    (0xE080, 0xE095, "ARIB additional symbols PUA"),
    (0xE0C9, 0xE0CE, "ARIB additional symbols PUA"),
    (0xE0D0, 0xE0D3, "ARIB additional symbols PUA"),
    (0xE0D8, 0xE0D9, "ARIB additional symbols PUA"),
    (0xE0DC, 0xE0F0, "ARIB additional symbols PUA"),
    (0xE0F5, 0xE0FF, "ARIB additional symbols PUA"),
    (0xE180, 0xE19C, "ARIB additional symbols PUA"),
    (0xE1A7, 0xE1D7, "ARIB additional symbols PUA"),
    (0xE285, 0xE2C6, "ARIB additional symbols PUA"),
    (0xE2C9, 0xE2E2, "ARIB additional symbols PUA"),
    (0xE2E5, 0xE2F7, "ARIB additional symbols PUA"),
    (0xE2F9, 0xE2FB, "ARIB additional symbols PUA"),
    (0xE2FF, 0xE2FF, "ARIB additional symbols PUA"),
    (0xE380, 0xE3A5, "ARIB additional symbols PUA"),
    (0xE3A7, 0xE3A8, "ARIB additional symbols PUA"),
    (0xE760, 0xE88E, "ARIB JIS X0213 BMP PUA reassignment"),
)


@lru_cache(maxsize=1)
def jis_x0208_codepoints() -> frozenset[int]:
    codepoints: set[int] = set()
    for ku in range(1, 95):
        for ten in range(1, 95):
            sequence = b"\x1b$B" + bytes([ku + 0x20, ten + 0x20]) + b"\x1b(B"
            try:
                text = sequence.decode("iso2022_jp")
            except UnicodeDecodeError:
                continue
            if len(text) == 1:
                codepoints.add(ord(text))
    return frozenset(codepoints)


def jis_x0201_codepoints() -> set[int]:
    return set(range(0x20, 0x7F)) | {0x00A5, 0x203E} | set(range(0xFF61, 0xFFA0))


@lru_cache(maxsize=1)
def jis_x0213_codepoints() -> frozenset[int]:
    codepoints: set[int] = set()
    for first in range(0xA1, 0xFF):
        for second in range(0xA1, 0xFF):
            try:
                text = bytes([first, second]).decode("euc_jis_2004")
            except UnicodeDecodeError:
                text = ""
            codepoints.update(ord(char) for char in text)
            try:
                text = bytes([0x8F, first, second]).decode("euc_jis_2004")
            except UnicodeDecodeError:
                continue
            codepoints.update(ord(char) for char in text)
    return frozenset(codepoints)


def codepoints_in_ranges(codepoints: set[int], ranges: tuple[tuple[int, int, str], ...]) -> set[int]:
    return {
        cp
        for cp in codepoints
        if any(first <= cp <= last for first, last, _ in ranges)
    }


def arib_b24_b62_codepoints(implementation_codepoints: set[int]) -> set[int]:
    return (
        set(jis_x0208_codepoints())
        | jis_x0201_codepoints()
        | set(jis_x0213_codepoints())
        | set(range(0x00A0, 0x0100))
        | (ARIB_B24_ADDITIONAL_CODEPOINTS & implementation_codepoints)
        | (ARIB_B62_ADDITIONAL_CODEPOINTS & implementation_codepoints)
        | codepoints_in_ranges(implementation_codepoints, ARIB_PUA_RANGES)
    )


def codepoint_summary(codepoints: set[int]) -> dict[str, int]:
    result: dict[str, int] = {}
    remaining = set(codepoints)

    for label, group in (
        ("ARIB STD-B24 Table 7-19", ARIB_B24_ADDITIONAL_CODEPOINTS),
        ("ARIB STD-B62 / BS4K additions", ARIB_B62_ADDITIONAL_CODEPOINTS),
    ):
        count = len(remaining & group)
        if count:
            result[label] = count
            remaining -= group

    for first, last, label in ARIB_PUA_RANGES:
        group = {cp for cp in remaining if first <= cp <= last}
        if group:
            result[label] = result.get(label, 0) + len(group)
            remaining -= group

    jis_and_latin = (
        set(jis_x0208_codepoints())
        | jis_x0201_codepoints()
        | set(jis_x0213_codepoints())
        | set(range(0x00A0, 0x0100))
    )
    count = len(remaining & jis_and_latin)
    if count:
        result["JIS X 0208 / JIS X 0201 / JIS X 0213 / Latin-1"] = count
        remaining -= jis_and_latin

    if remaining:
        result["採用範囲外"] = len(remaining)
    return result
