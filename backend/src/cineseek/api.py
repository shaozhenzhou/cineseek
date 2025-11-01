# -*- coding: utf-8 -*-
"""FastAPI 应用：提供搜索 API。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json

from .models import SearchRequest, MovieResult
from .parser import parse_title
from .providers.wikidata import search_movies

app = FastAPI(title="CineSeek API", version="0.1.0")

# 开发阶段允许跨域（前端默认跑在 5173 端口）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    """健康检查。"""
    return {"ok": True}


@app.post("/api/search", response_model=list[MovieResult])
async def api_search(req: SearchRequest):
    """电影搜索接口：解析标题后到 Wikidata 检索。"""
    name, year = parse_title(req.query)
    # 这里先直接用解析出的 name 搜索；若需要，也可在 providers 中加入年份权重
    results = await search_movies(name, limit=5)
    # 若解析到年份，则将最匹配年份的结果置顶（简单排序）
    if year is not None:
        results.sort(key=lambda r: (r.year is not None, abs((r.year or 0) - year)) if r.year is not None else (False, 999))
    
    # 确保 UTF-8 编码响应
    return JSONResponse(
        content=[result.dict() for result in results],
        headers={"Content-Type": "application/json; charset=utf-8"}
    )
