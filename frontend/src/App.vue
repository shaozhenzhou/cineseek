<template>
  <div class="container">
    <div class="header">
      <div>
        <div class="title">CineSeek</div>
        <div class="subtitle">电影信息搜索 · 基于 Wikidata/Wikipedia · 无需 TMDB</div>
      </div>
    </div>

    <div class="search" style="position: relative;">
      <input
        class="input"
        v-model.trim="q"
        :placeholder="placeholder"
        @keyup.enter="doSearch"
        @focus="showHistory = true"
      />
      <button class="button" :disabled="loading || !q" @click="doSearch">搜索</button>
      
      <!-- 历史搜索记录 -->
      <div v-if="showHistory && searchHistory.length > 0" class="history-panel">
      <div class="history-header">
        <span>搜索历史</span>
        <button class="clear-btn" @click="clearHistory">清除</button>
      </div>
      <div class="history-list">
        <div 
          v-for="(item, index) in searchHistory" 
          :key="index"
          class="history-item"
          @click="selectHistory(item)"
        >
          <span>{{ item }}</span>
        </div>
      </div>
      </div>
    </div>

    <div v-if="error" style="margin-top:12px;color:#ff9a9a">{{ error }}</div>

    <div class="grid" v-if="results.length">
      <div class="card" v-for="(m,i) in results" :key="m.wikidata_id || i">
        <img class="poster" :src="m.poster_url || placeholderImg" :alt="m.display_title" loading="lazy" />
        <div class="card-body">
          <div class="card-title">{{ m.display_title }}</div>
          <div style="margin-bottom:8px">
            <span v-for="g in m.genres" :key="g" class="badge">{{ g }}</span>
          </div>
          <div style="margin-bottom:8px">
            <span v-for="c in m.countries" :key="c" class="badge">{{ c }}</span>
          </div>
          <div style="font-size:12px;color:#9fb1ff">
            <a v-if="m.wikipedia_links?.zh" :href="m.wikipedia_links.zh" target="_blank" rel="noreferrer">中文维基</a>
            <span v-if="m.wikipedia_links?.zh && m.wikipedia_links?.en"> · </span>
            <a v-if="m.wikipedia_links?.en" :href="m.wikipedia_links.en" target="_blank" rel="noreferrer">英文维基</a>
          </div>
        </div>
      </div>
    </div>

    <div class="footer">© 2025 CineSeek</div>
  </div>
</template>

<script setup>
// 前端使用最新版 Vue 3，直接通过 fetch 请求后端 API
import { ref, onMounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

const q = ref('')
const loading = ref(false)
const results = ref([])
const error = ref('')
const showHistory = ref(false)
const searchHistory = ref([])

const HISTORY_KEY = 'cineseek_search_history'
const MAX_HISTORY = 10 // 最多保存10条历史记录

const placeholder = '例如：White.House.Down.2013.1080p.BluRay.DTS-HD.MA.5.1.x264-PublicHD 或 我是传奇(蓝光国英双音轨...).I.Am.Legend.2007...'
const placeholderImg = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1200"><rect width="100%" height="100%" fill="%23151b2e"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%239fb1ff" font-size="24">No Poster</text></svg>'

// 从 localStorage 加载历史记录
function loadHistory() {
  try {
    const saved = localStorage.getItem(HISTORY_KEY)
    if (saved) {
      searchHistory.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('加载历史记录失败', e)
  }
}

// 保存历史记录到 localStorage
function saveHistory() {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(searchHistory.value))
  } catch (e) {
    console.error('保存历史记录失败', e)
  }
}

// 添加搜索记录（不重复）
function addToHistory(query) {
  const trimmed = query.trim()
  if (!trimmed) return
  
  // 移除已存在的相同记录
  const index = searchHistory.value.indexOf(trimmed)
  if (index > -1) {
    searchHistory.value.splice(index, 1)
  }
  
  // 添加到开头
  searchHistory.value.unshift(trimmed)
  
  // 限制最大数量
  if (searchHistory.value.length > MAX_HISTORY) {
    searchHistory.value = searchHistory.value.slice(0, MAX_HISTORY)
  }
  
  saveHistory()
}

// 清除所有历史记录
function clearHistory() {
  searchHistory.value = []
  saveHistory()
  showHistory.value = false
}

// 选择历史记录
function selectHistory(item) {
  q.value = item
  showHistory.value = false
  doSearch()
}

async function doSearch(){
  error.value = ''
  results.value = []
  const text = q.value.trim()
  if(!text) return
  
  showHistory.value = false
  loading.value = true
  
  try{
    const r = await fetch(`${API_BASE}/api/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text }),
    })
    if(!r.ok){
      throw new Error(`服务错误：${r.status}`)
    }
    const data = await r.json()
    results.value = Array.isArray(data) ? data : []
    
    // 搜索成功后添加到历史记录
    if (results.value.length > 0) {
      addToHistory(text)
    }
  }catch(e){
    error.value = e?.message || '网络错误'
  }finally{
    loading.value = false
  }
}

// 点击外部关闭历史面板
function handleClickOutside(event) {
  const historyPanel = document.querySelector('.history-panel')
  const searchInput = document.querySelector('.input')
  if (historyPanel && !historyPanel.contains(event.target) && !searchInput.contains(event.target)) {
    showHistory.value = false
  }
}

// 组件挂载时加载历史记录
onMounted(() => {
  loadHistory()
  document.addEventListener('click', handleClickOutside)
})

</script>

<style scoped>
/***** 局部样式补充（通用样式在 assets/style.css） *****/

.history-panel {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 8px;
  background: #1a2332;
  border: 1px solid #2d3748;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  z-index: 1000;
  max-height: 400px;
  overflow-y: auto;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #2d3748;
  color: #9fb1ff;
  font-size: 14px;
  font-weight: 500;
}

.clear-btn {
  background: transparent;
  border: 1px solid #4a5568;
  color: #9fb1ff;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.clear-btn:hover {
  background: #2d3748;
  border-color: #5a6b82;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  padding: 10px 12px;
  background: #151b2e;
  border: 1px solid #2d3748;
  border-radius: 6px;
  color: #cbd5e0;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}

.history-item:hover {
  background: #1f2937;
  border-color: #5a6b82;
  color: #9fb1ff;
  transform: translateX(4px);
}
</style>
