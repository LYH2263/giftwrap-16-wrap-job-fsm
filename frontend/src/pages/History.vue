<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'

const items = ref([])
const err = ref('')

const STATUS_LABEL = {
  draft: '草稿',
  quoted: '已报价',
  wrapping: '包装中',
  done: '已完成',
  cancelled: '已取消',
}

onMounted(async () => {
  try {
    items.value = (await getJSON('/api/runs')).items
  } catch (e) {
    err.value = String(e.message || e)
  }
})
</script>

<template>
  <div class="page">
    <h1>用纸档</h1>
    <p class="lede">算纸页「写入用纸档」后的落库结果，按次保留盒名与面积；被工单引用时会标出。</p>
    <p v-if="err" class="bad">{{ err }}</p>
    <p v-else-if="!items.length" class="empty">还没有写入过。先去算纸试一单。</p>
    <ul v-else class="item-list">
      <li v-for="r in items" :key="r.id">
        <span>
          <router-link :to="`/runs/${r.id}`">#{{ r.id }} · {{ r.box_name }}</router-link>
          <span v-if="r.work_orders?.length" class="meta">
            <span
              v-for="w in r.work_orders"
              :key="w.id"
              class="pill wo-status"
              :class="`st-${w.status}`"
              style="margin-left: 0.4rem"
            >
              <router-link :to="`/work-orders/${w.id}`" class="wo-ref">{{ w.code }} · {{ STATUS_LABEL[w.status] }}</router-link>
            </span>
          </span>
          <span v-else class="meta" style="margin-left: 0.5rem">未被引用</span>
        </span>
        <span class="meta">{{ r.result?.paper_m2 ?? '—' }} m²</span>
      </li>
    </ul>
  </div>
</template>
