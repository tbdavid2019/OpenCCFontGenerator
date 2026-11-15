"""Simulate compiled OpenCCFontGenerator GSUB rules for instant UI specimen previews."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Set, Tuple

from ..font import build_codepoints_non_han, build_opencc_char_table, build_opencc_word_table


DEFAULT_PREVIEW_WORDS = (
    '皇后',
    '后来',
    '软件',
    '头发',
    '发现',
    '面条',
    '业余',
    '“你好”',
)

CONFIG_PAIR_MAP = {
    's2t': DEFAULT_PREVIEW_WORDS,
    'twp': DEFAULT_PREVIEW_WORDS,
    's2tw': DEFAULT_PREVIEW_WORDS,
    's2hk': DEFAULT_PREVIEW_WORDS,
    't2s': ('皇后', '後來', '軟體', '頭髮', '發現', '麵條', '業餘', '「你好」'),
}


@lru_cache(maxsize=1)
def _get_non_han_codepoints() -> Set[int]:
    return set(build_codepoints_non_han())


@lru_cache(maxsize=8)
def _load_preview_tables(config: str) -> Tuple[Dict[str, str], int, Dict[int, str]]:
    word_entries = build_opencc_word_table(config)
    word_map: Dict[str, str] = {}
    max_word_len = 1
    for src_cps, dst_cps in word_entries:
        src = ''.join(chr(cp) for cp in src_cps)
        dst = ''.join(chr(cp) for cp in dst_cps)
        word_map[src] = dst
        if len(src) > max_word_len:
            max_word_len = len(src)

    char_map = {src_cp: chr(dst_cp) for src_cp, dst_cp in build_opencc_char_table(config)}
    return word_map, max_word_len, char_map


def preview_convert(text: str, config: str = 's2t', no_punc: bool = False) -> str:
    """Convert text using the exact word2pseu -> char2char -> pseu2word lookup logic."""
    if not text:
        return ''

    word_map, max_len, char_map = _load_preview_tables(config)
    non_han = _get_non_han_codepoints() if no_punc else set()

    out: List[str] = []
    idx = 0
    length = len(text)
    while idx < length:
        matched = False
        upper = min(max_len, length - idx)
        for span in range(upper, 1, -1):
            segment = text[idx:idx + span]
            if no_punc and any(ord(c) in non_han for c in segment):
                continue
            if segment in word_map:
                out.append(word_map[segment])
                idx += span
                matched = True
                break
        if matched:
            continue

        ch = text[idx]
        cp = ord(ch)
        if no_punc and cp in non_han:
            out.append(ch)
        else:
            out.append(char_map.get(cp, ch))
        idx += 1

    return ''.join(out)


def build_specimen_pairs(config: str = 's2t', no_punc: bool = False) -> List[Dict[str, str]]:
    """Return representative conversion pairs matching the selected OpenCC configuration."""
    sources = CONFIG_PAIR_MAP.get(config, DEFAULT_PREVIEW_WORDS)
    return [{'source': src, 'converted': preview_convert(src, config=config, no_punc=no_punc)} for src in sources]
