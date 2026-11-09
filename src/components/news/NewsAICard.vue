<template>
  <section class="news-ai-card">
    <header class="news-ai-card__header">
      <div>
        <div class="news-ai-card__eyebrow">AI 预审</div>
        <h2>新闻摘要与考点</h2>
      </div>
      <span v-if="status" class="news-ai-card__status">{{ statusText }}</span>
    </header>

    <div v-if="summary" class="ai-section">
      <h3>AI 摘要</h3>
      <p class="ai-summary">{{ summary }}</p>
    </div>

    <div v-if="examPoints.length" class="ai-section">
      <h3>申论考点</h3>
      <ul class="exam-point-list">
        <li v-for="(point, index) in examPoints" :key="point">
          <span class="exam-point-index">{{ index + 1 }}</span>
          <span>{{ point }}</span>
        </li>
      </ul>
    </div>

    <div v-if="entityGroups.length" class="ai-section">
      <h3>实体</h3>
      <div class="entity-groups">
        <div
          v-for="group in entityGroups"
          :key="group.key"
          class="entity-group">
          <span class="entity-group__label">{{ group.label }}</span>
          <div class="entity-group__tags">
            <span
              v-for="entity in group.items"
              :key="group.key + entity.name"
              :class="['entity-tag', `entity-tag--${group.key}`]">
              {{ entity.name }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="riskFlags.length" class="ai-section">
      <div class="risk-alert" role="alert">
        <span class="risk-alert__icon" aria-hidden="true">!</span>
        <div>
          <h3>风险提示</h3>
          <ul>
            <li v-for="risk in riskFlags" :key="risk">{{ risk }}</li>
          </ul>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

export interface NewsEntity {
  type?: string;
  name: string;
}

const props = defineProps<{
  summary?: string;
  examPoints?: string[];
  entities?: NewsEntity[];
  riskFlags?: string[];
  status?: string;
}>();

const examPoints = computed(() => props.examPoints || []);
const riskFlags = computed(() => props.riskFlags || []);

const typeMeta: Record<string, { label: string; order: number }> = {
  organization: { label: '组织', order: 1 },
  policy: { label: '政策', order: 2 },
  person: { label: '人物', order: 3 },
  region: { label: '地域', order: 4 }
};

const statusText = computed(() => {
  if (props.status === 'ok') return '已处理';
  if (props.status === 'high_risk') return '高风险';
  return props.status || '';
});

const entityGroups = computed(() => {
  const groups = new Map<
    string,
    { key: string; label: string; order: number; items: NewsEntity[] }
  >();

  for (const entity of props.entities || []) {
    const key = (entity.type || 'other').toLowerCase();
    const meta = typeMeta[key] || { label: '其他', order: 5 };
    if (!groups.has(key)) {
      groups.set(key, { key, label: meta.label, order: meta.order, items: [] });
    }
    groups.get(key)?.items.push(entity);
  }

  return Array.from(groups.values()).sort((a, b) => a.order - b.order);
});
</script>

<style scoped>
.news-ai-card {
  margin: 22px 0;
  padding: 24px 26px;
  border: 1px solid #ece8df;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(31, 35, 33, 0.06);
  color: #2b332e;
}

.news-ai-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f1eee7;
}

.news-ai-card__eyebrow {
  color: #2f5d50;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.news-ai-card__header h2 {
  margin: 4px 0 0;
  color: #1f2321;
  font-size: 18px;
  font-weight: 700;
}

.news-ai-card__status {
  flex: 0 0 auto;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eaf4ee;
  color: #2f6b57;
  font-size: 12px;
  font-weight: 600;
}

.ai-section {
  padding: 18px 0;
  border-bottom: 1px solid #f3f0ea;
}

.ai-section:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.ai-section h3 {
  margin: 0 0 10px;
  color: #34413a;
  font-size: 15px;
  font-weight: 700;
}

.ai-summary {
  margin: 0;
  color: #4a534d;
  font-size: 14px;
  line-height: 1.85;
}

.exam-point-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.exam-point-list li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 12px;
  border: 1px solid #e3eef9;
  border-radius: 10px;
  background: #f5f9ff;
  color: #385269;
  font-size: 14px;
  line-height: 1.65;
}

.exam-point-index {
  flex: 0 0 20px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #dcecff;
  color: #3d6e9e;
  font-size: 11px;
  font-weight: 700;
  line-height: 20px;
  text-align: center;
}

.entity-groups {
  display: grid;
  gap: 12px;
}

.entity-group {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.entity-group__label {
  flex: 0 0 42px;
  padding-top: 4px;
  color: #8a938c;
  font-size: 12px;
}

.entity-group__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.entity-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 9px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.4;
}

.entity-tag--organization {
  background: #f2ecfb;
  color: #6c4aa4;
}

.entity-tag--policy {
  background: #eaf5ed;
  color: #34724e;
}

.entity-tag--person {
  background: #eaf2fb;
  color: #356a9c;
}

.entity-tag--region {
  background: #fff3e4;
  color: #95632e;
}

.entity-tag--other {
  background: #f2f3f1;
  color: #68716b;
}

.risk-alert {
  display: flex;
  gap: 10px;
  padding: 13px 14px;
  border-left: 4px solid #d77a68;
  border-radius: 8px;
  background: #fff5f3;
}

.risk-alert__icon {
  flex: 0 0 20px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #f2c4ba;
  color: #a33b2d;
  font-size: 13px;
  font-weight: 700;
  line-height: 20px;
  text-align: center;
}

.risk-alert h3 {
  margin: 0 0 6px;
  color: #9d4436;
  font-size: 14px;
  font-weight: 700;
}

.risk-alert ul {
  margin: 0;
  padding-left: 18px;
  color: #8f5147;
  font-size: 13px;
  line-height: 1.75;
}

@media (max-width: 640px) {
  .news-ai-card {
    padding: 18px 16px;
  }

  .entity-group {
    display: block;
  }

  .entity-group__label {
    display: block;
    margin-bottom: 5px;
  }
}
</style>
