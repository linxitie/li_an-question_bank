<template>
  <div class="recruitment-panel">
    <div class="panel-header">
      <div class="header-left">
        <XIcon :icon="Opportunity" :size="22" color="#c8161e"></XIcon>
        <span class="header-title"> 招考信息</span>
      </div>
      <span class="header-badge pulse-dot"> 实时更新</span>
    </div>
    <div class="recruitment-grid">
      <div
        v-for="(item, index) in state.recruitmentList"
        :key="index"
        class="recruitment-card"
        @click="handleRecruitmentClick(item)">
        <div class="card-icon-area">
          <div class="card-icon-circle">
            <XIcon :icon="item.icon" :size="24" :color="item.color"></XIcon>
          </div>
          <div v-if="item.newCount > 0" class="card-badge">
            <span>
              <span>
                <span> {{ item.newCount > 99 ? '99+' : item.newCount }}</span>
                <span> 条新</span></span
              ></span
            >
          </div>
        </div>
        <div class="card-body">
          <span class="card-title"> {{ item.title }}</span>
          <span class="card-subtitle"> {{ item.subtitle }}</span>
        </div>
        <div
          class="card-status-bar div_26h1jvd021f"
          :style="{ background: item.color }"></div>
      </div>
    </div>
    <div class="quick-links">
      <div
        v-for="(link, idx) in state.quickLinks"
        :key="idx"
        class="quick-link-item"
        @click="handleQuickLink(link)">
        <XIcon :icon="link.icon" :size="14" color="#c8161e"></XIcon>
        <span> {{ link.label }}</span>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import {
    Opportunity,
    Files,
    DArrowRight,
    OfficeBuilding,
    Suitcase,
    CreditCard,
    FirstAidKit,
    School,
    Briefcase
  } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'RecruitmentInfo',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'hjv83oby', version: '1778915950685' });
      const state = reactive({
        quickLinks: [
          { label: '查看全部招考', icon: Files },
          { label: '订阅提醒', icon: DArrowRight }
        ],
        recruitmentList: [
          {
            title: '国考/省考',
            subtitle: '公务员单招',
            icon: OfficeBuilding,
            color: '#c8161e',
            newCount: 12,
            route: ''
          },
          {
            title: '事业单位',
            subtitle: '编制考试',
            icon: Suitcase,
            color: '#e67e22',
            newCount: 8,
            route: ''
          },
          {
            title: '银行/农信社',
            subtitle: '金融系统',
            icon: CreditCard,
            color: '#2e86c1',
            newCount: 5,
            route: ''
          },
          {
            title: '医疗/三支一扶',
            subtitle: '基层服务',
            icon: FirstAidKit,
            color: '#27ae60',
            newCount: 3,
            route: ''
          },
          {
            title: '教师招聘',
            subtitle: '教育系统',
            icon: School,
            color: '#8e44ad',
            newCount: 7,
            route: ''
          },
          {
            title: '国企招聘',
            subtitle: '中央企业',
            icon: Briefcase,
            color: '#d35400',
            newCount: 15,
            route: ''
          }
        ]
      });
      return {
        state,
        props,
        provider,
        Opportunity,
        Files,
        DArrowRight,
        OfficeBuilding,
        Suitcase,
        CreditCard,
        FirstAidKit,
        School,
        Briefcase
      };
    },
    methods: {
      handleQuickLink(link) {
        if (link.label === '查看全部招考') {
          this.$message.info('全部招考信息页面加载中...');
        } else {
          this.$message.success('订阅提醒功能已开启');
        }
      },
      handleRecruitmentClick(item) {
        this.$message.info(`正在加载「${item.title}」详细招考信息...`);
      }
    }
  })
</script>
<style lang="css" scoped>
  /* 招考信息面板 */
  .recruitment-panel {
    background: #ffffff;
    border-radius: 16px;
    padding: 24px;
    border: 1px solid #e8ecf1;
    box-shadow: 0 4px 20px rgba(10, 22, 40, 0.06);
  }
  /* 面板标题 */
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .header-title {
    font-size: 19px;
    font-weight: 700;
    color: #1a2a4a;
    letter-spacing: 1.5px;
    background: linear-gradient(135deg, #1a2a4a 0%, #2c3e50 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .header-badge {
    font-size: 11px;
    color: #c8161e;
    background: rgba(200, 22, 30, 0.08);
    padding: 3px 10px;
    border-radius: 12px;
    font-weight: 500;
    position: relative;
  }
  .pulse-dot::before {
    content: '';
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #c8161e;
    margin-right: 4px;
    animation: pulse-dot 2s ease-in-out infinite;
  }
  @keyframes pulse-dot {
    0%,
    100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.4;
      transform: scale(1.5);
    }
  }
  /* 招考卡片网格 */
  .recruitment-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }
  @media (max-width: 1200px) {
    .recruitment-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }
  /* 单个招考卡片 */
  .recruitment-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 18px 12px 0;
    border-radius: 12px;
    background: #fafbfc;
    border: 1px solid #eef1f5;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
    text-align: center;
  }
  .recruitment-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 28px rgba(10, 22, 40, 0.1);
    border-color: rgba(200, 22, 30, 0.2);
    background: #fef5f5;
  }
  .recruitment-card:active {
    transform: scale(0.96);
  }
  /* 图标区域 */
  .card-icon-area {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card-icon-circle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 50px;
    height: 50px;
    border-radius: 50%;
    background: rgba(10, 22, 40, 0.04);
    transition: all 0.3s ease;
  }
  .recruitment-card:hover .card-icon-circle {
    transform: scale(1.08);
    background: rgba(200, 22, 30, 0.08);
  }
  /* 新消息徽章 */
  .card-badge {
    position: absolute;
    top: -8px;
    right: -12px;
    background: linear-gradient(135deg, #c8161e 0%, #a0121a 100%);
    color: #ffffff;
    font-size: 9px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(200, 22, 30, 0.3);
    white-space: nowrap;
    animation: badge-bounce 2s ease-in-out infinite;
  }
  @keyframes badge-bounce {
    0%,
    100% {
      transform: translateY(0);
    }
    50% {
      transform: translateY(-2px);
    }
  }
  /* 卡片内容 */
  .card-body {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding-bottom: 12px;
  }
  .card-title {
    font-size: 13px;
    font-weight: 600;
    color: #2c3e50;
  }
  .card-subtitle {
    font-size: 11px;
    color: #8899aa;
  }
  /* 状态条 */
  .card-status-bar {
    height: 3px;
    width: 100%;
    border-radius: 0 0 12px 12px;
    opacity: 0.6;
    transition: opacity 0.3s ease;
  }
  .recruitment-card:hover .card-status-bar {
    opacity: 1;
  }
  /* 快捷链接 */
  .quick-links {
    display: flex;
    justify-content: center;
    gap: 20px;
    padding-top: 12px;
    border-top: 1px solid #f0f2f5;
  }
  .quick-link-item {
    display: flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    color: #8899aa;
    font-size: 12px;
    transition: all 0.25s ease;
  }
  .quick-link-item:hover {
    color: #c8161e;
    transform: translateX(2px);
  }
  .quick-link-item span {
    border-bottom: 1px dashed transparent;
    transition: border-color 0.25s ease;
  }
  .quick-link-item:hover span {
    border-bottom-color: #c8161e;
  }
</style>
