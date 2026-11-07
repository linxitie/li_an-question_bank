<template>
  <div class="sp-page">
    <AdminPageHeader
      title="画风组件库"
      desc="A0 基座 · 6 个组件 + 令牌 + 工具类。12 个管理页从这里取样式，不再各写一套"
    >
      <template #actions>
        <button class="adm-btn adm-btn--line" @click="reload">刷新</button>
        <router-link class="adm-btn adm-btn--primary" to="/admin/materials">去看资料页</router-link>
      </template>
    </AdminPageHeader>

    <div class="sp-stats">
      <AdminStatCard label="总资料数" :value="119" icon="📚" />
      <AdminStatCard label="讲义" :value="1" icon="📘" tone="info" />
      <AdminStatCard label="试卷" :value="3" icon="📄" tone="warn" />
      <AdminStatCard label="待补全" :value="1" icon="⚠️" tone="danger" />
      <AdminStatCard label="暂无数据" :value="null" icon="📈" />
    </div>

    <AdminToolbar>
      <select class="adm-select"><option>全部科目</option><option>行测</option><option>申论</option></select>
      <select class="adm-select"><option>全部类型</option><option>讲义</option><option>试卷</option></select>
      <input class="adm-input" placeholder="搜索标题…" style="width: 200px" />
      <template #actions>
        <button class="adm-btn">搜索</button>
        <button class="adm-btn adm-btn--primary">批量导入</button>
      </template>
    </AdminToolbar>

    <div class="sp-grid">
      <AdminTable title="资料列表（表格壳 + 徽标）" :empty="rows.length === 0" empty-text="暂无数据 · 换个筛选条件试试">
        <template #head><span class="adm-tag is-tone-primary">示例</span></template>
        <table>
          <thead>
            <tr>
              <th style="width: 56px">ID</th>
              <th>标题 / 类型</th>
              <th style="width: 64px">科目</th>
              <th style="width: 140px">上传时间</th>
              <th style="width: 84px">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id">
              <td class="adm-mono">{{ r.id }}</td>
              <td>
                <b>{{ r.title }}</b>
                <AdminTag :type="r.type" style="margin-left: 6px">{{ r.typeLabel }}</AdminTag>
              </td>
              <td>{{ r.subject }}</td>
              <td class="adm-mono" style="color: var(--adm-muted)">{{ r.time }}</td>
              <td><AdminTag :tone="r.published ? 'ok' : 'muted'">{{ r.published ? '已上架' : '未上架' }}</AdminTag></td>
            </tr>
          </tbody>
        </table>
        <template #footer><span class="adm-empty" style="padding: 0">共 {{ rows.length }} 条</span></template>
      </AdminTable>

      <div>
        <div class="adm-card sp-card">
          <h3>徽标 · 6 类资料 × 4 态状态</h3>
          <div class="sp-line">
            <AdminTag type="video_intro">入门视频</AdminTag>
            <AdminTag type="video_advanced">进阶视频</AdminTag>
            <AdminTag type="article">文章</AdminTag>
            <AdminTag type="card">知识卡片</AdminTag>
            <AdminTag type="lecture">讲义</AdminTag>
            <AdminTag type="paper">试卷</AdminTag>
          </div>
          <div class="sp-line">
            <AdminTag tone="ok">已上架</AdminTag>
            <AdminTag tone="muted">未上架</AdminTag>
            <AdminTag tone="warn">待补全</AdminTag>
            <AdminTag tone="danger">校验失败</AdminTag>
            <AdminTag tone="info">解析中</AdminTag>
            <AdminTag tone="primary">新</AdminTag>
          </div>
        </div>

        <div class="adm-card sp-card">
          <h3>按钮 · 四态</h3>
          <div class="sp-line">
            <button class="adm-btn adm-btn--primary">主按钮</button>
            <button class="adm-btn">次按钮</button>
            <button class="adm-btn adm-btn--line">描边</button>
            <button class="adm-btn adm-btn--danger">删除</button>
            <button class="adm-btn" disabled>禁用</button>
            <button class="adm-btn adm-btn--sm">小号</button>
          </div>
        </div>

        <div class="adm-card sp-card">
          <h3>表单行 · 表单控件</h3>
          <AdminFormItem label="试卷标题" required hint="可留空，入库后在列表里改">
            <input class="adm-input" style="width: 100%" value="2024年国考公安专业科目·题本" />
          </AdminFormItem>
          <AdminFormItem label="年份" hint="格式校验 2000–2035">
            <select class="adm-select"><option>2024</option></select>
          </AdminFormItem>
          <AdminFormItem label="题量" error="题量必须是 1–300 的整数">
            <input class="adm-input" value="999" style="width: 120px" />
          </AdminFormItem>
        </div>

        <div class="adm-card sp-card">
          <h3>空状态</h3>
          <div class="adm-empty">暂无数据 · 换个筛选条件试试</div>
        </div>

        <div class="adm-card sp-card">
          <h3>预览抽屉（A3）· 6 类共用一个</h3>
          <div class="sp-line">
            <button class="adm-btn adm-btn--primary" @click="openMock('card')">卡片样例</button>
            <button class="adm-btn" @click="openMock('article')">文章样例</button>
            <button class="adm-btn" @click="openMock('video')">视频样例</button>
          </div>
          <div class="sp-line">
            <input v-model="realId" class="adm-input" style="width: 110px" placeholder="资料 ID" />
            <button class="adm-btn adm-btn--line" :disabled="drawerLoading" @click="openReal">
              {{ drawerLoading ? '读取中…' : '用真实数据打开' }}
            </button>
            <span class="sp-tip">走 GET /api/materials/admin/{id}/preview</span>
          </div>
        </div>
      </div>
    </div>

    <div class="sp-note">
      色值/圆角/字号全部来自 <code>src/styles/admin-tokens.css</code>（CSS 变量），页面里不再写字面量。
      保留 emoji 图标（E3 裁定），但尺寸、对齐、透明度由 <code>AdminStatCard</code> 统一。
      本页仅管理员可见，用于 E1/E2 改造时的视觉基准。
    </div>

    <!-- A3：预览抽屉（6 类共用一个组件；这里用样例数据演示，也可读真实资料） -->
    <MaterialPreviewDrawer
      :open="drawerOpen"
      :preview="drawerData"
      :loading="drawerLoading"
      :error="drawerError"
      @close="drawerOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * 画风组件库预览页（A0）
 *
 * 作用：E1/E2 把 12 个管理页改成统一画风时，这里是**唯一视觉基准**；
 * 同时用来做"改完像不像"的走查对照（截图对比）。
 *
 * 路由：`/admin/dev/style`（`roles: ['admin']`）——本页新增了 1 条页面路由，
 * 因此 L6/L7 门禁的页面计数从 104 同步到 105（见 A0 交付记录）。
 */
import { ref } from 'vue';
import {
  AdminPageHeader,
  AdminStatCard,
  AdminTag,
  AdminTable,
  AdminToolbar,
  AdminFormItem,
  MaterialPreviewDrawer
} from '@/components/admin';
import { fetchMaterialPreview, type MaterialPreview } from '@/modules/library/api';

const rows = ref([
  {
    id: 115,
    title: '2024年国考公安专业科目·题本',
    type: 'paper' as const,
    typeLabel: '试卷',
    subject: '公专',
    time: '2026-11-05 21:12',
    published: true
  },
  {
    id: 114,
    title: '公专·行政执法程序讲义',
    type: 'lecture' as const,
    typeLabel: '讲义',
    subject: '公专',
    time: '2026-11-05 20:48',
    published: true
  },
  {
    id: 108,
    title: '申论·概括题四步法',
    type: 'article' as const,
    typeLabel: '文章',
    subject: '申论',
    time: '2026-11-03 10:22',
    published: false
  }
]);

function reload(): void {
  rows.value = [...rows.value];
}

// ---------------- A3：预览抽屉演示 ----------------
const drawerOpen = ref(false);
const drawerLoading = ref(false);
const drawerError = ref('');
const drawerData = ref<MaterialPreview | null>(null);
const realId = ref('115');

function basePreview(over: Partial<MaterialPreview>): MaterialPreview {
  return {
    id: 0,
    type: 'card',
    type_label: '知识卡片',
    title: '样例资料',
    summary: null,
    subject: 'gongzhuan',
    subject_label: '公专',
    category: '基础知识',
    status: 1,
    badge: null,
    difficulty: 2,
    read_time: 3,
    duration: 0,
    view_count: 12,
    study_count: 0,
    publisher: { id: 2, name: 'cbrycc', role: 'admin', role_label: '管理员' },
    created_at: '2026-11-05T21:12:37+08:00',
    uploaded_at: null,
    content_html: null,
    card: null,
    video: null,
    chapters: [],
    files: [],
    paper: null,
    ...over
  };
}

const MOCKS: Record<'card' | 'article' | 'video', MaterialPreview> = {
  card: basePreview({
    id: 120,
    title: '继续盘问的适用对象？（第2组）',
    type: 'card',
    type_label: '知识卡片',
    card: {
      front: '继续盘问的适用对象是？',
      back: '① 被指控有犯罪行为 ② 有现场作案嫌疑 ③ 有作案嫌疑身份不明 ④ 携带物品可能是赃物',
      images: []
    }
  }),
  article: basePreview({
    id: 108,
    title: '申论·概括题四步法',
    type: 'article',
    type_label: '文章',
    category: '归纳概括',
    subject: 'shenlun',
    subject_label: '申论',
    content_html:
      '<h2>一、审题</h2><p>先定位「作答对象 + 给定范围 + 字数」，再回材料。</p>' +
      '<h2>二、找点</h2><p>按段落逐句圈关键词，宁多勿少。</p>' +
      '<h2>三、合并</h2><p>同类项合并，异类项分条，控制在 4–6 条。</p>' +
      '<h2>四、成文</h2><p>总分结构：总括句 + 分条，每条 15–25 字。</p>'
  }),
  video: basePreview({
    id: 130,
    title: '公专·传唤与拘传的区别（入门）',
    type: 'video_intro',
    type_label: '入门视频',
    duration: 318,
    video: { url: '' }
  })
};

function openMock(kind: 'card' | 'article' | 'video'): void {
  drawerError.value = '';
  drawerLoading.value = false;
  drawerData.value = MOCKS[kind];
  drawerOpen.value = true;
}

async function openReal(): Promise<void> {
  const id = Number(realId.value);
  if (!Number.isFinite(id) || id <= 0) {
    drawerError.value = '请输入有效的资料 ID';
    drawerData.value = null;
    drawerOpen.value = true;
    return;
  }
  drawerOpen.value = true;
  drawerLoading.value = true;
  drawerError.value = '';
  drawerData.value = null;
  try {
    drawerData.value = await fetchMaterialPreview(id);
  } catch (e: unknown) {
    drawerError.value = e instanceof Error ? e.message : '读取失败（可能是 ID 不存在或无权限）';
  } finally {
    drawerLoading.value = false;
  }
}
</script>

<style scoped>
.sp-page {
  padding: var(--adm-s5) var(--adm-s6) var(--adm-s6);
  background: var(--adm-bg);
  min-height: 100%;
  font-family: var(--adm-font);
}
.sp-stats {
  display: flex;
  gap: var(--adm-s2);
  margin-bottom: var(--adm-s2);
}
.sp-grid {
  display: grid;
  grid-template-columns: 1.35fr 1fr;
  gap: var(--adm-s3);
  align-items: start;
}
.sp-card { margin-bottom: var(--adm-s2); }
.sp-card h3 {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--adm-text-mid);
  margin-bottom: var(--adm-s2);
}
.sp-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--adm-s1);
  margin-bottom: var(--adm-s1);
}
.sp-tip { font-size: 11px; color: var(--adm-text-weak); font-family: var(--adm-font-mono); }
.sp-note {
  margin-top: var(--adm-s2);
  padding: 10px 13px;
  border: 1px solid #f4e3b0;
  border-radius: 10px;
  background: #fffdf3;
  color: #7a5f16;
  font-size: 11.5px;
  line-height: 1.7;
}
.sp-note code {
  font-family: var(--adm-font-mono);
  background: #fff;
  border: 1px solid #efe3c4;
  border-radius: 4px;
  padding: 0 4px;
}
</style>
