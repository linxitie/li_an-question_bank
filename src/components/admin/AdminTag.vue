<template>
  <span class="adm-tag" :class="cls"><slot>{{ text }}</slot></span>
</template>

<script setup lang="ts">
/**
 * 徽标（A0）：类型徽标 6 类 + 状态徽标 4 态，色值全部来自 `--adm-*` 令牌。
 *
 * 为什么要有它：现网各页各写一遍 `<span class="tag">`（admin_materials 的 `.type-tag`、
 * dashboard 的 `.badge`、users 的 `.pill`），颜色与圆角都不一致；统一到这里，
 * 一处改全站变（E1 的 `.vtj` 覆盖层也复用同一组 CSS 变量）。
 *
 * 用法：
 *   <AdminTag type="paper">试卷</AdminTag>     ← 资料类型（与 materialTypes.ts 的 key 同集）
 *   <AdminTag tone="ok">已上架</AdminTag>       ← 状态
 *   <AdminTag tone="warn" text="待补全" />      ← 也可用 text 传文案
 */
import { computed } from 'vue';

/** 资料类型（与 `src/modules/library/materialTypes.ts` 的 key 保持一致） */
export type MaterialTagType = 'video_intro' | 'video_advanced' | 'article' | 'card' | 'lecture' | 'paper';
/** 状态/语义色 */
export type TagTone = 'ok' | 'warn' | 'danger' | 'info' | 'primary' | 'muted';

const props = defineProps<{
  type?: MaterialTagType | '';
  tone?: TagTone | '';
  text?: string;
}>();

const cls = computed(() => {
  if (props.type) return `is-type-${props.type}`;
  if (props.tone) return `is-tone-${props.tone}`;
  return '';
});
</script>

<style scoped>
.adm-tag {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: var(--adm-r-tag);
  font-family: var(--adm-font);
  font-size: 10.5px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  background: var(--adm-muted-weak);
  color: var(--adm-muted);
}

/* 资料类型：视频灰 / 文章蓝 / 卡片紫 / 讲义青 / 试卷橙 */
.adm-tag.is-type-video_intro,
.adm-tag.is-type-video_advanced { background: var(--adm-muted-weak); color: var(--adm-muted); }
.adm-tag.is-type-article { background: var(--adm-blue-weak); color: var(--adm-blue); }
.adm-tag.is-type-card { background: var(--adm-purple-weak); color: var(--adm-purple); }
.adm-tag.is-type-lecture { background: var(--adm-info-weak); color: var(--adm-info); }
.adm-tag.is-type-paper { background: var(--adm-warn-weak); color: var(--adm-warn); }

/* 状态 */
.adm-tag.is-tone-ok { background: var(--adm-ok-weak); color: var(--adm-ok); }
.adm-tag.is-tone-warn { background: var(--adm-warn-weak); color: var(--adm-warn); }
.adm-tag.is-tone-danger { background: var(--adm-danger-weak); color: var(--adm-danger); }
.adm-tag.is-tone-info { background: var(--adm-info-weak); color: var(--adm-info); }
.adm-tag.is-tone-primary { background: var(--adm-primary-weak); color: var(--adm-primary-dark); }
.adm-tag.is-tone-muted { background: var(--adm-muted-weak); color: var(--adm-text-sub); }
</style>
