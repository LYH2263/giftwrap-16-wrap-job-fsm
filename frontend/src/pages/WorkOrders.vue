<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getJSON, postJSON } from '../api'

const router = useRouter()
const items = ref([])
const runs = ref([])
const err = ref('')
const creating = ref(false)
const selectedRun = ref(null)

const STATUS_LABEL = {
  draft: '草稿',
  quoted: '已报价',
  wrapping: '包装中',
  done: '已完成',
  cancelled: '已取消',
}

async function load() {
  err.value = ''
  try {
    const [wo, rs] = await Promise.all([getJSON('/api/work-orders'), getJSON('/api/runs')])
    items.value = wo.items
    runs.value = rs.items
    if (!selectedRun.value && runs.value.length) selectedRun.value = runs.value[0].id
  } catch (e) {
    err.value = String(e.message || e)
  }
}

onMounted(load)

async function create() {
  if (!selectedRun.value) return
  creating.value = true
  err.value = ''
  try {
    const wo = await postJSON('/api/work-orders', { run_id: selectedRun.value })
    router.push(`/work-orders/${wo.id}`)
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="page">
    <h1>包装工单</h1>
    <p class="lede">挂接一条用纸档即可开单；报价后纸量与丝带长度固化为快照，不再随盒边或折边变动。</p>

    <div class="row">
      <select v-model.number="selectedRun" :disabled="!runs.length">
        <option v-for="r in runs" :key="r.id" :value="r.id">
          #{{ r.id }} · {{ r.box_name }} · {{ r.result?.paper_m2 ?? '—' }} m²
        </option>
      </select>
      <button class="ribbon" :disabled="creating || !runs.length" @click="create">
        新建草稿工单
      </button>
    </div>
    <p v-if="!runs.length" class="empty">还没有用纸档，先去「算纸」写入一条。</p>
    <p v-if="err" class="bad">{{ err }}</p>

    <ul v-if="items.length" class="item-list">
      <li v-for="w in items" :key="w.id">
        <span>
          <router-link :to="`/work-orders/${w.id}`">{{ w.code }}</router-link>
          <span class="meta">
            用纸档 #{{ w.run_id ?? '—' }}<template v-if="w.run"> · {{ w.run.box_name }}</template>
          </span>
        </span>
        <span class="meta">
          <span class="pill wo-status" :class="`st-${w.status}`">{{ STATUS_LABEL[w.status] }}</span>
          固化 {{ w.paper_m2 ?? '—' }} m²
        </span>
      </li>
    </ul>
    <p v-else-if="runs.length" class="empty">还没有工单。</p>
  </div>
</template>
