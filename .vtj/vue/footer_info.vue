<!-- 招考信息（增强版：API驱动 + 3x2网格 + 展开全部） -->
<template>
  <div class="recruit-panel">
    <div class="panel-header">
      <XIcon :icon="Search" :size="20" color="#c41e3a"></XIcon>
      <span class="panel-title">招考信息</span>
      <span class="panel-badge">{{ totalCount }} 条</span>
    </div>

    <!-- 3x2 网格布局 -->
    <div class="recruit-grid">
      <div
        v-for="cat in state.categories"
        :key="cat.key"
        class="recruit-card"
        :class="{ expanded: state.expandedCats.includes(cat.key) }">
        <!-- 卡片头部 -->
        <div class="card-header" @click="toggleCategory(cat.key)">
          <div class="card-header-left">
            <span class="card-icon">{{ cat.icon }}</span>
            <span class="card-title">{{ cat.label }}</span>
            <span class="card-count">{{ getCatCount(cat.key) }}条</span>
          </div>
          <XIcon
            :icon="ArrowRight"
            :size="14"
            :color="state.expandedCats.includes(cat.key) ? '#c41e3a' : '#8899aa'"
            class="card-arrow"
            :class="{ rotated: state.expandedCats.includes(cat.key) }"></XIcon>
        </div>

        <!-- 信息列表 -->
        <div class="card-list">
          <a
            v-for="(item, idx) in getVisibleItems(cat.key)"
            :key="idx"
            :href="item.url || '#'"
            target="_blank"
            class="card-item"
            :title="item.title">
            <span class="item-num">{{ idx + 1 }}</span>
            <span class="item-title">{{ item.title }}</span>
            <XIcon :icon="ArrowRight" :size="11" color="#556677"></XIcon>
          </a>

          <!-- 展开全部按钮 -->
          <div
            v-if="getCatCount(cat.key) > 5"
            class="expand-toggle"
            @click="toggleCategory(cat.key)">
            <span>{{ state.expandedCats.includes(cat.key) ? '收起' : '展开全部（' + getCatCount(cat.key) + '条）' }}</span>
          </div>

          <!-- 暂无数据 -->
          <div v-if="getCatCount(cat.key) === 0" class="card-empty">
            暂无招考信息
          </div>
        </div>
      </div>
    </div>

    <!-- 底部提示 -->
    <div class="panel-footer">
      <span class="footer-hint">数据来源：rszk.net · 每30分钟自动更新</span>
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
    name: 'RecruitmentPanel',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'footer_info', version: '1778907995433' });
      const state = reactive({
        // 按用户指定顺序排列的6个分类
        categories: [
          { key: '国考省考', label: '国考省考', icon: '🏛' },
          { key: '教师招聘', label: '教师招聘', icon: '📚' },
          { key: '事业单位', label: '事业单位', icon: '🏢' },
          { key: '国企招聘', label: '国企招聘', icon: '🏭' },
          { key: '医疗卫生', label: '医疗卫生', icon: '🏥' },
          { key: '三支一扶', label: '三支一扶', icon: '🌾' },
        ],
        // API数据：{ 国考省考: [...], ... }
        items: {},
        // 已展开的分类
        expandedCats: [],
        // 加载状态
        loading: false,
      });
      return { state, props, provider, Search, ArrowRight };
    },
    computed: {
      totalCount() {
        var total = 0;
        var items = this.state.items;
        for (var k in items) {
          if (items.hasOwnProperty(k)) total += items[k].length;
        }
        return total;
      }
    },
    methods: {
      getCatCount(catKey) {
        var items = this.state.items[catKey];
        return items ? items.length : 0;
      },
      getVisibleItems(catKey) {
        var items = this.state.items[catKey] || [];
        if (this.state.expandedCats.includes(catKey)) {
          return items;
        }
        return items.slice(0, 6);
      },
      toggleCategory(catKey) {
        var idx = this.state.expandedCats.indexOf(catKey);
        if (idx >= 0) {
          this.state.expandedCats.splice(idx, 1);
        } else {
          this.state.expandedCats.push(catKey);
        }
      },
      fetchRecruitment() {
        var self = this;
        self.state.loading = true;
        // 使用 VTJ 认证包装器调用 API
        var apiCall;
        if (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.apiFetch) {
          apiCall = window.__VTJ_AUTH__.apiFetch('/api/recruitment?limit=10');
        } else {
          // 回退：直接 fetch
          apiCall = fetch('/api/recruitment?limit=10', {
            headers: { 'Content-Type': 'application/json' }
          }).then(function(r) { return r.json(); });
        }

        apiCall.then(function(data) {
          if (data && data.items) {
            // 按categories顺序映射数据
            var mapped = {};
            for (var i = 0; i < self.state.categories.length; i++) {
              var catKey = self.state.categories[i].key;
              mapped[catKey] = (data.items[catKey] || []).map(function(item) {
                return {
                  title: item.title || '',
                  url: item.url || '#',
                  category: item.category || catKey,
                };
              });
            }
            self.state.items = mapped;
          }
        }).catch(function(err) {
          console.warn('[RecruitmentPanel] API 获取失败:', err);
          // 加载失败显示空状态
          var empty = {};
          for (var j = 0; j < self.state.categories.length; j++) {
            empty[self.state.categories[j].key] = [];
          }
          self.state.items = empty;
        }).finally(function() {
          self.state.loading = false;
        });
      },
    },
    mounted() {
      this.fetchRecruitment();
    }
  })
</script>
<style lang="css" scoped>
  .recruit-panel {
    background: linear-gradient(135deg, #1a2a3a 0%, #1e2e3e 100%);
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
    color: #ffffff;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }

  /* 头部 */
  .panel-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 18px;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  .panel-title {
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 0.5px;
    flex: 1;
  }
  .panel-badge {
    background: rgba(196, 30, 58, 0.2);
    color: #e63946;
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 12px;
    font-weight: 600;
  }

  /* 3x2 网格 */
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

  /* 卡片 */
  .recruit-card {
    background: rgba(255, 255, 255, 0.04);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    overflow: hidden;
    transition: all 0.3s ease;
    min-height: 200px;
  }
  .recruit-card:hover {
    border-color: rgba(196, 30, 58, 0.2);
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
  }
  .recruit-card.expanded {
    border-color: rgba(196, 30, 58, 0.3);
    background: rgba(255, 255, 255, 0.06);
  }

  /* 卡片头部 */
  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 14px 10px;
    cursor: pointer;
    user-select: none;
  }
  .card-header-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
  }
  .card-icon {
    font-size: 18px;
  }
  .card-title {
    font-size: 14px;
    font-weight: 700;
    color: #e0e4ea;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .card-count {
    font-size: 11px;
    color: #8899aa;
    background: rgba(255, 255, 255, 0.06);
    padding: 2px 8px;
    border-radius: 10px;
    white-space: nowrap;
  }
  .card-arrow {
    transition: transform 0.3s ease;
    flex-shrink: 0;
  }
  .card-arrow.rotated {
    transform: rotate(90deg);
  }

  /* 列表 */
  .card-list {
    padding: 0 14px 10px;
  }
  .card-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 8px;
    border-radius: 6px;
    text-decoration: none;
    transition: all 0.2s ease;
    cursor: pointer;
  }
  .card-item:hover {
    background: rgba(196, 30, 58, 0.1);
  }
  .item-num {
    font-size: 11px;
    font-weight: 600;
    color: #556677;
    min-width: 18px;
    text-align: center;
  }
  .item-title {
    flex: 1;
    font-size: 13px;
    color: #c0c8d4;
    line-height: 1.4;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .card-item:hover .item-title {
    color: #e63946;
  }

  /* 展开全部 */
  .expand-toggle {
    text-align: center;
    padding: 8px;
    margin-top: 4px;
    color: #c41e3a;
    font-size: 12px;
    cursor: pointer;
    border-radius: 6px;
    transition: background 0.2s;
  }
  .expand-toggle:hover {
    background: rgba(196, 30, 58, 0.1);
  }

  /* 空状态 */
  .card-empty {
    text-align: center;
    padding: 20px 10px;
    color: #556677;
    font-size: 13px;
  }

  /* 底部 */
  .panel-footer {
    margin-top: 14px;
    padding-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    text-align: center;
  }
  .footer-hint {
    font-size: 11px;
    color: #556677;
  }
</style>
