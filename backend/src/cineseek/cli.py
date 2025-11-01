# -*- coding: utf-8 -*-
"""命令行入口（Typer）。"""
from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .parser import parse_title
from .providers.wikidata import search_movies

app = typer.Typer(help="CineSeek：命令行电影搜索工具（数据源：Wikidata/Wikipedia）")
console = Console()


@app.command("search")
def cli_search(query: str = typer.Argument(..., help="模糊文件名或片名"), limit: int = typer.Option(5, help="返回条目数量")):
    """搜索电影，并以表格形式输出。"""
    name, year = parse_title(query)

    async def _run():
        results = await search_movies(name, limit=limit)
        # 年份简单排序靠前
        if year is not None:
            results.sort(key=lambda r: (r.year is not None, abs((r.year or 0) - year)) if r.year is not None else (False, 999))
        return results

    results = asyncio.run(_run())

    table = Table(title=f"CineSeek 搜索：{name} ({year or '?'})")
    table.add_column("标题", style="bold")
    table.add_column("类型")
    table.add_column("国家/地区")
    table.add_column("年份", justify="right")
    for r in results:
        table.add_row(r.display_title, " / ".join(r.genres), " / ".join(r.countries), str(r.year or ""))
    console.print(table)


if __name__ == "__main__":
    app()
