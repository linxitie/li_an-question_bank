<!-- 底部卡片设计 -->
<template>
  <div class="home-page">
    <NavBar></NavBar>
    <main class="home-main">
      <section class="top-section">
        <div class="left-col">
          <SignInCard></SignInCard>
          <GoalCard></GoalCard>
        </div>
        <div class="center-col">
          <QuoteBanner></QuoteBanner>
          <CountdownTimer></CountdownTimer>
        </div>
        <div class="right-col">
          <ExamCalendar></ExamCalendar>
        </div>
      </section>
      <section class="study-materials-section">
        <StudyMaterialsEntry></StudyMaterialsEntry>
      </section>
      <section class="recruit-section">
        <div class="section-header">
          <h2 class="section-title">
            <XIcon :icon="Briefcase" :size="24" color="#c41e3a"></XIcon>
            <span>招考信息</span>
          </h2>
          <span class="section-subtitle">最新招考动态，助你把握每一个机会</span>
        </div>
        <div class="recruit-grid">
          <div v-for="(item, index) in state.recruitCategories"
               :key="item.id"
               class="recruit-card">
            <!-- 卡片头部：图标 + 分类名 + 数量 + 箭头(›) -->
            <div class="recruit-card-header" @click="scrollToTop(item)">
              <div class="recruit-header-left">
                <div class="recruit-icon2" :style="{ background: item.bg }">
                  <span class="recruit-emoji">{{ item.icon }}</span>
                </div>
                <div class="recruit-card-title-row">
                  <span class="recruit-name">{{ item.name }}</span>
                  <span class="recruit-count-badge">{{ item.allItems.length }}条招考</span>
                </div>
              </div>
              <div class="recruit-header-right">
                <span class="recruit-arrow">›</span>
              </div>
            </div>
            <!-- 标题列表：全部条目，卡片内滚动查看 -->
            <div class="recruit-title-list-scroll" v-if="item.allItems.length > 0">
            <div class="recruit-title-list" :ref="(el: any) => setRecruitListRef(item.id, el)">
              <div v-for="(ri, ridx) in item.allItems"
                   :key="ridx"
                   class="recruit-title-item"
                   @click="openRecruitDetail(ri)">
                <!-- 胶囊状状态标签 -->
                <span class="status-badge" :style="{
                  color: ri.status_color || ri.tag_color || '#10b981',
                  background: (ri.status_color || ri.tag_color || '#10b981') + '18'
                }">{{ ri.status_label || ri.tag || '正在报名' }}</span>
                <!-- 标题文字 -->
                <span class="recruit-title-text" :title="ri.title">{{ ri.title && ri.title.length > 16 ? ri.title.substring(0, 16) + '...' : (ri.title || '未知标题') }}</span>
              </div>
            </div>
            </div>
            <!-- 空状态 -->
            <div class="recruit-empty" v-else>
              <span>暂无招考信息</span>
            </div>
          </div>
        </div>

        <!-- 招考详情弹窗 -->
        <div class="recruit-modal-overlay" v-if="state.showRecruitModal" @click.self="closeRecruitDetail">
          <div class="recruit-modal">
            <div class="recruit-modal-header">
              <h3 class="recruit-modal-title">{{ state.selectedRecruit.title }}</h3>
              <button class="recruit-modal-close" @click="closeRecruitDetail">&times;</button>
            </div>
            <div class="recruit-modal-tags">
              <span class="recruit-modal-cat">{{ state.selectedRecruit.category }}</span>
              <span class="recruit-modal-status" v-if="state.selectedRecruit.status_label" :style="{
                color: state.selectedRecruit.status_color || '#10b981',
                background: (state.selectedRecruit.status_color || '#10b981') + '18'
              }">{{ state.selectedRecruit.status_label }}</span>
              <span class="recruit-modal-org" v-if="state.selectedRecruit.organization">{{ state.selectedRecruit.organization }}</span>
              <span class="recruit-modal-time" v-if="state.selectedRecruit.registration_start">报名: {{ state.selectedRecruit.registration_start }}</span>
              <span class="recruit-modal-time" v-if="state.selectedRecruit.registration_end">截止: {{ state.selectedRecruit.registration_end }}</span>
            </div>
            <div class="recruit-modal-body">
              <div class="recruit-modal-section" v-if="state.selectedRecruit.requirements">
                <h4>招聘条件</h4>
                <p>{{ state.selectedRecruit.requirements }}</p>
              </div>
              <div class="recruit-modal-section" v-if="state.selectedRecruit.content_html">
                <h4>招聘详情</h4>
                <div class="detail-content-html" v-html="sanitizeHtml(state.selectedRecruit.content_html || state.selectedRecruit.content || '')"></div>
              </div>
              <div class="recruit-modal-section" v-else>
                <h4>招聘详情</h4>
                <p>{{ state.selectedRecruit.content || '暂无详细内容，请点击"查看原文"获取完整信息。' }}</p>
              </div>
            </div>
            <div class="recruit-modal-footer">
              <a :href="state.selectedRecruit.url" target="_blank" class="recruit-modal-link">查看原文</a>
              <button class="recruit-modal-btn" @click="closeRecruitDetail">关闭</button>
            </div>
          </div>
        </div>
      </section>
      <footer class="footer-section">
        <div class="footer-links">
          <div class="footer-links xh"></div>
          <a href="#"> 用户协议</a>
          <span class="footer-divider"> |</span>
          <a href="#"> 隐私政策</a>
          <span class="footer-divider"> |</span>
          <a href="#"> 法律声明</a>
          <span class="footer-divider"> |</span>
          <a href="#"> 联系我们</a>
          <span class="footer-divider"> |</span>
          <a href="#"> 加入我们</a>
        </div>
        <p class="footer-copy">
          © 2025 砺安题库 · 专注公安联考备考 备案号：京ICP备2025000000号
        </p>
      </footer>
    </main>
  </div>
</template>
<script lang="ts">
import { sanitizeHtml } from '@/utils/questionRender';
import { createRecruitmentRefresher } from '@/utils/recruitmentRefresh';
  // @ts-nocheck
  import { defineComponent, reactive, ref } from 'vue';
  import { XIcon } from '@vtj/ui';
  import {
    Briefcase,
    ArrowRight
  } from '@vtj/icons';
  import NavBar from './navbar.vue';
  import SignInCard from './signin_card.vue';
  import GoalCard from './goal_card.vue';
  import QuoteBanner from './quote_banner.vue';
  import CountdownTimer from './countdown_timer.vue';
  import ExamCalendar from './exam_calendar_block.vue';
  import StudyMaterialsEntry from './study_materials.vue';
  import { useProvider } from '@vtj/renderer';
  import { ElMessage } from 'element-plus';
  export default defineComponent({
    name: 'HomePage',
    components: {
      NavBar,
      SignInCard,
      GoalCard,
      QuoteBanner,
      CountdownTimer,
      ExamCalendar,
      StudyMaterialsEntry,
      XIcon
    },
    setup(props) {
      const provider = useProvider({ id: 'home_page', version: '1785750000100' });
      const recruitListRefs = ref({} as Record<string, HTMLElement>);
      const state = reactive({
        recruitCategories: [],
        recruitAllData: {},
        showRecruitModal: false,
        selectedRecruit: {},
        // 后端元信息（本次更新时间 / 站点最新发布日期），P2 文案消费
        recruitMeta: null,
      });
      return { state, props, provider, recruitListRefs, Briefcase, ArrowRight, sanitizeHtml };
    },
    methods: {
      scrollToTop(cardItem) {
        // 点击箭头时，将对应卡片滚动到顶部
        const el = this.recruitListRefs[cardItem.id];
        if (el) {
          el.scrollTo({ top: 0, behavior: 'smooth' });
        }
      },
      openRecruitDetail(recruit) {
        this.state.selectedRecruit = recruit;
        this.state.showRecruitModal = true;
      },
      closeRecruitDetail() {
        this.state.showRecruitModal = false;
        this.state.selectedRecruit = {};
      },
      async fetchRecruitment(ctx: any) {
        const categories = ['国考省考', '事业单位', '教师招聘', '国企招聘', '医疗卫生', '三支一扶'];
        const icons = { '国考省考': '🏛️', '事业单位': '🏢', '教师招聘': '📚', '国企招聘': '🏭', '医疗卫生': '🏥', '三支一扶': '🌾' };
        const bgs = {
          '国考省考': 'linear-gradient(135deg, #eef2ff, #e0e7ff)',
          '事业单位': 'linear-gradient(135deg, #fef3c7, #fde68a)',
          '教师招聘': 'linear-gradient(135deg, #e0f2fe, #bae6fd)',
          '国企招聘': 'linear-gradient(135deg, #faf5ff, #ede9fe)',
          '医疗卫生': 'linear-gradient(135deg, #fce7f3, #fbcfe8)',
          '三支一扶': 'linear-gradient(135deg, #d1fae5, #a7f3d0)'
        };
        try {
          // ctx 由刷新内核提供：signal 取消过期请求，ts 破缓存（招考每日更新，须禁缓存）
          const opts: any = { cache: 'no-store' };
          if (ctx && ctx.signal) opts.signal = ctx.signal;
          const res = await window.__VTJ_AUTH__.apiFetch(
            '/api/recruitment?limit=20&_ts=' + ((ctx && ctx.ts) || Date.now()), opts);
          const data = await res.json();
          if (res.ok && data.items) {
            this.state.recruitAllData = data.items;
            this.state.recruitMeta = data.meta || null;
            this.buildRecruitCards();
          } else {
            this.loadFallbackRecruit(categories, icons, bgs);
          }
        } catch (e) {
          if (e && (e.name === 'AbortError' || e.__aborted)) return;
          this.loadFallbackRecruit(categories, icons, bgs);
        }
      },
      buildRecruitCards() {
        // 构建招考信息卡片数据（每个分类默认显示前6条，卡片内滚动查看更多）
        var result = [];
        var self = this;
        for (var cat in this.state.recruitAllData) {
          var items = this.state.recruitAllData[cat] || [];
          result.push({
            id: cat, name: cat,
            icon: self._catIcon(cat),
            bg: self._catBg(cat),
            allItems: items
          });
        }
        var order = ['国考省考', '事业单位', '教师招聘', '国企招聘', '医疗卫生', '三支一扶'];
        result.sort(function(a, b) { return order.indexOf(a.id) - order.indexOf(b.id); });
        this.state.recruitCategories = result;
      },
      loadFallbackRecruit(categories, icons, bgs) {
        var self = this;
        this.state.recruitCategories = categories.map(function(cat) {
          return { id: cat, name: cat, icon: icons[cat] || '📋', bg: bgs[cat] || 'linear-gradient(135deg, #f8f9fc, #f1f3f8)', allItems: [] };
        });
      },
      setRecruitListRef(name, el) {
        if (el) {
          this.recruitListRefs[name] = el;
        }
      },
      _catIcon(cat) {
        var m = { '国考省考': '🏛️', '事业单位': '🏢', '教师招聘': '📚', '国企招聘': '🏭', '医疗卫生': '🏥', '三支一扶': '🌾' };
        return m[cat] || '📋';
      },
      _catBg(cat) {
        var m = {
          '国考省考': 'linear-gradient(135deg, #eef2ff, #e0e7ff)',
          '事业单位': 'linear-gradient(135deg, #fef3c7, #fde68a)',
          '教师招聘': 'linear-gradient(135deg, #e0f2fe, #bae6fd)',
          '国企招聘': 'linear-gradient(135deg, #faf5ff, #ede9fe)',
          '医疗卫生': 'linear-gradient(135deg, #fce7f3, #fbcfe8)',
          '三支一扶': 'linear-gradient(135deg, #d1fae5, #a7f3d0)'
        };
        return m[cat] || 'linear-gradient(135deg, #f8f9fc, #f1f3f8)';
      }
    },
    mounted() {
      // 统一刷新内核接管取数（首屏/广播/可见性/聚焦/跨日/15分钟轮询/登录态/手动）
      this._recruitRefresher = createRecruitmentRefresher({
        fetchFn: (ctx) => this.fetchRecruitment(ctx),
        pollMs: 15 * 60 * 1000,
      });
    },
    beforeUnmount() {
      if (this._recruitRefresher) {
        this._recruitRefresher.destroy();
        this._recruitRefresher = null;
      }
    }

  })
</script>
<style lang="css" scoped>
  .home-page {
    min-height: 100vh;
    background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .home-main {
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px 32px 0;
  }
  /* 上层模块 */
  .top-section {
    display: grid;
    grid-template-columns: 280px 1fr 320px;
    gap: 20px;
    margin-bottom: 28px;
  }
  .left-col {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .center-col {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .right-col {
    display: flex;
  }
  /* 中层模块 */
  .recruit-section,
  .study-materials-section {
    margin-bottom: 28px;
  }
  .section-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 16px;
  }
  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 20px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0;
  }
  .section-subtitle {
    font-size: 20px;
    color: #8a8faa;
  }
  .recruit-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
  }
  @media (max-width: 900px) {
    .recruit-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
  @media (max-width: 600px) {
    .recruit-grid {
      grid-template-columns: 1fr;
    }
  }

  /* 招考卡片 — 纯白底色 */
  .recruit-card {
    background: #ffffff; border-radius: 14px; padding: 18px;
    box-shadow: 0 1px 8px rgba(26,43,95,0.04); border: 1px solid #f0f2f5;
    transition: all 0.3s; display: flex; flex-direction: column;
  }
  .recruit-card:hover { box-shadow: 0 4px 18px rgba(26,43,95,0.1); }

  /* 卡片头部 — 无线条，含箭头 */
  .recruit-card-header {
    display: flex; align-items: center; justify-content: space-between;
    cursor: pointer; padding-bottom: 10px; user-select: none;
  }
  .recruit-card-header:hover .recruit-arrow { color: #c41e3a; }
  .recruit-header-left {
    display: flex; align-items: center; gap: 10px;
  }
  .recruit-header-right {
    display: flex; align-items: center; flex-shrink: 0;
  }
  .recruit-card-title-row { flex: 1; display: flex; align-items: center; justify-content: space-between; gap: 6px; }
  .recruit-count-badge { font-size: 20px; color: #8a8faa; background: #f8f9fc; padding: 3px 10px; border-radius: 10px; }
  .recruit-icon2 { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .recruit-emoji { font-size: 20px; }
  .recruit-name { font-size: 20px; font-weight: 700; color: #1a2b5f; }

  /* 箭头 › */
  .recruit-arrow {
    font-size: 30px; font-weight: 300; color: #bcc5ce;
    transition: color 0.3s ease; line-height: 1;
  }
  .recruit-card-header:hover .recruit-arrow { color: #c41e3a; }

  /* 标题列表包裹 — 可滚动容器 */
  .recruit-title-list-scroll {
    max-height: 400px;
    overflow-y: auto;
    scroll-behavior: smooth;
  }
  .recruit-title-list-scroll::-webkit-scrollbar {
    width: 4px;
  }
  .recruit-title-list-scroll::-webkit-scrollbar-track {
    background: transparent;
  }
  .recruit-title-list-scroll::-webkit-scrollbar-thumb {
    background: #d0d5dd;
    border-radius: 2px;
  }
  .recruit-title-list-scroll::-webkit-scrollbar-thumb:hover {
    background: #a0a8b4;
    width: 8px;
  }

  /* 标题列表 — 纯行高留白，无分割线 */
  .recruit-title-list { display: flex; flex-direction: column; }
  .recruit-title-item {
    display: flex; align-items: center; gap: 8px;
    padding: 9px 0; cursor: pointer; transition: background 0.15s;
  }
  .recruit-title-item:hover { background: rgba(10,22,40,0.02); }

  /* 胶囊状态标签 */
  .status-badge {
    display: inline-block; font-size: 20px; font-weight: 500;
    padding: 3px 12px; border-radius: 20px;
    white-space: nowrap; flex-shrink: 0; min-width: 80px; text-align: center;
  }

  .recruit-title-text {
    font-size: 20px; color: #2c3e50; flex: 1;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }

  /* 空状态 */
  .recruit-empty { text-align: center; padding: 18px 0; }
  .recruit-empty span { font-size: 20px; color: #bcc5ce; }

  /* 招考详情弹窗 */
  .recruit-modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
  .recruit-modal { background: #fff; border-radius: 16px; width: 90%; max-width: 860px; max-height: 85vh; display: flex; flex-direction: column; box-shadow: 0 8px 40px rgba(26,43,95,0.15); overflow: hidden; }
  .recruit-modal-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 24px 28px 16px; border-bottom: 1px solid #f0f2f5; }
  .recruit-modal-title { font-size: 20px; font-weight: 700; color: #1a2b5f; margin: 0; flex: 1; padding-right: 12px; }
  .recruit-modal-close { width: 32px; height: 32px; border: none; background: #f8f9fc; border-radius: 8px; cursor: pointer; font-size: 20px; color: #8a8faa; }
  .recruit-modal-close:hover { background: #f0f2f5; color: #1a2b5f; }
  .recruit-modal-tags { display: flex; align-items: center; gap: 8px; padding: 12px 28px; border-bottom: 1px solid #f8f9fc; flex-wrap: wrap; }
  .recruit-modal-cat { font-size: 20px; font-weight: 600; color: #c41e3a; background: #fef0f2; padding: 3px 12px; border-radius: 10px; }
  .recruit-modal-status { font-size: 20px; font-weight: 500; padding: 3px 12px; border-radius: 20px; }
  .recruit-modal-org { font-size: 20px; color: #5a6488; }
  .recruit-modal-time { font-size: 20px; color: #f59e0b; font-weight: 600; }
  .recruit-modal-body { padding: 20px 28px; overflow-y: auto; flex: 1; max-height: 65vh; }
  .recruit-modal-section { margin-bottom: 16px; }
  .recruit-modal-section h4 { font-size: 20px; font-weight: 700; color: #1a2b5f; margin: 0 0 8px; }
  .recruit-modal-section p { font-size: 20px; line-height: 1.8; color: #33375a; white-space: pre-wrap; margin: 0; }
  .recruit-modal-section .detail-content-html {
    font-size: 18px;
    line-height: 1.9;
    color: #2c3e50;
  }
  .recruit-modal-section .detail-content-html p {
    margin-bottom: 14px;
  }
  .recruit-modal-section .detail-content-html img {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    margin: 12px auto;
    display: block;
  }
  .recruit-modal-section .detail-content-html table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 16px;
  }
  .recruit-modal-section .detail-content-html table td,
  .recruit-modal-section .detail-content-html table th {
    border: 1px solid #e0e4ea;
    padding: 8px 12px;
  }
  .recruit-modal-footer { display: flex; justify-content: flex-end; gap: 12px; padding: 16px 28px; border-top: 1px solid #f0f2f5; }
  .recruit-modal-link { padding: 8px 16px; border-radius: 8px; font-size: 20px; text-decoration: none; color: #5a6488; background: #f8f9fc; }
  .recruit-modal-link:hover { background: #f0f2f5; color: #1a2b5f; }
  .recruit-modal-btn { padding: 8px 20px; border: none; background: #c41e3a; color: #fff; border-radius: 8px; font-size: 20px; font-weight: 600; cursor: pointer; }
  .recruit-modal-btn:hover { background: #a0182e; }

  /* 底层 */
  .footer-section {
    padding: 24px 0 32px;
    text-align: center;
    border-top: 1px solid #e8eaf0;
  }
  .footer-links {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    margin-bottom: 12px;
  }
  .xh{
    width: 20px;
    height: 20px;
    margin-bottom: 0;
    background-image: url(./图片1.png);
  }
  .footer-links a {
    font-size: 13px;
    color: #5a6488;
    text-decoration: none;
    transition: color 0.2s;
  }
  .footer-links a:hover {
    color: #c41e3a;
  }
  .footer-divider {
    color: #d1d5db;
    margin: 0 4px;
  }
  .footer-copy {
    font-size: 11px;
    color: #b0b7c3;
    margin: 0;
  }
</style>
