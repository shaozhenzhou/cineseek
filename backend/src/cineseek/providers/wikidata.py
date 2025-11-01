# -*- coding: utf-8 -*-
"""基于 Wikidata/Wikipedia 的电影数据搜索实现。

核心策略：
1. 先用 Wikidata 搜索 API (wbsearchentities) 按中文优先、英文次之检索条目
2. 过滤“电影”类条目（P31 派生自 Film(Q11424)）
3. 使用 SPARQL 一次性拉取候选条目的：标题(中/英)、年份、类型、国家、图片(P18)、维基百科链接
4. 整理为统一结果返回
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Iterable, List, Dict, Any, Tuple, Optional

import httpx
from urllib.parse import urlparse

try:
    from opencc import OpenCC
    _cc = OpenCC('t2s')  # 繁体到简体
except Exception:
    _cc = None

from ..models import MovieResult, MovieResultExtended

# Wikidata 端点
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# 为了在中国大陆更稳定，适当增加超时与重试
_HTTP_TIMEOUT = httpx.Timeout(15.0, connect=15.0)
_RETRIES = 2


async def _http_get(client: httpx.AsyncClient, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """带简单重试的 GET。"""
    for i in range(_RETRIES + 1):
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()
        except Exception:
            if i >= _RETRIES:
                raise
            await asyncio.sleep(0.5 * (i + 1))
    return {}


async def _sparql(client: httpx.AsyncClient, query: str) -> Dict[str, Any]:
    """执行 SPARQL 查询。"""
    headers = {"Accept": "application/sparql-results+json"}
    for i in range(_RETRIES + 1):
        try:
            r = await client.get(SPARQL_ENDPOINT, params={"query": query}, headers=headers)
            r.raise_for_status()
            return r.json()
        except Exception:
            if i >= _RETRIES:
                raise
            await asyncio.sleep(0.5 * (i + 1))
    return {}


async def _wbsearch(client: httpx.AsyncClient, text: str, lang: str, limit: int = 5) -> List[str]:
    """调用 Wikidata 搜索，返回 QID 列表。"""
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": lang,
        "uselang": lang,
        "type": "item",
        "search": text,
        "limit": str(limit),
    }
    data = await _http_get(client, WIKIDATA_API, params)
    ids: List[str] = []
    for it in data.get("search", []):
        if isinstance(it, dict) and it.get("id"):
            ids.append(it["id"])  # 形如 Q12345
    return ids


def _build_values(qids: Iterable[str]) -> str:
    vals = " ".join(f"wd:{qid}" for qid in qids)
    return f"VALUES ?item {{ {vals} }}"


def _text(b: Dict[str, Any], key: str) -> Optional[str]:
    v = b.get(key, {}).get("value")
    return v if isinstance(v, str) and v.strip() else None


def _to_simplified(text: Optional[str]) -> Optional[str]:
    """将繁体中文转换为简体中文。"""
    if not text or not _cc:
        return text
    try:
        return _cc.convert(text)
    except Exception:
        return text


def _process_image_url(raw_url: Optional[str]) -> Optional[str]:
    """处理 Wikidata 图片 URL。
    
    Wikidata P18 返回的是 Wikimedia Commons 的文件 URL，
    需要转换为 Special:FilePath 格式。
    """
    if not raw_url:
        return None
    
    try:
        # 如果已经是完整的 URL，直接返回
        if raw_url.startswith('http://') or raw_url.startswith('https://'):
            # 如果已经是 Special:FilePath，直接返回
            if 'Special:FilePath' in raw_url or 'upload.wikimedia.org' in raw_url:
                return raw_url
            # 否则提取文件名并构建 URL
            filename = raw_url.rsplit('/', 1)[-1]
            return f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}"
        
        # 如果是相对路径或文件名
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{raw_url}"
    except Exception:
        return None


async def _fetch_details(client: httpx.AsyncClient, qids: List[str], extended: bool = False) -> List[MovieResult] | List[MovieResultExtended]:
    if not qids:
        return []
    prefix = (
        "PREFIX wd: <http://www.wikidata.org/entity/>\n"
        "PREFIX wdt: <http://www.wikidata.org/prop/direct/>\n"
        "PREFIX wikibase: <http://wikiba.se/ontology#>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "PREFIX bd: <http://www.bigdata.com/rdf#>\n"
        "PREFIX schema: <http://schema.org/>\n"
    )
    values = _build_values(qids)

    # 根据是否需要扩展信息决定查询字段
    if extended:
        query = f"""
{prefix}
SELECT ?item ?zhcnLabel ?zhLabel ?enLabel ?year ?image ?zhwiki ?enwiki ?genreZhcn ?genreZh ?genreEn ?countryZhcn ?countryZh ?countryEn WHERE {{
  {values}
  ?item wdt:P31/wdt:P279* wd:Q11424 .
  OPTIONAL {{ ?item wdt:P577 ?date . BIND(YEAR(?date) AS ?year) }}
  OPTIONAL {{ ?item wdt:P18 ?image }}
  OPTIONAL {{ ?item wdt:P136 ?genre .
            OPTIONAL {{ ?genre rdfs:label ?genreZhcn FILTER (LANG(?genreZhcn) = \"zh-cn\" || LANG(?genreZhcn) = \"zh-hans\") }}
            OPTIONAL {{ ?genre rdfs:label ?genreZh FILTER (LANG(?genreZh) = \"zh\") }}
            OPTIONAL {{ ?genre rdfs:label ?genreEn FILTER (LANG(?genreEn) = \"en\") }} }}
  OPTIONAL {{ ?item wdt:P495 ?country .
            OPTIONAL {{ ?country rdfs:label ?countryZhcn FILTER (LANG(?countryZhcn) = \"zh-cn\" || LANG(?countryZhcn) = \"zh-hans\") }}
            OPTIONAL {{ ?country rdfs:label ?countryZh FILTER (LANG(?countryZh) = \"zh\") }}
            OPTIONAL {{ ?country rdfs:label ?countryEn FILTER (LANG(?countryEn) = \"en\") }} }}
  OPTIONAL {{ ?zhwikiArticle schema:about ?item ; schema:isPartOf <https://zh.wikipedia.org/> . BIND(STR(?zhwikiArticle) AS ?zhwiki) }}
  OPTIONAL {{ ?enwikiArticle schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . BIND(STR(?enwikiArticle) AS ?enwiki) }}
  OPTIONAL {{ ?item rdfs:label ?zhcnLabel FILTER (LANG(?zhcnLabel) = \"zh-cn\" || LANG(?zhcnLabel) = \"zh-hans\") }}
  OPTIONAL {{ ?item rdfs:label ?zhLabel FILTER (LANG(?zhLabel) = \"zh\") }}
  OPTIONAL {{ ?item rdfs:label ?enLabel FILTER (LANG(?enLabel) = \"en\") }}
}}
"""
    else:
        query = f"""
{prefix}
SELECT ?item ?zhcnLabel ?zhLabel ?enLabel ?year ?genreZhcn ?genreZh ?genreEn ?countryZhcn ?countryZh ?countryEn WHERE {{
  {values}
  ?item wdt:P31/wdt:P279* wd:Q11424 .
  OPTIONAL {{ ?item wdt:P577 ?date . BIND(YEAR(?date) AS ?year) }}
  OPTIONAL {{ ?item wdt:P136 ?genre .
            OPTIONAL {{ ?genre rdfs:label ?genreZhcn FILTER (LANG(?genreZhcn) = \"zh-cn\" || LANG(?genreZhcn) = \"zh-hans\") }}
            OPTIONAL {{ ?genre rdfs:label ?genreZh FILTER (LANG(?genreZh) = \"zh\") }}
            OPTIONAL {{ ?genre rdfs:label ?genreEn FILTER (LANG(?genreEn) = \"en\") }} }}
  OPTIONAL {{ ?item wdt:P495 ?country .
            OPTIONAL {{ ?country rdfs:label ?countryZhcn FILTER (LANG(?countryZhcn) = \"zh-cn\" || LANG(?countryZhcn) = \"zh-hans\") }}
            OPTIONAL {{ ?country rdfs:label ?countryZh FILTER (LANG(?countryZh) = \"zh\") }}
            OPTIONAL {{ ?country rdfs:label ?countryEn FILTER (LANG(?countryEn) = \"en\") }} }}
  OPTIONAL {{ ?item rdfs:label ?zhcnLabel FILTER (LANG(?zhcnLabel) = \"zh-cn\" || LANG(?zhcnLabel) = \"zh-hans\") }}
  OPTIONAL {{ ?item rdfs:label ?zhLabel FILTER (LANG(?zhLabel) = \"zh\") }}
  OPTIONAL {{ ?item rdfs:label ?enLabel FILTER (LANG(?enLabel) = \"en\") }}
}}
"""

    data = await _sparql(client, query)
    rows: List[Dict[str, Any]] = data.get("results", {}).get("bindings", [])

    # 聚合（同一 item 多行：多类型/多国家）
    agg: Dict[str, Dict[str, Any]] = {}
    for b in rows:
        item_uri = _text(b, "item") or ""
        if not item_uri:
            continue
        qid = item_uri.rsplit("/", 1)[-1]
        if qid not in agg:
            # 优先使用简体中文标签，如果没有则回退到通用中文
            title_cn = _text(b, "zhcnLabel") or _text(b, "zhLabel")
            agg[qid] = {
                "qid": qid,
                "title_cn": title_cn,
                "title_en": _text(b, "enLabel"),
                "year": None,
                "poster_url": None,
                "zhwiki": None,
                "enwiki": None,
                "genres_zh": set(),
                "genres_en": set(),
                "countries_zh": set(),
                "countries_en": set(),
            }
        # 更新海报URL（如果当前行有且还没有设置）
        if extended and not agg[qid]["poster_url"]:
            img = _text(b, "image")
            if img:
                # 处理图片URL
                processed_img = _process_image_url(img)
                if processed_img:
                    agg[qid]["poster_url"] = processed_img
        # 更新维基百科链接
        if extended:
            if not agg[qid]["zhwiki"]:
                zhwiki = _text(b, "zhwiki")
                if zhwiki:
                    agg[qid]["zhwiki"] = zhwiki
            if not agg[qid]["enwiki"]:
                enwiki = _text(b, "enwiki")
                if enwiki:
                    agg[qid]["enwiki"] = enwiki
        if _text(b, "year") and agg[qid]["year"] is None:
            try:
                agg[qid]["year"] = int(_text(b, "year") or "")
            except Exception:
                pass
        # 优先使用简体中文，如果没有则回退到通用中文
        gz = _text(b, "genreZhcn") or _text(b, "genreZh")
        ge = _text(b, "genreEn")
        cz = _text(b, "countryZhcn") or _text(b, "countryZh")
        ce = _text(b, "countryEn")
        if gz:
            agg[qid]["genres_zh"].add(gz)
        if ge:
            agg[qid]["genres_en"].add(ge)
        if cz:
            agg[qid]["countries_zh"].add(cz)
        if ce:
            agg[qid]["countries_en"].add(ce)

    results = []
    for qid, v in agg.items():
        # 已经从 Wikidata 获取了简体中文，作为备用仍然应用转换以防有漏网之鱼
        title_cn = _to_simplified(v.get("title_cn")) or ""
        title_en = v.get("title_en") or ""
        year_val = v.get("year")
        
        # 类型和国家数据（应用繁简转换作为备用）
        genres_zh = [_to_simplified(g) for g in (v.get("genres_zh") or []) if g]
        genres_en = list(v.get("genres_en") or [])
        countries_zh = [_to_simplified(c) for c in (v.get("countries_zh") or []) if c]
        countries_en = list(v.get("countries_en") or [])
        
        if extended:
            # 返回扩展格式（为前端使用）
            # 构建 display_title
            left = title_cn or title_en or ""
            right = title_en if title_cn else None
            if left and right and left != right:
                display = f"{left} {right}"
            else:
                display = left or right or ""
            if year_val:
                display = f"{display} ({year_val})" if display else f"({year_val})"
            
            genres = sorted(genres_zh) if genres_zh else sorted(genres_en)
            countries = sorted(countries_zh) if countries_zh else sorted(countries_en)
            
            # 海报URL（如果有），添加宽度参数
            poster = v.get("poster_url")
            if poster and "?" not in poster:
                poster = poster + "?width=700"
            elif poster:
                poster = poster + "&width=700"
            
            wikipedia_links = {}
            if v.get("zhwiki"):
                wikipedia_links["zh"] = v.get("zhwiki")
            if v.get("enwiki"):
                wikipedia_links["en"] = v.get("enwiki")
            
            results.append(
                MovieResultExtended(
                    wikidata_id=qid,
                    title_cn=title_cn if title_cn else None,
                    title_en=title_en if title_en else None,
                    year=year_val,
                    display_title=display,
                    genres=genres,
                    countries=countries,
                    poster_url=poster,
                    wikipedia_links=wikipedia_links
                )
            )
        else:
            # 返回基本格式（douban.py兼容）
            year = year_val or 0
            
            # 构建完整名称：中文 + 英文
            fullname = ""
            if title_cn and title_en and title_cn != title_en:
                fullname = f"{title_cn} {title_en}"
            else:
                fullname = title_cn or title_en

            # 类型和国家转换为字符串（用 / 分隔）
            genre = " / ".join(sorted(genres_zh)) if genres_zh else " / ".join(sorted(genres_en))
            country = " / ".join(sorted(countries_zh)) if countries_zh else " / ".join(sorted(countries_en))

            results.append(
                MovieResult(
                    fullname=fullname,
                    name=title_cn,
                    originalName=title_en,
                    year=year,
                    genre=genre,
                    country=country,
                    alias=""  # Wikidata 暂时不提供又名信息
                )
            )

    return results


async def _fill_posters_from_wikipedia(client: httpx.AsyncClient, items: List[MovieResultExtended], force_update: bool = False) -> None:
    """从 Wikipedia 获取电影海报。

    优先级顺序：
    1. 中文 Wikipedia REST API Summary (中国大陆版本海报)
    2. 中文 Wikipedia pageimages API
    3. 英文 Wikipedia REST API Summary
    4. 英文 Wikipedia pageimages API
    5. 如果都没有，保持原有值
    
    Args:
        force_update: 如果为 True，则替换现有的海报URL
    """
    async def fetch_thumb_rest(lang: str, url: str) -> Optional[str]:
        """使用 REST API 获取图片。"""
        try:
            p = urlparse(url)
            title = p.path.rsplit('/', 1)[-1]
            # 如果是中文，明确使用简体中文域名
            if lang == "zh":
                api = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{title}"
                # 添加 Accept-Language 头指定简体中文
                headers = {"Accept": "application/json", "Accept-Language": "zh-CN,zh-Hans"}
            else:
                api = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
                headers = {"Accept": "application/json"}
            
            r = await client.get(api, headers=headers)
            if r.status_code == 200:
                j = r.json()
                # 优先使用 originalimage，其次 thumbnail
                src = (j.get("originalimage") or {}).get("source") or (j.get("thumbnail") or {}).get("source")
                if src:
                    return src
        except Exception:
            pass
        return None
    async def fetch_thumb_pageimages(lang: str, url: str) -> Optional[str]:
        """使用 pageimages API 获取图片。"""
        try:
            p = urlparse(url)
            title = p.path.rsplit('/', 1)[-1]
            api = f"https://{lang}.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "format": "json",
                "prop": "pageimages",
                "titles": title,
                "piprop": "original",
                "pithumbsize": 700
            }
            # 如果是中文，指定简体中文变体
            if lang == "zh":
                params["variant"] = "zh-cn"
            
            r = await client.get(api, params=params)
            if r.status_code == 200:
                j = r.json()
                pages = j.get("query", {}).get("pages", {})
                for page_id, page_data in pages.items():
                    # 优先使用 original
                    if "original" in page_data:
                        return page_data["original"].get("source")
                    # 其次使用 thumbnail
                    if "thumbnail" in page_data:
                        return page_data["thumbnail"].get("source")
        except Exception:
            pass
        return None

    for it in items:
        # 如果已有海报且不强制更新，跳过
        if it.poster_url and not force_update:
            continue
        
        zh = it.wikipedia_links.get("zh") if it.wikipedia_links else None
        en = it.wikipedia_links.get("en") if it.wikipedia_links else None
        thumb = None
        
        # 优先尝试中文维基（中国大陆版本海报）
        if zh:
            thumb = await fetch_thumb_rest("zh", zh)
            if not thumb:
                thumb = await fetch_thumb_pageimages("zh", zh)
        
        # 如果中文没有，尝试英文
        if not thumb and en:
            thumb = await fetch_thumb_rest("en", en)
            if not thumb:
                thumb = await fetch_thumb_pageimages("en", en)
        
        # 更新海报URL（如果找到了）
        if thumb:
            it.poster_url = thumb


async def search_movies(query: str, limit: int = 5, extended: bool = False) -> List[MovieResult] | List[MovieResultExtended]:
    """综合搜索：简体中文优先，其次英文，合并候选后取前 N 个条目详情。
    
    Args:
        query: 搜索关键词
        limit: 返回结果数量
        extended: 是否返回扩展信息（包括海报、维基百科链接等）
    """
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers={"User-Agent": "CineSeek/0.1 (+https://www.wikidata.org/)"}) as client:
        # 分别按简体中文、英文搜，合并去重
        # 注：Wikidata API 的 language 参数使用 "zh" 可以覆盖所有中文变体
        zh_ids, en_ids = await asyncio.gather(
            _wbsearch(client, query, lang="zh", limit=limit),
            _wbsearch(client, query, lang="en", limit=limit),
        )
        seen = []
        for q in zh_ids + en_ids:
            if q not in seen:
                seen.append(q)
        # 拉取详情
        items = await _fetch_details(client, seen[:limit], extended=extended)
        # 如果是扩展模式，从 Wikipedia 获取海报
        # force_update=True 表示强制更新，优先使用 Wikipedia 的海报
        if extended and items:
            await _fill_posters_from_wikipedia(client, items, force_update=True)
        return items
