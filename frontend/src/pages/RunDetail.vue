<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'

const props = defineProps({ id: String })
const run = ref(null)
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
    run.value = await getJSON(`/api/runs/${props.id}`)
  } catch (e) {
    err.value = String(e.message || e)
  }
})
</script>

<template>
  <div class="page" v-if="run">
    <h1>用纸档 #{{ run.id }}</h1>
    <p class="lede">
      {{ run.box_name }} · 折边 ×{{ run.overlap }} · {{ run.created_at?.slice(0, 19).replace('T', ' ') }}
    </p>

    <div class="wo-grid">
      <section class="wo-card">
        <h2>现场存档值</h2>
        <div class="figure">{{ run.result?.paper_m2 ?? '—' }}<span>m²</span></div>
        <p class="stat-line">盒表面积 {{ run.result?.box_surface ?? '—' }} m²</p>
        <p class="stat-line" v-if="run.result?.ribbon">
          丝带 {{ run.result.ribbon.ribbon_m }} m · {{ run.result.ribbon.wrap_style === 'band' ? '单道' : '十字' }}
        </p>
        <p class="meta" v-if="run.note">{{ run.note }}</p>
      </section>

      <section class="wo-card">
        <h2>被工单引用</h2>
        <ul v-if="run.work_orders?.length" class="item-list">
          <li v-for="w in run.work_orders" :key="w.id">
            <span>
              <router-link :to="`/work-orders/${w.id}`">{{ w.code }}</router-link>
            </span>
            <span class="meta">
              <span class="pill wo-status" :class="`st-${w.status}`">{{ STATUS_LABEL[w.status] }}</span>
              固化 {{ w.paper_m2 ?? '—' }} m²
            </span>
          </li>
        </ul>
        <p v-else class="empty">尚未被任何工单引用。可去工单列表据此开单。</p>
        <div class="row" style="margin-top: 0.8rem">
          <router-link class="btn" to="/work-orders">去开工单</router-link>
        </div>
      </section>
    </div>

    <div class="row" style="margin-top: 1.25rem">
      <router-link class="btn ghost" to="/history">返回用纸档</router-link>
    </div>
  </div>
  <div class="page" v-else-if="err">
    <p class="bad">{{ err }}</p>
    <router-link class="btn ghost" to="/history">返回用纸档</router-link>
  </div>
</template>
