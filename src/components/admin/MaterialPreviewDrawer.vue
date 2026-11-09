<template>
  <Teleport to="body">
    <div v-if="open" class="mpd-root">
      <div class="mpd-mask" @click="emit('close')" />
      <aside class="mpd-panel" role="dialog" aria-modal="true" :aria-label="preview?.title || '资料预览'">
        <header class="mpd-head">
          <div class="mpd-head__text">
            <h3 class="mpd-title">{{ preview?.title || '加载中…' }}</h3>
            <div class="mpd-tags">
              <AdminTag v-if="preview" :type="preview.type">{{ preview.type_label }}</AdminTag>
              <span v-if="preview" class="mpd-chip">{{ preview.subject_label }}</span>
              <span v-if="preview?.category" class="mpd-chip">{{ preview.category }}</span>
              <AdminTag v-if="preview" :tone="preview.status === 1 ? 'ok' : 'muted'">
                {{ preview.status === 1 ? '已上架' : '未上架' }}
              </AdminTag>
            </div>
          </div>
          <button class="mpd-x" type="button" aria-label="关闭" @click="emit('close')">✕</button>
        </header>

        <div class="mpd-meta">
          <span>发布者：{{ preview?.publisher ? `${preview.publisher.name}（${preview.publisher.role_label}）` : '—' }}</span>
          <span>上传时间：<b class="adm-mono">{{ fmt(preview?.created_at) }}</b></span>
          <span v-if="preview?.uploaded_at">文件上传于：<b class="adm-mono">{{ fmt(preview.uploaded_at) }}</b></span>
          <span v-if="preview?.doc?.word_count">字数：<b>{{ preview.doc.word_count_label }}</b></span>
          <span>浏览 {{ preview?.view_count ?? 0 }} · 学习 {{ preview?.study_count ?? 0 }}</span>
        </div>

        <div class="mpd-body">
          <p v-if="loading" class="adm-empty">加载中…</p>
          <p v-else-if="error" class="mpd-error">{{ error }}</p>

          <!-- 卡片：正 / 背 / 配图 -->
          <template v-else-if="preview?.card">
            <section class="mpd-block">
              <div class="mpd-block__label">正面</div>
              <div class="mpd-face">{{ preview.card.front || '—' }}</div>
            </section>
            <section class="mpd-block">
              <div class="mpd-block__label">背面</div>
              <div class="mpd-face mpd-face--back">{{ preview.card.back || '—' }}</div>
            </section>
            <section v-if="preview.card.images.length" class="mpd-block">
              <div class="mpd-block__label">配图（{{ preview.card.images.length }}）</div>
              <div class="mpd-imgs">
                <img v-for="img in preview.card.images" :key="img" :src="img" alt="卡片配图" />
              </div>
            </section>
          </template>

          <!-- 视频 -->
          <template v-else-if="preview?.video">
            <video v-if="preview.video.url" class="mpd-video" :src="preview.video.url" controls />
            <p v-else class="adm-empty">该资料未绑定视频文件</p>
          </template>

          <!-- 文章 / 讲义 / 试卷：正文 HTML（服务端已 sanitize） -->
          <template v-else-if="preview?.content_html">
            <!-- eslint-disable-next-line vue/no-v-html -->
            <article class="mpd-html" v-html="preview.content_html" />
          </template>

          <p v-else class="adm-empty">该类型暂无预览内容</p>

          <!-- 后续批次占位：有数据才渲染，契约不变 -->
          <section v-if="preview?.chapters?.length" class="mpd-block">
            <div class="mpd-block__label">
              章节（{{ preview.chapters.length }}）
              <span v-if="preview.doc?.word_count" class="mpd-hint">
                · 共 {{ preview.doc.word_count_label }}
              </span>
            </div>
            <ul class="mpd-toc">
              <li v-for="(c, i) in preview.chapters" :key="i" :class="`is-lv${c.level}`">
                <span class="mpd-toc__dot" />{{ c.title }}
              </li>
            </ul>
          </section>
          <!-- C2/C4（2026-11-08）：试卷元数据 + 题库关联 -->
          <section v-if="preview?.paper" class="mpd-block">
            <div class="mpd-block__label">试卷信息</div>
            <dl class="mpd-paper">
              <div><dt>编号</dt><dd class="mpd-mono">{{ preview.paper.paper_code || '—' }}</dd></div>
              <div><dt>年份</dt><dd>{{ preview.paper.year ?? '—' }}</dd></div>
              <div><dt>地区</dt><dd>{{ preview.paper.region_name || '—' }}</dd></div>
              <div><dt>卷别</dt><dd>{{ preview.paper.book_kind_label || '—' }}</dd></div>
              <div><dt>题量</dt><dd>{{ preview.paper.question_count ?? '—' }}</dd></div>
              <div><dt>总分</dt><dd>{{ preview.paper.total_score ?? '—' }}</dd></div>
              <div><dt>时长</dt><dd>{{ preview.paper.duration ? preview.paper.duration + ' 分钟' : '—' }}</dd></div>
              <div>
                <dt>可作答卷</dt>
                <dd>
                  <AdminTag v-if="preview.paper.exam_paper_id" :tone="preview.paper.answerable ? 'ok' : 'muted'">
                    {{ preview.paper.answerable ? '已关联 · 可考' : '已关联 · 暂不可考' }}
                  </AdminTag>
                  <span v-else class="mpd-hint">题库里还没有这套卷</span>
                </dd>
              </div>
              <!-- P2（2026-11-09）：不可考时把原因写清楚（关闭/未开始/已结束/0 题），
                   否则管理员只能看到"暂不可考"却不知道是开关关了还是没导题 -->
              <div v-if="preview.paper.exam_paper_id && !preview.paper.answerable">
                <dt>原因</dt>
                <dd class="mpd-hint">{{ preview.paper.exam_hint || '暂时不能开考' }}</dd>
              </div>
            </dl>
          </section>

          <section v-if="preview?.files?.length" class="mpd-block">
            <div class="mpd-block__label">原件（{{ preview.files.length }}）</div>
            <ul class="mpd-files">
              <li v-for="f in preview.files" :key="f.file_id">
                <button type="button" class="mpd-file" @click="onDownload(f)">
                  <span class="mpd-file__ext">{{ (f.file_ext || '').toUpperCase() }}</span>
                  <span class="mpd-file__name">{{ f.file_name }}</span>
                  <span class="mpd-file__meta">{{ f.role_label }} · {{ f.size_label }}</span>
                  <span class="mpd-file__dl">下载</span>
                </button>
              </li>
            </ul>
          </section>
        </div>

        <footer class="mpd-foot">
          <span class="mpd-hint">只读预览 · 编辑请走列表「编辑 / 改信息」</span>
          <button class="adm-btn" type="button" @click="emit('close')">关闭</button>
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * 资料预览抽屉（A3）
 *
 * 为什么一个组件覆盖 6 类：管理端每行只要一个「预览」按钮，抽屉内部按 `type` 分支渲染。
 * 好处是列表页只需记一个开关状态（`open` + 当前 id），不用为每类挂不同弹层；
 * 也避免 6 个几乎一样的弹层组件各自漂移。
 *
 * 数据来源：`GET /api/materials/admin/{id}/preview`（见 `@/modules/library/api`）。
 * 组件本身**不发请求**，由调用方传 `preview`/`loading`/`error`——方便在组件库预览页用假数据演示，
 * 也方便 A4 在列表里复用同一份状态。
 *
 * 安全：正文用 `v-html`，但内容已由服务端 `sanitize_html` 二次清洗（见后端 A3 端点）。
 */
import { onBeforeUnmount, ref, watch } from 'vue';
import { AdminTag } from '@/components/admin';
import { downloadMaterialFile, type MaterialFileItem, type MaterialPreview } from '@/modules/library/api';
import { errorMessage } from '@/utils/apiError';
import { notify } from '@/utils/overlay';

const props = withDefaults(
  defineProps<{
    open: boolean;
    preview?: MaterialPreview | null;
    loading?: boolean;
    error?: string;
  }>(),
  { preview: null, loading: false, error: '' }
);

const emit = defineEmits<{ (e: 'close'): void }>();

/** `2026-11-05T21:12:00+08:00` → `2026-11-05 21:12`；空值显示 — */
function fmt(iso?: string | null): string {
  if (!iso) return '—';
  const d = iso.replace('T', ' ');
  return d.slice(0, 16);
}

/** ESC 关闭（只在本组件打开时挂监听，卸载时摘掉） */
function onKey(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) emit('close');
}

/**
 * 下载原件（B1）。
 * 下载接口要 token，不能裸 `<a href>`；失败要把服务端原因原样告诉管理员
 * （最常见的是「原件已丢失」和「未上架不可下载」两种 404/403）。
 */
const downloading = ref<number | null>(null);
async function onDownload(f: MaterialFileItem): Promise<void> {
  if (downloading.value !== null) return;
  downloading.value = f.file_id;
  try {
    await downloadMaterialFile(f);
    notify('success', `已开始下载 ${f.file_name}`);
  } catch (e) {
    notify('error', errorMessage(e, '下载失败'));
  } finally {
    downloading.value = null;
  }
}

watch(
  () => props.open,
  (open) => {
    if (typeof window === 'undefined') return;
    if (open) window.addEventListener('keydown', onKey);
    else window.removeEventListener('keydown', onKey);
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('keydown', onKey);
});
</script>

<style scoped>
.mpd-root {
  position: fixed;
  inset: 0;
  z-index: 3000;
  font-family: var(--adm-font);
}
.mpd-mask {
  position: absolute;
  inset: 0;
  background: rgba(17, 24, 39, 0.42);
}
.mpd-panel {
  position: absolute;
  top: 0;
  right: 0;
  height: 100%;
  width: 560px;
  max-width: 92vw;
  background: var(--adm-surface);
  box-shadow: var(--adm-shadow-dialog);
  display: flex;
  flex-direction: column;
}
.mpd-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--adm-s2);
  padding: var(--adm-s4) var(--adm-s4) var(--adm-s2);
  border-bottom: 1px solid var(--adm-line-soft);
}
.mpd-title {
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.2px;
  color: var(--adm-text);
  line-height: 1.35;
}
.mpd-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}
.mpd-chip {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: var(--adm-r-tag);
  background: var(--adm-muted-weak);
  color: var(--adm-muted);
  font-size: 10.5px;
  font-weight: 700;
}
.mpd-x {
  flex: none;
  width: 30px;
  height: 30px;
  border: 1px solid var(--adm-line);
  border-radius: var(--adm-r-ctl);
  background: #fff;
  color: var(--adm-text-sub);
  cursor: pointer;
  font-size: 14px;
}
.mpd-x:hover { border-color: var(--adm-primary); color: var(--adm-primary); }

.mpd-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  padding: 10px var(--adm-s4);
  background: var(--adm-head-bg);
  border-bottom: 1px solid var(--adm-line-soft);
  font-size: 11.5px;
  color: var(--adm-text-sub);
}
.mpd-meta b { color: var(--adm-text-mid); font-weight: 600; }

.mpd-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--adm-s4);
}
.mpd-block { margin-bottom: var(--adm-s3); }
.mpd-block__label {
  font-size: 11.5px;
  font-weight: 700;
  color: var(--adm-text-sub);
  margin-bottom: 6px;
  letter-spacing: 0.2px;
}
.mpd-face {
  padding: 14px;
  border: 1px solid var(--adm-line);
  border-radius: var(--adm-r-card);
  background: var(--adm-surface);
  font-size: 13.5px;
  line-height: 1.85;
  color: var(--adm-text);
  white-space: pre-wrap;
}
.mpd-face--back { background: #fbfcff; border-style: dashed; }
.mpd-imgs { display: flex; flex-wrap: wrap; gap: 8px; }
.mpd-imgs img {
  max-width: 160px;
  max-height: 120px;
  border-radius: var(--adm-r-ctl);
  border: 1px solid var(--adm-line);
}
.mpd-video { width: 100%; border-radius: var(--adm-r-card); background: #000; }
.mpd-html {
  font-size: 13.5px;
  line-height: 1.9;
  color: var(--adm-text);
  word-break: break-word;
}
.mpd-html :deep(img) { max-width: 100%; border-radius: var(--adm-r-ctl); }
.mpd-html :deep(h1),
.mpd-html :deep(h2),
.mpd-html :deep(h3) { margin: 14px 0 8px; font-size: 15px; color: var(--adm-text); }
.mpd-html :deep(p) { margin: 8px 0; }
.mpd-html :deep(table) { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.mpd-html :deep(th) { background: var(--adm-head-bg); text-align: left; padding: 8px; border: 1px solid var(--adm-line); }
.mpd-html :deep(td) { padding: 8px; border: 1px solid var(--adm-line); }
.mpd-list { padding-left: 18px; font-size: 12.5px; color: var(--adm-text-mid); line-height: 1.9; }
/* 原件清单（B1）：整行是一个按钮，点击即鉴权下载 */
.mpd-files { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.mpd-file {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--adm-line);
  border-radius: var(--adm-r-ctl);
  background: var(--adm-surface);
  font-family: var(--adm-font);
  font-size: 12.5px;
  color: var(--adm-text);
  cursor: pointer;
  text-align: left;
}
.mpd-file:hover { border-color: var(--adm-primary); background: #f7f9ff; }
.mpd-file__ext {
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: var(--adm-r-tag);
  background: var(--adm-primary-weak, #eef1fe);
  color: var(--adm-primary);
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: 0.4px;
}
.mpd-file__name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mpd-file__meta { flex-shrink: 0; color: var(--adm-text-weak); font-size: 11.5px; }
.mpd-file__dl { flex-shrink: 0; color: var(--adm-primary); font-weight: 700; margin-left: 4px; }
/* 试卷元数据（C2/C4）：两列小表，字段解析不出时显示 — */
.mpd-paper {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 16px;
  margin: 0;
  font-size: 12.5px;
}
.mpd-paper > div { display: flex; gap: 8px; align-items: baseline; }
.mpd-paper dt { flex-shrink: 0; width: 62px; color: var(--adm-text-weak); }
.mpd-paper dd { margin: 0; color: var(--adm-text); }
.mpd-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
.mpd-hint { color: var(--adm-text-weak); font-size: 12px; }
/* 讲义目录（C1）：一级标题加粗、二级缩进 */
.mpd-toc { list-style: none; margin: 0; padding: 0; font-size: 12.5px; line-height: 1.9; }
.mpd-toc li { display: flex; align-items: baseline; gap: 6px; color: var(--adm-text-mid); }
.mpd-toc li.is-lv1 { font-weight: 700; color: var(--adm-text); margin-top: 4px; }
.mpd-toc li.is-lv2 { padding-left: 18px; }
.mpd-toc__dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--adm-primary);
  flex-shrink: 0;
}
.mpd-error {
  padding: 12px 14px;
  border: 1px solid #f3c4ae;
  border-radius: var(--adm-r-ctl);
  background: var(--adm-danger-weak);
  color: var(--adm-danger);
  font-size: 12.5px;
}
.mpd-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--adm-s2);
  padding: var(--adm-s2) var(--adm-s4);
  border-top: 1px solid var(--adm-line-soft);
  background: #fbfcff;
}
.mpd-hint { font-size: 11.5px; color: var(--adm-text-weak); }
</style>
