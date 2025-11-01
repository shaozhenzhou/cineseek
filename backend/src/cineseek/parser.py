# -*- coding: utf-8 -*-
"""电影名称解析器。

优先使用 guessit 解析常见发布名；若不可用或解析失败，则回退到正则与启发式规则。
解析结果尽量给出：基础片名（尽可能干净）与可能的年份。
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

try:
    # guessit 在解析影视发布名方面非常强大
    from guessit import guessit  # type: ignore
except Exception:  # pragma: no cover - 环境无 guessit 时走降级
    guessit = None  # type: ignore


# 常见无用标记（分辨率、来源、音轨、编码等），用于降级清洗
_NOISE_TOKENS = {
    "1080p", "2160p", "720p", "480p", "4k", "8k",
    "webrip", "web-dl", "webdl", "hdr", "hdr10", "dv", "dolby", "vision",
    "x264", "x265", "h264", "h265", "hevc", "avc",
    "bluray", "bdrip", "brrip", "remux", "dvdrip",
    "dts", "dts-hd", "truehd", "atmos", "aac", "flac", "mp3",
    "dual", "audio", "multi", "subs", "multisub",
    "nf", "netflix", "imax", "remastered", "extended", "theatrical",
    "publichd", "eam", "protonmovies", "phdteam",
}

_SPLIT_PAT = re.compile(r"[\._\-\[\]\(\)\{\}\s]+", re.IGNORECASE)
_YEAR_PAT = re.compile(r"(?P<year>19\d{2}|20\d{2})")


def parse_title(raw: str) -> Tuple[str, Optional[int]]:
    """解析输入字符串，返回 (清洗后的片名, 年份或 None)。

    - 优先使用 guessit
    - 若失败，使用启发式：
      1) 提取第一个像年份的 4 位数字（>=1900）
      2) 以分隔符切分，剔除常见噪声标记
      3) 合并剩余 token 为片名，保持原有顺序
    """
    s = raw.strip()

    # 1) guessit 解析
    if guessit is not None:
        try:
            g = guessit(s)
            # title 可能不存在，或会分词，优先取 title
            title = None
            if isinstance(g.get("title"), str):
                title = g["title"]
            elif isinstance(g.get("title"), list):
                title = " ".join(g["title"])  # 极少出现
            year = g.get("year") if isinstance(g.get("year"), int) else None
            if title:
                return title.strip(), year
        except Exception:
            pass  # 回退到启发式

    # 2) 启发式
    year = None
    m = _YEAR_PAT.search(s)
    if m:
        try:
            y = int(m.group("year"))
            if 1900 <= y <= 2100:
                year = y
        except Exception:
            year = None

    # 切分并清洗
    tokens = [t for t in _SPLIT_PAT.split(s) if t]
    cleaned: list[str] = []
    for t in tokens:
        tt = t.lower()
        if tt in _NOISE_TOKENS:
            continue
        # 纯数字（可能是分辨率/集数），且不是年份，丢弃
        if tt.isdigit() and (year is None or tt != str(year)):
            continue
        cleaned.append(t)

    # 若为空，回退整个字符串
    if not cleaned:
        cleaned_name = _YEAR_PAT.sub("", s).strip()
        return cleaned_name, year

    # 片名尽量短：
    # - 若包含中文，通常中文段落更靠前，截取到首次出现的英文质量标记前
    cleaned_name = " ".join(cleaned).strip()

    return cleaned_name, year
