<template>
  <div class="card">
    <div class="wp-head">
      <h3 class="card-title"><span class="card-ico">🎯</span> 错题知识点</h3>
      <div class="wp-tabs">
        <button
          v-for="t in tabs"
          :key="t.key"
          class="wp-tab"
          :class="{ active: dimension === t.key }"
          @click="switchDim(t.key)"
        >{{ t.name }}</button>
      </div>
    </div>

    <p class="wp-hint">按错题数量排序，最多 10 项 · 点击柱子查看错题集</p>

    <EChart v-if="items.length" :option="barOption" height="260px" @chart-click="onClick" />
    <p v-else class="wp-empty">{{ loading ? '加载中…' : '暂无错题记录，继续保持！' }}</p>
  </div>
</template>

<script setup>
/**
 * WrongPointStatsCard.vue —— 「我的」页 错题知识点卡片
 *
 * 数据源：GET /api/wrong-questions/point-stats?dimension=subcategory|point&limit=10
 * （P2 新增）。两个维度由用户切换，均为只读聚合：
 *   subcategory —— 按子科目（题干文本列折成的一维）统计错题数/错误率；
 *   point       —— 按知识点（knowledge_point，level 不限）统计。
 * 点击柱子跳错题集页面，让数字可直接落到可操作的列表上。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import EChart from '@/components/charts/EChart.vue'

const router = useRouter()
const tabs = [
  { key: 'subcategory', name: '子科目' },
  { key: 'point', name: '知识点' }
]
const dimension = ref('subcategory')
const items = ref([])
const loading = ref(true)

function prettyName(name) {
  const s = String(name || '').replace(/^行测·|^申论·|^公专·/, '')
  return s.length > 10 ? s.slice(0, 10) + '…' : s
}

const barOption = computed(() => {
  // ECharts 的类目轴自下而上排列，倒序后最大值落在顶部
  const list = items.value.slice().reverse()
  return {
    grid: { left: 8, right: 46, top: 8, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const p = params && params[0]
        if (!p) return ''
        const it = list[p.dataIndex] || {}
        return `${it.name}<br/>错题 ${it.wrong_count} 题 · 作答 ${it.error_count} 次<br/>该范围错误率 ${it.wrong_rate}%`
      }
    },
    xAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, color: '#999' },
      splitLine: { lineStyle: { color: '#f1f2f4' } }
    },
    yAxis: {
      type: 'category',
      data: list.map((it) => prettyName(it.name)),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { fontSize: 11, color: '#555' }
    },
    series: [
      {
        type: 'bar',
        barMaxWidth: 16,
        data: list.map((it) => it.wrong_count),
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: (p) => (p.value >= Math.max(1, list[0] && list[0].wrong_count) ? '#C91F37' : '#e8737f')
        },
        label: {
          show: true,
          position: 'right',
          fontSize: 10,
          color: '#8a8f9c',
          formatter: (p) => `${list[p.dataIndex].wrong_rate}%`
        }
      }
    ]
  }
})

async function load() {
  loading.value = true
  try {
    const auth = (window).__VTJ_AUTH__
    if (auth && auth.apiFetch) {
      const res = await auth.apiFetch(
        `/api/wrong-questions/point-stats?dimension=${dimension.value}&limit=10`
      )
      const data = await res.json()
      items.value = Array.isArray(data.items) ? data.items : []
    }
  } catch (e) {
    console.warn('[错题知识点] 加载失败', e)
    items.value = []
  } finally {
    loading.value = false
  }
}

function switchDim(key) {
  if (dimension.value === key) return
  dimension.value = key
  items.value = []
  load()
}

function onClick() {
  router.push('/page/wrong_questions')
}

onMounted(load)
</script>

<style scoped>
.wp-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.card-title { display: flex; align-items: center; gap: 6px; margin: 0; }
.card-ico { font-size: 16px; }
.wp-tabs { display: flex; gap: 6px; }
.wp-tab {
  padding: 4px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 14px;
  background: #fff;
  color: #606266;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.wp-tab.active { border-color: #1A365D; background: #1A365D; color: #fff; }
.wp-hint { margin: 6px 0 0; font-size: 12px; color: #a5a9b4; }
.wp-empty { margin: 0; padding: 72px 0; text-align: center; font-size: 13px; color: #a5a9b4; }
</style>
