<!-- 行测备考资料（主题色 #3B82F6）— spec v2.2 §7.4 -->
<template>
  <div class="mat-page" :style="{ '--c': '#3B82F6' }">
    <header class="top-bar">
      <a class="back" @click="$router.push('/home')">← 返回首页</a>
      <h1>行测备考资料</h1>
      <label class="fav-toggle">
        <input type="checkbox" v-model="state.showFav"/> 只看收藏
      </label>
    </header>

    <section class="hero">
      <div class="hero-text">
        <h2>行测 · 行政职业能力测验</h2>
        <p>掌握五大模块解题规律，快速提升答题速度与准确率</p>
      </div>
      <div class="progress-line" v-if="state.loggedIn">
        学习进度
        <div class="bar"><i :style="{ width: state.summary.percentage + '%' }"></i></div>
        <b>{{ state.summary.percentage }}%</b>
        <span>（已完成 {{ state.summary.studied }}/{{ state.summary.total }}）</span>
      </div>
      <div class="progress-line muted" v-else>登录后可记录学习进度与收藏</div>
    </section>

    <template v-for="sec in sections()" :key="sec.key">
      <section class="block" v-if="state.loaded[sec.key] && list(sec.key).length">
        <div class="block-head">
          <h3>{{ sec.icon }} {{ sec.title }}</h3>
          <a v-if="(state.data[sec.key] || []).length > 4"
             @click="toggleFold(sec.key)">
            {{ state.folded[sec.key] ? '展开全部 ▾' : '收起 ▴' }}
          </a>
        </div>

        <!-- 视频：横向滚动卡片 -->
        <div v-if="sec.kind === 'video'" class="hscroll">
          <div class="vcard" v-for="it in list(sec.key)" :key="it.id"
               @click="openVideo(it)">
            <img :src="it.cover_image || fallbackCover(sec.key)" loading="lazy"/>
            <b class="dur">{{ fmtDur(it.duration) }}</b>
            <em class="done" v-if="it.is_studied">✅ 已学</em>
            <em class="prog" v-else-if="(it.progress_percent || 0) > 0">⏳ {{ it.progress_percent }}%</em>
            <span class="vtitle">{{ it.title }}</span>
            <span class="vmeta">{{ it.category || '行测' }} · {{ it.view_count }} 次学习</span>
          </div>
        </div>

        <!-- 文章：纵向列表 -->
        <ul v-if="sec.kind === 'article'" class="alist">
          <li v-for="it in list(sec.key)" :key="it.id" @click="openArticle(it)">
            <i class="a-icon">📄</i>
            <div class="a-body">
              <span class="a-title">{{ it.title }} <em v-if="it.is_studied">已读</em></span>
              <span class="a-sum" v-if="it.summary">{{ it.summary }}</span>
            </div>
            <small>{{ it.read_time }}min · {{ it.view_count }} 阅读</small>
            <span class="arrow">›</span>
          </li>
        </ul>

        <!-- 知识卡片：3D 翻转网格 -->
        <div v-if="sec.kind === 'card'" class="card-grid">
          <div v-for="it in list(sec.key)" :key="it.id"
               class="flip" :class="{ flipped: state.flipped[it.id] }"
               @click="flipCard(it)">
            <div class="inner">
              <div class="face front">
                <span class="tag">{{ it.category || '知识点' }}</span>
                <p>{{ it.card_front || it.title }}</p>
                <i>👆 点击翻转</i>
              </div>
              <div class="face back"><p>{{ it.card_back || '暂无背面内容' }}</p></div>
            </div>
          </div>
        </div>
      </section>
    </template>

    <!-- 整页空状态 -->
    <div class="empty-page" v-if="state.pageEmpty">
      <div class="empty-icon">📚</div>
      <p>该科目备考资料正在加紧制作中，敬请期待…</p>
      <div class="empty-btns">
        <button @click="$router.push('/home')">返回首页</button>
        <button class="ghost" @click="$router.push('/materials/shenlun')">去看申论</button>
      </div>
    </div>

    <!-- 视频播放弹窗 -->
    <el-dialog v-model="state.videoDlg" :title="state.cur.title || '视频学习'"
               width="900px" destroy-on-close class="video-dlg">
      <video v-if="state.videoDlg" controls autoplay playsinline
             style="width:100%;border-radius:8px;background:#000;max-height:60vh"
             :src="state.cur.video_url"
             @timeupdate="onVideoTime" @ended="markDone(state.cur)"></video>
      <p class="dlg-summary" v-if="state.cur.summary">{{ state.cur.summary }}</p>
      <footer class="dlg-foot">
        <span>{{ fmtDur(state.cur.duration) }} · 难度{{ '⭐'.repeat(state.cur.difficulty || 1) }}</span>
        <el-button size="small" round @click="toggleFav(state.cur)">
          {{ state.cur.is_favorite ? '★ 已收藏' : '☆ 收藏' }}
        </el-button>
      </footer>
    </el-dialog>

    <!-- 文章阅读弹窗 -->
    <el-dialog v-model="state.articleDlg" :title="state.cur.title || '备考指南'"
               width="820px" top="4vh" destroy-on-close>
      <div class="material-article" v-html="state.cur.content"></div>
      <footer class="dlg-foot">
        <span v-if="state.cur.read_time">约 {{ state.cur.read_time }} 分钟阅读</span>
        <el-button size="small" round @click="toggleFav(state.cur)">
          {{ state.cur.is_favorite ? '★ 已收藏' : '☆ 收藏' }}
        </el-button>
      </footer>
    </el-dialog>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive } from 'vue';
import { ElMessage } from 'element-plus';
import { useProvider } from '@vtj/renderer';

const SUBJECT = 'xingce';
const PAGE_VERSION = '20260825001';

export default defineComponent({
  name: 'MaterialsXingce',
  components: {},
  setup(props) {
    const provider = useProvider({ id: 'materials_xingce', version: PAGE_VERSION });
    const state = reactive({
      loggedIn: false,
      showFav: false,
      data: { video_intro: [], video_advanced: [], article: [], card: [] },
      loaded: { video_intro: false, video_advanced: false, article: false, card: false },
      folded: { video_intro: true, video_advanced: true, article: false, card: false },
      summary: { percentage: 0, studied: 0, total: 0 },
      pageEmpty: false,
      cur: {},
      videoDlg: false,
      articleDlg: false,
      flipped: {},
      _lastReport: {}
    });
    return { state, props, provider };
  },
  methods: {
    sections() {
      return [
        { key: 'video_intro', kind: 'video', title: '入门讲解视频', icon: '🎬' },
        { key: 'video_advanced', kind: 'video', title: '深度拓展视频', icon: '🎯' },
        { key: 'article', kind: 'article', title: '备考指南', icon: '📋' },
        { key: 'card', kind: 'card', title: '知识卡片', icon: '🃏' }
      ];
    },
    list(key) {
      const arr = this.state.data[key] || [];
      if (this.state.showFav) return arr.filter(i => i.is_favorite);
      return this.state.folded[key] ? arr.slice(0, 4) : arr;
    },
    toggleFold(key) {
      this.state.folded[key] = !this.state.folded[key];
    },
    async fetchAll() {
      for (const sec of this.sections()) {
        try {
          const r = await window.__VTJ_AUTH__.apiFetch(
            `/api/materials?subject=${SUBJECT}&type=${sec.key}&page_size=50`);
          const d = await r.json();
          this.state.data[sec.key] = d.items || [];
        } catch (e) {
          console.warn('[MatPage] load failed:', sec.key, e && e.message);
        } finally {
          this.state.loaded[sec.key] = true;
        }
      }
      this.state.pageEmpty =
        this.sections().every(s => !(this.state.data[s.key] || []).length);
    },
    async fetchSummary() {
      try {
        const auth = window.__VTJ_AUTH__ || {};
        this.state.loggedIn = !!(auth.isLoggedIn && auth.isLoggedIn());
        if (!this.state.loggedIn) return;
        const r = await window.__VTJ_AUTH__.apiFetch(
          `/api/materials/progress-summary?subject=${SUBJECT}`);
        if (r.ok) this.state.summary = await r.json();
      } catch (e) {
        console.warn('[MatPage] summary failed:', e && e.message);
      }
    },
    async ensureDetail(item) {
      // 列表接口不含 content/card_back/video_url，弹窗前拉详情补全
      if (item._detailLoaded) return item;
      try {
        const r = await window.__VTJ_AUTH__.apiFetch(`/api/materials/${item.id}`);
        if (r.ok) {
          const d = await r.json();
          Object.assign(item, d);
          item._detailLoaded = true;
        }
      } catch (e) {
        console.warn('[MatPage] detail failed:', e && e.message);
      }
      return item;
    },
    async openVideo(it) {
      await this.ensureDetail(it);
      if (!it.video_url && !it.video_id) {
        ElMessage.warning('该视频资源暂不可用');
        return;
      }
      this.state.cur = it;
      this.state.videoDlg = true;
    },
    async openArticle(it) {
      await this.ensureDetail(it);
      this.state.cur = it;
      this.state.articleDlg = true;
      this.report(it, 5, false);
    },
    cardBack(it) {
      return it.card_back || '';
    },
    flipCard(it) {
      this.state.flipped[it.id] = !this.state.flipped[it.id];
      if (this.state.flipped[it.id] && !it.is_studied) {
        this.markDone(it);   // 后端 UPSERT 幂等，重复翻看不重复计数
        it.is_studied = true;
      }
    },
    onVideoTime(e) {
      const v = e.target;
      if (!v || !v.duration) return;
      const pct = Math.round((v.currentTime / v.duration) * 100);
      this.report(this.state.cur, pct, pct >= 95);
    },
    report(item, pct, done) {
      if (!this.state.loggedIn || !item || !item.id) return;
      const now = Date.now();
      const last = this.state._lastReport[item.id];
      const due = !last || now - last.ts >= 10000 ||
                  Math.abs(pct - (last.pct || 0)) >= 20;
      if (!done && !due) return;
      this.state._lastReport[item.id] = { ts: now, pct };
      window.__VTJ_AUTH__.apiFetch('/api/materials/progress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          material_id: item.id, progress_percent: pct, completed: !!done })
      }).then(r => r.json()).then(d => {
        if (d && d.completed) {
          item.is_studied = true;
          this.fetchSummary();
        }
      }).catch(() => {});
    },
    markDone(it) {
      this.report(it, 100, true);
    },
    async toggleFav(it) {
      if (!this.state.loggedIn) {
        ElMessage.info('登录后可收藏资料');
        return;
      }
      try {
        const r = await window.__VTJ_AUTH__.apiFetch(
          `/api/materials/${it.id}/favorite`, { method: 'POST' });
        const d = await r.json();
        it.is_favorite = !!d.is_favorite;
        ElMessage.success(d.is_favorite ? '已收藏' : '已取消收藏');
      } catch (e) {
        console.warn('[MatPage] fav failed:', e && e.message);
      }
    },
    fmtDur(s) {
      s = s || 0;
      const m = Math.floor(s / 60);
      const ss = ('' + (s % 60)).padStart(2, '0');
      return `${m}:${ss}`;
    },
    fallbackCover(key) {
      const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='400' height='225'>
        <rect width='100%' height='100%' fill='%233B82F6' opacity='0.12'/>
        <text x='50%' y='50%' font-size='42' text-anchor='middle' dominant-baseline='middle'>▶</text></svg>`;
      return 'data:image/svg+xml;charset=utf-8,' + svg;
    }
  },
  mounted() {
    this.fetchAll();
    this.fetchSummary();
  }
})
</script>

<style lang="css" scoped>
.mat-page { min-height: 100vh; background: #f5f7fb; padding-bottom: 40px; }
/* 顶部条 */
.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px; background: #fff; border-bottom: 1px solid #eef1f6;
  position: sticky; top: 0; z-index: 10;
}
.back { cursor: pointer; color: #5a6b85; font-size: 14px; }
.back:hover { color: var(--c); }
.top-bar h1 { font-size: 17px; color: #1a2a4a; margin: 0; }
.fav-toggle { font-size: 13px; color: #5a6b85; cursor: pointer; display: flex; align-items: center; gap: 6px; }
/* 英雄区 */
.hero {
  max-width: 1200px; margin: 20px auto; padding: 26px 30px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(59,130,246,.10), #ffffff);
  border: 1px solid rgba(59,130,246,.25);
}
.hero h2 { color: #1a2a4a; font-size: 22px; margin: 0 0 6px; }
.hero p { color: #66738a; font-size: 13px; margin: 0; }
.progress-line {
  display: flex; align-items: center; gap: 10px;
  font-size: 12px; color: #5a6b85; margin-top: 14px;
}
.progress-line.muted { color: #9aa7bd; }
.progress-line .bar {
  width: 220px; height: 8px; background: #eef1f6;
  border-radius: 4px; overflow: hidden;
}
.progress-line .bar i { display: block; height: 100%; background: var(--c); transition: width .6s; }
.progress-line b { color: var(--c); }
/* 区块 */
.block {
  max-width: 1200px; margin: 18px auto; padding: 18px 20px;
  background: #fff; border-radius: 14px; border: 1px solid #eef1f6;
}
.block-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.block-head h3 { font-size: 16px; color: #1a2a4a; margin: 0; }
.block-head a { font-size: 12px; color: var(--c); cursor: pointer; }
/* 视频横滚 */
.hscroll { display: flex; gap: 12px; overflow-x: auto; scroll-snap-type: x mandatory; padding-bottom: 6px; }
.vcard {
  flex: 0 0 210px; scroll-snap-align: start; border: 1px solid #eef1f6;
  border-radius: 10px; overflow: hidden; cursor: pointer;
  position: relative; transition: transform .25s, box-shadow .25s;
}
.vcard:hover { transform: translateY(-3px); box-shadow: 0 8px 18px rgba(10,22,40,.08); }
.vcard img { width: 100%; height: 112px; object-fit: cover; background: #f2f5fa; display: block; }
.dur { position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,.55); color: #fff; font-size: 11px; padding: 1px 6px; border-radius: 4px; font-weight: 500; }
.done, .prog { position: absolute; left: 8px; top: 8px; font-style: normal; font-size: 11px; padding: 1px 6px; border-radius: 4px; }
.done { background: #10b981; color: #fff; }
.prog { background: rgba(59,130,246,.9); color: #fff; }
.vtitle { display: block; font-size: 13px; color: #333; padding: 8px 10px 2px; line-height: 1.4; font-weight: 600; }
.vmeta { display: block; font-size: 11px; color: #98a4b8; padding: 0 10px 10px; }
/* 文章列表 */
.alist { list-style: none; margin: 0; padding: 0; }
.alist li {
  padding: 12px 10px; border-bottom: 1px dashed #eef1f6; cursor: pointer;
  font-size: 14px; color: #2c3e50; display: flex; align-items: center; gap: 10px;
}
.alist li:last-child { border-bottom: none; }
.alist li:hover { background: #f7faff; }
.a-icon { font-style: normal; }
.a-body { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.a-title { font-weight: 600; }
.a-title em { font-style: normal; font-size: 11px; color: #10b981; margin-left: 8px; }
.a-sum {
  font-size: 12px; color: #98a4b8; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; margin-top: 2px;
}
.alist small { color: #98a4b8; font-size: 12px; flex-shrink: 0; }
.arrow { color: #c0c8d4; }
/* 卡片翻转 */
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 14px; }
.flip { perspective: 900px; height: 170px; cursor: pointer; }
.flip .inner {
  position: relative; width: 100%; height: 100%;
  transition: transform .6s; transform-style: preserve-3d;
}
.flip.flipped .inner { transform: rotateY(180deg); }
.face {
  position: absolute; inset: 0;
  backface-visibility: hidden; -webkit-backface-visibility: hidden;
  border-radius: 12px; padding: 12px;
  display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;
}
.front {
  background: linear-gradient(150deg, #f2f7ff, #ffffff);
  border: 1px solid rgba(59,130,246,.25);
}
.back { background: #fff; border: 1px solid #eef1f6; transform: rotateY(180deg); overflow-y: auto; justify-content: flex-start; }
.front .tag { font-size: 10px; color: var(--c); border: 1px solid currentColor; border-radius: 4px; padding: 0 6px; }
.front p { font-size: 14px; font-weight: 700; color: #1a2a4a; margin: 8px 0; }
.front i { font-style: normal; font-size: 10px; color: #a8b4c8; }
.back p { font-size: 12px; color: #44506a; line-height: 1.6; text-align: left; margin: 0; white-space: pre-wrap; }
/* 文章排版规范 */
.material-article :deep(h2) { border-left: 4px solid var(--c); padding-left: 12px; font-size: 19px; color: #1a2a4a; margin: 24px 0 12px; }
.material-article :deep(h3), .material-article :deep(h4) { color: #1a2a4a; margin: 18px 0 10px; }
.material-article :deep(p) { line-height: 1.8; margin: 14px 0; text-align: justify; color: #333; }
.material-article :deep(img) { max-width: 100%; border-radius: 8px; display: block; margin: 12px auto; }
.material-article :deep(table) { border-collapse: collapse; width: 100%; margin: 14px 0; }
.material-article :deep(th) { background: var(--c); color: #fff; padding: 8px; }
.material-article :deep(td) { border: 1px solid #edf0f5; padding: 8px; }
.material-article :deep(tr:nth-child(even)) { background: #fafcff; }
.material-article :deep(strong) { background: rgba(59,130,246,.12); padding: 0 2px; }
.material-article :deep(blockquote) { border-left: 3px solid #cbd5e1; margin: 12px 0; padding: 6px 14px; color: #64748b; background: #f8fafc; }
/* 弹窗脚注 */
.dlg-foot { display: flex; justify-content: space-between; align-items: center; padding-top: 10px; font-size: 13px; color: #5a6b85; }
.dlg-summary { color: #66738a; font-size: 13px; margin-top: 12px; }
/* 空状态 */
.empty-page { text-align: center; padding: 90px 20px; color: #8a97ad; font-size: 15px; }
.empty-icon { font-size: 52px; margin-bottom: 12px; }
.empty-btns button {
  margin: 16px 8px 0; padding: 9px 26px; border: 1px solid var(--c);
  background: var(--c); color: #fff; border-radius: 8px; cursor: pointer; font-size: 14px;
}
.empty-btns button.ghost { background: none; color: var(--c); }
@media (max-width: 768px) {
  .card-grid { grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .material-article { font-size: 15px; }
  .flip { height: 140px; }
  .hero { margin: 14px 12px; padding: 20px; }
  .block { margin: 14px 12px; }
}
</style>
