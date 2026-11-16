<template>
  <section class="news-ai-card">
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

    <div v-if="orderedEntities.length" class="ai-section">
      <h3>实体</h3>
      <div class="entity-tags">
        <span
          v-for="entity in orderedEntities"
          :key="entity.key"
          :class="['entity-tag', `entity-tag--${entity.kind}`]">
          {{ entity.name }}
        </span>
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
}>();

const examPoints = computed(() => props.examPoints || []);

const typeOrder: Record<string, number> = {
  organization: 1,
  policy: 2,
  person: 3,
  region: 4
};

const orderedEntities = computed(() => {
  const seen = new Set<string>();
  return (props.entities || [])
    .filter((entity) => entity && entity.name)
    .map((entity) => {
      const kind = (entity.type || 'other').toLowerCase();
      return {
        key: `${kind}:${entity.name}`,
        kind: typeOrder[kind] ? kind : 'other',
        name: entity.name
      };
    })
    .filter((entity) => {
      if (seen.has(entity.key)) return false;
      seen.add(entity.key);
      return true;
    })
    .sort(
      (a, b) =>
        (typeOrder[a.kind] || 5) - (typeOrder[b.kind] || 5) ||
        a.name.localeCompare(b.name, 'zh-CN')
    );
});
</script>

<style scoped>
.news-ai-card {
  margin: 18px 0;
  padding: 20px 24px;
  border: 1px solid #ece8df;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(31, 35, 33, 0.06);
  color: #2b332e;
}

.ai-section {
  padding: 15px 0;
  border-bottom: 1px solid #f3f0ea;
}

.ai-section:first-child {
  padding-top: 0;
}

.ai-section:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.ai-section h3 {
  margin: 0 0 9px;
  color: #34413a;
  font-size: 15px;
  font-weight: 700;
}

.ai-summary {
  margin: 0;
  color: #4a534d;
  font-size: 14px;
  line-height: 1.8;
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

.entity-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.entity-tag {
  display: inline-flex;
  align-items: center;
  padding: 5px 11px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1.45;
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

@media (max-width: 640px) {
  .news-ai-card {
    padding: 16px;
  }
}
</style>
