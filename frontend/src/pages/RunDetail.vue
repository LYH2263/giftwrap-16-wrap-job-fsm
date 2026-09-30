<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'

const STATUS = { draft: '草稿', quoted: '已报价', wrapping: '包装中', done: '已完成', cancelled: '已取消' }

const props = defineProps({ id: String })
const run = ref(null)
const err = ref('')

onMounted(async () => {
  try {
    run.value = await getJSON(`/api/runs/${props.id}`)
  } catch (e) {
    err.value = String(e.message || e)
  }
})
</script>

<template>
  <div class="page">
    <p v-if="err" class="bad">{{ err }}</p>
    <template v-else-if="run">
      <h1>用纸档 #{{ run.id }}</h1>
      <p class="lede">
        <router-link v-if="run.box_id" :to="`/boxes/${run.box_id}`">{{ run.box_name }}</router-link>
        <span class="meta"> · 折边 {{ run.overlap }} · {{ (run.created_at || '').slice(0, 10) }}</span>
      </p>
      <div class="result-board">
        <div class="figure">{{ run.result?.paper_m2 ?? '—' }}<span>m²</span></div>
        <p v-if="run.result?.ribbon" class="stat-line">丝带约 {{ run.result.ribbon.ribbon_m }} m</p>
        <p v-if="run.note" class="meta">备注：{{ run.note }}</p>
      </div>

      <section class="panel">
        <h2>引用工单</h2>
        <p v-if="!run.orders?.length" class="empty">未被工单引用。</p>
        <ul v-else class="item-list">
          <li v-for="o in run.orders" :key="o.id">
            <router-link :to="`/orders/${o.id}`">#{{ o.id }} {{ o.title }}</router-link>
            <span class="pill" :class="`st-${o.status}`">{{ STATUS[o.status] || o.status }}</span>
          </li>
        </ul>
      </section>

      <div class="row" style="margin-top: 1.25rem">
        <router-link class="btn ghost" to="/history">返回用纸档</router-link>
      </div>
    </template>
  </div>
</template>
