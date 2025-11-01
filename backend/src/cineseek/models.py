# -*- coding: utf-8 -*-
"""数据模型（Pydantic）。

- MovieResult: 返回给前端/CLI 的电影结果结构
- SearchRequest: API 搜索请求结构
"""
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class MovieResult(BaseModel):
    """电影搜索结果。"""
    wikidata_id: Optional[str] = Field(None, description="Wikidata 条目 ID（如 Q123456）")
    title_cn: Optional[str] = Field(None, description="中文标题")
    title_en: Optional[str] = Field(None, description="英文标题")
    year: Optional[int] = Field(None, description="年份")
    display_title: str = Field(..., description="用于显示的组合标题，如：中文 英文 (年份)")
    genres: List[str] = Field(default_factory=list, description="类型标签列表（中文优先）")
    countries: List[str] = Field(default_factory=list, description="制片国家/地区（中文优先）")
    poster_url: Optional[str] = Field(None, description="海报图片 URL（Wikimedia Commons FilePath）")
    wikipedia_links: Dict[str, str] = Field(default_factory=dict, description="维基百科词条链接，键为语言代码（zh、en）")


class SearchRequest(BaseModel):
    """API 搜索请求。"""
    query: str = Field(..., description="用户输入的模糊文件名或片名")
