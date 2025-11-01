<template>
  <div class="container">
    <div class="header">
      <div>
        <div class="title">CineSeek</div>
        <div class="subtitle">电影信息搜索 · 基于 Wikidata/Wikipedia · 无需 TMDB</div>
      </div>
    </div>

    <div class="search">
      <input
        class="input"
        v-model.trim="q"
        :placeholder="placeholder"
        @keyup.enter="doSearch"
      />
      <button class="button" :disabled="loading || !q" @click="doSearch">搜索</button>
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
import { ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

const q = ref('')
const loading = ref(false)
const results = ref([])
const error = ref('')

const placeholder = '例如：White.House.Down.2013.1080p.BluRay.DTS-HD.MA.5.1.x264-PublicHD 或 我是传奇(蓝光国英双音轨...).I.Am.Legend.2007...'
const placeholderImg = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1200"><rect width="100%" height="100%" fill="%23151b2e"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%239fb1ff" font-size="24">No Poster</text></svg>'

async function doSearch(){
  error.value = ''
  results.value = []
  const text = q.value.trim()
  if(!text) return
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
  }catch(e){
    error.value = e?.message || '网络错误'
  }finally{
    loading.value = false
  }
}
</script>

<style scoped>
/***** 局部样式补充（通用样式在 assets/style.css） *****/
</style>
