# -*- coding: utf-8 -*-
"""FastAPI 应用：提供搜索 API。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json

from .models import SearchRequest, MovieResult, MovieResultExtended
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


@app.get("/")
@app.get("/index")
def index():
    """首页路由处理函数"""
    return "<html><body>Hello, This is CineSeek!</body></html>"


@app.get("/api/health")
def health() -> dict:
    """健康检查。"""
    return {"ok": True}


@app.get("/search")
async def search(keyword: str):
    """电影搜索接口：解析标题后到 Wikidata 检索。兼容douban.py的/search路由格式。"""
    name, year = parse_title(keyword)
    # 这里先直接用解析出的 name 搜索
    results = await search_movies(name, limit=10, extended=False)  # 增加limit以便过滤后有足够结果
    
    # 若解析到年份，则过滤出年份匹配的结果（允许±1年误差）
    if year is not None:
        # 过滤出年份匹配的结果
        filtered = [r for r in results if r.year and abs(r.year - year) <= 1]
        if filtered:
            results = filtered
        # 对过滤后的结果按年份匹配度排序
        results.sort(key=lambda r: abs((r.year or 0) - year) if r.year else 999)
    
    # 返回第一个结果，如果没有结果返回空字符串（兼容douban.py）
    if not results:
        return ""
    
    # 确保 UTF-8 编码响应
    return JSONResponse(
        content=results[0].dict(),
        headers={"Content-Type": "application/json; charset=utf-8"}
    )


@app.post("/api/search", response_model=list[MovieResultExtended])
async def api_search(req: SearchRequest):
    """前端专用电影搜索接口：返回扩展信息（包括海报、维基百科链接等）。"""
    name, year = parse_title(req.query)
    # 使用extended=True获取完整信息
    results = await search_movies(name, limit=10, extended=True)  # 增加limit以便过滤后有足够结果
    
    # 若解析到年份，则过滤出年份匹配的结果（允许±1年误差）
    if year is not None:
        # 过滤出年份匹配的结果
        filtered = [r for r in results if r.year and abs(r.year - year) <= 1]
        if filtered:
            results = filtered
        # 对过滤后的结果按年份匹配度排序
        results.sort(key=lambda r: abs((r.year or 0) - year) if r.year else 999)
    
    # 限制返回结果数量为5个
    results = results[:5]
    
    # 确保 UTF-8 编码响应
    return JSONResponse(
        content=[result.dict() for result in results],
        headers={"Content-Type": "application/json; charset=utf-8"}
    )
