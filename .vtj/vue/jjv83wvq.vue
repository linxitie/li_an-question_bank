<template>
  <div class="recruitment-info">
    <div class="block-header">
      <XIcon :icon="Search" :size="18" color="#e63946"></XIcon>
      <span class="block-title"> 招考信息</span>
    </div>
    <div class="tab-nav">
      <div
        v-for="(tab, index) in state.tabs"
        :key="index"
        :class="
          Object.assign(
            { 'tab-item': true },
            { active: state.currentTab === index }
          )
        "
        @click="switchTab(index)">
        <span>
          <span> {{ tab.label }}</span>
          <span> </span
        ></span>
        <span v-if="tab.count" class="tab-badge"> {{ tab.count }}</span>
      </div>
    </div>
    <div class="info-list">
      <div
        v-for="(item, idx) in state.filteredItems"
        :key="idx"
        class="info-card"
        @click="handleInfoClick(item)">
        <div class="info-left">
          <div
            class="info-tag div_25k1jv89iw6"
            :style="{
              background: item.tagColor + '20',
              color: item.tagColor
            }">
            {{ item.tag }}
          </div>
        </div>
        <div class="info-center">
          <div class="info-title">
            {{ item.title }}
          </div>
          <div class="info-meta">
            <span> {{ item.organization }}</span>
            <span class="meta-divider"> |</span>
            <span> {{ item.region }}</span>
            <span class="meta-divider"> |</span>
            <span> {{ item.deadline }}</span>
          </div>
        </div>
        <div class="info-right">
          <XIcon :icon="ArrowRight" :size="14" color="#8898a8"></XIcon>
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Search, ArrowRight } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'FooterInfo',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'jjv83wvq', version: '1778907995433' });
      const state = reactive({
        tabs: [
          { label: '国考/省考', count: 12 },
          { label: '事业单位', count: 8 },
          { label: '银行/农信社', count: 5 },
          { label: '医疗/三支一扶', count: 6 },
          { label: '教师', count: 4 },
          { label: '国企', count: 7 }
        ],
        allItems: [
          {
            tabIndex: 0,
            title: '2025年国家公务员考试招录公告',
            organization: '国家公务员局',
            region: '全国',
            deadline: '2024-10-15截止',
            tag: '国考',
            tagColor: '#e63946'
          },
          {
            tabIndex: 0,
            title: '广东省2024年度考试录用公务员公告',
            organization: '广东省公务员局',
            region: '广东',
            deadline: '2024-08-20截止',
            tag: '省考',
            tagColor: '#00b4d8'
          },
          {
            tabIndex: 0,
            title: '浙江省公安机关特殊职位招录',
            organization: '浙江省公安厅',
            region: '浙江',
            deadline: '2024-09-05截止',
            tag: '省考',
            tagColor: '#00b4d8'
          },
          {
            tabIndex: 1,
            title: '北京市事业单位公开招聘工作人员公告',
            organization: '北京市人社局',
            region: '北京',
            deadline: '2024-09-10截止',
            tag: '联考',
            tagColor: '#ffd700'
          },
          {
            tabIndex: 1,
            title: '上海市事业单位招聘公告',
            organization: '上海市人社局',
            region: '上海',
            deadline: '2024-08-25截止',
            tag: '统考',
            tagColor: '#ffd700'
          },
          {
            tabIndex: 2,
            title: '中国工商银行2025年度校园招聘',
            organization: '中国工商银行',
            region: '全国',
            deadline: '2024-10-08截止',
            tag: '银行',
            tagColor: '#6f42c1'
          },
          {
            tabIndex: 2,
            title: '广东省农村信用社联合社招聘',
            organization: '广东省农信社',
            region: '广东',
            deadline: '2024-09-15截止',
            tag: '农信社',
            tagColor: '#6f42c1'
          },
          {
            tabIndex: 3,
            title: '2024年“三支一扶”计划招募公告',
            organization: '人力资源社会保障部',
            region: '全国',
            deadline: '2024-08-30截止',
            tag: '三支一扶',
            tagColor: '#20c997'
          },
          {
            tabIndex: 3,
            title: '广州市医疗卫生单位公开招聘',
            organization: '广州市卫健委',
            region: '广东',
            deadline: '2024-09-12截止',
            tag: '医疗',
            tagColor: '#20c997'
          },
          {
            tabIndex: 4,
            title: '深圳市公办中小学教师招聘公告',
            organization: '深圳市教育局',
            region: '广东',
            deadline: '2024-09-20截止',
            tag: '教师',
            tagColor: '#fd7e14'
          },
          {
            tabIndex: 4,
            title: '北京市海淀区教师招聘',
            organization: '北京市海淀区教委',
            region: '北京',
            deadline: '2024-08-28截止',
            tag: '教师',
            tagColor: '#fd7e14'
          },
          {
            tabIndex: 5,
            title: '国家电网2025年第一批招聘公告',
            organization: '国家电网有限公司',
            region: '全国',
            deadline: '2024-11-10截止',
            tag: '央企',
            tagColor: '#0d6efd'
          },
          {
            tabIndex: 5,
            title: '中国石油2024年秋季招聘',
            organization: '中国石油天然气集团',
            region: '全国',
            deadline: '2024-10-20截止',
            tag: '央企',
            tagColor: '#0d6efd'
          },
          {
            tabIndex: 5,
            title: '广东省交通集团招聘',
            organization: '广东省交通集团',
            region: '广东',
            deadline: '2024-09-08截止',
            tag: '省属国企',
            tagColor: '#0d6efd'
          }
        ],
        currentTab: 0
      });
      return { state, props, provider, Search, ArrowRight };
    },
    computed: {
      filteredItems() {
        return this.state.allItems
          .filter((item) => item.tabIndex === this.state.currentTab)
          .slice(0, 4);
      }
    },
    methods: {
      switchTab(index) {
        this.state.currentTab = index;
      },
      handleInfoClick(item) {
        this.$message.success(`即将跳转至：${item.title}`);
      }
    }
  })
</script>
<style lang="css" scoped>
  .recruitment-info {
    background: linear-gradient(135deg, #1a2a3a 0%, #2a3a4a 100%);
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    color: #ffffff;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .block-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
  }
  .block-title {
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 0.5px;
  }
  .tab-nav {
    display: flex;
    gap: 6px;
    margin-bottom: 16px;
    overflow-x: auto;
    padding-bottom: 4px;
  }
  .tab-item {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
    color: #b0b8c4;
    background: rgba(255, 255, 255, 0.04);
    cursor: pointer;
    transition: all 0.3s ease;
    white-space: nowrap;
    border: 1px solid transparent;
  }
  .tab-item:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #ffffff;
  }
  .tab-item.active {
    background: rgba(230, 57, 70, 0.15);
    color: #e63946;
    border-color: #e63946;
    font-weight: 600;
  }
  .tab-badge {
    background: #e63946;
    color: #ffffff;
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 10px;
    font-weight: 600;
  }
  .info-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .info-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.3s ease;
    border: 1px solid rgba(255, 255, 255, 0.05);
  }
  .info-card:hover {
    background: rgba(255, 255, 255, 0.07);
    border-color: rgba(230, 57, 70, 0.2);
    transform: translateX(4px);
  }
  .info-left {
    display: flex;
    align-items: center;
  }
  .info-tag {
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
  }
  .info-center {
    flex: 1;
    min-width: 0;
  }
  .info-title {
    font-size: 14px;
    font-weight: 500;
    color: #d0d8e0;
    margin-bottom: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .info-meta {
    font-size: 11px;
    color: #8898a8;
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .meta-divider {
    opacity: 0.3;
  }
  .info-right {
    display: flex;
    align-items: center;
  }
</style>
