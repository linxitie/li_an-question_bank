<!-- 招考信息模块 - Accordion展开 · 1200px卡片 · 15px字体 -->
<template>
  <div class="recruitment-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <XIcon :icon="Opportunity" :size="24" color="#c8161e"></XIcon>
        <span class="header-title">招考信息</span>
      </div>
      <span class="header-badge pulse-dot">实时更新</span>
    </div>

    <!-- 加载状态 -->
    <div v-if="state.loading" class="recruit-loading">
      <span>正在加载招考信息...</span>
    </div>

    <!-- Accordion 列表（可滚动） -->
    <div v-else class="recruitment-list-scroll" ref="scrollContainer">
    <div class="recruitment-list">
      <div
        v-for="item in state.allItems.slice(0, state.displayCount)"
        :key="item.id"
        class="recruitment-card"
      >
        <!-- 卡片头部：点击展开/收起 -->
        <div class="recruitment-header" @click="toggleExpand(item.id)">
          <div class="header-main">
            <span class="recruitment-title">{{ item.title }}</span>
            <div class="recruitment-meta">
              <span v-if="item.organization" class="meta-org">{{ item.organization }}</span>
              <span v-if="item.region" class="meta-region">{{ item.region }}</span>
              <span v-if="item._category" class="meta-cat">{{ item._category }}</span>
            </div>
          </div>
          <div class="header-right">
            <span
              class="status-badge"
              :style="getStatusStyle(item.status_label || '正在报名')"
            >{{ item.status_label || item.tag || '正在报名' }}</span>
            <span v-if="item.registration_start || item.registration_end" class="reg-time">
              {{ item.registration_start || '' }}{{ item.registration_start && item.registration_end ? ' ~ ' : '' }}{{ item.registration_end || '' }}
            </span>
            <span class="expand-arrow" :class="{ 'arrow-expanded': state.expandedId === item.id }">&#9660;</span>
          </div>
        </div>

        <!-- 展开详情 -->
        <div v-if="state.expandedId === item.id" class="recruitment-detail">
          <!-- 图片展示 -->
          <div v-if="item.images && item.images.length > 0" class="detail-images">
            <img
              v-for="(img, iidx) in item.images"
              :key="iidx"
              :src="img.url"
              :alt="img.alt"
              class="detail-img"
            />
          </div>

          <!-- 报名截止时间 红色高亮 -->
          <span v-if="item.registration_end" class="deadline-highlight">
            ⏰ 报名截止: {{ item.registration_end }}
          </span>

          <!-- HTML 正文 -->
          <div class="detail-content" v-html="sanitizeHtml(item.content_html || item.content || '')"></div>

          <!-- 纯文本正文（fallback） -->
          <div v-if="!item.content_html && item.content" class="detail-content-plain">
            <p>{{ item.content }}</p>
          </div>

          <!-- 考试方式 & 联系方式 -->
          <div class="detail-info-row" v-if="item.exam_format || item.contact_info">
            <span v-if="item.exam_format" class="info-tag exam-tag">
              考试方式：{{ item.exam_format }}
            </span>
            <span v-if="item.contact_info" class="info-tag contact-tag">
              {{ item.contact_info }}
            </span>
          </div>

          <!-- 底部操作 -->
          <div class="detail-footer">
            <a v-if="item.url" :href="item.url" target="_blank" class="detail-link">查看原文 &#8599;</a>
            <span class="detail-views">浏览 {{ item.view_count || 0 }}</span>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="state.allItems.length === 0 && !state.loading" class="recruit-empty">
        <span>暂无招考信息</span>
      </div>

      <!-- 滚动加载哨兵 -->
      <div ref="scrollSentinel" class="scroll-sentinel"></div>
    </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive, ref } from 'vue';
import { XIcon } from '@vtj/ui';
import { Opportunity } from '@vtj/icons';
import { useProvider } from '@vtj/renderer';
import { sanitizeHtml } from '@/utils/questionRender';
import { createRecruitmentRefresher } from '@/utils/recruitmentRefresh';

export default defineComponent({
  name: 'RecruitmentInfo',
  components: { XIcon },
  setup(props) {
    const provider = useProvider({ id: 'recruitment_info', version: '1785750000101' });
    const state = reactive({
      items: {} as Record<string, any[]>,
      expandedId: null as number | null,
      loading: false,
      categories: ['国考省考', '事业单位', '教师招聘', '国企招聘', '医疗卫生', '三支一扶'] as string[],
      allItems: [] as any[],
      displayCount: 10,
      // 后端返回的元信息（更新时间 / 站点最新发布日期），P2 文案将消费
      meta: null as any,
    });
    const scrollContainer = ref<HTMLElement | null>(null);
    const scrollSentinel = ref<HTMLElement | null>(null);
    let observer: IntersectionObserver | null = null;
    return { state, props, provider, Opportunity, scrollContainer, scrollSentinel, sanitizeHtml };
  },
  methods: {
    async fetchRecruitment(ctx: any) {
      if (this.state.loading) return;
      this.state.loading = true;
      try {
        // ctx 由刷新内核提供：signal 用于取消过期请求，ts 用于破缓存。
        // 招考信息每日更新，任何层级缓存都会让用户看到旧内容，故强制 no-store。
        const opts: any = { cache: 'no-store' };
        if (ctx && ctx.signal) opts.signal = ctx.signal;
        const url = '/api/recruitment?limit=20&_ts=' + ((ctx && ctx.ts) || Date.now());
        const resp = await (window as any).__VTJ_AUTH__.apiFetch(url, opts);
        const data = await resp.json();
        if (data && data.items) {
          this.state.items = data.items;
          this.state.meta = data.meta || null;
          // Flatten all items for accordion display
          const all: any[] = [];
          for (const cat of this.state.categories) {
            const catItems = data.items[cat] || [];
            for (const item of catItems) {
              all.push({ ...item, _category: cat });
            }
          }
          this.state.allItems = all;
          this.state.displayCount = 10;
        }
      } catch (e: any) {
        if (e && (e.name === 'AbortError' || e.__aborted)) return;
        console.warn('[RecruitmentInfo] fetchRecruitment failed:', e.message);
      } finally {
        this.state.loading = false;
      }
    },
    toggleExpand(id: number) {
      if (this.state.expandedId === id) {
        this.state.expandedId = null;
      } else {
        this.state.expandedId = id;
      }
    },
    getStatusStyle(statusLabel: string) {
      const colorMap: Record<string, string> = {
        '正在报名': '#10b981',
        '即将报名': '#1a2a6c',
        '报名结束': '#c41e3a',
      };
      const color = colorMap[statusLabel] || '#10b981';
      return { color, background: color + '15' };
    },
    loadMore() {
      if (this.state.displayCount < this.state.allItems.length) {
        const next = Math.min(this.state.displayCount + 10, this.state.allItems.length);
        this.state.displayCount = next;
      }
    },
    setupObserver() {
      if (!this.scrollSentinel) return;
      this.observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
          this.loadMore();
        }
      }, { threshold: 0.1 });
      this.observer.observe(this.scrollSentinel);
    },
  },
  mounted() {
    // 统一刷新内核接管取数：首屏加载 + 后端广播 + 可见性/聚焦 + 跨日 + 15 分钟轮询
    // + 登录态变化 + 手动刷新，全部收敛到一处，避免多套重复逻辑漏改。
    this._recruitRefresher = createRecruitmentRefresher({
      fetchFn: (ctx) => this.fetchRecruitment(ctx),
      pollMs: 15 * 60 * 1000,
    });
    this.$nextTick(() => {
      this.setupObserver();
    });
  },
  beforeUnmount() {
    if (this._recruitRefresher) {
      this._recruitRefresher.destroy();
      this._recruitRefresher = null;
    }
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
  }
})
</script>

<style lang="css" scoped>
/* ========== 页面容器 ========== */
.recruitment-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 24px;
  box-sizing: border-box;
}

/* ========== 页面标题 ========== */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-title {
  font-size: 22px;
  font-weight: 700;
  color: #1a2b5f;
  letter-spacing: 1.5px;
}
.header-badge {
  font-size: 14px;
  color: #c8161e;
  background: rgba(200, 22, 30, 0.06);
  padding: 4px 14px;
  border-radius: 20px;
  font-weight: 500;
}
.pulse-dot::before {
  content: "";
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #c8161e;
  margin-right: 6px;
  animation: pulse-dot 2s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(1.5); }
}

/* ========== 加载状态 ========== */
.recruit-loading {
  text-align: center;
  padding: 60px 0;
  color: #8899aa;
  font-size: 15px;
}

/* ========== 可滚动容器 ========== */
.recruitment-list-scroll {
  max-height: 60vh;
  overflow-y: auto;
  scroll-behavior: smooth;
}
.recruitment-list-scroll::-webkit-scrollbar {
  width: 6px;
}
.recruitment-list-scroll::-webkit-scrollbar-track {
  background: transparent;
}
.recruitment-list-scroll::-webkit-scrollbar-thumb {
  background: #d0d5dd;
  border-radius: 3px;
}
.recruitment-list-scroll::-webkit-scrollbar-thumb:hover {
  background: #a0a8b4;
}

/* ========== Accordion 列表 ========== */
.recruitment-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* ========== 招考卡片 ========== */
.recruitment-card {
  background: #fff;
  border-radius: 14px;
  margin-bottom: 12px;
  border: 1px solid #e8ecf1;
  box-shadow: 0 2px 12px rgba(26,43,95,0.04);
  overflow: hidden;
}

/* ========== 卡片头部 ========== */
.recruitment-header {
  padding: 18px 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: background 0.2s;
}
.recruitment-header:hover {
  background: #f8f9fc;
}
.header-main {
  flex: 1;
  min-width: 0;
}
.recruitment-title {
  font-size: 18px;
  font-weight: 700;
  color: #1a2b5f;
  display: block;
  margin-bottom: 4px;
}
.recruitment-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 13px;
  color: #5a6488;
}
.meta-org, .meta-region, .meta-cat {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.meta-cat {
  color: #c8161e;
  font-weight: 500;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

/* 胶囊状态标签 */
.status-badge {
  display: inline-block;
  font-size: 13px;
  font-weight: 500;
  padding: 3px 12px;
  border-radius: 20px;
  white-space: nowrap;
  flex-shrink: 0;
}

/* 报名时间 */
.reg-time {
  font-size: 13px;
  color: #5a6488;
  white-space: nowrap;
}

/* 展开箭头 */
.expand-arrow {
  font-size: 12px;
  color: #bcc5ce;
  transition: transform 0.3s ease;
  line-height: 1;
}
.expand-arrow.arrow-expanded {
  transform: rotate(180deg);
  color: #c8161e;
}

/* ========== 展开详情 ========== */
.recruitment-detail {
  padding: 0 24px 24px;
  border-top: 1px solid #f0f2f5;
}

/* 图片展示 */
.detail-images {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding-top: 20px;
  margin-bottom: 16px;
}
.detail-img {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  object-fit: contain;
  display: block;
}

/* 截止时间红色高亮 */
.deadline-highlight {
  color: #c41e3a;
  font-weight: 700;
  font-size: 15px;
  background: #fef2f2;
  padding: 6px 14px;
  border-radius: 8px;
  display: inline-block;
  margin: 8px 0;
}

/* HTML 正文 */
.detail-content {
  font-size: 15px;
  line-height: 1.8;
  padding-top: 20px;
  color: #2c3e50;
}
.detail-content :deep(p) {
  margin-bottom: 16px;
}
.detail-content :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  margin: 12px auto;
  display: block;
}

/* 纯文本 fallback */
.detail-content-plain {
  font-size: 15px;
  line-height: 1.8;
  padding-top: 20px;
  color: #2c3e50;
  white-space: pre-wrap;
  word-break: break-all;
}
.detail-content-plain p {
  margin-bottom: 16px;
}

/* 考试方式 & 联系方式 */
.detail-info-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f2f5;
}
.info-tag {
  font-size: 13px;
  padding: 4px 12px;
  border-radius: 8px;
  font-weight: 500;
}
.exam-tag {
  color: #2e86c1;
  background: rgba(46, 134, 193, 0.08);
}
.contact-tag {
  color: #e67e22;
  background: rgba(230, 126, 34, 0.08);
}

/* 底部操作 */
.detail-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #f0f2f5;
}
.detail-link {
  font-size: 14px;
  color: #2e86c1;
  text-decoration: none;
  transition: color 0.2s;
}
.detail-link:hover {
  color: #1a5f8a;
  text-decoration: underline;
}
.detail-views {
  font-size: 13px;
  color: #8899aa;
}

/* ========== 空状态 ========== */
.recruit-empty {
  text-align: center;
  padding: 60px 0;
}
.recruit-empty span {
  font-size: 15px;
  color: #bcc5ce;
}

/* ========== 滚动加载哨兵 ========== */
.scroll-sentinel {
  height: 1px;
  width: 100%;
}
</style>
