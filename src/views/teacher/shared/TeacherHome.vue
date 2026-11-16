<template>
  <div class="teacher-device-page">
    <header class="tdp-top">
      <div class="tdp-title">
        <span class="tdp-badge">教师</span>
        <b>教师工作台</b>
        <span class="tdp-platform">{{ platformLabel }}</span>
      </div>
      <div class="tdp-user">{{ username }}</div>
    </header>

    <section class="tdp-kpis">
      <div class="tdp-kpi"><b>—</b><span>待批作业</span></div>
      <div class="tdp-kpi"><b>—</b><span>待改试卷</span></div>
      <div class="tdp-kpi"><b>—</b><span>班级人数</span></div>
      <div class="tdp-kpi"><b>—</b><span>本周提交率</span></div>
    </section>

    <section class="tdp-entries">
      <div class="tdp-entry">
        <span class="t">📚 题目管理</span>
        <span class="d">浏览 / 搜索 / 预览</span>
        <span class="tag ok">设备端可用</span>
      </div>
      <div class="tdp-entry">
        <span class="t">📝 试卷</span>
        <span class="d">查看列表与状态</span>
        <span class="tag ok">设备端可用</span>
      </div>
      <div class="tdp-entry">
        <span class="t">📊 成绩分析</span>
        <span class="d">班级对比 / 知识点</span>
        <span class="tag ok">设备端可用</span>
      </div>
      <div class="tdp-entry">
        <span class="t">✏️ 组卷 / 编辑试卷</span>
        <span class="d">需要键盘与双栏工作台</span>
        <span class="tag warn">请到电脑端</span>
      </div>
      <div class="tdp-entry">
        <span class="t">✅ 批改作业 / 判分</span>
        <span class="d">需逐题打分</span>
        <span class="tag warn">请到电脑端</span>
      </div>
      <div class="tdp-entry">
        <span class="t">📤 批量导入题目</span>
        <span class="d">需上传文件与校验</span>
        <span class="tag warn">请到电脑端</span>
      </div>
    </section>

    <p class="tdp-note">
      本期设备端为「只读优先」：查看类可用，写操作请回电脑端。
      <br />数据接入与各功能页在 P3/P4 交付（本页为 P2 的落地点，先解决"教师登录后被弹走"）。
    </p>
  </div>
</template>

<script lang="ts">
/**
 * 教师设备端工作台（P2 落地页，2026-11-16）
 *
 * 为什么先放占位页：
 *   三端登录的缺口是"教师能登录、但登录后无处可去（被守卫弹到 unauthorized）"。
 *   P2 先给一个**正确的落地页与路由**，让登录闭环成立；真实数据与列表页在 P3/P4 接。
 *   这样 P2 可以单独验收（教师登录 → 停在教师工作台），不必等 P3。
 *
 * 为什么一套组件同时供平板与手机：
 *   守 R12（不造重复副本）。用 `meta.platform` 区分布局，CSS 断点在 640px。
 *
 * 为什么不动 .vtj 模板：既有 4 个教师页是 raw 页（R3 不许改模板），
 * 设备端只能新建手写组件；这里放在 `src/views/teacher/shared/`，可被两条路由复用。
 */
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'TeacherDeviceHome',
  computed: {
    platformLabel(): string {
      const platform = (this.$route.meta as any)?.platform
      if (platform === 'tablet') return '平板'
      if (platform === 'mobile') return '手机'
      return '设备端'
    },
    username(): string {
      const auth = (window as any).__VTJ_AUTH__
      try {
        const state = auth && auth.getState ? auth.getState() : null
        return (state && state.username) || ''
      } catch (e) {
        return ''
      }
    },
  },
})
</script>

<style scoped>
.teacher-device-page {
  min-height: 100vh;
  background: #f2f5f9;
  color: #1f2d3d;
  padding: 16px;
  font-size: 15px;
}
.tdp-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: #163a5f;
  color: #fff;
  border-radius: 12px;
  padding: 12px 16px;
  margin-bottom: 14px;
}
.tdp-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tdp-title b { font-size: 16px; letter-spacing: 0.4px; }
.tdp-badge {
  background: rgba(255, 255, 255, 0.18);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
}
.tdp-platform { font-size: 12px; opacity: 0.8; }
.tdp-user { font-size: 13px; opacity: 0.9; white-space: nowrap; }

.tdp-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
.tdp-kpi {
  background: #fff;
  border: 1px solid #e6ebf2;
  border-radius: 12px;
  padding: 14px;
  text-align: left;
}
.tdp-kpi b { display: block; font-size: 22px; color: #163a5f; }
.tdp-kpi span { font-size: 12px; color: #7a8797; }

.tdp-entries {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.tdp-entry {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
  background: #fff;
  border: 1px solid #e6ebf2;
  border-radius: 12px;
  padding: 14px;
}
.tdp-entry .t { font-weight: 600; font-size: 14px; }
.tdp-entry .d { font-size: 12px; color: #7a8797; }
.tag { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.tag.ok { background: #eaf4ee; color: #2f9e6e; }
.tag.warn { background: #fdf0e6; color: #c97a2b; }

.tdp-note {
  margin: 14px 0 0;
  border: 1px dashed #e6ebf2;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 12px;
  color: #7a8797;
  background: #fbfcfe;
  line-height: 1.7;
}

@media (max-width: 1024px) {
  .tdp-entries { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .teacher-device-page { padding: 12px; }
  .tdp-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tdp-entries { grid-template-columns: 1fr; }
  .tdp-title b { font-size: 15px; }
}
</style>
