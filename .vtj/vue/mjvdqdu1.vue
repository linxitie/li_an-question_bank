<template>
  <div class="question-bank">
    <NavBar></NavBar>
    <main class="qb-main">
      <section class="qb-top">
        <div class="qb-actions">
          <div ref="actionScrollRef" class="action-scroll">
            <button
              v-for="(item, index) in topActions"
              :key="item.key"
              :class="[
                'action-btn',
                { active: state.activeTopAction === item.key }
              ]"
              @click="handleTopAction(item.key)">
              <span class="action-icon"> {{ item.icon }}</span>
              <span class="action-name"> {{ item.name }}</span>
              <span v-if="item.tag" class="action-tag"> {{ item.tag }}</span>
            </button>
          </div>
          <div class="scroll-indicator left" @click="scrollActions(-200)">
            ‹
          </div>
          <div class="scroll-indicator right" @click="scrollActions(200)">
            ›
          </div>
        </div>
        <div class="qb-sub-actions">
          <button class="sub-btn" @click="handleSubAction('mini')">
            <XIcon :icon="Timer" :size="16" color="#c41e3a"></XIcon>
            <span> 小模考</span>
          </button>
          <button class="sub-btn" @click="handleSubAction('college')">
            <XIcon :icon="Monitor" :size="16" color="#1565c0"></XIcon>
            <span> 院校联考机考系统</span>
          </button>
          <div class="search-box">
            <XIcon :icon="Search" :size="16" color="#8a8faa"></XIcon>
            <input
              v-model="state.searchQuery"
              placeholder="搜索题目..."
              @keyup.enter="handleSearch" />
          </div>
        </div>
      </section>
      <div class="qb-body">
        <div class="qb-left">
          <div class="category-tabs">
            <button
              v-for="(cat, index) in categoryList"
              :key="cat.key"
              :class="['cat-tab', { active: state.activeCategory === cat.key }]"
              @click="switchCategory(cat.key)">
              {{ cat.name }}
            </button>
          </div>
          <div class="subcategory-grid">
            <div
              v-for="(sub, index) in currentSubCategories"
              :key="sub.key"
              class="subcard"
              @click="startPractice(sub.key)">
              <div
                class="subcard-icon div_26rejvefdo6"
                :style="{ background: sub.bg }">
                {{ sub.emoji }}
              </div>
              <div class="subcard-info">
                <span class="subcard-name"> {{ sub.name }}</span>
                <span class="subcard-count">
                  <span>
                    <span> {{ sub.count }}</span>
                    <span> 题</span></span
                  ></span
                >
              </div>
              <XIcon :icon="ArrowRightBold" :size="14" color="#d1d5db"></XIcon>
            </div>
          </div>
        </div>
        <aside class="qb-right">
          <div class="right-card practice-log">
            <div class="right-header">
              <XIcon :icon="DataLine" :size="18" color="#1a2b5f"></XIcon>
              <span> 练习记录</span>
            </div>
            <div class="log-stats">
              <div class="log-item">
                <span class="log-value"> {{ state.practiceLog.today }}</span>
                <span class="log-label"> 今日</span>
              </div>
              <div class="log-item">
                <span class="log-value"> {{ state.practiceLog.week }}</span>
                <span class="log-label"> 本周</span>
              </div>
              <div class="log-item">
                <span class="log-value"> {{ state.practiceLog.total }}</span>
                <span class="log-label"> 累计</span>
              </div>
            </div>
          </div>
          <GoalCard></GoalCard>
          <div class="right-card quick-tools">
            <div class="right-header">
              <span> 快捷工具</span>
            </div>
            <div class="tools-grid">
              <div class="tool-item" @click="navigateTo('rjvduc4b')">
                <XIcon
                  :icon="DocumentDelete"
                  :size="20"
                  color="#ef4444"></XIcon>
                <span> 错题集</span>
              </div>
              <div class="tool-item" @click="handleToolClick('note')">
                <XIcon :icon="Edit" :size="20" color="#3b82f6"></XIcon>
                <span> 笔记</span>
              </div>
              <div class="tool-item" @click="handleToolClick('fav')">
                <XIcon :icon="StarFilled" :size="20" color="#f59e0b"></XIcon>
                <span> 收藏</span>
              </div>
              <div class="tool-item" @click="navigateTo('sjvdul3v')">
                <XIcon :icon="DataAnalysis" :size="20" color="#10b981"></XIcon>
                <span> 成绩分析</span>
              </div>
              <div class="tool-item" @click="navigateTo('tjvdux1w')">
                <XIcon
                  :icon="ShoppingCartFull"
                  :size="20"
                  color="#8b5cf6"></XIcon>
                <span> 金币购</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </main>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import {
    Timer,
    Monitor,
    Search,
    ArrowRightBold,
    DataLine,
    DocumentDelete,
    Edit,
    StarFilled,
    DataAnalysis,
    ShoppingCartFull
  } from '@vtj/icons';
  import NavBar from './ijvdn7sw.vue';
  import GoalCard from './zjve4pgr.vue';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'QuestionBank',
    components: { NavBar, XIcon, GoalCard },
    setup(props) {
      const provider = useProvider({ id: 'mjvdqdu1', version: '1778918346107' });
      const state = reactive({
        practiceLog: { today: 38, week: 256, total: 1289 },
        searchQuery: '',
        activeCategory: 'xc',
        activeTopAction: 'quick'
      });
      return {
        state,
        props,
        provider,
        Timer,
        Monitor,
        Search,
        ArrowRightBold,
        DataLine,
        DocumentDelete,
        Edit,
        StarFilled,
        DataAnalysis,
        ShoppingCartFull
      };
    },
    computed: {
      topActions() {
        return [
          { key: 'quick', name: '快速练习', icon: '⚡', tag: 'NEW' },
          { key: 'history', name: '历年试卷', icon: '📋' },
          { key: 'smart', name: '智能组卷', icon: '🤖' },
          { key: 'ai', name: '联考小智', icon: '🧠', tag: 'AI' }
        ];
      },
      categoryList() {
        return [
          { key: 'xc', name: '行测' },
          { key: 'sl', name: '申论' },
          { key: 'ga', name: '公专' },
          { key: 'custom', name: '自定义刷题' }
        ];
      },
      currentSubCategories() {
        const map = {
          xc: [
            {
              key: 'zzll',
              name: '政治理论',
              count: 128,
              emoji: '📖',
              bg: '#eff6ff'
            },
            {
              key: 'zlfx',
              name: '资料分析',
              count: 96,
              emoji: '📊',
              bg: '#fef2f2'
            },
            {
              key: 'slgx',
              name: '数量关系',
              count: 112,
              emoji: '🔢',
              bg: '#fffbeb'
            },
            { key: 'cs', name: '常识', count: 200, emoji: '💡', bg: '#f0fdf4' },
            {
              key: 'sd',
              name: '速度与知觉训练',
              count: 60,
              emoji: '⏱️',
              bg: '#ede9fe'
            },
            {
              key: 'pdtl',
              name: '判断推理',
              count: 144,
              emoji: '🔍',
              bg: '#fdf2f8'
            },
            {
              key: 'yylj',
              name: '语言理解与表达',
              count: 108,
              emoji: '📝',
              bg: '#e0f2fe'
            }
          ],
          sl: [
            {
              key: 'gngk',
              name: '归纳概括',
              count: 45,
              emoji: '📋',
              bg: '#eff6ff'
            },
            {
              key: 'zhfx',
              name: '综合分析',
              count: 52,
              emoji: '🔬',
              bg: '#fef2f2'
            },
            {
              key: 'tcdc',
              name: '提出对策',
              count: 38,
              emoji: '💬',
              bg: '#fffbeb'
            },
            {
              key: 'yywxz',
              name: '应用文写作',
              count: 30,
              emoji: '✍️',
              bg: '#f0fdf4'
            },
            {
              key: 'ylwxz',
              name: '议论文写作',
              count: 25,
              emoji: '📄',
              bg: '#ede9fe'
            }
          ],
          ga: [
            {
              key: 'zysy',
              name: '职业素养',
              count: 86,
              emoji: '🛡️',
              bg: '#eff6ff'
            },
            {
              key: 'jbjwnl',
              name: '基本警务能力',
              count: 74,
              emoji: '🚔',
              bg: '#fef2f2'
            },
            {
              key: 'jczs',
              name: '基础知识',
              count: 120,
              emoji: '📚',
              bg: '#fffbeb'
            }
          ],
          custom: [
            {
              key: 'custom-all',
              name: '自定义选题',
              count: 0,
              emoji: '⚙️',
              bg: '#f8f9fc'
            }
          ]
        };
        return map[this.state.activeCategory] || [];
      }
    },
    methods: {
      navigateTo(id) {
        this.$router.push('/page/' + id);
      },
      handleSearch() {
        if (this.state.searchQuery.trim()) {
          this.$message.info('搜索：' + this.state.searchQuery);
        }
      },
      scrollActions(offset) {
        const el = this.$refs.actionScrollRef;
        if (el) {
          el.scrollBy({ left: offset, behavior: 'smooth' });
        }
      },
      startPractice(subKey) {
        this.navigateTo('ujvdv5fe');
      },
      switchCategory(key) {
        this.state.activeCategory = key;
      },
      handleSubAction(type) {
        this.$message.info(
          type === 'mini' ? '小模考即将开始' : '院校联考机考系统'
        );
      },
      handleToolClick(type) {
        this.$message.info(type + '功能');
      },
      handleTopAction(key) {
        this.state.activeTopAction = key;
        if (key === 'quick') this.$message.info('进入快速练习模式');
        else if (key === 'history') this.$message.info('查看历年试卷');
        else if (key === 'smart') this.$message.info('智能组卷生成中...');
        else if (key === 'ai') this.$message.info('联考小智助手已上线');
      }
    }
  })
</script>
<style lang="css" scoped>
  .question-bank {
    min-height: 100vh;
    background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .qb-main {
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px 32px 40px;
  }
  /* 上层 */
  .qb-top {
    margin-bottom: 24px;
  }
  .qb-actions {
    position: relative;
    margin-bottom: 12px;
  }
  .action-scroll {
    display: flex;
    gap: 12px;
    overflow-x: auto;
    scrollbar-width: none;
    padding: 4px 0;
  }
  .action-scroll::-webkit-scrollbar {
    display: none;
  }
  .scroll-indicator {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    width: 28px;
    height: 28px;
    background: #ffffff;
    border-radius: 50%;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 18px;
    color: #5a6488;
    z-index: 2;
  }
  .scroll-indicator.left {
    left: -8px;
  }
  .scroll-indicator.right {
    right: -8px;
  }
  .action-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 14px 24px;
    border: none;
    border-radius: 14px;
    background: #ffffff;
    cursor: pointer;
    transition: all 0.3s;
    white-space: nowrap;
    box-shadow: 0 2px 10px rgba(26, 43, 95, 0.04);
  }
  .action-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(26, 43, 95, 0.1);
  }
  .action-btn.active {
    background: linear-gradient(135deg, #1a2b5f, #1e3470);
    box-shadow: 0 4px 18px rgba(26, 43, 95, 0.3);
  }
  .action-btn.active .action-name {
    color: #ffffff;
  }
  .action-icon {
    font-size: 20px;
  }
  .action-name {
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
  }
  .action-tag {
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 6px;
    background: #c41e3a;
    color: #fff;
    font-weight: 700;
  }
  .qb-sub-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .sub-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border: 1px solid #e8eaf0;
    border-radius: 10px;
    background: #ffffff;
    font-size: 13px;
    font-weight: 600;
    color: #1a2b5f;
    cursor: pointer;
    transition: all 0.3s;
  }
  .sub-btn:hover {
    border-color: #c41e3a;
  }
  .search-box {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-left: auto;
    padding: 8px 16px;
    background: #ffffff;
    border-radius: 10px;
    border: 1px solid #e8eaf0;
    width: 240px;
  }
  .search-box input {
    border: none;
    outline: none;
    font-size: 13px;
    flex: 1;
    color: #1a2b5f;
  }
  /* 主体 */
  .qb-body {
    display: grid;
    grid-template-columns: 1fr 300px;
    gap: 24px;
  }
  .category-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 20px;
    background: #ffffff;
    border-radius: 12px;
    padding: 4px;
    box-shadow: 0 1px 8px rgba(26, 43, 95, 0.04);
  }
  .cat-tab {
    flex: 1;
    padding: 12px;
    border: none;
    background: transparent;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 700;
    color: #5a6488;
    cursor: pointer;
    transition: all 0.3s;
  }
  .cat-tab.active {
    background: #1a2b5f;
    color: #ffffff;
    box-shadow: 0 2px 10px rgba(26, 43, 95, 0.3);
  }
  .subcategory-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  .subcard {
    background: #ffffff;
    border-radius: 14px;
    padding: 18px 16px;
    cursor: pointer;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    gap: 12px;
    box-shadow: 0 1px 8px rgba(26, 43, 95, 0.04);
  }
  .subcard:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 18px rgba(26, 43, 95, 0.1);
  }
  .subcard-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
  }
  .subcard-info {
    flex: 1;
  }
  .subcard-name {
    font-size: 14px;
    font-weight: 700;
    color: #1a2b5f;
    display: block;
    margin-bottom: 4px;
  }
  .subcard-count {
    font-size: 11px;
    color: #8a8faa;
  }
  /* 右侧 */
  .qb-right {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .right-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  }
  .right-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 700;
    color: #1a2b5f;
    margin-bottom: 14px;
  }
  .log-stats {
    display: flex;
    justify-content: space-around;
  }
  .log-item {
    text-align: center;
  }
  .log-value {
    display: block;
    font-size: 22px;
    font-weight: 900;
    color: #1a2b5f;
    font-family: 'DIN Alternate', sans-serif;
  }
  .log-label {
    font-size: 11px;
    color: #8a8faa;
  }
  .tools-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }
  .tool-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 12px 4px;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.3s;
    font-size: 11px;
    color: #5a6488;
    background: #f8f9fc;
  }
  .tool-item:hover {
    background: #f0f2f5;
    transform: scale(1.03);
  }
</style>
