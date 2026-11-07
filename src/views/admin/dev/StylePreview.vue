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
      </div>
    </div>

    <div class="sp-note">
      色值/圆角/字号全部来自 <code>src/styles/admin-tokens.css</code>（CSS 变量），页面里不再写字面量。
      保留 emoji 图标（E3 裁定），但尺寸、对齐、透明度由 <code>AdminStatCard</code> 统一。
      本页仅管理员可见，用于 E1/E2 改造时的视觉基准。
    </div>
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
  AdminFormItem
} from '@/components/admin';

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
