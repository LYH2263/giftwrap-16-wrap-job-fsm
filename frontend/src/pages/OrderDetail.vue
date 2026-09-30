<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'

const STATUS = { draft: '草稿', quoted: '已报价', wrapping: '包装中', done: '已完成', cancelled: '已取消' }
const ACTIONS = { quoted: '报价固化', wrapping: '开始包装', done: '完工', cancelled: '取消工单', draft: '退回草稿' }

const props = defineProps({ id: String })
const order = ref(null)
const runs = ref([])
const pick = ref(null)
const err = ref('')
const busy = ref(false)

async function load() {
  err.value = ''
  try {
    order.value = await getJSON(`/api/orders/${props.id}`)
    if (order.value.status === 'draft') {
      runs.value = (await getJSON('/api/runs')).items
      pick.value = order.value.run_id ?? runs.value[0]?.id ?? null
    }
  } catch (e) {
    err.value = String(e.message || e)
  }
}

onMounted(load)

async function attach() {
  if (!pick.value) return
  busy.value = true
  try {
    await postJSON(`/api/orders/${props.id}/attach`, { run_id: pick.value })
    await load()
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

async function go(to) {
  busy.value = true
  try {
    await postJSON(`/api/orders/${props.id}/transition`, { to })
    await load()
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page">
    <p v-if="err" class="bad">{{ err }}</p>
    <template v-if="order">
      <h1>工单 #{{ order.id }} · {{ order.title }}</h1>
      <p class="lede">
        <span class="pill" :class="`st-${order.status}`">{{ STATUS[order.status] || order.status }}</span>
        <span class="meta"> 创建于 {{ (order.created_at || '').slice(0, 10) }}</span>
      </p>

      <section class="panel">
        <h2>挂接用纸档</h2>
        <p v-if="order.run">
          <router-link :to="`/history/${order.run.id}`">#{{ order.run.id }} · {{ order.run.box_name }}</router-link>
          <span class="meta"> · 折边 {{ order.run.overlap }} · {{ (order.run.created_at || '').slice(0, 10) }}</span>
        </p>
        <p v-else class="empty">尚未挂接；报价前必须先挂一条用纸档。</p>
        <div v-if="order.status === 'draft'" class="row">
          <select v-model.number="pick">
            <option v-for="r in runs" :key="r.id" :value="r.id">
              #{{ r.id }} · {{ r.box_name }} · {{ r.result?.paper_m2 ?? '—' }} m²
            </option>
          </select>
          <button :disabled="busy || !pick" @click="attach">{{ order.run_id ? '重新挂接' : '挂接' }}</button>
        </div>
        <p v-else-if="order.status === 'quoted'" class="meta">已报价锁定挂接；如需更换请先「退回草稿」。</p>
      </section>

      <section class="panel">
        <h2>固化用量（快照，只读）</h2>
        <template v-if="order.paper_m2 != null">
          <div class="figure-line">{{ order.paper_m2 }}<span> m² 包装纸</span></div>
          <p class="meta">丝带 {{ order.ribbon_m }} m · 固化于 {{ (order.quoted_at || '').slice(0, 10) }}</p>
        </template>
        <p v-else class="empty">未报价，尚未固化。报价时以挂接用纸档的数值写入快照。</p>
      </section>

      <section v-if="order.live" class="panel">
        <h2>现场重算（仅供参考，不回写工单）</h2>
        <p class="meta">
          按当前盒尺寸与当前折边系数 {{ order.live.overlap }} 现算：
          {{ order.live.paper_m2 }} m² 包装纸 · {{ order.live.ribbon_m }} m 丝带
        </p>
      </section>

      <div class="row">
        <button
          v-for="t in order.allowed_transitions"
          :key="t"
          :class="{ ghost: t === 'draft' || t === 'cancelled' }"
          :disabled="busy"
          @click="go(t)"
        >{{ ACTIONS[t] || t }}</button>
        <router-link class="btn ghost" to="/orders">返回工单列表</router-link>
      </div>
    </template>
  </div>
</template>
