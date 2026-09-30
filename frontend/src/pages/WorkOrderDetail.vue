<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getJSON, postJSON, putJSON } from '../api'

const props = defineProps({ id: String })
const router = useRouter()

const wo = ref(null)
const runs = ref([])
const err = ref('')
const busy = ref(false)

const STATUS_LABEL = {
  draft: '草稿',
  quoted: '已报价',
  wrapping: '包装中',
  done: '已完成',
  cancelled: '已取消',
}

// 各状态下可用的服务端动作
const ACTIONS = {
  draft: [{ action: 'quote', label: '报价并固化', kind: 'ribbon' }, { action: 'cancel', label: '取消工单', kind: 'ghost' }],
  quoted: [
    { action: 'start', label: '开始包装', kind: '' },
    { action: 'revert', label: '退回草稿', kind: 'ghost' },
    { action: 'cancel', label: '取消工单', kind: 'ghost' },
  ],
  wrapping: [{ action: 'complete', label: '完成包装', kind: 'ribbon' }],
  done: [],
  cancelled: [],
}

const availableRuns = computed(() => runs.value.filter((r) => r.id !== wo.value?.run_id))

async function load() {
  err.value = ''
  try {
    wo.value = await getJSON(`/api/work-orders/${props.id}`)
    const rs = await getJSON('/api/runs')
    runs.value = rs.items
  } catch (e) {
    err.value = String(e.message || e)
  }
}

onMounted(load)

async function act(action) {
  busy.value = true
  err.value = ''
  try {
    wo.value = await postJSON(`/api/work-orders/${props.id}/transition`, { action })
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

async function attach(rid) {
  busy.value = true
  err.value = ''
  try {
    wo.value = await putJSON(`/api/work-orders/${props.id}/run`, { run_id: rid })
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page" v-if="wo">
    <h1>{{ wo.code }}</h1>
    <p class="lede">
      <span class="pill wo-status" :class="`st-${wo.status}`">{{ STATUS_LABEL[wo.status] }}</span>
      创建于 {{ wo.created_at?.slice(0, 19).replace('T', ' ') }}
    </p>
    <p v-if="err" class="bad">{{ err }}</p>

    <div class="wo-grid">
      <section class="wo-card snapshot" :class="{ frozen: wo.paper_m2 != null }">
        <h2>报价快照（只读）</h2>
        <template v-if="wo.paper_m2 != null">
          <div class="figure">{{ wo.paper_m2 }}<span>m² 用纸</span></div>
          <p class="stat-line">丝带 {{ wo.ribbon_m ?? '—' }} m · {{ wo.wrap_style === 'band' ? '单道' : '十字' }}</p>
          <p class="stat-line">
            {{ wo.box_name }} · 折边 ×{{ wo.overlap }}
            <span v-if="wo.snapshot_drifted" class="pill warn">与现场现值不一致</span>
          </p>
          <p class="meta">固化于 {{ wo.quoted_at?.slice(0, 19).replace('T', ' ') }}，此后改盒边或折边不覆盖此值。</p>
        </template>
        <p v-else class="empty">尚未报价。报价时把挂接用纸档的纸量与丝带固化到此。</p>
      </section>

      <section class="wo-card">
        <h2>挂接用纸档</h2>
        <template v-if="wo.run">
          <p>
            <router-link :to="`/runs/${wo.run.id}`">#{{ wo.run.id }} · {{ wo.run.box_name }}</router-link>
          </p>
          <p class="stat-line">
            现场现值 {{ wo.run.paper_m2 ?? '—' }} m² · 丝带 {{ wo.run.ribbon_m ?? '—' }} m
          </p>
        </template>
        <p v-else class="empty">未挂接，草稿状态下请先选一条用纸档。</p>

        <div v-if="wo.status === 'draft'" class="row">
          <select :value="wo.run_id ?? ''" @change="(e) => e.target.value && attach(Number(e.target.value))" :disabled="busy">
            <option v-if="!wo.run" value="" disabled>选择用纸档…</option>
            <option v-if="wo.run" :value="wo.run.id">#{{ wo.run.id }}（当前）</option>
            <option v-for="r in availableRuns" :key="r.id" :value="r.id">
              #{{ r.id }} · {{ r.box_name }} · {{ r.result?.paper_m2 ?? '—' }} m²
            </option>
          </select>
        </div>
        <p v-else-if="wo.status !== 'draft'" class="meta">
          已离开草稿，挂接锁定；如需更换，请先退回草稿。
        </p>
      </section>
    </div>

    <div class="row" style="margin-top: 1.4rem">
      <button
        v-for="a in ACTIONS[wo.status]"
        :key="a.action"
        :class="a.kind"
        :disabled="busy || (a.action === 'quote' && !wo.run)"
        @click="act(a.action)"
      >
        {{ a.label }}
      </button>
      <router-link class="btn ghost" to="/work-orders">返回工单列表</router-link>
    </div>
  </div>
  <div class="page" v-else-if="err">
    <p class="bad">{{ err }}</p>
    <router-link class="btn ghost" to="/work-orders">返回工单列表</router-link>
  </div>
</template>
