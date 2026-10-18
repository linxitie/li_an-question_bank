<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">备考资料</h1>
      <span class="spacer"></span>
    </header>

    <!-- 科目 Tab -->
    <div class="tabs">
      <div
        v-for="s in subjects"
        :key="s.key"
        :class="['tab', { active: activeSubject === s.key }]"
        @click="switchSubject(s.key)"
      >
        {{ s.name }}
      </div>
    </div>

    <main class="list">
      <div v-for="m in materials" :key="m.id" class="card" @click="toggleDetail(m)">
        <div class="m-title">{{ m.title }}</div>
        <div class="m-meta">
          <span class="tag">{{ typeName(m.type) }}</span>
          <span v-if="m.duration" class="tag">⏱ {{ m.duration }}分钟</span>
          <span v-if="m.read_time" class="tag">阅读 {{ m.read_time }}分钟</span>
          <span v-if="m.is_studied" class="done">已学</span>
          <span v-if="m.progress_percent" class="progress">进度 {{ m.progress_percent }}%</span>
        </div>
        <div v-if="expandedId === m.id" class="detail" @click.stop>
          <p v-if="m.summary" class="summary">{{ m.summary }}</p>
          <button class="view-btn" @click="openDetail(m)">查看详情</button>
        </div>
      </div>
      <div v-if="!materials.length && !loading" class="empty">该科目暂无备考资料</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>

    <!-- 资料详情弹层（页内展示；原实现跳 /materials/{subject}?id= 该路由不存在，必然 404） -->
    <div v-if="detailVisible" class="modal-mask" @click="closeDetail">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <span class="modal-title">{{ detailData ? detailData.title : '' }}</span>
          <button class="modal-close" @click="closeDetail" aria-label="关闭">✕</button>
        </div>
        <div class="modal-body">
          <div v-if="detailLoading" class="empty">加载中...</div>
          <div v-else-if="detailError" class="empty">{{ detailError }}</div>
          <template v-else-if="detailData">
            <video
              v-if="detailData.video_url"
              class="detail-video"
              :src="detailData.video_url"
              controls
              playsinline
            ></video>
            <img
              v-if="detailData.cover_image"
              class="detail-cover"
              :src="detailData.cover_image"
              alt="资料封面"
            />
            <div class="m-meta">
              <span class="tag">{{ typeName(detailData.type) }}</span>
              <span v-if="detailData.read_time" class="tag">阅读 {{ detailData.read_time }}分钟</span>
            </div>
            <p v-if="detailData.summary" class="summary">{{ detailData.summary }}</p>
            <div class="detail-content" v-html="renderQuestionContent(detailData.content)"></div>
            <div v-if="detailData.card_back" class="detail-card-back" v-html="renderQuestionContent(detailData.card_back)"></div>
          </template>
        </div>
        <div class="modal-actions">
          <button class="action-btn" @click="markStudied">标记已学</button>
          <button class="action-btn" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';
import { renderQuestionContent } from '@/utils/questionRender';
import { ElMessage } from 'element-plus';
import { useLibraryStore } from '@/modules/library/store';

const router = useRouter();
const library = useLibraryStore();
const { items: materials, loading, selected: detailData } = storeToRefs(library);

const subjects = [
  { key: 'xingce', name: '行测' },
  { key: 'shenlun', name: '申论' },
  { key: 'gongzhuan', name: '公专' }
] as const;
const activeSubject = ref<'xingce' | 'shenlun' | 'gongzhuan'>('xingce');
const expandedId = ref<number | null>(null);

// ===== 资料详情弹层 =====
const detailVisible = ref(false);
const detailLoading = ref(false);
const detailError = ref('');
const currentMaterial = ref<any>(null);

const closeDetail = () => {
  detailVisible.value = false;
  detailError.value = '';
  currentMaterial.value = null;
  library.clearSelection();
};

const loadDetail = async (id: number) => {
  detailLoading.value = true;
  detailError.value = '';
  try {
    const detail = await library.openMaterial(id);
    if (!detail) {
      detailError.value = library.error || '资料加载失败，请检查网络后重试';
    }
  } finally {
    detailLoading.value = false;
  }
};

// 上报学习进度（进度只存后端，不写 localStorage）
const markStudied = async () => {
  const m = currentMaterial.value;
  if (!m || m.id == null) return;
  const ok = await library.reportProgress(m.id, 100, true);
  if (ok) {
    ElMessage.success('已标记为学完');
    closeDetail();
  } else {
    ElMessage.error('提交进度失败，请稍后重试');
  }
};

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const typeName = (t: string) => {
  return {
    video_intro: '入门视频',
    video_advanced: '进阶视频',
    article: '文章',
    card: '知识卡片'
  }[t] || '资料';
};

const switchSubject = (key: 'xingce' | 'shenlun' | 'gongzhuan') => {
  activeSubject.value = key;
  expandedId.value = null;
  fetchMaterials();
};

const toggleDetail = (m: any) => {
  expandedId.value = expandedId.value === m.id ? null : m.id;
};

const fetchMaterials = async () => {
  await library.load({
    subject: activeSubject.value,
    page: 1,
    pageSize: 50
  });
};

const openDetail = async (m: any) => {
  if (!m || m.id == null) {
    ElMessage.info('该资料暂时无法打开');
    return;
  }
  currentMaterial.value = m;
  detailVisible.value = true;
  await loadDetail(m.id);
};

onMounted(fetchMaterials);
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
.tabs {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid #f0f2f5;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 8px 0;
  border-radius: 8px;
  font-size: 14px;
  color: #5a6488;
  background: #f0f3f7;
  cursor: pointer;
}
.tab.active {
  background: #1a2b5f;
  color: #fff;
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
.m-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.5;
  margin-bottom: 8px;
}
.m-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.tag {
  font-size: 12px;
  color: #5a6488;
  background: #f0f3f7;
  padding: 3px 8px;
  border-radius: 6px;
}
.done {
  font-size: 12px;
  color: #10b981;
  font-weight: 600;
}
.progress {
  font-size: 12px;
  color: #f59e0b;
}
.detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}
.summary {
  font-size: 13px;
  color: #5a6488;
  line-height: 1.6;
  margin: 0 0 10px;
}
.view-btn {
  min-height: 36px;
  padding: 0 16px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #1a2b5f, #1e3470);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}

/* ===== 资料详情弹层 ===== */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 1000;
}
.modal {
  background: #fff;
  border-radius: 14px;
  width: 100%;
  max-width: 560px;
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #eef1f5;
  flex-shrink: 0;
}
.modal-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.4;
  padding-right: 8px;
}
.modal-close {
  background: none;
  border: none;
  font-size: 18px;
  color: #8899aa;
  cursor: pointer;
  min-width: 44px;
  min-height: 44px;
  flex-shrink: 0;
}
.modal-body {
  padding: 16px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  flex: 1;
}
.detail-video {
  width: 100%;
  max-height: 220px;
  border-radius: 8px;
  margin-bottom: 12px;
  background: #000;
}
.detail-cover {
  width: 100%;
  border-radius: 8px;
  margin-bottom: 12px;
}
.summary {
  font-size: 13px;
  color: #5a6488;
  line-height: 1.7;
  margin: 10px 0;
}
.detail-content {
  font-size: 14px;
  line-height: 1.8;
  color: #1a2a3a;
}
.detail-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
}
.detail-card-back {
  margin-top: 14px;
  padding: 12px;
  background: #f8f9fc;
  border-radius: 8px;
  font-size: 13px;
  color: #1a2b5f;
  line-height: 1.7;
}
.modal-actions {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid #eef1f5;
  flex-shrink: 0;
}
.action-btn {
  flex: 1;
  min-height: 44px;
  border: 1px solid #1a2b5f;
  background: #1a2b5f;
  color: #fff;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}
.action-btn:active {
  opacity: 0.85;
}
</style>
