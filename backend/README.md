# CineSeek（电影信息搜索）

> 使用 Python(uv) + FastAPI 提供 Web API，Typer 提供命令行；前端使用最新 Vue 构建精美搜索页面。信息来源为 Wikidata/Wikipedia（无需 TMDB）。

## 功能
- 输入模糊电影文件名，解析出片名与年份等关键信息
- 到 Wikidata/Wikipedia 搜索并返回：
  - 电影标题（中文 + 英文 + 年份）
  - 类型（多标签）
  - 制片国家/地区
  - 海报图片（优先使用 P18 图片）
- 三种使用方式：CLI、Web API、Vue 前端页面

## 运行环境
- 已安装 Python 与 uv（本项目通过 `pyproject.toml` 管理依赖）

## 后端快速开始
```powershell
# 切换到后端目录
cd backend

# 安装依赖（创建隔离环境并安装）
uv sync

# 启动 API（默认 http://127.0.0.1:8000 ）
uv run uvicorn cineseek.api:app --reload

# 命令行搜索（两种任选其一）
uv run cineseek search "Fight Club (1999)(FHD)"
# 或
uv run python -m cineseek.cli search "Fight Club (1999)(FHD)"
```

## API
- POST `/api/search`
  - 请求体：`{ "query": "模糊文件名或片名" }`
  - 返回：电影结果数组（含标题、年份、类型、国家、海报等）

## 前端开发（Vue）
```powershell
cd ../frontend
npm i
npm run dev
```
默认前端开发服运行在 `http://127.0.0.1:5173`，会请求后端 `http://127.0.0.1:8000` 的 API（可在 `.env.development` 中修改）。

## 说明
- 数据源使用 Wikidata/Wikipedia 开放 API，尽量选择“电影(Instance of: Film)”条目
- 海报优先使用 Wikidata 的 `P18` 图片（Commons 链接），若未找到则为空
- 标题优先中文标签，其次英文标签；显示格式如：`一战再战 One Battle After Another (2025)`
- 解析片名优先使用 `guessit`，若不可用则使用内置正则/启发式规则

## 许可
MIT
