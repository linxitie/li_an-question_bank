<!-- 备考资料模块 -->
<template>
  <div class="materials-panel">
    <div class="panel-header">
      <div class="header-left">
        <XIcon :icon="ReadingLamp" :size="22" color="#c8161e"></XIcon>
        <span class="header-title"> 备考资料</span>
      </div>
      <span class="header-desc"> 精选干货，助你上岸</span>
    </div>
    <div class="tab-bar">
      <div
        v-for="(tab, index) in state.tabList"
        :key="tab.key"
        :class="['tab-item', { 'tab-active': state.activeTab === tab.key }]"
        @click="handleTabClick(tab.key)">
        <XIcon
          :icon="tab.icon"
          :size="16"
          :color="state.activeTab === tab.key ? '#ffffff' : '#8899aa'"></XIcon>
        <span> {{ tab.label }}</span>
      </div>
    </div>
    <div class="materials-grid">
      <div v-if="state.activeTab === 'xingce'" class="material-category">
        <div class="category-header">
          <XIcon :icon="EditPen" :size="18" color="#1a2a4a"></XIcon>
          <span class="category-title"> 行测小讲堂</span>
        </div>
        <div class="category-items">
          <div
            v-for="(item, idx) in state.xingceMaterials"
            :key="idx"
            class="material-item"
            @click="handleMaterialClick(item)">
            <div class="item-icon">
              <XIcon :icon="item.icon" :size="20" color="#c8161e"></XIcon>
            </div>
            <div class="item-content">
              <span class="item-title"> {{ item.title }}</span>
              <span class="item-desc"> {{ item.desc }}</span>
            </div>
            <div v-if="item.badge" class="item-badge">
              {{ item.badge }}
            </div>
            <XIcon
              :icon="DArrowRight"
              :size="14"
              class="item-arrow"
              color="#c0c8d4"></XIcon>
          </div>
        </div>
      </div>
      <div v-if="state.activeTab === 'shenlun'" class="material-category">
        <div class="category-header">
          <XIcon :icon="Document" :size="18" color="#1a2a4a"></XIcon>
          <span class="category-title"> 申论小讲堂</span>
        </div>
        <div class="category-items">
          <div
            v-for="(item, idx) in state.shenlunMaterials"
            :key="idx"
            class="material-item"
            @click="handleMaterialClick(item)">
            <div class="item-icon">
              <XIcon :icon="item.icon" :size="20" color="#c8161e"></XIcon>
            </div>
            <div class="item-content">
              <span class="item-title"> {{ item.title }}</span>
              <span class="item-desc"> {{ item.desc }}</span>
            </div>
            <div v-if="item.badge" class="item-badge">
              {{ item.badge }}
            </div>
            <XIcon
              :icon="DArrowRight"
              :size="14"
              class="item-arrow"
              color="#c0c8d4"></XIcon>
          </div>
        </div>
      </div>
      <div v-if="state.activeTab === 'gongzhuan'" class="material-category">
        <div class="category-header">
          <XIcon :icon="Medal" :size="18" color="#1a2a4a"></XIcon>
          <span class="category-title"> 公安专业知识卡片</span>
        </div>
        <div class="category-items">
          <div
            v-for="(item, idx) in state.gongzhuanMaterials"
            :key="idx"
            class="material-item"
            @click="handleMaterialClick(item)">
            <div class="item-icon">
              <XIcon :icon="item.icon" :size="20" color="#c8161e"></XIcon>
            </div>
            <div class="item-content">
              <span class="item-title"> {{ item.title }}</span>
              <span class="item-desc"> {{ item.desc }}</span>
            </div>
            <div v-if="item.badge" class="item-badge">
              {{ item.badge }}
            </div>
            <XIcon
              :icon="DArrowRight"
              :size="14"
              class="item-arrow"
              color="#c0c8d4"></XIcon>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import {
    ReadingLamp,
    EditPen,
    DArrowRight,
    Document,
    Medal,
    DataAnalysis,
    Notebook,
    Collection,
    Reading,
    TrophyBase,
    School
  } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'StudyMaterials',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'study_materials', version: '1778915843581' });
      const state = reactive({
        tabList: [
          { key: 'xingce', label: '行测', icon: EditPen },
          { key: 'shenlun', label: '申论', icon: Document },
          { key: 'gongzhuan', label: '公专', icon: Medal }
        ],
        activeTab: 'xingce',
        xingceMaterials: [
          {
            title: '类比推理-拆分思维',
            desc: '题型分辨不清？掌握拆分思维轻松应对',
            icon: DataAnalysis,
            badge: '热门'
          },
          {
            title: '组合排列材料题',
            desc: '材料题解题思路与技巧详解',
            icon: Notebook,
            badge: '精华'
          },
          {
            title: '组合排列方法精讲',
            desc: '排列组合常见误区与高效方法',
            icon: Collection,
            badge: ''
          }
        ],
        shenlunMaterials: [
          {
            title: '拟定文章标题技巧',
            desc: '如何写出高分申论标题',
            icon: EditPen,
            badge: '精华'
          },
          {
            title: '文章写作技巧精讲',
            desc: '从结构到语言的全面指导',
            icon: Document,
            badge: '热门'
          },
          {
            title: '申论范文展示',
            desc: '历年高分范文深度赏析',
            icon: Reading,
            badge: ''
          },
          {
            title: '申论必知知识点',
            desc: '核心考点与答题模板',
            icon: Notebook,
            badge: ''
          }
        ],
        gongzhuanMaterials: [
          {
            title: '职业素养必背',
            desc: '公安职业素养核心知识卡片',
            icon: Medal,
            badge: '重要'
          },
          {
            title: '基本警务技能了解',
            desc: '警务实战技能要点速记',
            icon: TrophyBase,
            badge: ''
          },
          {
            title: '基础知识记背',
            desc: '公安基础法律知识卡片',
            icon: School,
            badge: '精华'
          }
        ]
      });
      return {
        state,
        props,
        provider,
        ReadingLamp,
        EditPen,
        DArrowRight,
        Document,
        Medal,
        DataAnalysis,
        Notebook,
        Collection,
        Reading,
        TrophyBase,
        School
      };
    },
    methods: {
      handleTabClick(key) {
        this.state.activeTab = key;
      },
      handleMaterialClick(item) {
        this.$message.info(`正在加载「${item.title}」详细内容...`);
      }
    }
  })
</script>
<style lang="css" scoped>
  /* 备考资料面板 */
  .materials-panel {
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
    padding-bottom: 14px;
    border-bottom: 2px solid #f0f2f5;
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
  .header-desc {
    font-size: 12px;
    color: #8899aa;
    font-weight: 500;
  }
  /* Tab切换栏 */
  .tab-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    background: #f5f7fa;
    border-radius: 10px;
    padding: 4px;
  }
  .tab-item {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    color: #778899;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid transparent;
  }
  .tab-item:hover {
    color: #c8161e;
    background: rgba(200, 22, 30, 0.05);
  }
  .tab-item.tab-active {
    background: linear-gradient(135deg, #0d1b2a 0%, #152238 100%);
    color: #ffffff;
    font-weight: 600;
    border-color: rgba(200, 22, 30, 0.3);
    box-shadow: 0 4px 12px rgba(10, 22, 40, 0.2);
    transform: translateY(-1px);
  }
  .tab-item:active {
    transform: scale(0.96);
  }
  /* 内容网格 */
  .materials-grid {
    min-height: 200px;
  }
  /* 分类区块 */
  .material-category {
    animation: fadeInUp 0.4s ease;
  }
  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  .category-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    padding-bottom: 10px;
    border-bottom: 1px dashed #e8ecf1;
  }
  .category-title {
    font-size: 15px;
    font-weight: 600;
    color: #1a2a4a;
  }
  /* 资料项列表 */
  .category-items {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  /* 单个资料项 */
  .material-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 16px;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.3s ease;
    border: 1px solid transparent;
    background: #fafbfc;
    position: relative;
    overflow: hidden;
  }
  .material-item::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    width: 3px;
    background: #c8161e;
    border-radius: 0 3px 3px 0;
    transform: scaleY(0);
    transition: transform 0.3s ease;
  }
  .material-item:hover::before {
    transform: scaleY(1);
  }
  .material-item:hover {
    background: #fef5f5;
    border-color: rgba(200, 22, 30, 0.12);
    transform: translateX(4px);
    box-shadow: 0 4px 16px rgba(200, 22, 30, 0.08);
  }
  /* 图标 */
  .item-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: rgba(200, 22, 30, 0.06);
    flex-shrink: 0;
  }
  .material-item:hover .item-icon {
    background: rgba(200, 22, 30, 0.12);
    transform: scale(1.05);
    transition: all 0.3s ease;
  }
  /* 内容 */
  .item-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }
  .item-title {
    font-size: 14px;
    font-weight: 600;
    color: #2c3e50;
  }
  .item-desc {
    font-size: 12px;
    color: #8899aa;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* 徽章 */
  .item-badge {
    font-size: 10px;
    font-weight: 600;
    color: #ffffff;
    background: linear-gradient(135deg, #c8161e 0%, #a0121a 100%);
    padding: 2px 8px;
    border-radius: 4px;
    flex-shrink: 0;
  }
  /* 箭头 */
  .item-arrow {
    flex-shrink: 0;
    opacity: 0;
    transition: all 0.3s ease;
  }
  .material-item:hover .item-arrow {
    opacity: 1;
    transform: translateX(2px);
  }
</style>
