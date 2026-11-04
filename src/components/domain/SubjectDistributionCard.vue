<template>
  <div class="card">
    <h3 class="card-title"><span class="card-ico">📊</span> 学习分布</h3>

    <div class="dist-row">
      <div class="dist-box">
        <p class="dist-label">科目题量占比</p>
        <EChart v-if="subjectItems.length" :option="pieOption" height="210px" />
        <p v-else class="dist-empty">{{ loading ? '加载中…' : '暂无做题数据' }}</p>
      </div>

      <div class="dist-box">
        <p class="dist-label">对错比例</p>
        <EChart v-if="totalCount > 0" :option="donutOption" height="210px" />
        <p v-else class="dist-empty">{{ loading ? '加载中…' : '暂无做题数据' }}</p>
      </div>

      <div class="dist-side">
        <div class="dist-stat">
          <span class="dist-num">{{ totalCount }}</span>
          <span class="dist-cap">累计作答</span>
        </div>
        <div class="dist-stat">
          <span class="dist-num ok">{{ correctCount }}</span>
          <span class="dist-cap">答对</span>
        </div>
        <div class="dist-stat">
          <span class="dist-num bad">{{ wrongCount }}</span>
          <span class="dist-cap">答错</span>
        </div>
        <div class="dist-stat">
          <span class="dist-num">{{ accuracy }}%</span>
          <span class="dist-cap">正确率</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * SubjectDistributionCard.vue —— 「我的」页 学习分布卡片
 *
 * 数据源：GET /api/stats/subject-distribution（P2 新增，口径同 /api/practice/unified-stats：
 * practice_record 全量 + exam_answer_detail，已排除智能组卷双计）。
 * 左右两图：①各科目作答量占比（饼）②总对/错比例（环）。
 * 纯只读展示，无任何写路径。
 */
import { computed, onMounted, ref } from 'vue'
import EChart from '@/components/charts/EChart.vue'

const items = ref([])
const totalCount = ref(0)
const correctCount = ref(0)
const wrongCount = ref(0)
const accuracy = ref(0)
const loading = ref(true)

const subjectItems = computed(() => items.value.filter((it) => Number(it.total) > 0))

const pieOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (p) => `${p.name}<br/>${p.value} 题 · ${p.percent}%`
  },
  legend: { bottom: 0, itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 11, color: '#666' } },
  series: [
    {
      type: 'pie',
      radius: ['0%', '62%'],
      center: ['50%', '44%'],
      data: subjectItems.value.map((it) => ({ name: it.subject_name, value: it.total })),
      label: { show: false },
      itemStyle: { borderColor: '#fff', borderWidth: 2 }
    }
  ]
}))

const donutOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (p) => `${p.name}<br/>${p.value} 题 · ${p.percent}%`
  },
  legend: { bottom: 0, itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 11, color: '#666' } },
  series: [
    {
      type: 'pie',
      radius: ['46%', '66%'],
      center: ['50%', '44%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
      label: { show: true, position: 'center', formatter: `${accuracy.value}%`, fontSize: 16, color: '#1A365D' },
      data: [
        { name: '答对', value: correctCount.value, itemStyle: { color: '#10b981' } },
        { name: '答错', value: wrongCount.value, itemStyle: { color: '#C91F37' } }
      ]
    }
  ]
}))

onMounted(async () => {
  try {
    const auth = (window).__VTJ_AUTH__
    if (auth && auth.apiFetch) {
      const res = await auth.apiFetch('/api/stats/subject-distribution')
      const data = await res.json()
      items.value = Array.isArray(data.items) ? data.items : []
      totalCount.value = Number(data.total) || 0
      correctCount.value = Number(data.correct) || 0
      wrongCount.value = Number(data.wrong) || 0
      accuracy.value = Number(data.accuracy) || 0
    }
  } catch (e) {
    console.warn('[学习分布] 加载失败', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.card-title { display: flex; align-items: center; gap: 6px; }
.card-ico { font-size: 16px; }
.dist-row { display: flex; gap: 12px; margin-top: 4px; }
.dist-box { flex: 1 1 0; min-width: 0; }
.dist-label { margin: 0 0 4px; font-size: 12px; color: #8a8f9c; text-align: center; }
.dist-empty { margin: 0; padding: 64px 0; text-align: center; font-size: 13px; color: #a5a9b4; }
.dist-side { display: flex; flex-direction: column; justify-content: center; gap: 10px; width: 92px; flex: 0 0 92px; }
.dist-stat { display: flex; flex-direction: column; align-items: center; }
.dist-num { font-size: 18px; font-weight: 700; color: #1A365D; line-height: 1.2; }
.dist-num.ok { color: #10b981; }
.dist-num.bad { color: #C91F37; }
.dist-cap { font-size: 11px; color: #8a8f9c; }
</style>
