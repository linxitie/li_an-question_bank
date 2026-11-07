<template>
  <div class="adm-stat" :class="tone ? `is-tone-${tone}` : ''">
    <!-- E3 裁定（2026-11-07）：保留 emoji 图标，但统一尺寸/对齐/透明度，
         不再让各页自己写 20~26px 的乱尺寸。icon 不传则不占位。 -->
    <span v-if="icon" class="adm-stat__icon" aria-hidden="true">{{ icon }}</span>
    <div class="adm-stat__body">
      <div class="adm-stat__value">
        {{ display }}
        <!-- 2026-11-07：双值形态（如「已上架/未上架：103/11」「文章/讲义：3/1」）。
             单个字符串拼不出来是因为两半要不同颜色，所以拆成 value + value2。 -->
        <template v-if="hasSecond">
          <span class="adm-stat__slash">/</span><span class="adm-stat__value2" :class="value2Class">{{ display2 }}</span>
        </template>
      </div>
      <div class="adm-stat__label">{{ label }}</div>
    </div>
    <slot name="suffix" />
  </div>
</template>

<script setup lang="ts">
/**
 * 统计卡（A0）：替换各页自造的 `.stat-card`。
 *
 * 现网问题：dashboard/backup/questions/materials 各有一套 `.stat-card`，
 * 圆角 12/13px、阴影两套、数值字号 24~28px 混用，emoji 尺寸也各写各的。
 *
 * 用法：
 *   <AdminStatCard label="总资料数" :value="119" icon="📚" />
 *   <AdminStatCard label="待审批" :value="2" icon="📄" tone="warn" />
 *   <AdminStatCard label="已上架/未上架" :value="103" :value2="11"
 *                  icon="✅" tone="ok" value2-tone="warn" />
 */
import { computed } from 'vue';

export type StatTone = 'default' | 'primary' | 'ok' | 'warn' | 'danger' | 'info' | 'purple';

const props = withDefaults(
  defineProps<{
    label: string;
    /** 不传或 null 时显示 `—`：区分"数据没回来"和"真的是 0" */
    value?: number | string | null;
    /** 第二个值（双值卡片的右半，如「未上架」数）；不传则只显示单值 */
    value2?: number | string | null;
    /** emoji 图标（E3 保留 emoji） */
    icon?: string;
    tone?: StatTone;
    /** 第二值的颜色；默认跟随弱文色 */
    value2Tone?: StatTone | 'weak';
    /** 副标题/环比等补充说明 */
    hint?: string;
  }>(),
  { tone: 'default', icon: '', hint: '', value2Tone: 'weak' }
);

/** 空值显示 — 而不是空白，避免"数据没回来"看起来像 0 */
function fmt(v: number | string | null | undefined): string {
  if (v === null || v === undefined || v === '') return '—';
  return typeof v === 'number' ? v.toLocaleString('zh-CN') : v;
}

const display = computed(() => fmt(props.value));
const display2 = computed(() => fmt(props.value2));
const hasSecond = computed(() => props.value2 !== undefined && props.value2 !== null);
const value2Class = computed(() =>
  props.value2Tone && props.value2Tone !== 'default' ? `is-tone-${props.value2Tone}` : ''
);
</script>

<style scoped>
.adm-stat {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  padding: var(--adm-s3) var(--adm-s4);
  background: var(--adm-surface);
  border: 1px solid var(--adm-line);
  border-radius: var(--adm-r-card);
  box-shadow: var(--adm-shadow-card);
  font-family: var(--adm-font);
}
.adm-stat__icon {
  flex: none;
  font-size: 20px;
  line-height: 1;
  opacity: 0.92;
}
.adm-stat__body { min-width: 0; }
.adm-stat__value {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.5px;
  color: var(--adm-text);
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
  white-space: nowrap;
}
.adm-stat__slash {
  margin: 0 2px;
  font-size: 20px;
  font-weight: 700;
  color: var(--adm-text-weak);
}
.adm-stat__value2 {
  font-size: 26px;
  font-weight: 800;
  color: var(--adm-text-weak);
}
.adm-stat__value2.is-tone-ok { color: var(--adm-ok); }
.adm-stat__value2.is-tone-warn { color: var(--adm-warn); }
.adm-stat__value2.is-tone-danger { color: var(--adm-danger); }
.adm-stat__value2.is-tone-primary { color: var(--adm-primary); }
.adm-stat__value2.is-tone-info { color: var(--adm-info); }
.adm-stat__value2.is-tone-purple { color: var(--adm-purple); }
.adm-stat__label {
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--adm-text-weak);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 语义着色只作用于数值，标签保持中性灰 */
.adm-stat.is-tone-primary .adm-stat__value { color: var(--adm-primary); }
.adm-stat.is-tone-ok .adm-stat__value { color: var(--adm-ok); }
.adm-stat.is-tone-warn .adm-stat__value { color: var(--adm-warn); }
.adm-stat.is-tone-danger .adm-stat__value { color: var(--adm-danger); }
.adm-stat.is-tone-info .adm-stat__value { color: var(--adm-info); }
.adm-stat.is-tone-purple .adm-stat__value { color: var(--adm-purple); }
</style>
