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
      <section class="recruit-section">
        <div class="section-header">
          <h2 class="section-title">
            <XIcon :icon="Briefcase" :size="20" color="#c41e3a"></XIcon>
            <span> 招考信息</span>
          </h2>
          <span class="section-subtitle">
            最新招考动态，助你把握每一个机会</span
          >
        </div>
        <div class="recruit-grid">
          <div
            v-for="(item, index) in state.recruitCategories"
            :key="item.id"
            class="recruit-card"
            @click="handleRecruitClick(item.id)">
            <div
              class="recruit-icon div_26ozjvebfbw"
              :style="{ background: item.bg }">
              <span class="recruit-emoji"> {{ item.icon }}</span>
            </div>
            <div class="recruit-info">
              <span class="recruit-name"> {{ item.name }}</span>
              <span class="recruit-count"> {{ item.latest }}</span>
            </div>
            <XIcon :icon="ArrowRight" :size="14" color="#cbd5e0"></XIcon>
          </div>
        </div>
      </section>
      <section class="resource-section">
        <div class="section-header">
          <h2 class="section-title">
            <XIcon :icon="Reading" :size="20" color="#c41e3a"></XIcon>
            <span> 备考资料</span>
          </h2>
          <span class="section-subtitle"> 系统化备考，全面提升应试能力</span>
        </div>
        <div class="resource-grid">
          <div class="resource-card xc-card" @click="handleResourceClick('xc')">
            <div class="card-badge">行测</div>
            <h4 class="card-title">行测小讲堂</h4>
            <p class="card-desc">类比推理·拆分思维·组合排列·材料题精讲</p>
            <div class="card-topics">
              <span> 题型分辨</span>
              <span> 组合排列</span>
              <span> 方法技巧</span>
            </div>
            <div class="card-footer">
              <span> 视频+文档</span>
              <XIcon :icon="VideoPlay" :size="16" color="#c41e3a"></XIcon>
            </div>
          </div>
          <div class="resource-card sl-card" @click="handleResourceClick('sl')">
            <div class="card-badge">申论</div>
            <h4 class="card-title">申论小讲堂</h4>
            <p class="card-desc">标题拟定·写作技巧·范文展示·必知知识点</p>
            <div class="card-topics">
              <span> 文章写作</span>
              <span> 范文精读</span>
              <span> 素材积累</span>
            </div>
            <div class="card-footer">
              <span> 视频+文档</span>
              <XIcon :icon="Document" :size="16" color="#c41e3a"></XIcon>
            </div>
          </div>
          <div class="resource-card ga-card" @click="handleResourceClick('ga')">
            <div class="card-badge">公专</div>
            <h4 class="card-title">公安专业知识卡片</h4>
            <p class="card-desc">职业素养·警务技能·基础知识记背</p>
            <div class="card-topics">
              <span> 必背卡片</span>
              <span> 警务技能</span>
              <span> 法条速记</span>
            </div>
            <div class="card-footer">
              <span> 知识卡片</span>
              <XIcon :icon="Tickets" :size="16" color="#c41e3a"></XIcon>
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
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import {
    Briefcase,
    ArrowRight,
    Reading,
    VideoPlay,
    Document,
    Tickets
  } from '@vtj/icons';
  import NavBar from './ijvdn7sw.vue';
  import SignInCard from './wjve09k1.vue';
  import GoalCard from './zjve4pgr.vue';
  import QuoteBanner from './11jve6eq7.vue';
  import CountdownTimer from './kjvdoyca.vue';
  import ExamCalendar from './ljvdpmh9.vue';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'HomePage',
    components: {
      NavBar,
      SignInCard,
      GoalCard,
      QuoteBanner,
      CountdownTimer,
      ExamCalendar,
      XIcon
    },
    setup(props) {
      const provider = useProvider({ id: 'jjvdntly', version: '1778936500684' });
      const state = reactive({ resourceItems: [], recruitCategories: [] });
      return {
        state,
        props,
        provider,
        Briefcase,
        ArrowRight,
        Reading,
        VideoPlay,
        Document,
        Tickets
      };
    },
    computed: {
      recruitCategories() {
        return [
          {
            id: 'gk',
            name: '国考/省考/公务员单招',
            icon: '🏛️',
            latest: '2025国考面试公告已发布',
            bg: 'linear-gradient(135deg, #eef2ff, #e0e7ff)'
          },
          {
            id: 'sy',
            name: '事业单位',
            icon: '🏢',
            latest: '江苏事业单位统考报名中',
            bg: 'linear-gradient(135deg, #fef3c7, #fde68a)'
          },
          {
            id: 'bank',
            name: '银行/农信社',
            icon: '🏦',
            latest: '六大行春招公告汇总',
            bg: 'linear-gradient(135deg, #d1fae5, #a7f3d0)'
          },
          {
            id: 'medical',
            name: '医疗/三支一扶',
            icon: '🏥',
            latest: '三支一扶招募计划启动',
            bg: 'linear-gradient(135deg, #fce7f3, #fbcfe8)'
          },
          {
            id: 'teacher',
            name: '教师',
            icon: '📚',
            latest: '教师资格证笔试报名提醒',
            bg: 'linear-gradient(135deg, #e0f2fe, #bae6fd)'
          },
          {
            id: 'soe',
            name: '国企',
            icon: '🏭',
            latest: '国家电网第二批招聘公告',
            bg: 'linear-gradient(135deg, #faf5ff, #ede9fe)'
          }
        ];
      }
    },
    methods: {
      handleRecruitClick(id) {
        this.$message.info('跳转至招考详情页面：' + id);
      },
      handleResourceClick(type) {
        this.$message.info('跳转至备考资料详情：' + type);
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
  .resource-section {
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
    font-size: 18px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0;
  }
  .section-subtitle {
    font-size: 13px;
    color: #8a8faa;
  }
  .recruit-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
  }
  .recruit-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 16px 14px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    align-items: center;
    gap: 10px;
    box-shadow: 0 1px 8px rgba(26, 43, 95, 0.04);
  }
  .recruit-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 18px rgba(26, 43, 95, 0.1);
  }
  .recruit-icon {
    width: 42px;
    height: 42px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .recruit-emoji {
    font-size: 20px;
  }
  .recruit-info {
    flex: 1;
    min-width: 0;
  }
  .recruit-name {
    font-size: 13px;
    font-weight: 700;
    color: #1a2b5f;
    display: block;
    margin-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .recruit-count {
    font-size: 11px;
    color: #c41e3a;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* 下层模块 */
  .resource-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }
  .resource-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 24px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.05);
    position: relative;
    overflow: hidden;
  }
  .resource-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 24px rgba(26, 43, 95, 0.12);
  }
  .resource-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
    border-radius: 4px 0 0 4px;
  }
  .xc-card::before {
    background: #3b82f6;
  }
  .sl-card::before {
    background: #f59e0b;
  }
  .ga-card::before {
    background: #c41e3a;
  }
  .card-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 12px;
    letter-spacing: 1px;
  }
  .xc-card .card-badge {
    background: #eff6ff;
    color: #3b82f6;
  }
  .sl-card .card-badge {
    background: #fffbeb;
    color: #f59e0b;
  }
  .ga-card .card-badge {
    background: #fef2f2;
    color: #c41e3a;
  }
  .card-title {
    font-size: 17px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0 0 8px;
  }
  .card-desc {
    font-size: 13px;
    color: #5a6488;
    margin: 0 0 12px;
    line-height: 1.5;
  }
  .card-topics {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 16px;
  }
  .card-topics span {
    padding: 4px 10px;
    background: #f8f9fc;
    border-radius: 8px;
    font-size: 11px;
    color: #5a6488;
  }
  .card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    color: #8a8faa;
    padding-top: 12px;
    border-top: 1px dashed #e8eaf0;
  }
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
