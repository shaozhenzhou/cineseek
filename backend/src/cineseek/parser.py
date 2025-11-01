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

# 匹配英文和中文的分隔符（包括全角和半角括号）
_SPLIT_PAT = re.compile(r"[\._\-\[\]\(\)\{\}（）【】《》\s]+", re.IGNORECASE)
_YEAR_PAT = re.compile(r"(?P<year>19\d{2}|20\d{2})")
# 匹配括号内容（用于提取）
_BRACKET_CONTENT = re.compile(r"[（\(]([^）\)]+)[）\)]")


def parse_title(raw: str) -> Tuple[str, Optional[int]]:
    """解析输入字符串，返回 (清洗后的片名, 年份或 None)。

    - 优先使用 guessit
    - 若失败，使用启发式：
      1) 先尝试从括号中提取年份
      2) 移除括号内容（通常是备注信息）
      3) 以分隔符切分，剮除常见噪声标记
      4) 合并剩余 token 为片名，保持原有顺序
    """
    s = raw.strip()
    
    # 特殊处理：对于中文+年份紧密连接的格式（如“变形金刳2007”）
    # 先尝试提取年份，并在年份前添加空格
    year_match_direct = _YEAR_PAT.search(s)
    if year_match_direct:
        year_pos = year_match_direct.start()
        # 检查年份前是否是非分隔符字符（如中文或英文）
        if year_pos > 0 and not s[year_pos - 1].isspace() and s[year_pos - 1] not in '._-[](){}（）【】《》':
            # 在年份前添加空格，方便后续处理
            s = s[:year_pos] + ' ' + s[year_pos:]
    
    # 先尝试从括号中提取年份，然后移除括号内容
    year_from_bracket = None
    bracket_matches = _BRACKET_CONTENT.findall(s)
    for content in bracket_matches:
        # 检查括号内是否有年份
        year_match = _YEAR_PAT.search(content)
        if year_match:
            try:
                y = int(year_match.group("year"))
                if 1900 <= y <= 2100:
                    year_from_bracket = y
                    break
            except Exception:
                pass
    
    # 移除所有括号内容（包括中文和英文括号）
    s_no_brackets = _BRACKET_CONTENT.sub("", s).strip()

    # 1) guessit 解析（使用移除括号后的字符串）
    if guessit is not None:
        try:
            g = guessit(s_no_brackets)
            # title 可能不存在，或会分词，优先取 title
            title = None
            if isinstance(g.get("title"), str):
                title = g["title"]
            elif isinstance(g.get("title"), list):
                title = " ".join(g["title"])  # 极少出现
            year = g.get("year") if isinstance(g.get("year"), int) else None
            # 优先使用从括号提取的年份
            if year_from_bracket:
                year = year_from_bracket
            if title:
                return title.strip(), year
        except Exception:
            pass  # 回退到启发式

    # 2) 启发式
    year = year_from_bracket  # 使用从括号提取的年份
    if not year:
        # 如果括号中没有年份，在剩余文本中查找
        m = _YEAR_PAT.search(s_no_brackets)
        if m:
            try:
                y = int(m.group("year"))
                if 1900 <= y <= 2100:
                    year = y
            except Exception:
                year = None
    
    # 如果找到了年份，先从字符串中移除年份，避免干扰后续处理
    s_no_year = s_no_brackets
    if year:
        s_no_year = _YEAR_PAT.sub("", s_no_brackets).strip()

    # 切分并清洗（使用移除括号和年份后的字符串）
    tokens = [t for t in _SPLIT_PAT.split(s_no_year) if t]
    cleaned: list[str] = []
    for t in tokens:
        tt = t.lower()
        if tt in _NOISE_TOKENS:
            continue
        # 纯数字（可能是分辨率/集数），且不是年份，丢弃
        # 注意：已经移除了年份，所以这里不会误伤
        if tt.isdigit():
            continue
        cleaned.append(t)

    # 若为空，回退整个字符串（移除括号和年份）
    if not cleaned:
        # 直接使用已移除年份的字符串
        cleaned_name = s_no_year.strip()
        if not cleaned_name:
            # 如果还是空，移除年份后使用原始字符串
            cleaned_name = _YEAR_PAT.sub("", s).strip()
        return cleaned_name, year

    # 片名尽量短：
    # - 若包含中文，通常中文段落更靠前，截取到首次出现的英文质量标记前
    cleaned_name = " ".join(cleaned).strip()

    return cleaned_name, year
