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

from ..models import MovieResult

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


def _poster_url_from_binding(b: Dict[str, Any]) -> Optional[str]:
    # SPARQL 中 P18 会返回 Special:FilePath 直链，可直接加缩放参数
    url = b.get("image", {}).get("value")
    if url:
        # 控制宽度，避免前端加载过大
        if "?" in url:
            return url + "&width=700"
        return url + "?width=700"
    return None


def _text(b: Dict[str, Any], key: str) -> Optional[str]:
    v = b.get(key, {}).get("value")
    return v if isinstance(v, str) and v.strip() else None


async def _fetch_details(client: httpx.AsyncClient, qids: List[str]) -> List[MovieResult]:
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

    query = f"""
{prefix}
SELECT ?item ?zhLabel ?enLabel ?year ?image ?zhwiki ?enwiki ?genreZh ?genreEn ?countryZh ?countryEn WHERE {{
  {values}
  ?item wdt:P31/wdt:P279* wd:Q11424 .
  OPTIONAL {{ ?item wdt:P577 ?date . BIND(YEAR(?date) AS ?year) }}
  OPTIONAL {{ ?item wdt:P18 ?imageFile .
             BIND(CONCAT(\"https://commons.wikimedia.org/wiki/Special:FilePath/\", ENCODE_FOR_URI(STR(?imageFile))) AS ?image) }}
  OPTIONAL {{ ?item wdt:P136 ?genre .
            OPTIONAL {{ ?genre rdfs:label ?genreZh FILTER (LANG(?genreZh) = \"zh\") }}
            OPTIONAL {{ ?genre rdfs:label ?genreEn FILTER (LANG(?genreEn) = \"en\") }} }}
  OPTIONAL {{ ?item wdt:P495 ?country .
            OPTIONAL {{ ?country rdfs:label ?countryZh FILTER (LANG(?countryZh) = \"zh\") }}
            OPTIONAL {{ ?country rdfs:label ?countryEn FILTER (LANG(?countryEn) = \"en\") }} }}
  OPTIONAL {{ ?zhwikiArticle schema:about ?item ; schema:isPartOf <https://zh.wikipedia.org/> . BIND(STR(?zhwikiArticle) AS ?zhwiki) }}
  OPTIONAL {{ ?enwikiArticle schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . BIND(STR(?enwikiArticle) AS ?enwiki) }}
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
            agg[qid] = {
                "qid": qid,
                "title_cn": _text(b, "zhLabel"),
                "title_en": _text(b, "enLabel"),
                "year": None,
                "poster_url": _poster_url_from_binding(b),
                "zhwiki": _text(b, "zhwiki"),
                "enwiki": _text(b, "enwiki"),
                "genres_zh": set(),
                "genres_en": set(),
                "countries_zh": set(),
                "countries_en": set(),
            }
        if _text(b, "year") and agg[qid]["year"] is None:
            try:
                agg[qid]["year"] = int(_text(b, "year") or "")
            except Exception:
                pass
        gz = _text(b, "genreZh")
        ge = _text(b, "genreEn")
        cz = _text(b, "countryZh")
        ce = _text(b, "countryEn")
        if gz:
            agg[qid]["genres_zh"].add(gz)
        if ge:
            agg[qid]["genres_en"].add(ge)
        if cz:
            agg[qid]["countries_zh"].add(cz)
        if ce:
            agg[qid]["countries_en"].add(ce)

    results: List[MovieResult] = []
    for qid, v in agg.items():
        title_cn = v.get("title_cn")
        title_en = v.get("title_en")
        year = v.get("year")
        # 中文优先回退：没有中文时用英文
        left = title_cn or title_en or ""
        right = title_en if title_cn else None  # 若已有中文，再同时展示英文
        if left and right and left != right:
            display = f"{left} {right}"
        else:
            display = left or right or ""
        if year:
            display = f"{display} ({year})" if display else f"({year})"

        genres = list(v.get("genres_zh") or []) or list(v.get("genres_en") or [])
        countries = list(v.get("countries_zh") or []) or list(v.get("countries_en") or [])

        results.append(
            MovieResult(
                wikidata_id=qid,
                title_cn=title_cn,
                title_en=title_en,
                year=year,
                display_title=display,
                genres=sorted(genres),
                countries=sorted(countries),
                poster_url=v.get("poster_url"),
                wikipedia_links={k: v for k, v in {"zh": v.get("zhwiki"), "en": v.get("enwiki")}.items() if v},
            )
        )

    return results


async def _fill_posters_from_wikipedia(client: httpx.AsyncClient, items: List[MovieResult]) -> None:
    """对缺少 poster 的条目，尝试用 Wikipedia REST Summary 的缩略图作为备选。

    - 优先 zh.wikipedia.org，其次 en.wikipedia.org
    - REST: https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}
    - 字段：thumbnail.source 或 originalimage.source
    """
    async def fetch_thumb(lang: str, url: str) -> Optional[str]:
        try:
            p = urlparse(url)
            title = p.path.rsplit('/', 1)[-1]
            api = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
            r = await client.get(api, headers={"Accept": "application/json"})
            if r.status_code == 200:
                j = r.json()
                src = (j.get("originalimage") or {}).get("source") or (j.get("thumbnail") or {}).get("source")
                return src
        except Exception:
            return None
        return None

    for it in items:
        if it.poster_url:
            continue
        zh = it.wikipedia_links.get("zh") if it.wikipedia_links else None
        en = it.wikipedia_links.get("en") if it.wikipedia_links else None
        thumb = None
        if zh:
            thumb = await fetch_thumb("zh", zh)
        if not thumb and en:
            thumb = await fetch_thumb("en", en)
        if thumb:
            it.poster_url = thumb


async def search_movies(query: str, limit: int = 5) -> List[MovieResult]:
    """综合搜索：中文优先，其次英文，合并候选后取前 N 个条目详情。"""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers={"User-Agent": "CineSeek/0.1 (+https://www.wikidata.org/)"}) as client:
        # 分别按中文、英文搜，合并去重
        zh_ids, en_ids = await asyncio.gather(
            _wbsearch(client, query, lang="zh", limit=limit),
            _wbsearch(client, query, lang="en", limit=limit),
        )
        seen = []
        for q in zh_ids + en_ids:
            if q not in seen:
                seen.append(q)
        # 拉取详情
        items = await _fetch_details(client, seen[:limit])
        # 补充 Wikipedia 海报
        await _fill_posters_from_wikipedia(client, items)
        return items
