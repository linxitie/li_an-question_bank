<template>
  <Teleport to="body">
    <div v-if="open" class="med-root" role="dialog" aria-modal="true" :aria-label="title">
      <div class="med-mask" @click="requestClose" />
      <section class="med-panel">
        <header class="med-head">
          <div>
            <h2 class="med-title">{{ title }}</h2>
            <p class="med-desc">
              保存后一律是「未上架」（上架=审批通过，在列表里点）。<b>视频不做</b>（全库 0 条，旧页那套分片上传不再搬）。
            </p>
          </div>
          <button class="med-x" type="button" :disabled="saving" @click="requestClose">×</button>
        </header>

        <div class="med-body">
          <div v-if="loading" class="med-loading">读取中…</div>

          <template v-else>
            <div class="med-grid">
              <label v-if="mode === 'create'" class="med-field">
                <span>类型<i>*</i></span>
                <select v-model="form.type" class="adm-select" :disabled="saving">
                  <option value="article">文章</option>
                  <option value="lecture">讲义</option>
                  <option value="card">知识卡片</option>
                </select>
              </label>
              <label v-if="mode === 'create'" class="med-field">
                <span>科目<i>*</i></span>
                <select v-model="form.subject" class="adm-select" :disabled="saving">
                  <option value="xingce">行测</option>
                  <option value="shenlun">申论</option>
                  <option value="gongzhuan">公专</option>
                </select>
              </label>
              <label class="med-field med-field--wide">
                <span>标题<i>*</i></span>
                <input v-model="form.title" class="adm-input" maxlength="200" :disabled="saving" placeholder="例如：传唤的适用对象" />
              </label>
              <label class="med-field">
                <span>分类（可空）</span>
                <input v-model="form.category" class="adm-input" maxlength="100" :disabled="saving" placeholder="如 基础知识" />
              </label>
              <label class="med-field">
                <span>标记（可空）</span>
                <input v-model="form.badge" class="adm-input" maxlength="20" :disabled="saving" placeholder="热门 / 精华 / 重要" />
              </label>
            </div>

            <!-- 文章 / 讲义：摘要 + 富文本正文 -->
            <template v-if="blocks.richText">
              <label class="med-field med-field--wide">
                <span>摘要（可空，列表里显示一句话）</span>
                <textarea v-model="form.summary" class="adm-input med-textarea" rows="2" maxlength="500" :disabled="saving" />
              </label>
              <div class="med-rich">
                <div class="med-rich__label">
                  正文<i>*</i>
                  <span class="med-rich__hint">支持加粗、列表、表格、插图（图片走「上传图片」按钮，也可以直接拖进来）</span>
                </div>
                <div ref="editorEl" class="med-rich__editor" />
                <p v-if="editorError" class="med-warn">{{ editorError }}</p>
              </div>
            </template>

            <!-- 卡片：正 / 背 / 封面 -->
            <template v-else>
              <label class="med-field med-field--wide">
                <span>卡片正面<i>*</i>（{{ form.cardFront.length }}/{{ CARD_FRONT_MAX }}）</span>
                <input v-model="form.cardFront" class="adm-input" :maxlength="CARD_FRONT_MAX" :disabled="saving" placeholder="词条 / 关键词 / 问题" />
              </label>
              <label class="med-field med-field--wide">
                <span>卡片背面（{{ form.cardBack.length }}/{{ CARD_BACK_MAX }}）</span>
                <textarea v-model="form.cardBack" class="adm-input med-textarea" rows="4" :maxlength="CARD_BACK_MAX" :disabled="saving" placeholder="释义 / 口诀 / 要点" />
              </label>
              <div class="med-field med-field--wide">
                <span>封面（可空）</span>
                <div class="med-cover">
                  <input v-model="form.cover" class="adm-input" :disabled="saving" placeholder="点「上传封面」自动填，也可粘图片地址" />
                  <button class="adm-btn adm-btn--line" type="button" :disabled="saving" @click="pickCover">上传封面</button>
                </div>
                <img v-if="form.cover" :src="form.cover" class="med-cover__preview" alt="封面预览" />
              </div>
            </template>

            <ul v-if="errors.length" class="med-errors">
              <li v-for="(e, i) in errors" :key="i">{{ e }}</li>
            </ul>
            <p v-if="error" class="med-error">{{ error }}</p>
          </template>
        </div>

        <footer class="med-foot">
          <span class="med-foot-hint">
            <template v-if="mode === 'edit'">改的是正文/卡片内容；标题与分类也可以用这里改</template>
            <template v-else>保存后到列表里点「上架」学生才可见</template>
          </span>
          <div class="med-foot-btns">
            <button class="adm-btn adm-btn--line" type="button" :disabled="saving" @click="requestClose">取消</button>
            <button class="adm-btn adm-btn--primary" type="button" :disabled="saving || loading" @click="save">
              {{ saving ? '保存中…' : mode === 'edit' ? '保存修改' : '保存（未上架）' }}
            </button>
          </div>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * S2（2026-11-12）：把旧版页「＋新建资料」的手写能力搬进新版资料管理页。
 *
 * 背景：新版只能"上传文件"，短文章/说明类内容此前只能进旧版 `.vtj` 富文本弹窗
 * （`/admin/materials/legacy`），旧页要下线就必须先把这件事搬过来。
 *
 * **顺手修掉旧页那个误报**：旧页 `editDlg` 与 `form.type` 两个 watcher 都会调
 * `mountEditor()`，而去重判断在 `await import('wangeditor')` 之前 → 并发创建两次，
 * 第二次抛「初始化节点已存在编辑器实例」，界面上弹出"编辑器加载失败"但编辑器其实是好的。
 * 这里只有**一个**同步入口 + `mounting` 锁，不会重复创建。
 */
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';

import {
  createMaterial,
  fetchMaterialPreview,
  updateMaterial,
  uploadMaterialImage
} from '@/modules/library/api';
import { errorMessage } from '@/utils/apiError';
import {
  CARD_BACK_MAX,
  CARD_FRONT_MAX,
  buildMaterialPayload,
  editorBlocks,
  emptyForm,
  validateEditor,
  type EditorForm,
  type EditorMode,
  type EditorSubject,
  type EditorType
} from '@/utils/materialEditor';

/** wangeditor 是 CJS 包，只声明用到的那一小撮接口，避免 `any` 满天飞 */
interface WangEditorInstance {
  config: {
    height?: number;
    placeholder?: string;
    zIndex?: number;
    customUploadImg?: (files: File[], insert: (url: string) => void) => void;
  };
  create(): void;
  txt: { html(html?: string): string };
  destroy(): void;
}

const props = withDefaults(
  defineProps<{
    open: boolean;
    mode?: EditorMode;
    materialId?: number | null;
    defaultType?: EditorType;
    defaultSubject?: EditorSubject;
  }>(),
  { mode: 'create', materialId: null, defaultType: 'article', defaultSubject: 'gongzhuan' }
);
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'saved', payload: { id: number | null; mode: EditorMode }): void;
}>();

const form = reactive<EditorForm>(emptyForm('gongzhuan'));
const loading = ref(false);
const saving = ref(false);
const errors = ref<string[]>([]);
const error = ref('');
const editorEl = ref<HTMLElement | null>(null);
const editor = ref<WangEditorInstance | null>(null);
const /** 挂载中锁：防止同一节点被并发 create（旧页那个 bug 的根因） */ mounting = ref(false);
const editorError = ref('');

const blocks = computed(() => editorBlocks(form.type));
const title = computed(() => (props.mode === 'edit' ? '编辑资料内容' : '新建资料'));

function reset(): void {
  Object.assign(form, emptyForm(props.defaultSubject));
  if (props.mode === 'create') form.type = props.defaultType;
  errors.value = [];
  error.value = '';
  editorError.value = '';
}

function requestClose(): void {
  if (saving.value) return;
  destroyEditor();
  emit('close');
}

function destroyEditor(): void {
  if (editor.value) {
    try {
      editor.value.destroy();
    } catch {
      /* 已被外部移除时 destroy 会抛，忽略 */
    }
    editor.value = null;
  }
}

/** 挂载富文本编辑器（唯一入口；有锁，重复调用直接返回） */
async function ensureEditor(): Promise<void> {
  if (!blocks.value.richText || !props.open) return;
  if (editor.value || mounting.value) return;
  if (!editorEl.value) return;
  mounting.value = true;
  try {
    const mod = (await import('wangeditor')) as unknown as {
      default: new (el: HTMLElement) => WangEditorInstance;
    };
    const ed = new mod.default(editorEl.value);
    ed.config.height = 320;
    ed.config.placeholder = '写正文，支持加粗、列表、表格；插图走图片按钮';
    ed.config.zIndex = 60;
    ed.config.customUploadImg = async (files, insert) => {
      for (const f of files) {
        try {
          insert(await uploadMaterialImage(f, 'inline'));
        } catch (e) {
          ElMessage.error(`插图上传失败：${errorMessage(e, '未知错误')}`);
        }
      }
    };
    ed.create();
    editor.value = ed;
    if (form.content) ed.txt.html(form.content);
  } catch (e) {
    editorError.value = `富文本编辑器没加载起来：${errorMessage(e, '未知错误')}。可以先用「批量上传文章」传 docx。`;
  } finally {
    mounting.value = false;
  }
}

async function loadDetail(id: number): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const d = await fetchMaterialPreview(id);
    Object.assign(form, {
      type: (d.type === 'card' ? 'card' : d.type === 'lecture' ? 'lecture' : 'article') as EditorType,
      subject: d.subject,
      title: d.title || '',
      summary: d.summary || '',
      category: d.category || '',
      content: d.content_html || '',
      cardFront: d.card?.front || '',
      cardBack: d.card?.back || '',
      cover: '',
      badge: d.badge || ''
    });
  } catch (e) {
    error.value = errorMessage(e, '读取资料失败');
  } finally {
    loading.value = false;
  }
}

/** 打开时：重置 → 编辑模式拉详情 → 有富文本就挂编辑器 */
watch(
  () => props.open,
  async (open) => {
    if (!open) {
      destroyEditor();
      return;
    }
    reset();
    if (props.mode === 'edit' && props.materialId) await loadDetail(props.materialId);
    await nextTick();
    await ensureEditor();
  },
  { immediate: true }
);

/** 类型切换：卡片/文章是两套输入块，面板 v-if 重建了 DOM → 必须重新挂 */
watch(
  () => form.type,
  async () => {
    destroyEditor();
    await nextTick();
    await ensureEditor();
  }
);

onBeforeUnmount(destroyEditor);

function pickCover(): void {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.onchange = async () => {
    const f = input.files?.[0];
    if (!f) return;
    try {
      form.cover = await uploadMaterialImage(f, 'cover');
    } catch (e) {
      ElMessage.error(`封面上传失败：${errorMessage(e, '未知错误')}`);
    }
  };
  input.click();
}

async function save(): Promise<void> {
  // 富文本的内容只在编辑器里，先回读再校验（否则"正文不能为空"会误报）
  if (blocks.value.richText && editor.value) form.content = editor.value.txt.html();
  errors.value = validateEditor(form, props.mode);
  error.value = '';
  if (errors.value.length) return;
  saving.value = true;
  try {
    const payload = buildMaterialPayload(form, props.mode);
    if (props.mode === 'edit' && props.materialId) {
      await updateMaterial(props.materialId, payload);
      ElMessage.success('已保存（上架状态不变）');
      emit('saved', { id: props.materialId, mode: 'edit' });
    } else {
      const r = await createMaterial(payload);
      ElMessage.success('已创建（未上架），到列表里核对后点「上架」');
      emit('saved', { id: r.id ?? null, mode: 'create' });
    }
    destroyEditor();
  } catch (e) {
    error.value = errorMessage(e, '保存失败');
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.med-root {
  position: fixed;
  inset: 0;
  z-index: 78;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 40px 16px;
}
.med-mask {
  position: absolute;
  inset: 0;
  background: rgba(10, 22, 40, 0.45);
}
.med-panel {
  position: relative;
  width: min(860px, 100%);
  max-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 18px 48px rgba(10, 22, 40, 0.28);
  overflow: hidden;
}
.med-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid #eef1f6;
}
.med-title {
  margin: 0 0 4px;
  font-size: 16px;
  color: var(--adm-text, #1a2a4a);
}
.med-desc {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--adm-text-2, #6b7c99);
}
.med-x {
  border: 0;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: #8a9ab5;
  cursor: pointer;
}
.med-body {
  padding: 14px 20px 6px;
  overflow: auto;
}
.med-loading {
  padding: 24px 0;
  text-align: center;
  font-size: 13px;
  color: #8a9ab5;
}
.med-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px 12px;
  margin-bottom: 10px;
}
.med-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
  font-size: 12px;
  color: #46587a;
}
.med-field--wide {
  grid-column: 1 / -1;
}
.med-field i {
  font-style: normal;
  color: #c62828;
  margin-left: 2px;
}
.med-textarea {
  height: auto;
  padding: 8px 10px;
  line-height: 1.6;
  resize: vertical;
}
.med-rich__label {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 4px 0 6px;
  font-size: 12px;
  color: #46587a;
}
.med-rich__label i {
  font-style: normal;
  color: #c62828;
}
.med-rich__hint {
  color: #8a9ab5;
}
.med-rich__editor {
  border: 1px solid #e3e9f2;
  border-radius: 8px;
  overflow: hidden;
}
.med-cover {
  display: flex;
  gap: 8px;
}
.med-cover .adm-input {
  flex: 1;
}
.med-cover__preview {
  margin-top: 8px;
  max-height: 120px;
  border-radius: 8px;
  border: 1px solid #eef1f6;
}
.med-errors {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: 12.5px;
  color: #c62828;
  line-height: 1.7;
}
.med-error,
.med-warn {
  margin: 6px 0 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: #c62828;
}
.med-warn {
  color: #b26a00;
}
.med-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  border-top: 1px solid #eef1f6;
  background: #fbfcfe;
}
.med-foot-hint {
  font-size: 12px;
  color: #8a9ab5;
}
.med-foot-btns {
  display: flex;
  gap: 8px;
}
</style>
