# CineSeek

一个支持 命令行 + Web API + 精美 Vue 页面 的电影信息搜索工具。

- 数据来源：Wikidata/Wikipedia（不使用 TMDB）
- 后端：Python + FastAPI + Typer（使用 uv 管理依赖）
- 前端：Vite + Vue 3
- 路径：`C:\Users\shaoz\Developer\CineSeek`

## 快速开始
1) 启动后端
```powershell
cd backend
uv sync
uv run uvicorn cineseek.api:app --reload --host 127.0.0.1 --port 8000
```
2) 启动前端
```powershell
cd ../frontend
npm i
npm run dev
```
3) 命令行搜索示例
```powershell
cd backend
uv run cineseek search "White.House.Down.2013.1080p.BluRay.DTS-HD.MA.5.1.x264-PublicHD"
uv run cineseek search "我是传奇(蓝光国英双音轨...).I.Am.Legend.2007..."
```

## API
- POST `http://127.0.0.1:8000/api/search`
  - body: `{ "query": "模糊文件名或片名" }`

## 说明
- 解析文件名采用 guessit + 启发式；标题优先中文，其次英文，并附上年份
- 返回字段：标题、类型、国家/地区、海报（Commons）、中/英维基百科链接

## 许可
MIT