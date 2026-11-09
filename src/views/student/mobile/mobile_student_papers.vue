<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">历年试卷</h1>
      <span class="spacer"></span>
    </header>

    <main class="list">
      <div
        v-for="p in papers"
        :key="p.paper_id"
        class="card"
        :class="{ 'card--off': !isAnswerable(p) }"
        @click="startPaper(p)"
      >
        <div class="p-head">
          <div class="p-name">{{ p.paper_name }}</div>
          <!-- P2 补（2026-11-09）：考试状态角标。数据来自后端 contract.exam_state()，
               含开关/定时窗口/有题三种闸；ready=false 时显示原因，学生不用再猜"为什么考不了"。 -->
          <span class="p-state" :class="isAnswerable(p) ? 'is-ready' : 'is-off'">
            {{ isAnswerable(p) ? '可考' : stateLabel(p) }}
          </span>
        </div>
        <div class="p-meta">
          <span class="tag">{{ subjectName(p.subject_id) }}</span>
          <span class="tag">{{ p.question_count }} 题</span>
          <span v-if="p.total_score" class="tag">{{ p.total_score }} 分</span>
          <span class="tag">{{ p.duration }} 分钟</span>
          <span class="tag">{{ examTypeName(p.exam_type) }}</span>
        </div>
        <p v-if="!isAnswerable(p) && p.exam_hint" class="p-hint">{{ p.exam_hint }}</p>
      </div>
      <div v-if="!papers.length && !loading" class="empty">暂无已发布试卷</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { fetchExamPapers, type ExamPaperItem } from '@/modules/papers/api';
import { onPapersDataChanged } from '@/modules/papers/events';

const router = useRouter();
const route = useRoute();
const papers = ref<ExamPaperItem[]>([]);
const loading = ref(false);
let unbindRefresh: (() => void) | null = null;

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const subjectName = (id?: number) => {
  return ({ 1: '行测', 2: '申论', 3: '公专' } as Record<number, string>)[id || 0] || '通用';
};

const examTypeName = (t?: string | null) => {
  // p.exam_type 来自后端，可能缺省；显式声明映射表避免用 undefined 索引对象
  const map: Record<string, string> = { SIMULATION: '模拟卷', PRACTICE: '练习卷', FORMAL: '真题卷' };
  return (t && map[t]) || '试卷';
};

/** 能不能点「开考」：只有后端说 ready 才允许（口径与资料页 canExam 一致） */
const isAnswerable = (p: ExamPaperItem) => p.answerable !== false && p.exam?.ready !== false;

/** 角标文案：把后端原因码翻成 2–4 个字，长原因放在下面的 p-hint 里 */
const stateLabel = (p: ExamPaperItem) => {
  const reason = p.exam?.reason;
  const map: Record<string, string> = {
    closed: '已关闭',
    not_started: '未开始',
    expired: '已结束',
    no_questions: '无题目',
    draft: '未发布',
    no_paper: '未建卷'
  };
  return (reason && map[reason]) || '不可考';
};

const load = async () => {
  const auth = (window as any).__VTJ_AUTH__;
  if (!auth || !auth.isLoggedIn || !auth.isLoggedIn()) return;
  loading.value = true;
  try {
    papers.value = await fetchExamPapers(50);
  } catch (e) {
    console.error('加载试卷失败:', e);
  } finally {
    loading.value = false;
  }
};

/** 开考：手机走 /mobile/answer，平板走 /tablet/answer（同一份组件，paper_id 触发整卷模式） */
const startPaper = (p: ExamPaperItem) => {
  if (!isAnswerable(p)) {
    // 不可考时把原因说清楚，不让用户点了没反应
    window.alert(p.exam_hint || '这场考试暂时不能开始');
    return;
  }
  const prefix = route.path.startsWith('/tablet') ? '/tablet' : '/mobile';
  router.push(`${prefix}/answer?paper_id=${p.paper_id}`);
};

onMounted(async () => {
  await load();
  unbindRefresh = onPapersDataChanged(() => {
    void load();
  });
});

onUnmounted(() => {
  if (unbindRefresh) unbindRefresh();
});
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 48px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e8ecf1;
  position: sticky;
  top: 0;
  z-index: 10;
}
.back-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #1a2b5f;
  cursor: pointer;
  padding: 4px 8px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}
.spacer {
  width: 32px;
}
.list {
  flex: 1;
  padding: 12px;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
}
/* 不可考的卷：整卡降饱和，但仍然显示 —— 学生要知道"这套卷在，只是现在不能考" */
.card--off {
  opacity: 0.72;
}
.p-head {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}
.p-name {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.5;
}
.p-state {
  flex: none;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.7;
  padding: 0 8px;
  border-radius: 999px;
  white-space: nowrap;
}
.p-state.is-ready {
  color: #0f7a4d;
  background: #e8f8f0;
  border: 1px solid #bfe9d4;
}
.p-state.is-off {
  color: #8a6d3b;
  background: #fff7e6;
  border: 1px solid #fde68a;
}
.p-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.tag {
  font-size: 12px;
  color: #5a6488;
  background: #f0f3f7;
  padding: 3px 8px;
  border-radius: 6px;
}
.p-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #b45309;
  line-height: 1.5;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}
</style>
