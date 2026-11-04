<template>
  <!-- inline：桌面/独立页内嵌；默认：手机端弹层 -->
  <div v-if="open" :class="inline ? 'cc-inline' : 'cc-mask'" @click.self="inline ? null : close()">
    <div :class="inline ? 'cc-panel is-inline' : 'cc-panel'" role="dialog" aria-modal="true">
      <header v-if="!inline" class="cc-head">
        <span class="cc-title">{{ step === 'subject' ? '选择科目' : '创建卡片' }}</span>
        <button class="cc-x" aria-label="关闭" @click="close">✕</button>
      </header>

      <!-- 第 1 步：选科目（对应 Excel 的「科目」维度） -->
      <div v-if="step === 'subject'" class="cc-subjects">
        <button
          v-for="s in SUBJECTS"
          :key="s.value"
          class="cc-subject"
          :class="{ 'is-on': subject === s.value }"
          @click="pickSubject(s.value)"
        >
          <span class="cc-subject-name">{{ s.label }}</span>
          <span class="cc-subject-desc">{{ s.desc }}</span>
        </button>
        <p class="cc-tip">选好科目后填写正面 / 背面，可另加 1~2 张配图；保存即公开展示，无需审核。</p>
        <!-- Excel 批量上传入口：第一屏就能看到，不用先填表 -->
        <button v-if="!inline" type="button" class="cc-batch cc-batch-step" @click="goBatchImport">
          一次要传很多张？用「Excel 批量导入」→
        </button>
      </div>

      <!-- 第 2 步：填卡片（字段与 Excel 模板逐列对应） -->
      <div v-else class="cc-body">
        <div class="cc-seg">
          <button
            v-for="s in SUBJECTS"
            :key="s.value"
            class="cc-seg-btn"
            :class="{ 'is-on': subject === s.value }"
            @click="switchSubject(s.value)"
          >{{ s.label }}</button>
        </div>

        <label class="cc-field">
          <span class="cc-lab">正面<em>必填</em><i>{{ front.length }}/{{ FRONT_MAX }}</i></span>
          <textarea
            v-model="front"
            class="cc-input"
            :maxlength="FRONT_MAX"
            rows="2"
            placeholder="与表格「正面」列一致：一句话结论或问题"
          ></textarea>
        </label>

        <label class="cc-field">
          <span class="cc-lab">背面<i>{{ back.length }}/{{ BACK_MAX }}</i></span>
          <textarea
            v-model="back"
            class="cc-input"
            :maxlength="BACK_MAX"
            rows="4"
            placeholder="要点、步骤或答案；留空时必须配图"
          ></textarea>
        </label>

        <div class="cc-row">
          <label class="cc-field cc-half">
            <span class="cc-lab">分类</span>
            <select v-model="category" class="cc-input" @change="onCategoryChange">
              <option value="">自动判定</option>
              <option v-for="c in categories" :key="c.name" :value="c.name">{{ c.name }}</option>
            </select>
          </label>
          <label class="cc-field cc-half">
            <span class="cc-lab">考点</span>
            <select v-model="pointId" class="cc-input">
              <option value="">不指定</option>
              <option v-for="p in pointOptions" :key="p.id" :value="String(p.id)">{{ p.name }}</option>
            </select>
          </label>
        </div>

        <div class="cc-field">
          <span class="cc-lab">配图<em>选填，最多 {{ IMG_MAX }} 张</em></span>
          <div class="cc-imgs">
            <div v-for="(img, i) in images" :key="img.key" class="cc-img">
              <img :src="img.preview" alt="卡片配图" />
              <button class="cc-img-del" type="button" aria-label="删除图片" @click="removeImage(i)">✕</button>
            </div>
            <label v-if="images.length < IMG_MAX" class="cc-img-add">
              <input type="file" accept="image/png,image/jpeg,image/webp" hidden @change="onPickImage" />
              <span class="cc-img-plus">＋</span>
              <em>添加图片</em>
            </label>
          </div>
        </div>

        <p v-if="error" class="cc-err">{{ error }}</p>
        <p v-else class="cc-tip">{{ hint }}</p>

        <div class="cc-actions">
          <button v-if="!inline" class="cc-btn cc-ghost" :disabled="saving" @click="step = 'subject'">上一步</button>
          <button class="cc-btn cc-primary" :disabled="saving" @click="submit">
            {{ saving ? '保存中…' : '保存并公开' }}
          </button>
        </div>

        <!-- 手机端也能走 Excel 批量（两种方式并存） -->
        <button v-if="!inline" class="cc-batch" type="button" @click="goBatchImport">
          一次多张？改用「Excel 批量导入」→
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import {
  BACK_MAX,
  FRONT_MAX,
  IMG_MAX,
  checkImageFile,
  validateDraft
} from './cardDraft';

interface SubjectOpt {
  value: 'xingce' | 'shenlun' | 'gongzhuan';
  label: string;
  desc: string;
}
interface PointOpt {
  id: number;
  name: string;
}
interface CategoryOpt {
  name: string;
  points: PointOpt[];
}
interface PickedImage {
  key: number;
  file: File;
  preview: string;
}const SUBJECTS: SubjectOpt[] = [
  { value: 'xingce', label: '行测', desc: '言语 / 判断 / 数量 / 资料 / 常识' },
  { value: 'shenlun', label: '申论', desc: '归纳概括 / 综合分析 / 应用文' },
  { value: 'gongzhuan', label: '公专', desc: '公安专业科目知识' }
];

const props = withDefaults(
  defineProps<{
    open?: boolean;
    subject?: string;
    /** 桌面页内嵌：不显示遮罩与关闭按钮，直接从填写步骤开始 */
    inline?: boolean;
  }>(),
  { open: false, subject: 'xingce', inline: false }
);

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'saved', payload: Record<string, unknown>): void;
}>();

/** taxonomy 一次请求，按科目缓存（同一次会话内下拉不重复拉取） */
const taxonomyCache = new Map<string, CategoryOpt[]>();

const step = ref<'subject' | 'form'>('subject');
const subject = ref<string>(props.subject);
const front = ref('');
const back = ref('');
const category = ref('');
const pointId = ref('');
const categories = ref<CategoryOpt[]>([]);
const images = ref<PickedImage[]>([]);
const saving = ref(false);
const error = ref('');
const taxLoading = ref(false);
let imgSeq = 0;

const hint = computed(() => {
  if (!categories.value.length && taxLoading.value) return '正在加载分类…';
  if (category.value && !pointId.value) {
    return '未指定考点：这类卡片会以「通用技巧」展示（不影响保存）。';
  }
  return '保存后立即公开展示（免审批）；分类留空时按正面 + 背面自动判定。';
});

const pointOptions = computed<PointOpt[]>(() => {
  if (category.value) {
    return categories.value.find((c) => c.name === category.value)?.points || [];
  }
  return categories.value.flatMap((c) => c.points);
});

const apiFetch = (url: string, init?: RequestInit) => {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && typeof auth.apiFetch === 'function') return auth.apiFetch(url, init);
  return fetch(url, { credentials: 'include', ...(init || {}) });
};

const loadTaxonomy = async (subj: string) => {
  if (taxonomyCache.has(subj)) {
    categories.value = taxonomyCache.get(subj) || [];
    return;
  }
  taxLoading.value = true;
  try {
    const resp = await apiFetch(`/api/materials/taxonomy?subject=${encodeURIComponent(subj)}`);
    if (!resp.ok) throw new Error(`分类加载失败（${resp.status}）`);
    const data = await resp.json();
    const list: CategoryOpt[] = (data.categories || []).map((c: any) => ({
      name: c.name,
      points: c.points || []
    }));
    taxonomyCache.set(subj, list);
    categories.value = list;
  } catch (e) {
    categories.value = [];
    error.value = (e as Error)?.message || '分类加载失败';
  } finally {
    taxLoading.value = false;
  }
};

const resetForm = () => {
  front.value = '';
  back.value = '';
  category.value = '';
  pointId.value = '';
  error.value = '';
  images.value = [];
};

const openSheet = (subj: string) => {
  subject.value = subj;
  resetForm();
  step.value = props.inline ? 'form' : 'subject';
  loadTaxonomy(subj);
};

const pickSubject = (subj: string) => {
  if (subject.value !== subj) {
    resetForm();
    loadTaxonomy(subj);
  }
  subject.value = subj;
  step.value = 'form';
};

const switchSubject = (subj: string) => {
  if (subject.value === subj) return;
  subject.value = subj;
  category.value = '';
  pointId.value = '';
  loadTaxonomy(subj);
};

const onCategoryChange = () => {
  // 换分类后，已选考点若不属于新分类则清空（避免提交跨分类考点）
  if (!pointId.value) return;
  const ids = pointOptions.value.map((p) => String(p.id));
  if (!ids.includes(pointId.value)) pointId.value = '';
};

const onPickImage = async (e: Event) => {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;
  error.value = '';
  const bad = checkImageFile(file, images.value.length);
  if (bad) {
    error.value = bad;
    return;
  }
  // 缩略图用 dataURL 而不是 blob: — 站点 CSP 的 img-src 只放行 'self' data:，
  // blob: 会被拦截（实测 naturalWidth=0，界面只剩 alt 文本）。
  const preview = await new Promise<string>((ok) => {
    const fr = new FileReader();
    fr.onload = () => ok(String(fr.result || ''));
    fr.onerror = () => ok('');
    fr.readAsDataURL(file);
  });
  images.value.push({ key: ++imgSeq, file, preview });
};

const removeImage = (idx: number) => {
  images.value.splice(idx, 1);
};

const close = () => {
  resetForm();
  step.value = 'subject';
  emit('close');
};

/** 手机端跳到「Excel 批量导入」页（与学生端 Excel 通道并存） */
const goBatchImport = () => {
  emit('close');
  window.location.hash = '#/materials/upload?tab=excel';
};

const submit = async () => {
  if (saving.value) return;
  error.value = validateDraft({
    front: front.value,
    back: back.value,
    imageCount: images.value.length
  });
  if (error.value) return;
  saving.value = true;
  try {
    const fd = new FormData();
    fd.append('subject', subject.value);
    fd.append('card_front', front.value.trim());
    fd.append('card_back', back.value.trim());
    fd.append('category', category.value);
    fd.append('point_id', pointId.value);
    images.value.forEach((img) => fd.append('images', img.file, img.file.name));

    const resp = await apiFetch('/api/materials/my/card', { method: 'POST', body: fd });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error((data as any)?.detail || `保存失败（${resp.status}）`);
    }
    emit('saved', data as Record<string, unknown>);
    resetForm();
    step.value = props.inline ? 'form' : 'subject';
    if (props.inline) loadTaxonomy(subject.value);
  } catch (e) {
    error.value = (e as Error)?.message || '保存失败，请稍后重试';
  } finally {
    saving.value = false;
  }
};

watch(
  () => props.open,
  (v) => {
    if (v) openSheet(props.subject || 'xingce');
  },
  { immediate: true }
);

watch(
  () => props.subject,
  (v) => {
    if (props.open && v && v !== subject.value && step.value === 'form' && !front.value) {
      switchSubject(v);
    }
  }
);

onBeforeUnmount(() => {
  images.value = [];
});
</script>

<style scoped>
.cc-mask {
  position: fixed;
  inset: 0;
  z-index: 1100;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.cc-panel {
  width: 100%;
  max-width: 520px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.22);
}
.cc-inline {
  width: 100%;
}
.cc-panel.is-inline {
  max-width: 720px;
  max-height: none;
  margin: 0 auto;
  border: 1px solid #e5eaf3;
  box-shadow: 0 6px 20px rgba(23, 43, 77, 0.06);
}
.cc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #eef1f6;
  flex: none;
}
.cc-title {
  font-size: 15px;
  font-weight: 700;
  color: #1a2b5f;
}
.cc-x {
  border: none;
  background: none;
  font-size: 18px;
  color: #8899aa;
  min-width: 44px;
  min-height: 44px;
  cursor: pointer;
}
.cc-subjects {
  padding: 14px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cc-subject {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid #e6ecf5;
  border-radius: 12px;
  background: #fbfcff;
  cursor: pointer;
  text-align: left;
}
.cc-subject.is-on,
.cc-subject:active {
  border-color: #3b82f6;
  background: #eff6ff;
}
.cc-subject-name {
  font-size: 15px;
  font-weight: 700;
  color: #1a2b5f;
}
.cc-subject-desc {
  font-size: 12px;
  color: #6b7a90;
}
.cc-body {
  padding: 14px 16px 16px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
.cc-seg {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.cc-seg-btn {
  flex: 1;
  height: 34px;
  border-radius: 9px;
  border: 1px solid #e6ecf5;
  background: #f5f7fb;
  color: #5a6b85;
  font-size: 13px;
  cursor: pointer;
}
.cc-seg-btn.is-on {
  background: #1a2b5f;
  border-color: #1a2b5f;
  color: #fff;
  font-weight: 600;
}
.cc-field {
  display: block;
  margin-bottom: 12px;
}
.cc-row {
  display: flex;
  gap: 10px;
}
.cc-half {
  flex: 1;
  min-width: 0;
}
.cc-lab {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 5px;
  font-size: 12.5px;
  color: #3d4d66;
  font-weight: 600;
}
.cc-lab em {
  font-style: normal;
  font-size: 11px;
  font-weight: 400;
  color: #94a3b8;
}
.cc-lab i {
  margin-left: auto;
  font-style: normal;
  font-weight: 400;
  font-size: 11px;
  color: #a3aec0;
}
.cc-input {
  width: 100%;
  padding: 9px 11px;
  border: 1px solid #dfe6f0;
  border-radius: 10px;
  font-size: 13.5px;
  line-height: 1.6;
  color: #1a2b5f;
  background: #fff;
  font-family: inherit;
  resize: vertical;
}
.cc-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}
.cc-imgs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.cc-img,
.cc-img-add {
  position: relative;
  width: 76px;
  height: 76px;
  border-radius: 10px;
  overflow: hidden;
}
.cc-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.cc-img-del {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.62);
  color: #fff;
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
}
.cc-img-add {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border: 1px dashed #cbd5e1;
  background: #fafbff;
  cursor: pointer;
  color: #7c8aa0;
}
.cc-img-plus {
  font-size: 20px;
  line-height: 1;
  color: #94a3b8;
}
.cc-img-add em {
  font-style: normal;
  font-size: 10.5px;
}
.cc-err {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: #dc2626;
}
.cc-tip {
  margin: 4px 0 0;
  font-size: 11.5px;
  color: #94a3b8;
  line-height: 1.6;
}
.cc-actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
.cc-btn {
  flex: 1;
  height: 44px;
  border-radius: 10px;
  font-size: 14px;
  cursor: pointer;
  border: 1px solid #e6ecf5;
  background: #fff;
  color: #5a6b85;
}
.cc-primary {
  background: #3b82f6;
  border-color: #3b82f6;
  color: #fff;
  font-weight: 700;
}
.cc-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
/* 手机端：切换到 Excel 批量导入 */
.cc-batch {
  display: block;
  width: 100%;
  margin-top: 10px;
  padding: 6px 0;
  border: none;
  background: none;
  color: #2a5298;
  font-size: 12.5px;
  text-align: center;
  cursor: pointer;
}
/* 第一步（选科目）里的入口：做成浅底卡片，更显眼 */
.cc-batch-step {
  margin-top: 14px;
  padding: 12px 10px;
  border: 1px dashed #c9d9f8;
  border-radius: 12px;
  background: #f4f8ff;
  font-size: 13px;
  font-weight: 600;
}
.cc-batch:hover {
  text-decoration: underline;
}
</style>
