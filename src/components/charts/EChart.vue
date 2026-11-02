<template>
  <div ref="host" class="echart-host" :style="{ height: height, width: '100%' }"></div>
</template>

<script setup>
/**
 * EChart.vue —— echarts 通用容器
 *
 * 为什么单独封一层：
 *  1. 项目里没有统一的图表入口，直接在每个页面 new echarts 会出现
 *     「onUnmounted 忘记 dispose」「容器尺寸变化不 resize」两类泄漏；
 *  2. 三端（PC/平板/手机）都要用同一份配置，收口后只需改这一处；
 *  3. 点击事件统一 emit('chart-click', params)，业务侧只处理下标。
 *
 * 用法：
 *   <EChart :option="chartOption" height="260px" @chart-click="onChartClick" />
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '260px' },
  // true 时不合并旧配置，直接整体替换（维度切换时避免残留系列）
  notMerge: { type: Boolean, default: true }
})

const emit = defineEmits(['chart-click'])

const host = ref(null)
let chart = null
let observer = null

const render = () => {
  if (!chart) return
  chart.setOption(props.option || {}, props.notMerge)
}

onMounted(() => {
  if (!host.value) return
  chart = echarts.init(host.value)
  render()
  chart.on('click', (params) => emit('chart-click', params))
  if (typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(() => {
      if (chart) chart.resize()
    })
    observer.observe(host.value)
  } else {
    window.addEventListener('resize', handleWindowResize)
  }
})

const handleWindowResize = () => {
  if (chart) chart.resize()
}

watch(
  () => props.option,
  () => render(),
  { deep: true }
)

onBeforeUnmount(() => {
  if (observer) {
    observer.disconnect()
    observer = null
  } else {
    window.removeEventListener('resize', handleWindowResize)
  }
  if (chart) {
    chart.off('click')
    chart.dispose()
    chart = null
  }
})

defineExpose({
  getInstance: () => chart,
  resize: () => chart && chart.resize()
})
</script>

<style scoped>
.echart-host {
  display: block;
  min-height: 120px;
}
</style>
