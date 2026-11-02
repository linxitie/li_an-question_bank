<template>
  <div class="af">
    <header class="page-head">
      <div>
        <h2>论坛管理</h2>
        <p>全站内容管理 · 教师隐藏复核 · 回收站</p>
      </div>
      <div class="head-actions">
        <button class="btn" @click="exportReport">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4">
            <path d="M8 2.4v8" /><path d="M5 7.6l3 3 3-3" /><path d="M2.6 12.4h10.8" />
          </svg>
          导出报表
        </button>
      </div>
    </header>

    <div class="tabs">
      <button
        v-for="t in tabs"
        :key="t.key"
        :class="['tab', { on: tab === t.key }]"
        @click="switchTab(t.key)"
      >
        {{ t.label }}<b v-if="t.count">{{ t.count }}</b>
      </button>
      <div class="spacer"></div>
      <div v-if="tab === 'dash'" class="seg-time">
        <button
          v-for="r in ranges"
          :key="r.days"
          :class="{ on: dashRange === r.days }"
          @click="setRange(r.days)"
        >{{ r.label }}</button>
      </div>
      <button v-else class="btn btn-accent" @click="openComposer">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7">
          <path d="M8 3.2v9.6M3.2 8h9.6" />
        </svg>
        发布新帖
      </button>
    </div>

    <!-- ============ 数据看板（P3b） ============ -->
    <template v-if="tab === 'dash'">
      <div class="kpi-row">
        <div v-for="k in kpis" :key="k.label" :class="['kpi', k.tone]">
          <div class="k-label">{{ k.label }}</div>
          <div class="k-val">{{ k.value }}<small>{{ k.unit }}</small></div>
          <div class="k-foot">
            <span
              v-if="k.delta !== null && k.delta !== undefined"
              :class="['delta', k.delta >= 0 ? 'up' : 'down']"
            >{{ k.delta >= 0 ? '↑' : '↓' }} {{ Math.abs(k.delta) }}%</span>
            <span>{{ k.foot }}</span>
          </div>
        </div>
      </div>

      <div class="dash-grid">
        <div class="span-8">
          <div class="card">
            <div class="card-hd"><h3>发帖 / 评论趋势</h3><span class="sub">近 {{ dashRange }} 天</span></div>
            <div class="card-bd"><XChart :key="`trend-${dashVersion}`" width="100%" height="240px" :option="trendOption" /></div>
          </div>
        </div>
        <div class="span-4">
          <div class="card">
            <div class="card-hd"><h3>班级发帖分布</h3><span class="sub">按班级</span></div>
            <div class="card-bd"><XChart :key="`class-${dashVersion}`" width="100%" height="240px" :option="classOption" /></div>
          </div>
        </div>
        <div class="span-8">
          <div class="card">
            <div class="card-hd">
              <h3>帖子关键词</h3>
              <span class="sub">近 {{ dashRange }} 天 · 词频 TOP {{ dash.keywords.length }}</span>
            </div>
            <div class="card-bd">
              <p v-if="!dash.keywords.length" class="empty">窗口内暂无可提取的关键词</p>
              <div v-else ref="cloudRef" class="wordcloud">
                <span
                  v-for="(w, i) in cloudLayout"
                  :key="w.word"
                  :class="['w', `w${i % 6}`]"
                  :style="{ left: `${w.x}px`, top: `${w.y}px`, fontSize: `${w.size}px` }"
                  :title="`${w.word} · ${w.count} 次`"
                >{{ w.word }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="span-4">
          <div class="card">
            <div class="card-hd"><h3>科目热度</h3><span class="sub">讨论量指数</span></div>
            <div class="card-bd">
              <div class="hbars">
                <div v-for="(s, i) in dash.subjects" :key="s.name" class="hbar">
                  <span class="lb">{{ s.name }}</span>
                  <span class="track">
                    <span class="fill" :style="{ width: barWidth(s.value) + '%', background: subjectColor(i) }"></span>
                  </span>
                  <span class="vl">{{ s.value }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="span-7">
          <div class="card">
            <div class="card-hd"><h3>违规处理量</h3><span class="sub">近 8 周</span></div>
            <div class="card-bd"><XChart :key="`vio-${dashVersion}`" width="100%" height="200px" :option="violationOption" /></div>
          </div>
        </div>
        <div class="span-5">
          <div class="card">
            <div class="card-hd"><h3>风险提示</h3><span class="sub">需人工确认</span></div>
            <div class="card-bd risk">
              <div v-for="(r, i) in dash.risks" :key="i" class="item">
                <span :class="['ic', r.level === 'high' ? 'r' : r.level === 'mid' ? 'a' : 'b']">!</span>
                <div class="tx"><p>{{ r.text }}</p></div>
                <button class="go" @click="jumpFromRisk(r.tab)">查看</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ============ 内容管理 ============ -->
    <template v-else-if="tab === 'list'">
      <div class="filterbar">
        <label class="field search">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="7" cy="7" r="4.4" /><path d="M10.4 10.4L14 14" />
          </svg>
          <input v-model="q" placeholder="搜索标题 / 内容 / 作者" @keyup.enter="searchPosts" />
        </label>
        <select v-model="cls" class="plain">
          <option value="">全部班级</option>
          <option v-for="c in classes" :key="c" :value="c">{{ c }}</option>
        </select>
        <select v-model="st" class="plain">
          <option value="">全部状态</option>
          <option value="NORMAL">正常</option>
          <option value="BLOCKED">已隐藏</option>
          <option value="DELETED">已删除</option>
        </select>
        <label class="field date">
          <input v-model="dateFrom" type="date" />
          <span class="dash">–</span>
          <input v-model="dateTo" type="date" />
        </label>
        <button class="btn btn-primary btn-sm" @click="searchPosts">查询</button>
        <button class="btn btn-sm btn-ghost" @click="resetFilters">重置</button>
        <div class="fb-right">
          <span v-if="selectedIds.length" class="muted">已选 {{ selectedIds.length }} 项</span>
          <button v-if="selectedIds.length" class="btn btn-sm" @click="askBatch('hide')">批量隐藏</button>
          <button v-if="selectedIds.length" class="btn btn-sm btn-danger" @click="askBatch('delete')">批量删除</button>
        </div>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="cb-col"><input type="checkbox" class="cb" :checked="allSelected" @change="toggleAll" /></th>
              <th>帖子内容</th>
              <th style="width: 118px">作者</th>
              <th style="width: 96px">班级</th>
              <th style="width: 86px">状态</th>
              <th style="width: 104px">发布时间</th>
              <th style="width: 124px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in posts" :key="p.id">
              <td class="cb-col"><input v-model="selectedIds" type="checkbox" class="cb" :value="p.id" /></td>
              <td>
                <div class="cell-post">
                  <div class="t">
                    <a class="ttl" @click="openDrawer(p)">{{ p.title || '（无标题）' }}</a>
                    <span v-if="p.isTop" class="pill pin"><i></i>置顶</span>
                    <span v-if="p.isEssence" class="pill essence"><i></i>精华</span>
                  </div>
                  <div class="e content-clip">{{ snippet(contentWithoutStickers(p.content), 90) }}</div>
                  <ImageGrid
                    v-if="postImageUrls(p).length"
                    class="row-media"
                    :images="postImageUrls(p)"
                    mode="post"
                  />
                  <AttachmentList
                    v-if="postDocAttachments(p).length"
                    class="row-media"
                    :attachments="postDocAttachments(p)"
                    mode="post"
                  />
                </div>
              </td>
              <td>
                <div class="who">
                  <div class="ava">{{ (p.author || '?').slice(0, 1) }}</div>
                  <span class="n">{{ p.author || '匿名' }}</span>
                </div>
              </td>
              <td class="nowrap"><span class="muted">{{ p.authorClass || '—' }}</span></td>
              <td class="nowrap"><span :class="['pill', statusClass(p.status)]"><i></i>{{ statusText(p.status) }}</span></td>
              <td class="nowrap"><span class="muted mono">{{ fmtTime(p.createTime) }}</span></td>
              <td>
                <div class="acts">
                  <button v-if="p.status === 'NORMAL'" class="lnk warn" @click="askAction('hide', p)">隐藏</button>
                  <button v-else-if="p.status === 'BLOCKED'" class="lnk strong" @click="askAction('unhide', p)">取消隐藏</button>
                  <button v-else class="lnk strong" @click="askAction('restore', p)">恢复</button>
                  <button class="lnk danger" @click="askAction('delete', p)">删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="!posts.length && !loading">
              <td colspan="7"><div class="empty">没有符合条件的帖子</div></td>
            </tr>
            <tr v-if="loading">
              <td colspan="7"><div class="empty">加载中…</div></td>
            </tr>
          </tbody>
        </table>
        <div class="pager">
          <span>共 {{ total }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
          <div class="pages">
            <button :disabled="page <= 1" @click="gotoPage(page - 1)">上一页</button>
            <button
              v-for="p in pageButtons"
              :key="p"
              :class="{ on: p === page }"
              @click="gotoPage(p)"
            >{{ p }}</button>
            <button :disabled="page >= totalPages" @click="gotoPage(page + 1)">下一页</button>
          </div>
        </div>
      </div>
    </template>

    <!-- ============ 待复核 ============ -->
    <template v-else-if="tab === 'review'">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>类型</th>
              <th>内容</th>
              <th style="width: 180px">隐藏原因</th>
              <th style="width: 104px">时间</th>
              <th style="width: 124px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in records" :key="r.id">
              <td class="nowrap"><span class="pill hidden"><i></i>{{ r.target_type === 'POST' ? '帖子' : '评论' }}</span></td>
              <td>
                <div class="cell-post">
                  <div class="t"><a class="ttl" @click="openRecordTarget(r)">{{ recordTitle(r) }}</a></div>
                  <div class="e">{{ recordSnippet(r) }}</div>
                </div>
              </td>
              <td class="nowrap"><span class="muted">{{ r.reason || '—' }}</span></td>
              <td class="nowrap"><span class="muted mono">{{ fmtTime(r.created_at) }}</span></td>
              <td>
                <div class="acts">
                  <button class="lnk strong" @click="reviewRecord(r, 'approve')">通过</button>
                  <button class="lnk danger" @click="reviewRecord(r, 'reject')">驳回</button>
                </div>
              </td>
            </tr>
            <tr v-if="!records.length">
              <td colspan="5"><div class="empty">暂无待复核记录</div></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ============ 回收站 ============ -->
    <template v-else>
      <div class="noticebar">
        <span class="dot"></span>
        <span v-if="audit">
          已删帖子 {{ audit.deleted_posts }} · 隐藏帖子 {{ audit.hidden_posts }} · 已删评论
          {{ audit.deleted_comments }} · 隐藏评论 {{ audit.hidden_comments }} · 待复核
          {{ audit.pending_moderation }}
        </span>
        <span v-if="audit && audit.stale_pending > 0" class="stale">超 7 天未复核 {{ audit.stale_pending }}</span>
        <span v-if="!isSuperAdmin" class="muted">仅超级管理员可彻底删除</span>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>帖子</th>
              <th style="width: 118px">作者</th>
              <th style="width: 170px">删除原因</th>
              <th style="width: 86px">状态</th>
              <th style="width: 150px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in trashPosts" :key="`p-${p.id}`">
              <td>
                <div class="cell-post">
                  <div class="t"><a class="ttl" @click="openDrawer(p)">{{ p.title || '（无标题）' }}</a></div>
                  <div class="e">{{ snippet(p.content) }}</div>
                </div>
              </td>
              <td class="nowrap"><span class="muted">{{ p.author || '匿名' }}</span></td>
              <td class="nowrap"><span class="muted">{{ p.deletedReason || '无原因' }}</span></td>
              <td class="nowrap"><span :class="['pill', statusClass(p.status)]"><i></i>{{ statusText(p.status) }}</span></td>
              <td>
                <div class="acts">
                  <button class="lnk strong" @click="askAction('restore', p)">恢复</button>
                  <button v-if="isSuperAdmin" class="lnk danger" @click="askAction('purge', p)">彻底删除</button>
                </div>
              </td>
            </tr>
            <tr v-for="c in trashComments" :key="`c-${c.id}`">
              <td>
                <div class="cell-post">
                  <div class="t"><span class="ttl">评论：{{ snippet(c.content, 40) }}</span></div>
                  <div class="e">评论编号 #{{ c.id }}</div>
                </div>
              </td>
              <td class="nowrap"><span class="muted">{{ c.user?.nickname || c.author || '匿名' }}</span></td>
              <td class="nowrap"><span class="muted">{{ c.deletedReason || '无原因' }}</span></td>
              <td class="nowrap"><span class="pill deleted"><i></i>已删除</span></td>
              <td>
                <div class="acts">
                  <button class="lnk strong" @click="restoreCommentRow(c)">恢复</button>
                  <button v-if="isSuperAdmin" class="lnk danger" @click="purgeCommentRow(c)">彻底删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="!trashPosts.length && !trashComments.length">
              <td colspan="5"><div class="empty">回收站为空</div></td>
            </tr>
          </tbody>
        </table>
        <div class="pager">
          <span>帖子 {{ trashTotalPosts }} 条 · 评论 {{ trashTotalComments }} 条</span>
          <div class="pages">
            <button :disabled="trashPage <= 1" @click="gotoTrashPage(trashPage - 1)">上一页</button>
            <button :class="{ on: true }">{{ trashPage }}</button>
            <button
              :disabled="trashPage * PAGE_SIZE >= Math.max(trashTotalPosts, trashTotalComments)"
              @click="gotoTrashPage(trashPage + 1)"
            >下一页</button>
          </div>
        </div>
      </div>
    </template>

    <!-- ============ 详情抽屉 ============ -->
    <div class="scrim" :class="{ on: drawerOpen }" @click="closeDrawer"></div>
    <aside class="drawer" :class="{ on: drawerOpen }">
      <div class="drawer-hd">
        <h3>帖子详情</h3>
        <button class="close-x" @click="closeDrawer">×</button>
      </div>
      <div class="drawer-bd">
        <template v-if="activePost">
          <div class="post-main">
            <div class="post-meta">
              <div class="ava">{{ (activePost.author || '?').slice(0, 1) }}</div>
              <div>
                <div class="nm">{{ activePost.author || '匿名' }}</div>
                <div class="sub">{{ activePost.authorClass || '未分班' }} · 帖子编号 #{{ activePost.id }}</div>
              </div>
              <div class="time mono">{{ fmtTime(activePost.createTime) }}</div>
            </div>
            <div class="post-title">
              {{ activePost.title || '（无标题）' }}
              <span :class="['pill', statusClass(activePost.status)]"><i></i>{{ statusText(activePost.status) }}</span>
              <span v-if="activePost.isTop" class="pill pin"><i></i>置顶</span>
              <span v-if="activePost.isEssence" class="pill essence"><i></i>精华</span>
            </div>
            <div class="post-body text-body"><ForumContent :content="contentWithoutStickers(activePost.content) || '（无正文）'" /></div>
            <ImageGrid
              v-if="postImageUrls(activePost).length"
              class="post-media"
              :images="postImageUrls(activePost)"
              mode="post"
            />
            <AttachmentList
              v-if="postDocAttachments(activePost).length"
              class="post-media"
              :attachments="postDocAttachments(activePost)"
              mode="post"
            />
            <div class="post-stats">
              <span>浏览 <b>{{ activePost.viewCount ?? 0 }}</b></span>
              <span>点赞 <b>{{ activePost.likeCount ?? 0 }}</b></span>
              <span>评论 <b>{{ activePost.commentCount ?? 0 }}</b></span>
              <span>收藏 <b>{{ activePost.favoriteCount ?? 0 }}</b></span>
            </div>
            <div v-if="activePost.status !== 'DELETED'" class="post-admin">
              <span class="lbl">管理操作</span>
              <button class="btn btn-sm" @click="togglePin">
                {{ activePost.isTop ? '取消置顶' : '置顶' }}
              </button>
              <button v-if="activePost.status === 'BLOCKED'" class="btn btn-sm" @click="askAction('unhide', activePost)">
                取消隐藏
              </button>
              <button v-else class="btn btn-sm" @click="askAction('hide', activePost)">隐藏</button>
              <button class="btn btn-sm btn-danger" @click="askAction('delete', activePost)">删除</button>
              <span class="muted tail-hint">所有操作均记录到日志审计</span>
            </div>
          </div>

          <div class="cmt-sec">
            <h4>评论区 <span>共 {{ drawerComments.length }} 条</span></h4>
            <div v-for="c in drawerComments" :key="c.id" class="cmt">
              <div class="ava">{{ (c.user?.nickname || c.author || '?').slice(0, 1) }}</div>
              <div class="bd">
                <div class="hd">
                  <span class="n">{{ c.user?.nickname || c.author || '匿名' }}</span>
                  <span>{{ c.user?.className || '' }}</span>
                </div>
                <div class="tx text-body"><ForumContent :content="c.content" /></div>
                <AttachmentList
                  v-if="c.attachments && c.attachments.length"
                  :attachments="c.attachments"
                  mode="comment"
                />
                <div class="ft">
                  <button class="lnk danger" @click="deleteCommentRow(c)">删除评论</button>
                </div>
              </div>
            </div>
            <p v-if="!drawerComments.length" class="empty">暂无评论</p>

            <!-- 管理员代发评论：此前管理端只能看和删，不能评论（用户反馈） -->
            <div class="cmt-input">
              <input
                v-model="adminComment"
                maxlength="2000"
                placeholder="以管理员身份评论…"
                @keyup.enter="submitAdminComment"
              />
              <button
                class="btn btn-sm btn-primary"
                :disabled="sendingComment || !adminComment.trim()"
                @click="submitAdminComment"
              >{{ sendingComment ? '发送中…' : '发送' }}</button>
            </div>
          </div>
        </template>
      </div>
    </aside>

    <!-- ============ 确认弹窗 ============ -->
    <div v-if="modal.open" class="modal-mask on" @click.self="closeModal">
      <div class="modal">
        <div class="modal-hd">
          <h3>{{ modal.title }}</h3>
          <button class="close-x" @click="closeModal">×</button>
        </div>
        <div class="modal-bd">
          <div :class="modal.danger ? 'warn-box' : 'info-box'">
            <div class="wi">!</div>
            <p>{{ modal.hint }}</p>
          </div>
          <div v-if="modal.targets.length" class="confirm-list">
            <div v-for="t in modal.targets.slice(0, 8)" :key="t.id" class="ci">
              <em>{{ t.title || '（无标题）' }}</em>
              <span>#{{ t.id }}</span>
            </div>
            <div v-if="modal.targets.length > 8" class="ci">
              <em class="muted">… 另有 {{ modal.targets.length - 8 }} 条</em>
            </div>
          </div>
          <div v-if="modal.needReason" class="f-row">
            <label>原因</label>
            <input v-model="modal.reason" class="f-input" maxlength="200" placeholder="选填，记录到日志审计" />
          </div>
        </div>
        <div class="modal-ft">
          <button class="btn" @click="closeModal">取消</button>
          <button :class="['btn', modal.danger ? 'btn-danger-solid' : 'btn-primary']" :disabled="modal.submitting" @click="submitModal">
            {{ modal.submitting ? '处理中…' : '确认' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ============ 发布新帖 ============ -->
    <PostComposer
      v-model:visible="composerOpen"
      :initial="composerInitial"
      :can-pin="true"
      :classes="classes"
      :submitting="composerSubmitting"
      :saving-draft="composerSavingDraft"
      @submit="publishPost"
      @save-draft="saveDraft"
    />

    <div class="toast" :class="[toast.kind, { on: toast.on }]">
      <span class="ti">{{ toast.kind === 'err' ? '!' : '✓' }}</span>{{ toast.msg }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { XChart } from '@vtj/charts';

import PostComposer, { type PostDraft } from '@/components/forum/PostComposer.vue';
import AttachmentList from '@/components/forum/AttachmentList.vue';
import ForumContent from '@/components/forum/ForumContent.vue';
import ImageGrid from '@/components/forum/ImageGrid.vue';
import { isImageUrl } from '@/components/forum/imageUtils';
import {
  adminForumApi,
  type ModerationComment,
  type ModerationPost,
  type ModerationRecord
} from '@/modules/community/moderationApi';
import { createForumPostWithVisibility, createForumComment, fetchMyForumDraft, saveMyForumDraft } from '@/modules/community/api';

const PAGE_SIZE = 20;

type TabKey = 'dash' | 'list' | 'review' | 'trash';

const tab = ref<TabKey>('dash');
const loading = ref(false);

/* ---------- 数据看板（P3b） ---------- */
const dashRange = ref(7);
const ranges = [
  { days: 7, label: '近 7 天' },
  { days: 30, label: '近 30 天' },
  { days: 180, label: '本学期' }
];
const dash = ref<any>({
  kpi: {},
  trend: { labels: [], posts: [], comments: [] },
  classes: [],
  keywords: [],
  subjects: [],
  violations: { labels: [], deleted: [], hidden: [] },
  risks: []
});
/** 数据到位后让图表重建：ECharts 在容器未完成布局时初始化会把半径算成 0 */
const dashVersion = ref(0);

const posts = ref<ModerationPost[]>([]);
const total = ref(0);
const page = ref(1);
const classes = ref<string[]>([]);
const selectedIds = ref<number[]>([]);

const q = ref('');
const cls = ref('');
const st = ref('');
const dateFrom = ref('');
const dateTo = ref('');

const records = ref<ModerationRecord[]>([]);

const trashPosts = ref<ModerationPost[]>([]);
const trashComments = ref<ModerationComment[]>([]);
const trashTotalPosts = ref(0);
const trashTotalComments = ref(0);
const trashPage = ref(1);
const audit = ref<any>(null);

const drawerOpen = ref(false);
const activePost = ref<ModerationPost | null>(null);
const drawerComments = ref<ModerationComment[]>([]);
const adminComment = ref('');
const sendingComment = ref(false);

/** 表情包在正文里以 [[sticker:url]] 形式存储，抽出来按图片渲染 */
const STICKER_RE = /\[\[sticker:([^\]]+)\]\]/g;
function stickerUrls(content?: string): string[] {
  if (!content) return [];
  return Array.from(content.matchAll(STICKER_RE)).map((m) => m[1]);
}
function contentWithoutStickers(content?: string): string {
  return (content || '').replace(STICKER_RE, ' ').trim();
}

/**
 * 帖子要展示的图片：正文里的表情包 + 附件里的图片，**按 URL 去重**。
 * 不去重会出现「同一张图既当表情包渲染、又当附件渲染两次」（实测踩过）。
 */
function postImageUrls(post: ModerationPost): string[] {
  const fromContent = stickerUrls(post.content);
  const fromAttachments = (post.attachments || [])
    .filter((att) => isImageUrl(att.url))
    .map((att) => att.url);
  return Array.from(new Set([...fromContent, ...fromAttachments]));
}

/** 附件里的非图片文件（图片已由 ImageGrid 渲染，这里只留文档，避免重复） */
function postDocAttachments(post: ModerationPost) {
  return (post.attachments || []).filter((att) => !isImageUrl(att.url));
}

const isSuperAdmin = ref(
  (((window as any).__VTJ_AUTH__?.parseUserInfo?.() || {}).roleLevel || 0) >= 3
);

const composerOpen = ref(false);
const composerInitial = ref<Partial<PostDraft> | null>(null);
const composerSubmitting = ref(false);
const composerSavingDraft = ref(false);

const toast = reactive({ on: false, msg: '', kind: 'ok' as 'ok' | 'err' });

const modal = reactive({
  open: false,
  title: '',
  hint: '',
  danger: false,
  needReason: false,
  reason: '',
  submitting: false,
  action: '' as '' | 'hide' | 'unhide' | 'delete' | 'restore' | 'purge' | 'batch-hide' | 'batch-delete',
  targets: [] as ModerationPost[]
});

const tabs = computed(() => [
  { key: 'dash' as TabKey, label: '数据看板', count: 0 },
  { key: 'list' as TabKey, label: '内容管理', count: 0 },
  { key: 'review' as TabKey, label: '待复核', count: records.value.length },
  { key: 'trash' as TabKey, label: '回收站', count: trashTotalPosts.value + trashTotalComments.value }
]);

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)));
const allSelected = computed(() => posts.value.length > 0 && selectedIds.value.length === posts.value.length);
const pageButtons = computed(() => {
  const last = totalPages.value;
  const start = Math.max(1, Math.min(page.value - 2, last - 4));
  const end = Math.min(last, start + 4);
  const out: number[] = [];
  for (let i = start; i <= end; i += 1) out.push(i);
  return out;
});

/* ---------- 看板派生数据 ---------- */
const kpis = computed(() => {
  const k = dash.value.kpi || {};
  return [
    { label: '发帖量', value: k.posts ?? 0, unit: '篇', delta: k.postsDelta, foot: '较上一周期', tone: '' },
    { label: '评论量', value: k.comments ?? 0, unit: '条', delta: k.commentsDelta, foot: '较上一周期', tone: '' },
    { label: '待复核', value: k.pending ?? 0, unit: '条', delta: null, foot: '教师隐藏待处理', tone: 'k-amber' },
    { label: '已隐藏', value: k.hidden ?? 0, unit: '篇', delta: null, foot: '窗口内', tone: 'k-accent' },
    { label: '已删除', value: k.deleted ?? 0, unit: '篇', delta: null, foot: '窗口内可恢复', tone: 'k-accent' },
    { label: '覆盖班级', value: k.classes ?? 0, unit: '个', delta: null, foot: '窗口内发帖', tone: 'k-green' }
  ];
});

const AXIS_COLOR = '#8c99ac';
const GRID_LINE = '#f1f4f9';

const trendOption = computed<any>(() => ({
  animation: false,
  tooltip: { trigger: 'axis' },
  legend: { right: 0, top: 0, itemWidth: 10, itemHeight: 10, textStyle: { color: '#5b6b84', fontSize: 11 } },
  grid: { left: 34, right: 14, top: 30, bottom: 24 },
  xAxis: {
    type: 'category',
    data: dash.value.trend.labels,
    axisLine: { lineStyle: { color: GRID_LINE } },
    axisLabel: { color: AXIS_COLOR, fontSize: 10 },
    axisTick: { show: false }
  },
  yAxis: {
    type: 'value',
    splitLine: { lineStyle: { color: GRID_LINE } },
    axisLabel: { color: AXIS_COLOR, fontSize: 10 }
  },
  series: [
    {
      name: '发帖',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      data: dash.value.trend.posts,
      itemStyle: { color: '#123B63' },
      lineStyle: { width: 2 },
      areaStyle: { color: 'rgba(18,59,99,0.10)' }
    },
    {
      name: '评论',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      data: dash.value.trend.comments,
      itemStyle: { color: '#7FB0D8' },
      lineStyle: { width: 2, type: 'dashed' }
    }
  ]
}));

const classOption = computed<any>(() => ({
  animation: false,
  tooltip: { trigger: 'item', formatter: '{b}: {c} 篇 ({d}%)' },
  legend: { bottom: 0, itemWidth: 9, itemHeight: 9, textStyle: { color: '#5b6b84', fontSize: 11 } },
  series: [
    {
      type: 'pie',
      center: ['50%', '46%'],
      radius: '62%',
      label: { show: false },
      data: dash.value.classes.map((c: any) => ({ name: c.name, value: c.value })),
      itemStyle: { borderColor: '#fff', borderWidth: 2 }
    }
  ],
  color: ['#123B63', '#2F72B5', '#7FB0D8', '#3E9C96', '#D9902E', '#7566B0', '#B9C8DC']
}));

const violationOption = computed<any>(() => ({
  animation: false,
  tooltip: { trigger: 'axis' },
  legend: { right: 0, top: 0, itemWidth: 10, itemHeight: 10, textStyle: { color: '#5b6b84', fontSize: 11 } },
  grid: { left: 34, right: 14, top: 30, bottom: 24 },
  xAxis: {
    type: 'category',
    data: dash.value.violations.labels,
    axisLine: { lineStyle: { color: GRID_LINE } },
    axisLabel: { color: AXIS_COLOR, fontSize: 10 },
    axisTick: { show: false }
  },
  yAxis: {
    type: 'value',
    splitLine: { lineStyle: { color: GRID_LINE } },
    axisLabel: { color: AXIS_COLOR, fontSize: 10 }
  },
  series: [
    { name: '删除', type: 'bar', barMaxWidth: 14, data: dash.value.violations.deleted, itemStyle: { color: '#C64B34', borderRadius: [3, 3, 0, 0] } },
    { name: '隐藏', type: 'bar', barMaxWidth: 14, data: dash.value.violations.hidden, itemStyle: { color: '#D9902E', borderRadius: [3, 3, 0, 0] } }
  ]
}));

/* ================= 散点词云（中心向外辐射） =================
 * 布局规则（对齐用户要求）：
 *   1. 词频最高的词固定落在画布正中；
 *   2. 其余词按词频**降序**依次摆放，每个词用「由中心向外的螺旋」搜索第一个不重叠的位置，
 *      因此热度越低，离中心的半径越大 —— 形成由内向外散开的辐射状；
 *   3. 绝对定位 + 矩形碰撞检测，互不重叠；放不下就缩小字号重试，仍放不下则丢弃该词（不叠字）。
 * 不用行式 flex —— 行式必然对齐成整齐的行，做不出「杂乱分布」。
 */

interface CloudWord {
  word: string;
  count: number;
  x: number;
  y: number;
  size: number;
}

const cloudRef = ref<HTMLElement | null>(null);
const cloudLayout = ref<CloudWord[]>([]);

let measureCtx: CanvasRenderingContext2D | null = null;
/** 用 canvas 量真实字宽，比「字数 × 字号」准，中文/英文混排也不会算错 */
function textWidth(text: string, fontSize: number): number {
  if (!measureCtx) {
    const canvas = document.createElement('canvas');
    measureCtx = canvas.getContext('2d');
  }
  if (!measureCtx) return text.length * fontSize;
  measureCtx.font = `500 ${fontSize}px -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`;
  return measureCtx.measureText(text).width;
}

/** 黄金角：每个词的起始角度错开，避免所有词沿同一根轴排队 */
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

function layoutCloud(
  words: Array<{ word: string; count: number }>,
  boxW: number,
  boxH: number
): CloudWord[] {
  const result: CloudWord[] = [];
  if (!boxW || !boxH || !words.length) return result;

  const sorted = [...words].sort((a, b) => b.count - a.count);
  const maxCount = Math.max(1, ...sorted.map((w) => w.count));
  const minCount = Math.min(...sorted.map((w) => w.count));
  const span = Math.max(1, maxCount - minCount);

  const cx = boxW / 2;
  const cy = boxH / 2;
  // 画布是宽的：横向适度放大半径（上限 1.6，压太扁会让词全都沿横向排队、上下留白）
  const kx = Math.max(1, Math.min(1.6, boxW / boxH));
  const placed: Array<{ x: number; y: number; w: number; h: number }> = [];

  let startAngle = -Math.PI / 2;

  for (const item of sorted) {
    // 词频 → 字号（开方压缩长尾）
    const t = Math.sqrt(Math.max(0, item.count - minCount) / span);
    let size = Math.round(15 + t * 25);
    let placedOk = false;

    for (let shrink = 0; shrink < 5 && !placedOk; shrink += 1) {
      const tw = textWidth(item.word, size) + 8;
      const th = size * 1.3;
      if (tw > boxW || th > boxH) {
        size = Math.max(12, size - 3);
        continue;
      }

      const angleStep = Math.PI / 14; // 约 12.8°
      const radiusStep = 2.4;
      const maxSteps = 6000;

      for (let step = 0; step < maxSteps && !placedOk; step += 1) {
        const angle = startAngle + step * angleStep;
        const radius = step * radiusStep;
        const x = cx + Math.cos(angle) * radius * kx;
        const y = cy + Math.sin(angle) * radius;

        const box = { x: x - tw / 2, y: y - th / 2, w: tw, h: th };
        if (box.x < 0 || box.y < 0 || box.x + box.w > boxW || box.y + box.h > boxH) continue;

        const overlaps = placed.some(
          (p) =>
            !(
              box.x + box.w + 6 < p.x ||
              p.x + p.w + 6 < box.x ||
              box.y + box.h + 4 < p.y ||
              p.y + p.h + 4 < box.y
            )
        );
        if (overlaps) continue;

        placed.push(box);
        result.push({ word: item.word, count: item.count, x, y, size });
        placedOk = true;
      }

      if (!placedOk) size = Math.max(12, size - 2);
    }

    if (placedOk) startAngle += GOLDEN_ANGLE;
  }

  return result;
}

function relayoutCloud() {
  const el = cloudRef.value;
  if (!el) return;
  cloudLayout.value = layoutCloud(dash.value.keywords, el.clientWidth, el.clientHeight);
}

const maxSubjectValue = computed(() => Math.max(1, ...dash.value.subjects.map((s: any) => s.value)));
const barWidth = (value: any) => Math.round((value / maxSubjectValue.value) * 100);
const subjectColor = (index: any) => ['#123B63', '#2F72B5', '#3E9C96', '#D9902E'][index % 4];

const statusText = (status: string) =>
  ({ NORMAL: '正常', BLOCKED: '已隐藏', DELETED: '已删除' } as Record<string, string>)[status] || status;
const statusClass = (status: string) =>
  ({ NORMAL: 'ok', BLOCKED: 'hidden', DELETED: 'deleted' } as Record<string, string>)[status] || 'hidden';

const snippet = (text?: string, max = 60) => {
  const t = (text || '').replace(/\s+/g, ' ').trim();
  return t.length > max ? `${t.slice(0, max)}…` : t || '（无正文）';
};

const fmtTime = (iso?: string | null) => (iso ? iso.replace('T', ' ').slice(0, 16) : '—');

function showToast(msg: string, kind: 'ok' | 'err' = 'ok') {
  toast.msg = msg;
  toast.kind = kind;
  toast.on = true;
  window.setTimeout(() => {
    toast.on = false;
  }, 2200);
}

function recordTitle(r: ModerationRecord): string {
  const target = r.target as any;
  if (!target) return '内容已删除';
  return r.target_type === 'POST' ? target.title || '（无标题）' : snippet(target.content, 40);
}

function recordSnippet(r: ModerationRecord): string {
  const target = r.target as any;
  if (!target) return '原内容已不存在';
  return r.target_type === 'POST' ? snippet(target.content) : '评论（帖子内可见）';
}

async function loadPosts() {
  loading.value = true;
  try {
    const data = await adminForumApi.posts({
      keyword: q.value || undefined,
      class_name: cls.value || undefined,
      status: st.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      limit: PAGE_SIZE,
      offset: (page.value - 1) * PAGE_SIZE
    });
    posts.value = data.items;
    total.value = data.total;
    classes.value = data.classes || classes.value;
    selectedIds.value = [];
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载失败');
  } finally {
    loading.value = false;
  }
}

async function loadReview() {
  try {
    const data = await adminForumApi.moderation('PENDING');
    records.value = data.items;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载待复核失败');
  }
}

async function loadTrash() {
  try {
    const [data, stats] = await Promise.all([
      adminForumApi.recycle({ limit: PAGE_SIZE, offset: (trashPage.value - 1) * PAGE_SIZE }),
      adminForumApi.recycleAudit()
    ]);
    trashPosts.value = data.posts;
    trashComments.value = data.comments;
    trashTotalPosts.value = data.totalPosts;
    trashTotalComments.value = data.totalComments;
    audit.value = stats;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载回收站失败');
  }
}

async function loadDashboard() {
  try {
    dash.value = await adminForumApi.dashboard(dashRange.value);
    dashVersion.value += 1;
    // 词云是绝对定位的，必须等容器渲染出宽高后再算坐标
    await nextTick();
    relayoutCloud();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载看板失败');
  }
}

function setRange(days: number) {
  if (dashRange.value === days) return;
  dashRange.value = days;
  loadDashboard();
}

/** 风险提示的「查看」跳到对应页签 */
function jumpFromRisk(target: string) {
  if (target === 'review') switchTab('review');
  else if (target === 'trash') switchTab('trash');
  else switchTab('list');
}

function switchTab(key: TabKey) {
  tab.value = key;
  selectedIds.value = [];
  if (key === 'dash') loadDashboard();
  else if (key === 'list') loadPosts();
  else if (key === 'review') loadReview();
  else loadTrash();
}

function searchPosts() {
  page.value = 1;
  loadPosts();
}

function resetFilters() {
  q.value = '';
  cls.value = '';
  st.value = '';
  dateFrom.value = '';
  dateTo.value = '';
  page.value = 1;
  loadPosts();
}

function gotoPage(next: number) {
  if (next < 1 || next > totalPages.value) return;
  page.value = next;
  loadPosts();
}

function gotoTrashPage(next: number) {
  if (next < 1) return;
  trashPage.value = next;
  loadTrash();
}

function toggleAll(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  selectedIds.value = checked ? posts.value.map((p) => p.id) : [];
}

function openComposer() {
  composerInitial.value = null;
  composerOpen.value = true;
  fetchMyForumDraft()
    .then((draft) => {
      if (!draft) return;
      composerInitial.value = {
        title: draft.title,
        content: draft.content,
        attachments: draft.attachments,
        visibility: draft.visibility,
        visibleClasses: draft.visibleClasses,
        isTop: draft.isTop
      };
      showToast('已载入上次保存的草稿');
    })
    .catch(() => {
      /* 草稿读取失败不阻塞发帖 */
    });
}

async function publishPost(payload: PostDraft) {
  composerSubmitting.value = true;
  try {
    const created = await createForumPostWithVisibility({
      title: payload.title,
      content: payload.content,
      shareType: 'DISCUSSION',
      attachments: payload.attachments,
      visibility: payload.visibility,
      visibleClasses: payload.visibleClasses
    });
    // create_post 不接受 is_top，置顶走既有置顶接口，避免再改发帖契约
    if (payload.isTop && created?.id) {
      await adminForumApi.pinPost(created.id, true);
    }
    composerOpen.value = false;
    showToast('发布成功');
    if (tab.value === 'list') await loadPosts();
    else switchTab('list');
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '发布失败');
  } finally {
    composerSubmitting.value = false;
  }
}

async function saveDraft(payload: PostDraft) {
  composerSavingDraft.value = true;
  try {
    await saveMyForumDraft({
      title: payload.title,
      content: payload.content,
      attachments: payload.attachments,
      visibility: payload.visibility,
      visible_classes: payload.visibleClasses,
      is_top: payload.isTop
    });
    showToast('已保存到草稿箱');
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存草稿失败');
  } finally {
    composerSavingDraft.value = false;
  }
}

function askAction(action: 'hide' | 'unhide' | 'delete' | 'restore' | 'purge', post: ModerationPost) {
  const map: Record<string, { title: string; hint: string; danger: boolean; needReason: boolean }> = {
    hide: { title: '隐藏帖子', hint: '隐藏后学生端不可见，可在回收站恢复。', danger: false, needReason: true },
    unhide: { title: '取消隐藏', hint: '帖子将恢复为正常状态并重新出现在列表。', danger: false, needReason: false },
    delete: { title: '删除帖子', hint: '删除后进入回收站，可恢复。', danger: true, needReason: true },
    restore: { title: '恢复帖子', hint: '帖子将恢复到正常状态。', danger: false, needReason: false },
    purge: { title: '彻底删除', hint: '此操作不可恢复，帖子的评论也会一并删除。', danger: true, needReason: false }
  };
  const cfg = map[action];
  Object.assign(modal, {
    open: true,
    action,
    targets: [post],
    reason: '',
    submitting: false,
    ...cfg
  });
}

function askBatch(action: 'hide' | 'delete') {
  const targets = posts.value.filter((p) => selectedIds.value.includes(p.id));
  if (!targets.length) return;
  Object.assign(modal, {
    open: true,
    action: `batch-${action}` as 'batch-hide' | 'batch-delete',
    title: action === 'hide' ? `批量隐藏 ${targets.length} 篇帖子` : `批量删除 ${targets.length} 篇帖子`,
    hint: action === 'hide' ? '隐藏后学生端不可见，可在回收站恢复。' : '删除后进入回收站，可恢复。',
    danger: action === 'delete',
    needReason: true,
    reason: '',
    targets,
    submitting: false
  });
}

function closeModal() {
  modal.open = false;
  modal.submitting = false;
}

async function submitModal() {
  modal.submitting = true;
  const ids = modal.targets.map((t) => t.id);
  try {
    if (modal.action === 'batch-hide' || modal.action === 'batch-delete') {
      const act = modal.action === 'batch-hide' ? 'hide' : 'delete';
      const res = await adminForumApi.batchPosts(act, ids, modal.reason || undefined);
      showToast(`已处理 ${res.affected} 条${res.skipped.length ? `，跳过 ${res.skipped.length} 条` : ''}`);
    } else if (modal.action === 'hide') {
      await adminForumApi.hidePost(ids[0], modal.reason || undefined);
      showToast('已隐藏');
    } else if (modal.action === 'unhide') {
      await adminForumApi.unhidePost(ids[0]);
      showToast('已取消隐藏');
    } else if (modal.action === 'delete') {
      await adminForumApi.deletePost(ids[0], modal.reason || undefined);
      showToast('已删除并进入回收站');
    } else if (modal.action === 'restore') {
      await adminForumApi.restorePost(ids[0]);
      showToast('已恢复');
    } else if (modal.action === 'purge') {
      await adminForumApi.purgePost(ids[0]);
      showToast('已彻底删除');
    }
    closeModal();
    if (drawerOpen.value) await refreshDrawer();
    if (tab.value === 'list') await loadPosts();
    else if (tab.value === 'trash') await loadTrash();
    else if (tab.value === 'review') await loadReview();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败');
  } finally {
    modal.submitting = false;
  }
}

async function openDrawer(post: ModerationPost) {
  activePost.value = post;
  drawerOpen.value = true;
  drawerComments.value = [];
  try {
    const data = await adminForumApi.comments(post.id);
    drawerComments.value = data.items;
  } catch {
    drawerComments.value = [];
  }
}

function closeDrawer() {
  drawerOpen.value = false;
  activePost.value = null;
}

async function refreshDrawer() {
  if (!activePost.value) return;
  const inList = posts.value.find((p) => p.id === activePost.value!.id);
  if (inList) activePost.value = inList;
}

async function togglePin() {
  if (!activePost.value) return;
  const next = !activePost.value.isTop;
  try {
    await adminForumApi.pinPost(activePost.value.id, next);
    showToast(next ? '已置顶' : '已取消置顶');
    activePost.value = { ...activePost.value, isTop: next };
    await loadPosts();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '置顶失败');
  }
}

async function reviewRecord(r: ModerationRecord, action: 'approve' | 'reject') {
  try {
    if (action === 'approve') await adminForumApi.approve(r.id);
    else await adminForumApi.reject(r.id);
    showToast(action === 'approve' ? '已确认删除' : '已驳回并恢复');
    await loadReview();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败');
  }
}

function openRecordTarget(r: ModerationRecord) {
  const target = r.target as any;
  if (r.target_type === 'POST' && target) openDrawer(target as ModerationPost);
}

/** 管理员在抽屉里代发评论（此前管理端只能看/删，不能评论） */
async function submitAdminComment() {
  const text = adminComment.value.trim();
  if (!text || !activePost.value) return;
  sendingComment.value = true;
  try {
    await createForumComment(activePost.value.id, { content: text });
    adminComment.value = '';
    const data = await adminForumApi.comments(activePost.value.id);
    drawerComments.value = data.items;
    showToast('评论已发布');
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '评论发布失败');
  } finally {
    sendingComment.value = false;
  }
}

async function deleteCommentRow(c: ModerationComment) {
  try {
    await adminForumApi.deleteComment(c.id, '管理端删除评论');
    showToast('评论已删除');
    if (activePost.value) {
      const data = await adminForumApi.comments(activePost.value.id);
      drawerComments.value = data.items;
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除评论失败');
  }
}

async function restoreCommentRow(c: ModerationComment) {
  try {
    await adminForumApi.restoreComment(c.id);
    showToast('评论已恢复');
    await loadTrash();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '恢复失败');
  }
}

async function purgeCommentRow(c: ModerationComment) {
  try {
    await adminForumApi.purgeComment(c.id);
    showToast('评论已彻底删除');
    await loadTrash();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '彻底删除失败');
  }
}

/** 导出当前列表为 CSV（纯前端，不新增后端接口） */
function exportReport() {
  const rows = tab.value === 'trash' ? trashPosts.value : posts.value;
  if (!rows.length) {
    showToast('当前列表为空，无可导出内容', 'err');
    return;
  }
  const header = ['帖子ID', '标题', '作者', '班级', '状态', '点赞', '评论', '创建时间'];
  const csv = [
    header.join(','),
    ...rows.map((p) =>
      [
        p.id,
        `"${(p.title || '').replace(/"/g, '""')}"`,
        p.author || '',
        p.authorClass || '',
        statusText(p.status),
        p.likeCount ?? 0,
        p.commentCount ?? 0,
        fmtTime(p.createTime)
      ].join(',')
    )
  ].join('\r\n');
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `论坛管理_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('已导出当前列表');
}

let resizeTimer: number | undefined;
function onWindowResize() {
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    if (tab.value === 'dash') relayoutCloud();
  }, 180);
}

onMounted(async () => {
  window.addEventListener('resize', onWindowResize);
  await loadDashboard();
  await loadPosts();
  loadReview();
  loadTrash();
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize);
  window.clearTimeout(resizeTimer);
});
</script>

<style scoped>
.af {
  color: #17233a;
}
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}
.page-head h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.3px;
}
.page-head p {
  margin: 3px 0 0;
  font-size: 11.5px;
  color: #8c99ac;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.tab {
  height: 30px;
  padding: 0 14px;
  border-radius: 15px;
  border: 1px solid #e6ebf3;
  background: #fff;
  color: #5b6b84;
  font-size: 12.5px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: all 0.15s;
}
.tab:hover {
  border-color: #c9d8e8;
  color: #123b63;
}
.tab.on {
  background: #123b63;
  border-color: #123b63;
  color: #fff;
  box-shadow: 0 2px 6px rgba(18, 59, 99, 0.18);
}
.tab b {
  font-weight: 500;
  font-size: 10.5px;
  min-width: 15px;
  height: 15px;
  border-radius: 8px;
  padding: 0 4px;
  background: #eef2f8;
  color: #7c8aa0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.tab.on b {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
}
.tabs .spacer {
  flex: 1;
}
.btn {
  height: 30px;
  padding: 0 13px;
  border-radius: 7px;
  border: 1px solid #e6ebf3;
  background: #fff;
  color: #5b6b84;
  font-size: 12.5px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn:hover {
  border-color: #bfd0e4;
  color: #123b63;
}
.btn-primary {
  background: #123b63;
  border-color: #123b63;
  color: #fff;
}
.btn-primary:hover {
  background: #0e2f4f;
  border-color: #0e2f4f;
  color: #fff;
}
.btn-accent {
  background: #e23b2e;
  border-color: #e23b2e;
  color: #fff;
  box-shadow: 0 2px 6px rgba(226, 59, 46, 0.22);
}
.btn-accent:hover {
  background: #cb2f23;
  border-color: #cb2f23;
  color: #fff;
}
.btn-sm {
  height: 30px;
  padding: 0 12px;
  font-size: 12px;
}
.btn-ghost {
  background: transparent;
  border-color: transparent;
}
.btn-ghost:hover {
  background: #eef2f8;
}
.btn-danger {
  color: #c34a34;
  border-color: #efcdc7;
}
.btn-danger:hover {
  background: #fdedeb;
}
.btn-danger-solid {
  background: #d2462f;
  border-color: #d2462f;
  color: #fff;
}
.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.filterbar {
  background: #fff;
  border: 1px solid #e6ebf3;
  border-radius: 12px;
  padding: 11px 13px;
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 13px;
  flex-wrap: wrap;
}
.field {
  height: 30px;
  border: 1px solid #e6ebf3;
  border-radius: 7px;
  background: #fff;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 9px;
  color: #5b6b84;
  font-size: 12.5px;
}
.field:focus-within {
  border-color: #123b63;
  box-shadow: 0 0 0 3px rgba(18, 59, 99, 0.07);
}
.field input {
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 12.5px;
  color: #17233a;
  width: 100%;
}
.field.search {
  width: 220px;
}
.field.date {
  width: 236px;
  gap: 4px;
}
.field.date input {
  width: 104px;
}
.field.date .dash {
  color: #a9b5c6;
}
select.plain {
  height: 30px;
  border: 1px solid #e6ebf3;
  border-radius: 7px;
  background: #fff;
  color: #5b6b84;
  font-size: 12.5px;
  padding: 0 8px;
  outline: 0;
  font-family: inherit;
}
.fb-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
.noticebar {
  background: #fff;
  border: 1px solid #e6ebf3;
  border-radius: 12px;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 13px;
  font-size: 12.5px;
  color: #5b6b84;
  flex-wrap: wrap;
}
.noticebar .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #d9902e;
  flex: 0 0 6px;
}
.noticebar .stale {
  color: #c34a34;
}
.table-wrap {
  background: #fff;
  border: 1px solid #e6ebf3;
  border-radius: 12px;
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
}
thead th {
  text-align: left;
  font-weight: 500;
  font-size: 11.5px;
  color: #7c8aa0;
  padding: 10px;
  background: #f8fafd;
  border-bottom: 1px solid #e6ebf3;
  white-space: nowrap;
}
thead th:first-child {
  padding-left: 14px;
}
thead th:last-child {
  padding-right: 14px;
  text-align: right;
}
tbody td {
  padding: 10px;
  border-bottom: 1px solid #f1f4f9;
  vertical-align: middle;
  font-size: 12.5px;
}
tbody td:first-child {
  padding-left: 14px;
}
tbody td:last-child {
  padding-right: 14px;
  text-align: right;
  white-space: nowrap;
}
tbody tr:hover {
  background: #f7fafe;
}
tbody tr:last-child td {
  border-bottom: 0;
}
.cb-col {
  width: 34px;
}
input[type='checkbox'].cb {
  width: 13px;
  height: 13px;
  accent-color: #123b63;
  cursor: pointer;
}
.nowrap {
  white-space: nowrap;
}
.cell-post {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.cell-post .t {
  font-size: 13px;
  color: #17233a;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}
.cell-post .t .ttl {
  color: inherit;
  text-decoration: none;
  border-bottom: 1px solid transparent;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
}
.cell-post .t .ttl:hover {
  color: #123b63;
  border-bottom-color: #b9cde2;
}
.cell-post .e {
  font-size: 11.5px;
  color: #8c99ac;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
/* 正文含表情包/换行时允许两行截断，保证卡片高度稳定 */
.content-clip {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  white-space: normal;
  max-height: 2.9em;
}
.row-media {
  margin-top: 5px;
  /* 列表里的缩略图必须给容器加宽度上限，否则 3 列网格会把图撑到 180px+ */
  max-width: 200px;
}
.row-media :deep(.image-grid) {
  gap: 4px;
  margin-top: 4px;
}
.post-media {
  margin-top: 10px;
  max-width: 330px;
}
.cmt-input {
  position: sticky;
  bottom: 0;
  background: #fff;
  border: 1px solid #e6ebf3;
  border-radius: 10px;
  padding: 9px 11px;
  margin-top: 12px;
  display: flex;
  gap: 8px;
  align-items: center;
  box-shadow: 0 -4px 14px rgba(23, 35, 58, 0.05);
}
.cmt-input input {
  flex: 1;
  border: 0;
  outline: 0;
  font-size: 12.5px;
  background: transparent;
  color: #17233a;
}
.attach-row {
  margin-top: 3px;
}
.attach {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #5b6b84;
  background: #f3f6fa;
  border: 1px solid #e9eef6;
  border-radius: 4px;
  padding: 1px 6px;
  max-width: 100%;
  text-decoration: none;
}
.attach b {
  color: #2f72b5;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.who {
  display: flex;
  align-items: center;
  gap: 7px;
}
.who .ava {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  flex: 0 0 22px;
  background: linear-gradient(135deg, #7fb3de, #4e7fb0);
  color: #fff;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.who .n {
  font-size: 12.5px;
  color: #17233a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.muted {
  color: #8c99ac;
  font-size: 12px;
}
.mono {
  font-variant-numeric: tabular-nums;
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 20px;
  padding: 0 7px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
}
.pill i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
  display: inline-block;
}
.pill.ok {
  background: #eaf6f1;
  color: #2e8b6b;
}
.pill.hidden {
  background: #eff2f7;
  color: #6c7a90;
}
.pill.deleted {
  background: #fdedeb;
  color: #c34a34;
}
.pill.pin {
  background: #eaf1f8;
  color: #123b63;
}
.pill.essence {
  background: #fdf3e3;
  color: #b97b1e;
}
.acts {
  display: flex;
  align-items: center;
  gap: 2px;
  justify-content: flex-end;
}
.lnk {
  border: 0;
  background: transparent;
  color: #3e6e9e;
  font-size: 11.5px;
  padding: 3px 5px;
  border-radius: 5px;
  cursor: pointer;
  white-space: nowrap;
}
.lnk:hover {
  background: #eaf1f8;
  color: #123b63;
}
.lnk.danger {
  color: #c34a34;
}
.lnk.danger:hover {
  background: #fdedeb;
  color: #b03a26;
}
.lnk.warn {
  color: #b97b1e;
}
.lnk.warn:hover {
  background: #fdf3e3;
}
.lnk.strong {
  color: #123b63;
  font-weight: 500;
}
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-top: 1px solid #f1f4f9;
  font-size: 12px;
  color: #8c99ac;
  background: #fff;
}
.pages {
  display: flex;
  align-items: center;
  gap: 4px;
}
.pages button {
  min-width: 26px;
  height: 26px;
  border-radius: 6px;
  border: 1px solid transparent;
  background: transparent;
  color: #5b6b84;
  font-size: 12px;
  cursor: pointer;
  padding: 0 7px;
}
.pages button:hover {
  background: #eef2f8;
}
.pages button.on {
  background: #123b63;
  color: #fff;
  border-color: #123b63;
}
.pages button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.empty {
  padding: 46px 0;
  text-align: center;
  color: #8c99ac;
  font-size: 12.5px;
}
.scrim {
  position: fixed;
  inset: 0;
  background: rgba(12, 26, 44, 0.34);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.22s;
  z-index: 60;
}
.scrim.on {
  opacity: 1;
  pointer-events: auto;
}
.drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 560px;
  max-width: 90vw;
  background: #f0f3f8;
  transform: translateX(102%);
  transition: transform 0.28s cubic-bezier(0.3, 0.8, 0.3, 1);
  z-index: 61;
  display: flex;
  flex-direction: column;
  box-shadow: -16px 0 40px rgba(12, 26, 44, 0.16);
}
.drawer.on {
  transform: translateX(0);
}
.drawer-hd {
  height: 48px;
  background: #fff;
  border-bottom: 1px solid #e6ebf3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  flex: 0 0 48px;
}
.drawer-hd h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.close-x {
  border: 0;
  background: transparent;
  color: #8c99ac;
  font-size: 16px;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  cursor: pointer;
}
.close-x:hover {
  background: #eff2f7;
  color: #17233a;
}
.drawer-bd {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px 16px;
}
.post-main {
  background: #fff;
  border: 1px solid #e6ebf3;
  border-radius: 12px;
  padding: 16px 18px;
}
.post-meta {
  display: flex;
  align-items: center;
  gap: 9px;
}
.post-meta .ava {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #7fb3de, #4e7fb0);
  color: #fff;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 34px;
}
.post-meta .nm {
  font-size: 13.5px;
  font-weight: 600;
}
.post-meta .sub {
  font-size: 11px;
  color: #8c99ac;
  margin-top: 1px;
}
.post-meta .time {
  margin-left: auto;
  font-size: 11.5px;
  color: #8c99ac;
}
.post-title {
  font-size: 17px;
  font-weight: 600;
  margin: 13px 0 8px;
  line-height: 1.4;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.post-body {
  font-size: 13px;
  color: #33425b;
  line-height: 1.8;
}
.text-body {
  white-space: pre-wrap;
  word-break: break-word;
}
.post-files {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.post-files .attach {
  padding: 6px 10px;
  border-radius: 7px;
  font-size: 12px;
}
.post-files .attach .dl {
  margin-left: auto;
  color: #3e6e9e;
}
.post-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 14px;
  padding-top: 11px;
  border-top: 1px dashed #e6ebf3;
  font-size: 11.5px;
  color: #8c99ac;
}
.post-stats b {
  color: #5b6b84;
  font-weight: 500;
}
.post-admin {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 13px;
  padding-top: 12px;
  border-top: 1px solid #f1f4f9;
  flex-wrap: wrap;
}
.post-admin .lbl {
  font-size: 11px;
  color: #8c99ac;
}
.post-admin .tail-hint {
  margin-left: auto;
  font-size: 11px;
}
.cmt-sec {
  margin-top: 14px;
}
.cmt-sec h4 {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}
.cmt-sec h4 span {
  font-size: 11px;
  color: #8c99ac;
  font-weight: 400;
}
.cmt {
  background: #fff;
  border: 1px solid #e6ebf3;
  border-radius: 10px;
  padding: 11px 13px;
  margin-top: 9px;
  display: flex;
  gap: 10px;
}
.cmt .ava {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: linear-gradient(135deg, #8fb8dd, #5b87b5);
  color: #fff;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 26px;
}
.cmt .bd {
  flex: 1;
  min-width: 0;
}
.cmt .hd {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11.5px;
  color: #8c99ac;
}
.cmt .hd .n {
  font-size: 12.5px;
  font-weight: 500;
  color: #17233a;
}
.cmt .tx {
  font-size: 12.5px;
  color: #33425b;
  line-height: 1.7;
  margin-top: 4px;
}
.cmt .ft {
  display: flex;
  gap: 12px;
  margin-top: 7px;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(12, 26, 44, 0.38);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 70;
}
.modal {
  width: 520px;
  max-width: 92vw;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 24px 60px rgba(12, 26, 44, 0.22);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
}
.modal-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 0;
}
.modal-hd h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.modal-bd {
  padding: 14px 18px;
  overflow-y: auto;
}
.modal-ft {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  padding: 12px 18px;
  border-top: 1px solid #f1f4f9;
}
.warn-box,
.info-box {
  display: flex;
  gap: 10px;
  border-radius: 9px;
  padding: 11px 13px;
  margin-bottom: 12px;
}
.warn-box {
  background: #fef7f6;
  border: 1px solid #f5d5cf;
}
.info-box {
  background: #f4f8fc;
  border: 1px solid #d9e5f2;
}
.warn-box .wi {
  color: #c34a34;
}
.info-box .wi {
  color: #2f72b5;
}
.warn-box p,
.info-box p {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.65;
  color: #41536d;
}
.confirm-list {
  margin: 10px 0 4px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 180px;
  overflow-y: auto;
}
.confirm-list .ci {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  padding: 8px 11px;
  background: #f8fafd;
  border: 1px solid #f1f4f9;
  border-radius: 8px;
}
.confirm-list .ci em {
  font-style: normal;
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.confirm-list .ci span {
  color: #8c99ac;
  font-size: 11px;
}
.f-row {
  margin-bottom: 6px;
}
.f-row label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #5b6b84;
  margin-bottom: 6px;
}
.f-input {
  width: 100%;
  height: 32px;
  border: 1px solid #e6ebf3;
  border-radius: 7px;
  padding: 0 10px;
  font-size: 12.5px;
  font-family: inherit;
  color: #17233a;
  outline: 0;
  box-sizing: border-box;
}
.f-input:focus {
  border-color: #123b63;
  box-shadow: 0 0 0 3px rgba(18, 59, 99, 0.07);
}
.toast {
  position: fixed;
  top: 64px;
  left: 50%;
  transform: translateX(-50%) translateY(-10px);
  background: rgba(18, 35, 58, 0.94);
  color: #fff;
  font-size: 12.5px;
  padding: 9px 16px;
  border-radius: 9px;
  z-index: 100;
  opacity: 0;
  pointer-events: none;
  transition: all 0.25s;
  display: flex;
  align-items: center;
  gap: 8px;
}
.toast.on {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
.toast .ti {
  width: 15px;
  height: 15px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  flex: 0 0 15px;
  background: #2e9e7a;
}
.toast.err .ti {
  background: #d2462f;
}
@media (max-width: 1100px) {
  .filterbar {
    gap: 8px;
  }
  .field.search {
    width: 100%;
  }
  .fb-right {
    margin-left: 0;
    width: 100%;
  }
}

/* ================= 数据看板（P3b） ================= */
.seg-time {
  display: inline-flex;
  background: #e7ecf4;
  border-radius: 8px;
  padding: 2px;
}
.seg-time button {
  height: 24px;
  padding: 0 11px;
  border: 0;
  background: transparent;
  border-radius: 6px;
  font-size: 12px;
  color: #5b6b84;
  cursor: pointer;
}
.seg-time button.on {
  background: #fff;
  color: #123b63;
  font-weight: 500;
  box-shadow: 0 1px 3px rgba(23, 35, 58, 0.1);
}
.kpi-row {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 13px;
  margin-bottom: 13px;
}
@media (max-width: 1280px) {
  .kpi-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 760px) {
  .kpi-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.kpi {
  background: #fff;
  border: 1px solid #e6ebf3;
  border-radius: 12px;
  padding: 13px 15px 12px;
  position: relative;
  overflow: hidden;
}
.kpi::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: #123b63;
  opacity: 0.9;
}
.kpi.k-accent::after {
  background: #e23b2e;
}
.kpi.k-amber::after {
  background: #d9902e;
}
.kpi.k-green::after {
  background: #2e9e7a;
}
.kpi .k-label {
  font-size: 11.5px;
  color: #8c99ac;
}
.kpi .k-val {
  font-size: 26px;
  font-weight: 600;
  letter-spacing: -0.5px;
  margin-top: 4px;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}
.kpi .k-val small {
  font-size: 12px;
  font-weight: 400;
  color: #8c99ac;
  margin-left: 3px;
  letter-spacing: 0;
}
.kpi .k-foot {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 11px;
  color: #8c99ac;
}
.kpi .delta {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-weight: 500;
}
.kpi .delta.up {
  color: #2e9e7a;
}
.kpi .delta.down {
  color: #d2462f;
}
.dash-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 13px;
}
.dash-grid .span-8 {
  grid-column: span 8;
  min-width: 0;
}
.dash-grid .span-7 {
  grid-column: span 7;
  min-width: 0;
}
.dash-grid .span-5 {
  grid-column: span 5;
  min-width: 0;
}
.dash-grid .span-4 {
  grid-column: span 4;
  min-width: 0;
}
@media (max-width: 1100px) {
  .dash-grid .span-8,
  .dash-grid .span-7,
  .dash-grid .span-5,
  .dash-grid .span-4 {
    grid-column: span 12;
  }
}
.card {
  background: #fff;
  border: 1px solid #e6ebf3;
  border-radius: 12px;
  overflow: hidden;
  height: 100%;
}
.card-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 15px 0;
}
.card-hd h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #17233a;
  display: flex;
  align-items: center;
  gap: 6px;
}
.card-hd h3::before {
  content: '';
  width: 3px;
  height: 12px;
  border-radius: 2px;
  background: #123b63;
  display: inline-block;
}
.card-hd .sub {
  font-size: 11px;
  color: #8c99ac;
}
.card-bd {
  padding: 8px 15px 14px;
}
.wordcloud {
  /* 散点词云：容器只提供画布尺寸，具体坐标由 layoutCloud() 算好后绝对定位 */
  position: relative;
  width: 100%;
  height: 300px;
  margin: 0;
  padding: 0;
}
.wordcloud .w {
  position: absolute;
  transform: translate(-50%, -50%);
  line-height: 1;
  font-weight: 500;
  white-space: nowrap;
  cursor: default;
  transition: opacity 0.15s;
  user-select: none;
}
.wordcloud .w:hover {
  opacity: 0.68;
}
.wordcloud .w0 {
  color: #123b63;
}
.wordcloud .w1 {
  color: #2f72b5;
}
.wordcloud .w2 {
  color: #2e8b6b;
}
.wordcloud .w3 {
  color: #b97b1e;
}
.wordcloud .w4 {
  color: #5b6b84;
}
.wordcloud .w5 {
  color: #c34a34;
}
.hbars {
  display: flex;
  flex-direction: column;
  gap: 11px;
  padding-top: 6px;
}
.hbar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}
.hbar .lb {
  width: 74px;
  flex: 0 0 74px;
  color: #5b6b84;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hbar .track {
  flex: 1;
  height: 9px;
  background: #eff3f9;
  border-radius: 5px;
  overflow: hidden;
}
.hbar .fill {
  display: block;
  height: 100%;
  border-radius: 5px;
  transition: width 0.6s cubic-bezier(0.2, 0.7, 0.3, 1);
}
.hbar .vl {
  width: 34px;
  text-align: right;
  font-weight: 600;
  color: #17233a;
  font-variant-numeric: tabular-nums;
  font-size: 12px;
}
.risk {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.risk .item {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 10px 0;
  border-bottom: 1px dashed #e6ebf3;
}
.risk .item:last-child {
  border-bottom: 0;
}
.risk .ic {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 22px;
  font-size: 11px;
  font-weight: 600;
}
.risk .ic.r {
  background: #fdedeb;
  color: #c34a34;
}
.risk .ic.a {
  background: #fdf3e3;
  color: #b97b1e;
}
.risk .ic.b {
  background: #eaf1f8;
  color: #2f72b5;
}
.risk .tx {
  flex: 1;
  min-width: 0;
}
.risk .tx p {
  margin: 0;
  font-size: 12.5px;
  color: #17233a;
  line-height: 1.45;
}
.risk .go {
  font-size: 11.5px;
  color: #3e6e9e;
  border: 0;
  background: transparent;
  padding: 2px 4px;
  border-radius: 4px;
  cursor: pointer;
}
.risk .go:hover {
  background: #eaf1f8;
}
</style>
