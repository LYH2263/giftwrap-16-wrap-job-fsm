import { createRouter, createWebHistory } from 'vue-router'
import Overview from './pages/Overview.vue'
import Boxes from './pages/Boxes.vue'
import BoxDetail from './pages/BoxDetail.vue'
import Papers from './pages/Papers.vue'
import Bench from './pages/Bench.vue'
import Ribbon from './pages/Ribbon.vue'
import Overlap from './pages/Overlap.vue'
import History from './pages/History.vue'
import RunDetail from './pages/RunDetail.vue'
import WorkOrders from './pages/WorkOrders.vue'
import WorkOrderDetail from './pages/WorkOrderDetail.vue'
import Settings from './pages/Settings.vue'
export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Overview },
    { path: '/boxes', component: Boxes },
    { path: '/boxes/:id', component: BoxDetail, props: true },
    { path: '/papers', component: Papers },
    { path: '/bench', component: Bench },
    { path: '/ribbon', component: Ribbon },
    { path: '/overlap', component: Overlap },
    { path: '/history', component: History },
    { path: '/runs/:id', component: RunDetail, props: true },
    { path: '/work-orders', component: WorkOrders },
    { path: '/work-orders/:id', component: WorkOrderDetail, props: true },
    { path: '/settings', component: Settings },
  ],
})
