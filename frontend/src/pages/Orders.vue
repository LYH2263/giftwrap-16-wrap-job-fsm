<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getJSON, postJSON } from '../api'

const STATUS = { draft: '草稿', quoted: '已报价', wrapping: '包装中', done: '已完成', cancelled: '已取消' }

const items = ref([])
const err = ref('')
const title = ref('')
const busy = ref(false)
const router = useRouter()

onMounted(async () => {
  try {
    items.value = (await getJSON('/api/orders')).items
  } catch (e) {
    err.value = String(e.message || e)
  }
})

async function create() {
  err.value = ''
  busy.value = true
  try {
    const o = await postJSON('/api/orders', { title: title.value.trim() })
    router.push(`/orders/${o.id}`)
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page">
    <h1>工单</h1>
    <p class="lede">报价即固化：quoted 之后用纸与丝带以快照为准，改盒边、改折边都不再回写工单。</p>
    <div class="row">
      <input v-model="title" placeholder="工单标题（可空）" @keyup.enter="create" />
      <button :disabled="busy" @click="create">新建草稿</button>
    </div>
    <p v-if="err" class="bad">{{ err }}</p>
    <p v-else-if="!items.length" class="empty">还没有工单。先建一张草稿，再去详情页挂接用纸档。</p>
    <ul v-else class="item-list">
      <li v-for="o in items" :key="o.id">
        <router-link :to="`/orders/${o.id}`">#{{ o.id }} {{ o.title }}</router-link>
        <span class="meta">
          <span class="pill" :class="`st-${o.status}`">{{ STATUS[o.status] || o.status }}</span>
          挂接 {{ o.run_id ? `#${o.run_id}` : '—' }} · 固化 {{ o.paper_m2 ?? '—' }} m²
        </span>
      </li>
    </ul>
  </div>
</template>
