<!-- 备考资料管理（内容工厂）— spec v2.2 §7.6 -->
<template>
  <div class="adm-page">
    <!-- 统计概览 -->
    <div class="stats-overview">
      <div class="stat-card">
        <div class="stat-value">{{ state.stats.total }}</div>
        <div class="stat-label">总资料数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ (state.stats.by_type.video_intro || 0) + (state.stats.by_type.video_advanced || 0) }}</div>
        <div class="stat-label">视频</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ state.stats.by_type.article || 0 }}</div>
        <div class="stat-label">文档</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ state.stats.by_type.card || 0 }}</div>
        <div class="stat-label">卡片</div>
      </div>
    </div>
    <header class="bar">
      <div>
        <h2>备考资料管理</h2>
        <p>内容唯一入口：上传素材自动加工为原生备考内容，确认后上架对学生可见</p>
      </div>
      <div class="ops">
        <select v-model="state.fSubject" @change="loadList" class="mini">
          <option value="">全部科目</option>
          <option value="xingce">行测</option>
          <option value="shenlun">申论</option>
          <option value="gongzhuan">公专</option>
        </select>
        <select v-model="state.fType" @change="loadList" class="mini">
          <option value="">全部类型</option>
          <option value="video_intro">入门视频</option>
          <option value="video_advanced">进阶视频</option>
          <option value="article">文章</option>
          <option value="card">知识卡片</option>
        </select>
        <select v-model="state.fStatus" @change="loadList" class="mini">
          <option value="">全部状态</option>
          <option value="1">已发布</option>
          <option value="0">草稿</option>
        </select>
        <input v-model="state.fKeyword" placeholder="搜索标题..."
               @keyup.enter="loadList" class="mini" style="width:140px" />
        <button class="btn" @click="loadList">搜索</button>
        <button class="btn primary" @click="openCreate">＋ 新建资料</button>
        <button class="btn" @click="state.importDlg = true; resetImport()">智能导入</button>
      </div>
    </header>

    <!-- 批量操作工具栏 -->
    <div class="batch-toolbar" v-if="state.selectedItems.length > 0">
      <span>已选择 {{ state.selectedItems.length }} 项</span>
      <button class="btn danger" @click="batchDelete">批量删除</button>
      <button class="btn" @click="batchPublish">批量上架</button>
      <button class="btn" @click="batchUnpublish">批量下架</button>
    </div>

    <table class="tbl">
      <thead>
        <tr>
          <th style="width:40px">
            <input type="checkbox" @change="toggleSelectAll" :checked="state.selectedItems.length === state.items.length && state.items.length > 0" />
          </th>
          <th style="width:60px">ID</th><th style="text-align:left">标题 / 类型</th>
          <th style="width:80px">科目</th><th style="width:110px">分类</th>
          <th style="width:70px">浏览</th><th style="width:70px">完成</th>
          <th style="width:90px">上架</th><th style="width:150px">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in state.items" :key="row.id">
          <td>
            <input type="checkbox" :value="row.id" v-model="state.selectedItems" />
          </td>
          <td>{{ row.id }}</td>
          <td class="t-title">
            <b>{{ row.title }}</b>
            <span class="type-tag">{{ TYPE_LABEL[row.type] || row.type }}</span>
            <em v-if="row.status === 0" class="off">未上架</em>
          </td>
          <td>{{ SUBJECT_LABEL[row.subject] || row.subject }}</td>
          <td>{{ row.category || '-' }}</td>
          <td>{{ row.view_count }}</td>
          <td>{{ row.study_count }}</td>
          <td>
            <label class="switch">
              <input type="checkbox" :checked="row.status === 1"
                     @change="e => setStatus(row, e.target.checked)"/><i></i>
            </label>
          </td>
          <td>
            <a class="lnk" @click="openEdit(row)">编辑</a>
            <a class="lnk danger" @click="del(row)">删除</a>
          </td>
        </tr>
        <tr v-if="!state.items.length">
          <td colspan="8" class="empty-row">暂无资料，点击右上角「新建资料」或「智能导入」开始建内容</td>
        </tr>
      </tbody>
    </table>

    <!-- 新建/编辑弹窗 -->
    <div class="mask" v-if="state.editDlg" @click.self="closeEdit">
      <div class="dlg wide">
        <header><b>{{ state.form.id ? '编辑资料 #' + state.form.id : '新建资料' }}</b>
          <i class="x" @click="closeEdit">✕</i></header>
        <div class="dlg-body">
          <div class="frow">
            <label>类型</label>
            <div class="seg">
              <button v-for="(v, k) in TYPE_LABEL" :key="k"
                      :class="{ on: state.form.type === k }"
                      :disabled="!!state.form.id"
                      @click="state.form.type = k">{{ v }}</button>
            </div>
          </div>
          <div class="frow">
            <label>科目 *</label>
            <div class="seg">
              <button :class="{ on: state.form.subject === 'xingce' }" @click="state.form.subject='xingce'">行测</button>
              <button :class="{ on: state.form.subject === 'shenlun' }" @click="state.form.subject='shenlun'">申论</button>
              <button :class="{ on: state.form.subject === 'gongzhuan' }" @click="state.form.subject='gongzhuan'">公专</button>
            </div>
          </div>
          <div class="frow"><label>标题 *</label>
            <input v-model="state.form.title" placeholder="资料标题"/></div>
          <div class="frow"><label>徽章</label>
            <input v-model="state.form.badge" placeholder="热门 / 精华 / 重要 / 新（可留空）"/></div>

          <!-- 视频 -->
          <template v-if="isVideo(state.form.type)">
            <div class="frow"><label>视频文件</label>
              <div>
                <input type="file" accept=".mp4,.mov,.webm" @change="pickVideo"/>
                <div class="up-bar" v-if="state.uploadPct > 0">
                  <i :style="{ width: state.uploadPct + '%' }"></i>
                  <span>{{ state.uploadPct }}%</span>
                </div>
                <small v-if="state.form.video_id" class="ok-tip">✓ 已关联视频 #{{ state.form.video_id }}</small>
              </div>
            </div>
            <div class="frow"><label>封面图</label>
              <input type="file" accept="image/*" @change="e => uploadImage(e, 'cover_image')"/></div>
            <div class="frow"><label>时长(秒)</label>
              <input type="number" v-model="state.form.duration" min="0"/></div>
            <div class="frow"><label>难度</label>
              <select v-model.number="state.form.difficulty" class="mini">
                <option :value="1">⭐ 基础</option><option :value="2">⭐⭐ 进阶</option><option :value="3">⭐⭐⭐ 冲刺</option>
              </select></div>
            <div class="frow"><label>简介</label>
              <textarea v-model="state.form.summary" rows="2"></textarea></div>
          </template>

          <!-- 文章 -->
          <template v-if="state.form.type === 'article'">
            <div class="frow"><label>摘要</label>
              <textarea v-model="state.form.summary" rows="2"></textarea></div>
            <div class="frow"><label>正文</label>
              <div ref="editorEl" class="editor-box"></div></div>
          </template>

          <!-- 卡片 -->
          <template v-if="state.form.type === 'card'">
            <div class="frow"><label>正面 *</label>
              <input v-model="state.form.card_front" placeholder="卡片正面：词条/关键词"/></div>
            <div class="frow"><label>背面</label>
              <textarea v-model="state.form.card_back" rows="4" placeholder="背面：释义/口诀/要点"></textarea></div>
            <div class="frow"><label>分类</label>
              <input v-model="state.form.category" placeholder="如：言语理解"/></div>
          </template>
        </div>
        <footer class="dlg-foot">
          <span class="hint">保存后为「下架态」，需在列表开启上架学生才可见</span>
          <div>
            <button class="btn" @click="closeEdit">取消</button>
            <button class="btn primary" :disabled="state.saving" @click="saveForm">
              {{ state.saving ? '保存中…' : '保存' }}
            </button>
          </div>
        </footer>
      </div>
    </div>

    <!-- 智能导入向导 -->
    <div class="mask" v-if="state.importDlg" @click.self="state.importDlg = false">
      <div class="dlg wide">
        <header><b>智能导入素材</b><i class="x" @click="state.importDlg = false">✕</i></header>
        <div class="dlg-body">
          <ol class="steps">
            <li :class="{ on: impStep >= 1 }">① 上传</li>
            <li :class="{ on: impStep >= 2 }">② 解析</li>
            <li :class="{ on: impStep >= 3 }">③ 预览</li>
            <li :class="{ on: impStep >= 4 }">④ 入库</li>
          </ol>
          <div class="drop" v-if="impStep <= 1">
            <input type="file" accept=".docx,.xlsx,.pdf" id="impFile"
                   @change="importPick" :disabled="state.imp.busy"/>
            <label for="impFile">点击选择文件（支持 .docx 讲义 / .xlsx 词库 / .pdf 文档，≤20MB）</label>
          </div>
          <div v-if="state.imp.parse_status === 'processing'" class="ocr-tip">
            ⏳ 文字识别解析中…已耗时 {{ state.imp.elapsed }}秒
            <br/><small>扫描件解析较慢（约1分钟/页），请勿关闭本窗口</small>
          </div>
          <div v-if="state.imp.error" class="err-tip">{{ state.imp.error }}</div>

          <!-- 文档预览 -->
          <template v-if="state.imp.result && state.imp.file_type !== 'xlsx'">
            <b class="sec-b">章节预览</b>
            <ul class="chapters">
              <li v-for="c in state.imp.result.chapters" :key="c.title">{{ c.title }}</li>
            </ul>
            <details open>
              <summary>渲染预览（{{ state.imp.result.word_count }} 字）</summary>
              <div class="material-article preview" v-html="sanitizeHtml(state.imp.result.html)"></div>
            </details>
          </template>
          <!-- Excel 列映射预览 -->
          <template v-if="state.imp.result && state.imp.file_type === 'xlsx'">
            <b class="sec-b">共 {{ state.imp.result.total_rows }} 行数据 — 选择列映射生成知识卡片</b>
            <div class="map-row">
              正面列 <select v-model.number="state.imp.mapping.front">
                <option v-for="(h, i) in state.imp.result.headers" :key="i" :value="i">{{ h || ('第' + (i+1) + '列') }}</option>
              </select>
              背面列 <select v-model.number="state.imp.mapping.back">
                <option v-for="(h, i) in state.imp.result.headers" :key="i" :value="i">{{ h || ('第' + (i+1) + '列') }}</option>
              </select>
              分类列 <select v-model="state.imp.mapping.category">
                <option :value="null">无</option>
                <option v-for="(h, i) in state.imp.result.headers" :key="i" :value="i">{{ h || ('第' + (i+1) + '列') }}</option>
              </select>
            </div>
            <div class="card-prev">
              <div class="cp" v-for="(r, i) in (state.imp.result.rows || []).slice(0, 12)" :key="i">
                <b>{{ r[state.imp.mapping.front] }}</b><span>{{ r[state.imp.mapping.back] }}</span>
              </div>
            </div>
          </template>

          <!-- 元信息 + 入库 -->
          <div class="meta-form" v-if="canConfirmImport()">
            <select v-model="state.imp.subject" class="mini">
              <option value="xingce">入行测</option><option value="shenlun">入申论</option><option value="gongzhuan">入公专</option>
            </select>
            <select v-if="state.imp.file_type !== 'xlsx'" v-model="state.imp.type" class="mini">
              <option value="article">作为文章</option>
            </select>
            <input v-model="state.imp.category" placeholder="分类标签(可空)" class="mini"/>
            <button class="btn primary" :disabled="state.imp.confirming" @click="importConfirm">
              {{ state.imp.confirming ? '入库中…' : '确认入库（下架态）' }}
            </button>
          </div>
          <div v-if="state.imp.createdText" class="ok-tip big">{{ state.imp.createdText }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive } from 'vue';
import { ElMessage } from 'element-plus';
import { useProvider } from '@vtj/renderer';
import { sanitizeHtml } from '@/utils/questionRender';

const TYPE_LABEL = {
  video_intro: '入门视频', video_advanced: '进阶视频',
  article: '文章', card: '知识卡片'
};
const SUBJECT_LABEL = { xingce: '行测', shenlun: '申论', gongzhuan: '公专' };
const CHUNK_SIZE = 5 * 1024 * 1024;   // videos.py 固定 5MB 分片

export default defineComponent({
  name: 'AdminMaterials',
  components: {},
  setup(props) {
    const provider = useProvider({ id: 'admin_materials', version: '20260825001' });
    const state = reactive({
      items: [], fSubject: '', fType: '', fStatus: '', fKeyword: '',
      selectedItems: [],
      editDlg: false, saving: false,
      form: {}, editor: null, editorReady: false,
      uploadPct: 0,
      importDlg: false,
      imp: { busy: false, id: null, file_type: '', parse_status: '',
             elapsed: 0, error: '', result: null,
             subject: 'xingce', type: 'article', category: '',
             mapping: { front: 0, back: 1, category: null },
             confirming: false, createdText: '' },
      stats: { total: 0, by_type: { video_intro: 0, video_advanced: 0, article: 0, card: 0 },
               by_subject: { xingce: 0, shenlun: 0, gongzhuan: 0 },
               by_status: { published: 0, draft: 0 } }
    });
    return { state, props, provider, TYPE_LABEL, SUBJECT_LABEL, sanitizeHtml };
  },
  computed: {
    impStep() {
      const i = this.state.imp;
      if (i.createdText || i.parse_status === 'consumed') return 4;
      if (i.result) return 3;
      if (i.id && (i.parse_status === 'success' ||
          i.parse_status === 'processing')) return 2;
      return 1;
    }
  },
  methods: {
    isVideo(t) { return t === 'video_intro' || t === 'video_advanced'; },
    api(url, opt) { return window.__VTJ_AUTH__.apiFetch(url, opt); },
    async loadList() {
      const q = new URLSearchParams();
      if (this.state.fSubject) q.set('subject', this.state.fSubject);
      if (this.state.fType) q.set('type', this.state.fType);
      if (this.state.fStatus !== '') q.set('status', this.state.fStatus);
      if (this.state.fKeyword) q.set('keyword', this.state.fKeyword);
      q.set('page_size', '100');
      try {
        const r = await this.api('/api/materials/admin/list?' + q.toString());
        if (!r.ok) throw new Error('加载失败');
        const d = await r.json();
        this.state.items = d.items || [];
      } catch (e) { ElMessage.error(e.message); }
    },

    /* ---------- 统计概览 ---------- */
    async loadStats() {
      try {
        const r = await this.api('/api/materials/admin/stats');
        if (!r.ok) return;
        const d = await r.json();
        this.state.stats = d;
      } catch (e) { console.warn('[AdminMaterials] loadStats failed:', e); }
    },

    /* ---------- 批量操作 ---------- */
    toggleSelectAll(e) {
      if (e.target.checked) {
        this.state.selectedItems = this.state.items.map(item => item.id);
      } else {
        this.state.selectedItems = [];
      }
    },
    async batchDelete() {
      if (!confirm('确认删除选中的 ' + this.state.selectedItems.length + ' 项资料？')) return;
      try {
        const r = await this.api('/api/materials/admin/batch', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids: this.state.selectedItems })
        });
        if (!r.ok) throw new Error('批量删除失败');
        ElMessage.success('批量删除成功');
        this.state.selectedItems = [];
        this.loadList();
        this.loadStats();
      } catch (e) { ElMessage.error(e.message); }
    },
    async batchPublish() {
      try {
        for (const id of this.state.selectedItems) {
          await this.api('/api/materials/admin/' + id + '/status', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 1 })
          });
        }
        ElMessage.success('批量上架成功');
        this.state.selectedItems = [];
        this.loadList();
      } catch (e) { ElMessage.error(e.message); }
    },
    async batchUnpublish() {
      try {
        for (const id of this.state.selectedItems) {
          await this.api('/api/materials/admin/' + id + '/status', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 0 })
          });
        }
        ElMessage.success('批量下架成功');
        this.state.selectedItems = [];
        this.loadList();
      } catch (e) { ElMessage.error(e.message); }
    },

    /* ---------- 新建/编辑 ---------- */
    openCreate() {
      this.state.form = { type: 'article', subject: 'xingce', title: '',
        summary: '', content: '', card_front: '', card_back: '',
        category: '', badge: '', duration: 0, difficulty: 1, cover_image: '' };
      this.state.uploadPct = 0;
      this.state.editDlg = true;
    },
    async openEdit(row) {
      try {
        const r = await this.api(`/api/materials/${row.id}`);
        if (!r.ok) throw new Error('详情获取失败');
        const d = await r.json();
        // 学生详情接口对下架内容返回404 → 用列表行数据兜底
        this.state.form = r.ok ? { ...row, content: d.content || '',
          summary: d.summary ?? row.summary } : { ...row };
      } catch (e) {
        this.state.form = { ...row };   // 下架态兜底
      }
      this.state.editDlg = true;
    },
    closeEdit() { this.destroyEditor(); this.state.editDlg = false; },
    async saveForm() {
      const f = this.state.form;
      if (!f.subject || !f.title || !f.title.trim()) {
        ElMessage.warning('科目与标题必填'); return;
      }
      if (f.type === 'card' && !(f.card_front || '').trim()) {
        ElMessage.warning('卡片正面必填'); return;
      }
      if (this.isVideo(f.type) && !f.video_id) {
        ElMessage.warning('请先上传视频'); return;
      }
      this.state.saving = true;
      try {
        const payload = {};
        for (const k of ('subject,type,category,title,summary,content,' +
            'card_front,card_back,cover_image,video_id,duration,read_time,' +
            'difficulty,badge,sort_order').split(',')) {
          payload[k] = f[k];
        }
        if (this.isVideo(f.type)) payload.video_id = f.video_id || null;
        else { delete payload.video_id; delete payload.duration; delete payload.cover_image; }
        if (f.type !== 'card') { delete payload.card_front; delete payload.card_back; }
        const url = f.id ? `/api/materials/admin/${f.id}` : '/api/materials/admin';
        const r = await this.api(url, {
          method: f.id ? 'PUT' : 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!r.ok) {
          const d = await r.json().catch(() => ({}));
          throw new Error(d.error?.message || d.detail || '保存失败');
        }
        ElMessage.success('已保存（下架态）——请在列表开启上架');
        this.closeEdit(); this.loadList();
      } catch (e) { ElMessage.error(e.message); }
      finally { this.state.saving = false; }
    },
    async setStatus(row, v) {
      try {
        const r = await this.api(`/api/materials/admin/${row.id}/status`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: v ? 1 : 0 })
        });
        if (!r.ok) throw new Error('操作失败');
        row.status = v ? 1 : 0;
        ElMessage.success(v ? '已上架，学生端立即可见' : '已下架');
      } catch (e) { ElMessage.error(e.message); }
    },
    async del(row) {
      if (!confirm(`确认删除「${row.title}」？学习进度记录将一并清除。`)) return;
      try {
        const r = await this.api(`/api/materials/admin/${row.id}`, { method: 'DELETE' });
        if (!r.ok) throw new Error('删除失败');
        ElMessage.success('已删除'); this.loadList();
      } catch (e) { ElMessage.error(e.message); }
    },

    /* ---------- wangeditor 动态挂载/销毁 ---------- */
    async mountEditor() {
      if (this.state.editor || !this.$refs.editorEl) return;
      try {
        const E = (await import('wangeditor')).default;
        const ed = new E(this.$refs.editorEl);
        ed.config.height = 300;
        ed.config.placeholder = '撰写文章正文，支持图片、表格、加粗高亮…';
        ed.config.customUploadImg = async (files, insert) => {
          for (const f of files) {
            const url = await this.uploadFileTo(f, '/api/materials/admin/upload/image');
            if (url) insert(url);
          }
        };
        ed.create();
        ed.txt.html(this.state.form.content || '');
        this.state.editor = ed;
        this.state.editorReady = true;
      } catch (e) {
        console.warn('[AdminMaterials] editor load failed:', e);
        ElMessage.warning('富文本编辑器加载失败，可改用「智能导入」');
      }
    },
    destroyEditor() {
      if (this.state.editor) { this.state.editor.destroy(); this.state.editor = null; }
    },

    /* ---------- 上传工具 ---------- */
    async uploadFileTo(file, url) {
      const fd = new FormData(); fd.append('file', file);
      try {
        const r = await this.api(url, { method: 'POST', body: fd });
        const d = await r.json();
        if (!r.ok) throw new Error(d.error?.message || d.detail || '上传失败');
        return d.url;
      } catch (e) { ElMessage.error(e.message); return ''; }
    },
    async uploadImage(e, field) {
      const f = e.target.files[0]; if (!f) return;
      const url = await this.uploadFileTo(f, '/api/materials/admin/upload/image');
      if (url) this.state.form[field] = url;
    },

    /* ---------- 视频分片上传（协议经 T10 实测核对：
       init/complete 走 query 参数；chunk 走 form；complete 返回顶层 video_id）---------- */
    async pickVideo(e) {
      const file = e.target.files[0]; if (!file) return;
      this.state.uploadPct = 1;
      try {
        const ir = await this.api(
          `/api/video/upload/init?filename=${encodeURIComponent(file.name)}&file_size=${file.size}`);
        const init = await ir.json();
        if (!ir.ok) throw new Error(init.detail || init.message || '初始化失败');
        const uploadId = init.data.upload_id;
        let sent = 0, index = 0;
        while (sent < file.size) {
          const blob = file.slice(sent, Math.min(sent + CHUNK_SIZE, file.size));
          const fd = new FormData();
          fd.append('upload_id', uploadId);
          fd.append('chunk_index', String(index));
          fd.append('file', blob);
          const cr = await this.api('/api/video/upload/chunk',
            { method: 'POST', body: fd });
          if (!cr.ok) throw new Error(`分片 ${index} 上传失败`);
          sent += blob.size; index += 1;
          this.state.uploadPct = Math.round((sent / file.size) * 100);
        }
        const cr = await this.api(
          `/api/video/upload/complete?upload_id=${uploadId}&filename=${encodeURIComponent(file.name)}`);
        const done = await cr.json();
        if (!cr.ok) throw new Error(done.detail || '合并失败');
        this.state.form.video_id = done.video_id ?? (done.data && done.data.video_id);
        if (done.duration) this.state.form.duration = Math.round(done.duration);
        ElMessage.success('视频上传完成');
      } catch (err) {
        ElMessage.error(err.message); this.state.uploadPct = 0;
      }
    },

    /* ---------- 智能导入向导 ---------- */
    resetImport() {
      Object.assign(this.state.imp, { busy: false, id: null, file_type: '',
        parse_status: '', elapsed: 0, error: '', result: null,
        confirming: false, createdText: '' });
    },
    async importPick(e) {
      const f = e.target.files[0]; if (!f) return;
      const ext = '.' + f.name.split('.').pop().toLowerCase();
      this.state.imp.busy = true;
      this.state.imp.error = '';
      try {
        const fd = new FormData(); fd.append('file', f);
        const r = await this.api('/api/materials/admin/import/upload',
          { method: 'POST', body: fd });
        const d = await r.json();
        if (!r.ok) throw new Error(d.error?.message || d.detail || '上传失败');
        this.state.imp.id = d.import_id;
        this.state.imp.parse_status = d.parse_status;
        this.state.imp.file_type = ext.slice(1);
        if (d.error_message) this.state.imp.error = d.error_message;
        if (d.parse_status === 'processing') this.pollStatus();
        else if (d.parse_status === 'success') await this.fetchPreview();
      } catch (err) { this.state.imp.error = err.message; }
      finally { this.state.imp.busy = false; }
    },
    pollStatus() {
      const imp = this.state.imp;
      const timer = setInterval(async () => {
        if (!imp.id || imp.parse_status !== 'processing') {
          clearInterval(timer); return;
        }
        try {
          const r = await this.api(`/api/materials/admin/import/${imp.id}/status`);
          const d = await r.json();
          imp.parse_status = d.parse_status;
          imp.elapsed = d.elapsed_seconds;
          if (d.error_message) imp.error = d.error_message;
          if (d.parse_status === 'success') await this.fetchPreview();
        } catch (e) { console.warn('[Import] poll failed:', e); }
      }, 3000);
    },
    async fetchPreview() {
      const imp = this.state.imp;
      try {
        const r = await this.api(`/api/materials/admin/import/${imp.id}/preview`);
        if (!r.ok) return;
        const d = await r.json();
        imp.result = d.result;
        if (d.file_type === 'xlsx' && imp.subject) imp.type = 'card';
      } catch (e) { console.warn('[Import] preview failed:', e); }
    },
    canConfirmImport() {
      const i = this.state.imp;
      if (i.parse_status !== 'success' || !i.subject || i.createdText) return false;
      if (i.file_type === 'xlsx') {
        const m = i.mapping;
        return Number.isInteger(m.front) && Number.isInteger(m.back) && m.front !== m.back;
      }
      return true;
    },
    async importConfirm() {
      const i = this.state.imp;
      i.confirming = true;
      try {
        const body = { subject: i.subject, type: i.type, category: i.category };
        if (i.file_type === 'xlsx') body.column_mapping = i.mapping;
        const r = await this.api(`/api/materials/admin/import/${i.id}/confirm`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.error?.message || d.detail || '入库失败');
        i.createdText = `✅ 成功创建 ${d.created} 条资料（下架态），可在列表逐一上架`;
        i.parse_status = 'consumed';
        this.loadList();
      } catch (e) { ElMessage.error(e.message); }
      finally { i.confirming = false; }
    }
  },
  watch: {
    'state.editDlg'(v) {
      if (v && this.state.form.type === 'article') {
        this.$nextTick(() => this.mountEditor());
      }
      if (!v) this.destroyEditor();
    },
    'state.form.type'(t) {
      if (t === 'article' && this.state.editDlg) {
        this.$nextTick(() => this.mountEditor());
      }
    }
  },
  mounted() { this.loadList(); this.loadStats(); },
  beforeUnmount() { this.destroyEditor(); }
})
</script>

<style lang="css" scoped>
/* 统计概览 */
.stats-overview { display: flex; gap: 16px; margin-bottom: 20px; }
.stat-card { flex: 1; background: #fff; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 2px 12px rgba(10,22,40,.05); }
.stat-value { font-size: 28px; font-weight: 600; color: #1a2a4a; margin-bottom: 8px; }
.stat-label { font-size: 13px; color: #8899aa; }
/* 批量操作工具栏 */
.batch-toolbar { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: #f5f7fa; border-radius: 8px; margin-bottom: 16px; }
.batch-toolbar span { font-size: 13px; color: #5a6b85; }
.btn.danger { background: rgba(196, 30, 58, 0.08); border-color: #c41e3a; color: #c41e3a; }
/* 原有样式 */
.adm-page { max-width: 1280px; margin: 0 auto; padding: 24px; }
.bar { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 18px; gap: 14px; flex-wrap: wrap; }
.bar h2 { color: #1a2a4a; margin: 0 0 4px; font-size: 21px; }
.bar p { color: #8899aa; font-size: 12px; margin: 0; }
.ops { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.btn { border: 1px solid #d7dee9; background: #fff; color: #33415c; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 13px; }
.btn.primary { background: linear-gradient(135deg, #c8161e, #a0121a); border-color: transparent; color: #fff; font-weight: 600; }
.btn:disabled { opacity: .55; cursor: not-allowed; }
.mini { padding: 7px 10px; border: 1px solid #d7dee9; border-radius: 8px; font-size: 13px; background: #fff; }
/* 表格 */
.tbl { width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(10,22,40,.05); }
.tbl th { background: #f5f7fa; color: #5a6b85; font-size: 12px; padding: 11px 8px; text-align: center; }
.tbl td { padding: 11px 8px; border-top: 1px solid #f0f2f5; text-align: center; font-size: 13px; color: #33415c; }
.t-title { text-align: left !important; max-width: 380px; }
.t-title b { font-weight: 600; }
.type-tag { display: inline-block; margin-left: 8px; font-size: 11px; color: #1a63d8; background: rgba(26,99,216,.08); padding: 1px 8px; border-radius: 4px; }
.off { display: inline-block; margin-left: 6px; font-style: normal; font-size: 11px; color: #c41e3a; background: rgba(196,30,58,.08); padding: 1px 6px; border-radius: 4px; }
.lnk { cursor: pointer; color: #1a63d8; margin: 0 6px; font-size: 13px; }
.lnk.danger { color: #c41e3a; }
.empty-row { padding: 46px 0 !important; color: #98a4b8; }
/* 开关 */
.switch { position: relative; display: inline-block; width: 38px; height: 20px; }
.switch input { opacity: 0; width: 0; height: 0; }
.switch i { position: absolute; inset: 0; background: #cbd5e1; border-radius: 10px; transition: .25s; cursor: pointer; }
.switch i::before { content: ''; position: absolute; width: 16px; height: 16px; left: 2px; top: 2px; background: #fff; border-radius: 50%; transition: .25s; }
.switch input:checked + i { background: #10b981; }
.switch input:checked + i::before { transform: translateX(18px); }
/* 弹窗 */
.mask { position: fixed; inset: 0; background: rgba(10,22,40,.45); z-index: 100; display: flex; align-items: flex-start; justify-content: center; overflow-y: auto; padding: 40px 16px; }
.dlg { background: #fff; border-radius: 14px; width: 560px; max-width: 96vw; box-shadow: 0 18px 50px rgba(10,22,40,.2); }
.dlg.wide { width: 860px; }
.dlg header { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; border-bottom: 1px solid #f0f2f5; color: #1a2a4a; }
.dlg .x { cursor: pointer; font-style: normal; color: #98a4b8; font-size: 16px; }
.dlg-body { padding: 18px 20px; max-height: 66vh; overflow-y: auto; }
.frow { display: flex; gap: 12px; margin-bottom: 14px; align-items: flex-start; }
.frow > label { width: 76px; flex-shrink: 0; font-size: 13px; color: #5a6b85; padding-top: 8px; text-align: right; }
.frow input[type=text], .frow input:not([type]), .frow textarea, .frow select { flex: 1; padding: 8px 10px; border: 1px solid #d7dee9; border-radius: 8px; font-size: 13px; width: 100%; box-sizing: border-box; }
.seg { display: flex; gap: 6px; flex-wrap: wrap; }
.seg button { border: 1px solid #d7dee9; background: #fff; padding: 7px 14px; border-radius: 8px; cursor: pointer; font-size: 13px; }
.seg button.on { background: rgba(200,22,30,.07); border-color: #c8161e; color: #c8161e; font-weight: 600; }
.up-bar { height: 8px; background: #eef1f6; border-radius: 4px; overflow: hidden; margin-top: 8px; position: relative; }
.up-bar i { display: block; height: 100%; background: linear-gradient(90deg,#c8161e,#e8384f); transition: width .3s; }
.up-bar span { position: absolute; right: 6px; top: -4px; font-size: 10px; color: #fff; mix-blend-mode: difference; }
.ok-tip { color: #10b981; font-size: 12px; margin-top: 6px; }
.ok-tip.big { font-size: 14px; font-weight: 600; padding: 10px; background: rgba(16,185,129,.08); border-radius: 8px; }
.hint { font-size: 11px; color: #98a4b8; }
.dlg-foot { display: flex; justify-content: space-between; align-items: center; padding: 13px 20px; border-top: 1px solid #f0f2f5; gap: 10px; }
.editor-box { width: 100%; min-height: 320px; border: 1px solid #d7dee9; border-radius: 8px; overflow: hidden; }
/* 导入向导 */
.steps { display: flex; list-style: none; padding: 0; margin: 0 0 16px; gap: 6px; }
.steps li { flex: 1; text-align: center; font-size: 12px; color: #98a4b8; padding: 8px 0; background: #f5f7fa; border-radius: 6px; }
.steps li.on { color: #c8161e; background: rgba(200,22,30,.07); font-weight: 600; }
.drop { border: 2px dashed #cbd5e1; border-radius: 10px; padding: 28px; text-align: center; }
.drop label { cursor: pointer; color: #5a6b85; font-size: 13px; }
.drop input { display: none; }
.ocr-tip { margin-top: 12px; padding: 12px; background: rgba(26,99,216,.06); border-radius: 8px; color: #1a63d8; font-size: 13px; text-align: center; }
.err-tip { margin-top: 12px; padding: 12px; background: rgba(196,30,58,.06); border-radius: 8px; color: #c41e3a; font-size: 13px; }
.sec-b { display: block; margin: 16px 0 8px; color: #1a2a4a; font-size: 13px; }
.chapters { margin: 0 0 8px; padding-left: 20px; color: #33415c; font-size: 13px; }
.preview { border: 1px solid #eef1f6; border-radius: 8px; padding: 14px; max-height: 300px; overflow-y: auto; }
.map-row { display: flex; gap: 12px; align-items: center; font-size: 13px; color: #5a6b85; margin-bottom: 12px; flex-wrap: wrap; }
.card-prev { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }
.cp { border: 1px solid #eef1f6; border-radius: 8px; padding: 8px 10px; font-size: 12px; }
.cp b { display: block; color: #1a2a4a; }
.cp span { color: #8899aa; }
.meta-form { display: flex; gap: 10px; margin-top: 16px; align-items: center; flex-wrap: wrap; }
@media (max-width: 768px) {
  .frow { flex-direction: column; gap: 4px; }
  .frow > label { width: auto; text-align: left; padding-top: 0; }
}
</style>
