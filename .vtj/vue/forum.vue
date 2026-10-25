<!-- 论坛模块 -->
<template>
  <div class="forum-page">
    <NavBar></NavBar>
    <main class="forum-main">
      <div class="forum-header">
        <h2>
          <XIcon :icon="ChatRound" :size="24" color="#c41e3a"></XIcon>
          <span> 备考论坛</span>
        </h2>
        <button class="post-btn" @click="openNewPost">
          <XIcon :icon="EditPen" :size="16" color="#ffffff"></XIcon>
          <span> 发布新帖</span>
        </button>
      </div>
      <div class="forum-body">
        <div class="forum-left">
          <div class="category-bar">
            <button
              v-for="cat in categoryTabs"
              :key="cat.key"
              :class="['category-chip', { active: state.activeCategory === cat.key }]"
              @click="selectCategory(cat.key)">
              {{ cat.name }}
            </button>
          </div>
          <div class="post-list" v-if="state.posts.length">
            <div
              v-for="(post, index) in filteredPosts"
              :key="post.id"
              class="post-item">
              <UserBadge
                class="post-avatar"
                avatar-only
                clickable
                size="md"
                :src="post.avatar"
                :name="post.author"
                :user-id="post.userId"
                @click="viewUser(post.userId)" />
              <div class="post-content" @click="viewPost(post)">
                <h4 class="post-title" :style="{ color: titleColorValue(post.titleColor) }">{{ post.title }}</h4>
                <p class="post-excerpt"><ForumContent :content="post.content" /></p>
                <AttachmentList
                  v-if="post.attachments && post.attachments.length"
                  :attachments="post.attachments"
                  mode="post" />
                <div class="post-attachments" v-if="post.fileAttachments && post.fileAttachments.length">
                  <span
                    v-for="(att, idx) in post.fileAttachments"
                    :key="idx"
                    class="attachment-chip"
                    @click.stop="downloadAttachment(att)">
                    <XIcon :icon="Document" :size="12" color="#1a2b5f"></XIcon>
                    <span> {{ att.name }}</span>
                  </span>
                </div>
                <div class="post-meta">
                  <span class="meta-author" @click.stop="viewUser(post.userId)">{{ post.author }}</span>
                  <span class="meta-dot"> ·</span>
                  <span class="meta-date">{{ post.date }}</span>
                  <span class="meta-dot"> ·</span>
                  <span class="meta-likes" @click.stop="toggleLike(post)">
                    <XIcon
                      :icon="post.liked ? StarFilled : Star"
                      :size="13"
                      :color="post.liked ? '#c41e3a' : '#8a8faa'"></XIcon>
                    <span> {{ post.likeCount }}</span>
                  </span>
                  <span class="meta-dot"> ·</span>
                  <span class="meta-comments">
                    <XIcon :icon="ChatLineRound" :size="13" color="#8a8faa"></XIcon>
                    <span> {{ post.commentCount }}</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div v-else-if="state.loading" class="empty-tip">加载中...</div>
          <div v-else class="empty-tip">暂无帖子,快来发表第一篇吧!</div>
          <div class="pagination" v-if="state.total > state.pageSize">
            <button :disabled="state.page === 1" @click="prevPage">上一页</button>
            <span class="page-info">
              <span> {{ state.page }} </span>
              <span> / </span>
              <span> {{ totalPages }} </span>
            </span>
            <button :disabled="state.page >= totalPages" @click="nextPage">下一页</button>
          </div>
        </div>
        <aside class="forum-right">
          <div class="right-card hot-posts">
            <h4>
              <XIcon :icon="TrendCharts" :size="16" color="#ef4444"></XIcon>
              <span> 热门帖子</span>
            </h4>
            <div
              v-for="(hot, index) in hotPosts"
              :key="hot.id"
              class="hot-item"
              @click="viewPost(hot)">
              <span class="hot-rank" :class="'rank-' + hot.rank">{{ hot.rank }}</span>
              <span class="hot-title">{{ hot.title }}</span>
              <span class="hot-replies">
                <span> {{ hot.commentCount }} </span>
                <span> 回复</span>
              </span>
            </div>
            <div v-if="!hotPosts.length" class="empty-tip-mini">暂无热门</div>
          </div>
          <div class="right-card user-stats">
            <h4>
              <XIcon :icon="User" :size="16" color="#1a2b5f"></XIcon>
              <span> 论坛活跃</span>
            </h4>
            <div class="stats-grid">
              <div class="stats-item">
                <span class="stats-number">{{ state.forumStats.posts }}</span>
                <span class="stats-label"> 帖子</span>
              </div>
              <div class="stats-item">
                <span class="stats-number">{{ state.forumStats.users }}</span>
                <span class="stats-label"> 用户</span>
              </div>
              <div class="stats-item">
                <span class="stats-number">{{ state.forumStats.online }}</span>
                <span class="stats-label"> 在线</span>
              </div>
            </div>
          </div>
          <div v-if="isLoggedIn" class="right-card my-posts">
            <h4>
              <XIcon :icon="User" :size="16" color="#1a2b5f"></XIcon>
              <span> 我的帖子</span>
            </h4>
            <div v-if="state.myPosts.length" class="my-post-list">
              <div
                v-for="mp in state.myPosts.slice(0, 5)"
                :key="mp.id"
                class="my-post-item"
                @click="openPostDetail(mp)">
                <span class="my-post-title">{{ mp.title }}</span>
                <span class="my-post-stats">
                  <span class="my-stat">❤️ {{ mp.likeCount }}</span>
                  <span class="my-stat">💬 {{ mp.commentCount }}</span>
                </span>
              </div>
            </div>
            <div v-else-if="state.myPostsLoaded" class="empty-tip-mini">暂无帖子</div>
            <div v-else class="empty-tip-mini">加载中...</div>
            <div v-if="state.myPostsTotal > 5" class="my-posts-view-all" @click="openMyPosts">
              查看全部 {{ state.myPostsTotal }} 条 →
            </div>
          </div>
        </aside>
      </div>
      <div
        v-if="state.showNewPost"
        class="modal-overlay"
        @click.self="state.showNewPost = false">
        <div class="modal-card">
          <h3>发布新帖</h3>
          <input
            v-model="state.newPost.title"
            class="modal-input"
            placeholder="请输入标题..."
            maxlength="200"/>
          <div class="post-color-row">
            <span class="post-color-label">标题颜色</span>
            <TitleColorPicker v-model="state.newPost.titleColor" />
          </div>
          <textarea
            v-model="state.newPost.content"
            rows="6"
            class="modal-textarea"
            placeholder="请输入内容(分享观点、学习经验...)"
            maxlength="10000"></textarea>
          <div class="post-image-upload">
            <label class="post-color-label">图片（不限张数）</label>
            <FileUploader v-model="state.newPost.images" :max-docs="10" />
          </div>
          <div class="upload-area">
            <input
              type="file"
              ref="fileInput"
              multiple
              accept=".doc,.docx,.pdf,.xls,.xlsx"
              @change="handleFileUpload"
              style="display:none"/>
            <button class="upload-btn" @click="triggerUpload">
              <XIcon :icon="Upload" :size="14" color="#1a2b5f"></XIcon>
              <span> 上传学习资料(Word/PDF/Excel)</span>
            </button>
            <div v-for="(f, i) in state.newPost.attachments" :key="i" class="file-chip">
              <XIcon :icon="Document" :size="12" color="#1a2b5f"></XIcon>
              <span class="file-name"> {{ f.name }} </span>
              <span class="file-size"> ({{ formatFileSize(f.size) }}) </span>
              <span class="file-remove" @click="removeFile(i)"> ×</span>
            </div>
          </div>
          <div class="modal-actions">
            <button class="cancel-btn" @click="state.showNewPost = false">取消</button>
            <button class="confirm-btn" :disabled="state.submitting" @click="submitPost">
              {{ state.submitting ? '发布中...' : '发布' }}
            </button>
          </div>
        </div>
      </div>
      <div
        v-if="state.showUserProfile"
        class="modal-overlay"
        @click.self="state.showUserProfile = false">
        <div class="profile-card">
          <div class="profile-avatar-wrap">
            <img
              v-if="state.userProfile.avatar"
              :src="state.userProfile.avatar"
              class="profile-avatar"
              alt="头像"
              @error="onProfileAvatarError"/>
            <span v-else class="profile-avatar-text">{{ (state.userProfile.nickname || '匿').charAt(0) }}</span>
          </div>
          <h3>{{ state.userProfile.nickname }}</h3>
          <p class="profile-info" v-if="state.userProfile.school || state.userProfile.department">
            <span v-if="state.userProfile.school">{{ state.userProfile.school }}</span>
            <span v-if="state.userProfile.school && state.userProfile.department"> · </span>
            <span v-if="state.userProfile.department">{{ state.userProfile.department }}</span>
          </p>
          <p class="profile-info" v-if="state.userProfile.className">
            <span>{{ state.userProfile.className }}</span>
          </p>
          <p class="profile-joined" v-if="state.userProfile.createdAt">
            注册于 {{ formatTime(state.userProfile.createdAt) }}
          </p>
          <div class="profile-stats">
            <div class="profile-stat-item">
              <strong>{{ state.userProfile.postCount }}</strong>
              <span> 帖子</span>
            </div>
            <div class="profile-stat-item">
              <strong>{{ state.userProfile.likeReceived }}</strong>
              <span> 获赞</span>
            </div>
          </div>
          <button class="profile-close-btn" @click="state.showUserProfile = false">关闭</button>
        </div>
      </div>
      <!-- 帖子详情 Modal -->
      <div
        v-if="state.showPostDetail"
        class="modal-overlay"
        @click.self="closePostDetail">
        <div class="modal-card post-detail-card">
          <div v-if="state.detailLoading && !state.currentPost" class="empty-tip">加载中...</div>
          <template v-else-if="state.currentPost">
            <!-- 帖子头部 -->
            <div class="detail-header">
              <h3>{{ state.currentPost.title }}</h3>
              <span v-if="state.currentPost.isTop" class="badge badge-top">置顶</span>
              <span v-if="state.currentPost.isEssence" class="badge badge-essence">精华</span>
            </div>
            <!-- 作者信息 -->
            <div class="detail-author">
              <UserBadge
                class="post-avatar"
                avatar-only
                clickable
                size="md"
                :src="state.currentPost.avatar"
                :name="state.currentPost.author"
                :user-id="state.currentPost.userId"
                @click="viewUser(state.currentPost.userId)" />
              <div class="author-info">
                <span class="author-name" @click.stop="viewUser(state.currentPost.userId)">{{ state.currentPost.author }}</span>
                <span class="author-time">{{ state.currentPost.date }}</span>
              </div>
              <button v-if="canDeleteCurrentPost" class="delete-post-btn" @click="deletePost">删除</button>
            </div>
            <!-- 帖子正文 -->
            <h3 class="detail-title" :style="{ color: titleColorValue(state.currentPost.titleColor) }">
              {{ state.currentPost.title }}
            </h3>
            <div class="detail-content"><ForumContent :content="state.currentPost.content" /></div>
            <!-- 图片 + 文档附件 -->
            <AttachmentList
              v-if="state.currentPost.attachments && state.currentPost.attachments.length"
              :attachments="state.currentPost.attachments"
              mode="post" />
            <!-- 帖子互动数据 -->
            <div class="detail-stats">
              <span class="stat-action" @click="toggleLike(state.currentPost)">
                <XIcon
                  :icon="state.currentPost.liked ? StarFilled : Star"
                  :size="14"
                  :color="state.currentPost.liked ? '#c41e3a' : '#8a8faa'"></XIcon>
                <span> {{ state.currentPost.likeCount }}</span>
              </span>
              <span class="stat-label">
                <XIcon :icon="ChatLineRound" :size="14" color="#8a8faa"></XIcon>
                <span> {{ state.currentPost.commentCount }}</span>
              </span>
              <span class="stat-label">
                <XIcon :icon="View" :size="14" color="#8a8faa"></XIcon>
                <span> {{ state.currentPost.viewCount }}</span>
              </span>
            </div>
            <!-- 评论区域 -->
            <div class="comment-section">
              <h4>评论 ({{ state.currentPost.commentCount }})</h4>
              <div class="comment-sort-row">
                <CommentSortBar
                  :sort-by="state.commentSortBy"
                  :order="state.commentOrder"
                  @update:sortBy="changeCommentSort"
                  @update:order="changeCommentOrder" />
              </div>
              <div v-if="state.commentsLoading" class="empty-tip-mini">加载评论中...</div>
              <div v-else-if="!state.comments.length" class="empty-tip-mini">暂无评论，抢个沙发吧!</div>
              <div v-else class="comment-list">
                <div v-for="comment in state.comments" :key="comment.id" class="comment-item">
                  <div class="comment-main">
                    <UserBadge
                      class="comment-avatar"
                      avatar-only
                      clickable
                      size="sm"
                      :src="comment.user?.avatar"
                      :name="comment.user?.nickname"
                      :user-id="comment.user?.id"
                      :user-type="comment.user?.userType"
                      @click="viewUser(comment.user?.id)" />
                    <div class="comment-body">
                      <div class="comment-meta">
                        <span class="comment-author" @click.stop="viewUser(comment.user?.id)">{{ comment.user?.nickname }}</span>
                        <span class="comment-time">{{ formatTime(comment.createTime) }}</span>
                      </div>
                      <div class="comment-text"><ForumContent :content="comment.content" /></div>
                      <AttachmentList
                        v-if="comment.attachments && comment.attachments.length"
                        :attachments="comment.attachments"
                        mode="comment" />
                      <div class="comment-actions">
                        <span @click="toggleCommentLike(comment)" class="comment-action">
                          <XIcon
                            :icon="comment.liked ? StarFilled : Star"
                            :size="12"
                            :color="comment.liked ? '#c41e3a' : '#8a8faa'"></XIcon>
                          <span> {{ comment.likeCount }}</span>
                        </span>
                        <span @click="startReply(comment)" class="comment-action comment-reply">
                          <XIcon :icon="ChatLineRound" :size="12" color="#8a8faa"></XIcon>
                          <span> 回复</span>
                        </span>
                        <span
                          v-if="canPinComment(comment)"
                          class="comment-action"
                          @click="togglePinComment(comment)">
                          {{ comment.isPinned ? '取消置顶' : '置顶' }}
                        </span>
                        <span
                          v-if="canReportComment(comment)"
                          class="comment-action"
                          @click="reportComment(comment)">
                          举报
                        </span>
                      </div>
                    </div>
                  </div>
                  <!-- 子评论（楼中楼） -->
                  <div v-if="comment.children && comment.children.length" class="comment-children">
                    <div v-for="child in comment.children" :key="child.id" class="comment-item child">
                      <div class="comment-main">
                        <UserBadge
                          class="comment-avatar"
                          avatar-only
                          clickable
                          size="sm"
                          :src="child.user?.avatar"
                          :name="child.user?.nickname"
                          :user-id="child.user?.id"
                          :user-type="child.user?.userType"
                          @click="viewUser(child.user?.id)" />
                        <div class="comment-body">
                          <div class="comment-meta">
                            <span class="comment-author" @click.stop="viewUser(child.user?.id)">{{ child.user?.nickname }}</span>
                            <span class="comment-time">{{ formatTime(child.createTime) }}</span>
                          </div>
                          <div class="comment-text"><ForumContent :content="child.content" /></div>
                          <AttachmentList
                            v-if="child.attachments && child.attachments.length"
                            :attachments="child.attachments"
                            mode="comment" />
                          <div class="comment-actions">
                            <span @click="toggleCommentLike(child)" class="comment-action">
                              <XIcon
                                :icon="child.liked ? StarFilled : Star"
                                :size="12"
                                :color="child.liked ? '#c41e3a' : '#8a8faa'"></XIcon>
                              <span> {{ child.likeCount }}</span>
                            </span>
                            <span
                              v-if="canReportComment(child)"
                              class="comment-action"
                              @click="reportComment(child)">
                              举报
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <!-- 评论输入区 -->
              <div class="comment-input-area">
                <div v-if="state.replyTarget" class="reply-hint">
                  回复 @{{ state.replyTarget.username }}
                  <span class="cancel-reply" @click="cancelReply">× 取消</span>
                </div>
                <div v-if="state.showCommentPicker" class="comment-picker">
                  <EmojiStickerPicker
                    @select="insertCommentEmoji"
                    @close="state.showCommentPicker = false" />
                </div>
                <div class="comment-toolbar">
                  <button
                    class="emoji-btn"
                    title="表情 / 表情包"
                    @click="state.showCommentPicker = !state.showCommentPicker">
                    😀
                  </button>
                  <span class="comment-toolbar-tip">支持 emoji 与自定义表情包</span>
                </div>
                <div class="comment-image-upload">
                  <FileUploader v-model="state.newCommentImages" :max-docs="3" />
                </div>
                <textarea
                  v-model="state.newComment"
                  rows="3"
                  class="modal-textarea"
                  :placeholder="state.replyTarget ? '输入回复内容...' : '写下你的评论...'"
                  maxlength="2000"></textarea>
                <div class="modal-actions">
                  <button class="cancel-btn" @click="closePostDetail">关闭</button>
                  <button
                    class="confirm-btn"
                    :disabled="state.commentSubmitting || !state.newComment.trim()"
                    @click="submitComment">
                    {{ state.commentSubmitting ? '提交中...' : '发表评论' }}
                  </button>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
      <!-- 我的帖子完整列表 Modal -->
      <div
        v-if="state.showMyPosts"
        class="modal-overlay"
        @click.self="closeMyPosts">
        <div class="modal-card post-detail-card">
          <h3>我的帖子（{{ state.myPostsTotal }}）</h3>
          <div v-if="state.myPostsLoading" class="empty-tip-mini">加载中...</div>
          <div v-else-if="!state.myPosts.length" class="empty-tip-mini">暂无帖子</div>
          <div v-else class="my-posts-full-list">
            <div
              v-for="mp in state.myPosts"
              :key="mp.id"
              class="my-post-item"
              @click="openPostDetail(mp)">
              <span class="my-post-title">{{ mp.title }}</span>
              <span class="my-post-stats">
                <span class="my-stat">❤️ {{ mp.likeCount }}</span>
                <span class="my-stat">💬 {{ mp.commentCount }}</span>
              </span>
              <span class="my-post-date">{{ mp.date }}</span>
            </div>
          </div>
          <div v-if="myPostsTotalPages > 1" class="pagination">
            <button :disabled="state.myPostsPage === 1" @click="prevMyPostsPage">上一页</button>
            <span class="page-info">
              <span> {{ state.myPostsPage }} </span>
              <span> / </span>
              <span> {{ myPostsTotalPages }} </span>
            </span>
            <button :disabled="state.myPostsPage >= myPostsTotalPages" @click="nextMyPostsPage">下一页</button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import {
    ChatRound,
    EditPen,
    ChatLineRound,
    View,
    TrendCharts,
    User,
    Document,
    Upload,
    Star,
    StarFilled
  } from '@vtj/icons';
  import NavBar from './navbar.vue';
  import { useProvider } from '@vtj/renderer';
  import { ElMessage } from 'element-plus';
  import { useCommunityStore } from '@/modules/community/store';
  import {
    formatReactionSummary,
    reactionTotal
  } from '@/modules/community/reactions';
  import { avatarInitial } from '@/modules/community/avatar';
  import {
    FORUM_CATEGORY_TABS,
    toShareTypeParam
  } from '@/modules/community/categories';
  import EmojiStickerPicker from '@/components/forum/EmojiStickerPicker.vue';
  import ForumContent from '@/components/forum/ForumContent.vue';
  import ImageGrid from '@/components/forum/ImageGrid.vue';
  import ImageUploader from '@/components/forum/ImageUploader.vue';
  import FileUploader from '@/components/forum/FileUploader.vue';
  import AttachmentList from '@/components/forum/AttachmentList.vue';
  import CommentSortBar from '@/components/forum/CommentSortBar.vue';
  import TitleColorPicker from '@/components/forum/TitleColorPicker.vue';
  import UserBadge from '@/components/forum/UserBadge.vue';
  import { pinForumComment, reportForumTarget } from '@/modules/community/api';
  import { titleColorValue } from '@/components/forum/titleColors';
  import { isImageUrl } from '@/components/forum/imageUtils';
  import type { ForumImageAttachment } from '@/components/forum/imageUtils';
  export default defineComponent({
    name: 'Forum',
    components: {
      NavBar,
      XIcon,
      EmojiStickerPicker,
      ForumContent,
      ImageGrid,
      ImageUploader,
      FileUploader,
      AttachmentList,
      CommentSortBar,
      TitleColorPicker,
      UserBadge
    },
    setup(props) {
      const provider = useProvider({ id: 'forum', version: '1785094400000' });
      const community = useCommunityStore();
      const state = reactive({
        page: 1,
        pageSize: 8,
        activeCategory: 'all',
        showCommentPicker: false,
        posts: [] as any[],
        total: 0,
        loading: false,
        submitting: false,
        showNewPost: false,
        showUserProfile: false,
        userProfile: {} as any,
        newPost: {
          title: '',
          content: '',
          titleColor: 'default',
          images: [] as ForumImageAttachment[],
          attachments: [] as any[]
        },
        newCommentImages: [] as ForumImageAttachment[],
        commentSortBy: 'time',
        commentOrder: 'desc',
        forumStats: { posts: 0, users: 0, online: 0 },
        // === 帖子详情 ===
        showPostDetail: false,
        currentPost: null as any,
        detailLoading: false,
        // === 评论 ===
        comments: [] as any[],
        commentsLoading: false,
        newComment: '',
        commentSubmitting: false,
        replyTarget: null as any,
        // === 我的帖子 ===
        myPosts: [] as any[],
        myPostsLoaded: false,
        myPostsTotal: 0,
        showMyPosts: false,
        myPostsPage: 1,
        myPostsPageSize: 20,
        myPostsLoading: false,
        _refreshTimer: null as any,
        _visibilityHandler: null as any
      });
      const avatarFailed = reactive<Record<string, boolean>>({});
      const markAvatarFailed = (key: string) => {
        avatarFailed[key] = true;
      };
      return {
        state,
        props,
        provider,
        community,
        avatarInitial,
        avatarFailed,
        markAvatarFailed,
        titleColorValue,
        categoryTabs: FORUM_CATEGORY_TABS,
        ChatRound,
        EditPen,
        ChatLineRound,
        View,
        TrendCharts,
        User,
        Document,
        Upload,
        Star,
        StarFilled
      };
    },
    computed: {
      totalPages(): number {
        return Math.max(1, Math.ceil(this.state.total / this.state.pageSize));
      },
      filteredPosts(): any[] {
        // 后端已分页,直接返回(避免前端切片导致显示数量不准)
        return this.state.posts;
      },
      hotPosts(): any[] {
        return [...this.state.posts]
          .sort((a, b) => (b.reactionTotal + b.commentCount * 2) - (a.reactionTotal + a.commentCount * 2))
          .slice(0, 5)
          .map((p, i) => ({ ...p, rank: i + 1 }));
      },
      canDeleteCurrentPost(): boolean {
        if (!this.state.currentPost) return false;
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) return false;
        // 后端会最终校验,前端仅控制按钮显示
        return true;
      },
      isLoggedIn(): boolean {
        const auth = (window as any).__VTJ_AUTH__;
        return !!(auth && auth.isLoggedIn());
      },
      myPostsTotalPages(): number {
        return Math.max(1, Math.ceil(this.state.myPostsTotal / this.state.myPostsPageSize));
      }
    },
    methods: {
      async loadPosts(silent = false) {
        this.state.loading = true;
        try {
          await this.community.loadPage(this.state.page, this.state.pageSize);
          this.state.posts = this.community.posts.map((p: any) => this._mapPost(p));
          this.state.total = this.community.total;
          if (this.community.error && !silent) {
            this._safeMsg('error', this.community.error);
          }
        } finally {
          this.state.loading = false;
        }
      },
      async selectCategory(key: string) {
        if (this.state.activeCategory === key) return;
        this.state.activeCategory = key;
        this.state.page = 1;
        this.state.showCommentPicker = false;
        this.community.setShareType(toShareTypeParam(key));
        await this.loadPosts();
      },
      insertCommentEmoji(payload: { type: 'emoji' | 'sticker'; value: string }) {
        const text =
          payload.type === 'emoji' ? payload.value : `[[sticker:${payload.value}]]`;
        this.state.newComment = `${this.state.newComment || ''}${text}`;
      },
      async refreshSilently() {
        if (this.community.loading) return;
        if (this.state.showNewPost || this.state.showPostDetail) return;
        if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
          return;
        }
        await this.loadPosts(true);
      },
      async loadStats() {
        await this.community.loadStats();
        const stats = this.community.stats;
        if (stats) {
          this.state.forumStats = {
            posts: stats.posts || 0,
            users: stats.users || 0,
            online: stats.online || 0
          };
        }
      },
      async submitPost() {
        if (!this.state.newPost.title.trim()) {
          ElMessage.warning('请输入标题');
          return;
        }
        if (!this.state.newPost.content.trim()) {
          ElMessage.warning('请输入内容');
          return;
        }
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) {
          ElMessage.warning('请先登录后发帖');
          return;
        }
        this.state.submitting = true;
        try {
          const allAttachments = [
            ...this.state.newPost.images,
            ...this.state.newPost.attachments
          ];
          const created = await this.community.createPost({
            title: this.state.newPost.title,
            content: this.state.newPost.content,
            shareType: 'EXPERIENCE',
            titleColor: this.state.newPost.titleColor,
            attachments: allAttachments.length ? allAttachments : undefined
          });
          if (!created) return;
          // 成功:unshift 到列表头(实时更新)
          this.state.posts.unshift(this._mapPost(created));
          this.state.total += 1;
          // 同步刷新「我的帖子」卡片,该区域展示数字
          this.state.myPosts.unshift(this._mapPost(created, false));
          this.state.myPostsTotal = (this.state.myPostsTotal || 0) + 1;
          this.state.showNewPost = false;
          this.state.newPost = {
            title: '',
            content: '',
            titleColor: 'default',
            images: [],
            attachments: []
          };
          ElMessage.success('发布成功!');
        } catch (e) {
          this._safeMsg('error', this.community.error || '发布失败,请稍后重试');
        } finally {
          this.state.submitting = false;
        }
      },
      triggerUpload() {
        (this.$refs as any).fileInput && (this.$refs as any).fileInput.click();
      },
      async handleFileUpload(e: any) {
        const files = Array.from(e.target.files || []);
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) {
          ElMessage.warning('请先登录');
          return;
        }
        for (const file of files) {
          const formData = new FormData();
          formData.append('file', file);
          try {
            const res = await auth.apiFetch('/api/forum/upload', {
              method: 'POST',
              body: formData
            });
            const data = await res.json();
            if (res.ok) {
              this.state.newPost.attachments.push(data);
              ElMessage.success(`${file.name} 上传成功`);
            } else {
              ElMessage.error(data.message || data.detail || `${file.name} 上传失败`);
            }
          } catch (err) {
            ElMessage.error(`${file.name} 上传失败`);
          }
        }
        e.target.value = '';
      },
      removeFile(index: number) {
        this.state.newPost.attachments.splice(index, 1);
      },
      downloadAttachment(att: any) {
        if (!att.url) return;
        // 同页下载，避免新开标签页；图片已由 ImageGrid 在页内预览
        const link = document.createElement('a');
        link.href = att.url;
        link.download = att.name || '';
        link.rel = 'noopener';
        document.body.appendChild(link);
        link.click();
        link.remove();
      },
      async toggleLike(post: any) {
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) {
          ElMessage.warning('请先登录后点赞');
          return;
        }
        try {
          const data = await this.community.reactToPost(post.id, 'like');
          if (data) {
            post.myReaction = data.myReaction;
            post.reactions = data.reactions;
            post.reactionTotal = data.reactionCount;
            post.liked = data.myReaction !== null;
            post.likeCount =
              formatReactionSummary(data.reactions) || String(data.reactionCount);
          }
        } catch (e) {
          /* 静默 */
        }
      },
      async viewUser(userId: number) {
        if (!userId) return;
        const data = await this.community.loadUserPublic(userId);
        if (!data) {
          this._safeMsg('error', '获取用户信息失败');
          return;
        }
        this.state.userProfile = data;
        this.state.showUserProfile = true;
      },
      viewPost(post: any) {
        this.openPostDetail(post);
      },
      formatTime(iso: string): string {
        if (!iso) return '';
        const d = new Date(iso);
        const pad = (n: number) => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
      },
      formatFileSize(bytes: number): string {
        if (!bytes) return '0B';
        if (bytes < 1024) return bytes + 'B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
        return (bytes / 1024 / 1024).toFixed(1) + 'MB';
      },
      prevPage() {
        if (this.state.page > 1) {
          this.state.page--;
          this.loadPosts();
        }
      },
      nextPage() {
        if (this.state.page < this.totalPages) {
          this.state.page++;
          this.loadPosts();
        }
      },
      openNewPost() {
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) {
          ElMessage.warning('请先登录后发帖');
          return;
        }
        this.state.showNewPost = true;
      },
      onAvatarError(e: any) {
        // 头像加载失败,隐藏 img 显示首字母
        e.target.style.display = 'none';
      },
      onProfileAvatarError(e: any) {
        e.target.style.display = 'none';
      },
      // ===== 帖子详情 =====
      async openPostDetail(post: any) {
        if (this.state.detailLoading) return;
        this.resetDetailState();
        this.state.detailLoading = true;
        this.state.showPostDetail = true;
        try {
          await this.community.loadPost(post.id);
          if (!this.community.detail) throw new Error(this.community.error || '加载失败');
          this.state.currentPost = this._mapPost(this.community.detail);
          await this.loadComments(post.id);
        } catch (e) {
          this._safeMsg('error', '加载帖子详情失败');
          this.state.showPostDetail = false;
        } finally {
          this.state.detailLoading = false;
        }
      },
      closePostDetail() {
        this.resetDetailState();
      },
      resetDetailState() {
        this.state.showPostDetail = false;
        this.state.currentPost = null;
        this.state.comments = [];
        this.state.newComment = '';
        this.state.newCommentImages = [];
        this.state.replyTarget = null;
        this.state.showCommentPicker = false;
        this.state.detailLoading = false;
      },
      async deletePost() {
        const post = this.state.currentPost;
        if (!post) return;
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) {
          this._safeMsg('warning', '请先登录');
          return;
        }
        if (!confirm('确定要删除这篇帖子吗？删除后不可恢复。')) return;
        try {
          await this.community.deletePost(post.id);
          this._safeMsg('success', '删除成功');
          // 从列表中移除
          const idx = this.state.posts.findIndex((p: any) => p.id === post.id);
          if (idx >= 0) {
            this.state.posts.splice(idx, 1);
            this.state.total = Math.max(0, this.state.total - 1);
          }
          this.closePostDetail();
        } catch (e) {
          this._safeMsg('error', this.community.error || '删除失败');
        }
      },
      // ===== 评论系统 =====
      async loadComments(postId: number) {
        this.state.commentsLoading = true;
        try {
          await this.community.loadComments(postId, {
            sortBy: this.state.commentSortBy,
            order: this.state.commentOrder
          });
          this.state.comments = this.buildCommentTree(this.community.comments);
        } finally {
          this.state.commentsLoading = false;
        }
      },
      async changeCommentSort(key: string) {
        this.state.commentSortBy = key;
        if (this.state.currentPost) await this.loadComments(this.state.currentPost.id);
      },
      async changeCommentOrder(order: string) {
        this.state.commentOrder = order;
        if (this.state.currentPost) await this.loadComments(this.state.currentPost.id);
      },
      buildCommentTree(flatList: any[]): any[] {
        const map: any = {};
        const roots: any[] = [];
        flatList.forEach((c: any) => { map[c.id] = { ...c, children: [] }; });
        flatList.forEach((c: any) => {
          if (c.parentCommentId && map[c.parentCommentId]) {
            map[c.parentCommentId].children.push(map[c.id]);
          } else if (!c.parentCommentId) {
            roots.push(map[c.id]);
          }
        });
        return roots;
      },
      async submitComment() {
        if (!this.state.newComment.trim()) return;
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) {
          this._safeMsg('warning', '请先登录后评论');
          return;
        }
        if (!this.state.currentPost) return;
        this.state.commentSubmitting = true;
        try {
          await this.community.submitComment(this.state.currentPost.id, {
            content: this.state.newComment,
            parentCommentId: this.state.replyTarget
              ? this.state.replyTarget.commentId
              : undefined,
            attachments: this.state.newCommentImages.length
              ? this.state.newCommentImages
              : undefined
          });
          this._safeMsg('success', '评论成功');
          this.state.newComment = '';
          this.state.newCommentImages = [];
          this.state.replyTarget = null;
          if (this.state.currentPost) {
            this.state.currentPost.commentCount = (this.state.currentPost.commentCount || 0) + 1;
          }
          await this.loadComments(this.state.currentPost.id);
        } catch (e) {
          this._safeMsg('error', this.community.error || '评论失败');
        } finally {
          this.state.commentSubmitting = false;
        }
      },
      _currentUserId() {
        const auth = (window as any).__VTJ_AUTH__;
        const info = auth && auth.parseUserInfo ? auth.parseUserInfo() : null;
        return info && info.userId ? info.userId : null;
      },
      canPinComment(comment: any) {
        const uid = this._currentUserId();
        if (!uid) return false;
        const roleLevel =
          ((window as any).__VTJ_AUTH__?.parseUserInfo?.() || {}).roleLevel || 0;
        return uid === this.state.currentPost?.userId || roleLevel >= 2;
      },
      canReportComment(comment: any) {
        return comment.user?.id !== this._currentUserId();
      },
      async togglePinComment(comment: any) {
        try {
          await pinForumComment(comment.id, !comment.isPinned);
          if (this.state.currentPost) {
            await this.loadComments(this.state.currentPost.id);
          }
          this._safeMsg('success', comment.isPinned ? '已取消置顶' : '已置顶');
        } catch (e) {
          this._safeMsg('error', '操作失败');
        }
      },
      async reportComment(comment: any) {
        const reason = window.prompt(
          '举报原因：spam（广告）/ abuse（辱骂）/ illegal（违法）/ other（其他）',
          'abuse'
        );
        if (!reason) return;
        const allowed = ['spam', 'abuse', 'illegal', 'other'];
        try {
          await reportForumTarget({
            targetType: 'COMMENT',
            targetId: comment.id,
            reasonCode: (allowed.includes(reason) ? reason : 'other') as any
          });
          this._safeMsg('success', '举报已提交');
        } catch (e) {
          this._safeMsg('error', '举报失败');
        }
      },
      async toggleCommentLike(comment: any) {
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) {
          this._safeMsg('warning', '请先登录后点赞');
          return;
        }
        try {
          const data = await this.community.toggleCommentLike(comment.id);
          if (data) {
            comment.liked = data.liked;
            comment.likeCount = data.likeCount;
          }
        } catch (e) {
          /* 静默 */
        }
      },
      startReply(comment: any) {
        this.state.replyTarget = {
          commentId: comment.id,
          username: (comment.user && comment.user.nickname) || '匿名'
        };
        this.state.newComment = '';
        // 聚焦输入框
        this.$nextTick(() => {
          const textarea = document.querySelector('.comment-input-area textarea') as HTMLTextAreaElement;
          if (textarea) textarea.focus();
        });
      },
      cancelReply() {
        this.state.replyTarget = null;
        this.state.newComment = '';
      },
      // ===== 我的帖子 =====
      async loadMyPosts() {
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) return;
        await this.community.loadMyPosts({ limit: 5, offset: 0 });
          this.state.myPosts = this.community.myPosts.map((p: any) => this._mapPost(p, false));
          this.state.myPostsTotal = this.community.myPostsTotal;
          this.state.myPostsLoaded = true;
      },
      async openMyPosts() {
        this.state.showMyPosts = true;
        this.state.myPostsPage = 1;
        await this.loadMyPostsPage();
      },
      async loadMyPostsPage() {
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) return;
        this.state.myPostsLoading = true;
        try {
          const offset = (this.state.myPostsPage - 1) * this.state.myPostsPageSize;
          await this.community.loadMyPosts({
            limit: this.state.myPostsPageSize,
            offset
          });
          this.state.myPosts = this.community.myPosts.map((p: any) => this._mapPost(p, false));
          this.state.myPostsTotal = this.community.myPostsTotal;
        } finally {
          this.state.myPostsLoading = false;
        }
      },
      closeMyPosts() {
        this.state.showMyPosts = false;
      },
      prevMyPostsPage() {
        if (this.state.myPostsPage > 1) {
          this.state.myPostsPage--;
          this.loadMyPostsPage();
        }
      },
      nextMyPostsPage() {
        if (this.state.myPostsPage < this.myPostsTotalPages) {
          this.state.myPostsPage++;
          this.loadMyPostsPage();
        }
      },
      // ===== 安全辅助 =====
      _safeMsg(type: string, msg: string) {
        try {
          (ElMessage as any)[type](msg);
        } catch (e) {
          console.log(`[forum] ${type}: ${msg}`);
        }
      },
      _mapPost(p: any, withSummary = true): any {
        const reactions = p?.reactions ?? {};
        const total = reactionTotal(reactions);
        const summary = formatReactionSummary(reactions);
        const attachments = Array.isArray(p?.attachments) ? p.attachments : [];
        const imageUrls = attachments
          .map((att: any) => att?.url)
          .filter((url: any) => typeof url === 'string' && isImageUrl(url));
        const fileAttachments = attachments.filter(
          (att: any) => !isImageUrl(att?.url || '')
        );
        return {
          id: p?.id ?? 0,
          title: p?.title ?? '',
          content: p?.content ?? '',
          author: (p?.user && p.user.nickname) || '匿名',
          avatar: (p?.user && p.user.avatar) || '',
          date: this.formatTime(p?.createTime),
          likeCount: withSummary ? summary || String(total) : total,
          reactionTotal: total,
          reactions,
          myReaction: p?.myReaction ?? null,
          commentCount: p?.commentCount ?? 0,
          viewCount: p?.viewCount ?? 0,
          liked: p?.liked ?? false,
          attachments,
          imageUrls,
          fileAttachments,
          titleColor: p?.titleColor ?? 'default',
          isLocked: !!p?.isLocked,
          shareType: p?.shareType ?? '',
          userId: p?.user?.id ?? null,
          isTop: p?.isTop ?? false,
          isEssence: p?.isEssence ?? false
        };
      }
    },
    mounted() {
      // 分类状态以当前页面为准，避免 store 里残留上次的分类筛选
      this.state.activeCategory = 'all';
      this.community.setShareType('');
      this.loadPosts();
      this.loadStats();
      this.loadMyPosts();
      this.state._visibilityHandler = () => {
        if (document.visibilityState === 'visible') this.refreshSilently();
      };
      this.state._refreshTimer = setInterval(() => this.refreshSilently(), 15000);
      window.addEventListener('focus', this.state._visibilityHandler);
      document.addEventListener('visibilitychange', this.state._visibilityHandler);
    },
    beforeUnmount() {
      if (this.state._refreshTimer) {
        clearInterval(this.state._refreshTimer);
        this.state._refreshTimer = null;
      }
      if (this.state._visibilityHandler) {
        window.removeEventListener('focus', this.state._visibilityHandler);
        document.removeEventListener('visibilitychange', this.state._visibilityHandler);
        this.state._visibilityHandler = null;
      }
    }
  })
</script>
<style lang="css" scoped>
  .forum-page {
    min-height: 100vh;
    background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    /* 全局字体统一 15px */
    font-size: 15px;
  }
  .forum-main {
    max-width: 1300px;
    margin: 0 auto;
    padding: 24px 32px 40px;
  }
  .forum-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
  }
  .forum-header h2 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 22px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0;
  }
  .post-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 12px 24px;
    border: none;
    border-radius: 12px;
    background: linear-gradient(135deg, #c41e3a, #e8384f);
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s;
    box-shadow: 0 2px 12px rgba(196, 30, 58, 0.3);
  }
  .post-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 18px rgba(196, 30, 58, 0.4);
  }
  .forum-body {
    display: grid;
    grid-template-columns: 1fr 300px;
    gap: 24px;
  }
  .forum-left {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  }
  .category-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 14px;
  }
  .category-chip {
    border: 1px solid #e4e8f0;
    background: #f7f9fc;
    color: #4a5578;
    font-size: 13px;
    padding: 6px 14px;
    border-radius: 999px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .category-chip:hover {
    border-color: #c41e3a;
    color: #c41e3a;
  }
  .category-chip.active {
    background: #c41e3a;
    border-color: #c41e3a;
    color: #ffffff;
  }
  .post-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .post-item {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding: 16px;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.3s;
    border: 1px solid transparent;
  }
  .post-item:hover {
    background: #f8f9fc;
    border-color: #e8eaf0;
  }
  .post-avatar {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, #eef2ff, #e0e7ff);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    cursor: pointer;
    overflow: hidden;
    transition: all 0.2s;
  }
  .post-avatar:hover {
    box-shadow: 0 0 0 2px #c41e3a;
  }
  .avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 12px;
  }
  .avatar-text {
    font-size: 18px;
    font-weight: 700;
    color: #1a2b5f;
  }
  .post-content {
    flex: 1;
    min-width: 0;
  }
  .post-title {
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .detail-title {
    font-size: 20px;
    font-weight: 700;
    margin: 14px 0 8px;
  }
  .post-color-row,
  .post-image-upload,
  .comment-image-upload {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 10px 0;
  }
  .post-color-label {
    font-size: 13px;
    color: #6b7896;
    white-space: nowrap;
  }
  .post-image-upload {
    align-items: flex-start;
  }
  .post-excerpt {
    font-size: 15px;
    color: #5a6488;
    margin: 0 0 8px;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .post-attachments {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 8px;
  }
  .attachment-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: 8px;
    background: #f0f4ff;
    color: #1a2b5f;
    font-size: 15px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .attachment-chip:hover {
    background: #e0e7ff;
  }
  .post-meta {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 15px;
    color: #8a8faa;
    flex-wrap: wrap;
  }
  .meta-author {
    color: #1a2b5f;
    font-weight: 600;
    cursor: pointer;
  }
  .meta-author:hover {
    text-decoration: underline;
  }
  .meta-dot {
    color: #d1d5db;
  }
  .meta-likes,
  .meta-comments {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    cursor: pointer;
    transition: color 0.2s;
  }
  .meta-likes:hover {
    color: #c41e3a;
  }
  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #f0f2f5;
  }
  .pagination button {
    padding: 6px 16px;
    border: 1px solid #e8eaf0;
    border-radius: 8px;
    background: #ffffff;
    cursor: pointer;
    font-size: 15px;
    color: #1a2b5f;
    transition: all 0.2s;
  }
  .pagination button:hover:not(:disabled) {
    background: #f0f2f5;
  }
  .pagination button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .page-info {
    font-size: 15px;
    color: #5a6488;
  }
  .empty-tip {
    text-align: center;
    color: #8a8faa;
    padding: 60px 0;
    font-size: 15px;
  }
  .empty-tip-mini {
    text-align: center;
    color: #8a8faa;
    padding: 12px 0;
    font-size: 15px;
  }
  .forum-right {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .right-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 10px rgba(26, 43, 95, 0.04);
  }
  .right-card h4 {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 14px;
  }
  .hot-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    border-bottom: 1px solid #f8f9fc;
    cursor: pointer;
    font-size: 15px;
    transition: all 0.2s;
  }
  .hot-item:hover {
    background: #f8f9fc;
    border-radius: 8px;
    padding-left: 8px;
  }
  .hot-rank {
    width: 20px;
    height: 20px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
    flex-shrink: 0;
  }
  .hot-rank.rank-1 {
    background: #ef4444;
  }
  .hot-rank.rank-2 {
    background: #f97316;
  }
  .hot-rank.rank-3 {
    background: #f59e0b;
  }
  .hot-rank.rank-4,
  .hot-rank.rank-5 {
    background: #94a3b8;
  }
  .hot-title {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #1a2b5f;
  }
  .hot-replies {
    font-size: 13px;
    color: #8a8faa;
    flex-shrink: 0;
  }
  .stats-grid {
    display: flex;
    justify-content: space-around;
  }
  .stats-item {
    text-align: center;
  }
  .stats-number {
    display: block;
    font-size: 22px;
    font-weight: 900;
    color: #1a2b5f;
    font-family: 'DIN Alternate', sans-serif;
  }
  .stats-label {
    font-size: 15px;
    color: #8a8faa;
  }
  /* Modal */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
  }
  .modal-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 28px;
    width: 560px;
    max-width: 90vw;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  }
  .modal-card h3 {
    font-size: 18px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0 0 20px;
  }
  .modal-input,
  .modal-textarea,
  .modal-select {
    width: 100%;
    padding: 12px;
    border: 1px solid #e8eaf0;
    border-radius: 10px;
    font-size: 15px;
    margin-bottom: 14px;
    outline: none;
    color: #1a2b5f;
    box-sizing: border-box;
  }
  .modal-textarea {
    resize: vertical;
    min-height: 120px;
  }
  .upload-area {
    margin-bottom: 14px;
  }
  .upload-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 16px;
    border: 1px dashed #1a2b5f;
    border-radius: 10px;
    background: #f8f9fc;
    color: #1a2b5f;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .upload-btn:hover {
    background: #f0f4ff;
    border-color: #c41e3a;
    color: #c41e3a;
  }
  .file-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    margin-top: 8px;
    border-radius: 8px;
    background: #f0f4ff;
    color: #1a2b5f;
    font-size: 15px;
  }
  .file-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .file-size {
    color: #8a8faa;
    font-size: 13px;
  }
  .file-remove {
    color: #c41e3a;
    cursor: pointer;
    font-weight: 700;
    padding: 0 4px;
  }
  .file-remove:hover {
    color: #e8384f;
  }
  .modal-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 8px;
  }
  .cancel-btn {
    padding: 10px 20px;
    border: 1px solid #e8eaf0;
    border-radius: 10px;
    background: #ffffff;
    font-size: 15px;
    font-weight: 600;
    color: #5a6488;
    cursor: pointer;
  }
  .confirm-btn {
    padding: 10px 20px;
    border: none;
    border-radius: 10px;
    background: linear-gradient(135deg, #1a2b5f, #1e3470);
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
  }
  .confirm-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  /* 用户公开信息弹窗 */
  .profile-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 32px;
    width: 400px;
    max-width: 90vw;
    text-align: center;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  }
  .profile-avatar-wrap {
    width: 80px;
    height: 80px;
    margin: 0 auto 16px;
    border-radius: 50%;
    background: linear-gradient(135deg, #eef2ff, #e0e7ff);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }
  .profile-avatar {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 50%;
  }
  .profile-avatar-text {
    font-size: 32px;
    font-weight: 700;
    color: #1a2b5f;
  }
  .profile-card h3 {
    font-size: 18px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0 0 8px;
  }
  .profile-info {
    font-size: 15px;
    color: #5a6488;
    margin: 4px 0;
  }
  .profile-joined {
    font-size: 13px;
    color: #8a8faa;
    margin: 8px 0 16px;
  }
  .profile-stats {
    display: flex;
    justify-content: space-around;
    padding: 16px 0;
    border-top: 1px solid #f0f2f5;
    border-bottom: 1px solid #f0f2f5;
    margin-bottom: 16px;
  }
  .profile-stat-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .profile-stat-item strong {
    font-size: 22px;
    font-weight: 900;
    color: #c41e3a;
  }
  .profile-stat-item span {
    font-size: 15px;
    color: #8a8faa;
  }
  .profile-close-btn {
    padding: 8px 24px;
    border: 1px solid #e8eaf0;
    border-radius: 8px;
    background: #ffffff;
    font-size: 15px;
    color: #5a6488;
    cursor: pointer;
  }
  .profile-close-btn:hover {
    background: #f0f2f5;
  }
  /* === 帖子详情 Modal === */
  .post-detail-card {
    width: 680px;
    max-width: 95vw;
    max-height: 85vh;
    overflow-y: auto;
  }
  .detail-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }
  .detail-header h3 {
    font-size: 20px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0;
    flex: 1;
    min-width: 0;
  }
  .badge {
    font-size: 12px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    flex-shrink: 0;
  }
  .badge-top {
    background: #c41e3a;
    color: #ffffff;
  }
  .badge-essence {
    background: #f59e0b;
    color: #ffffff;
  }
  .detail-author {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f0f2f5;
  }
  .author-info {
    flex: 1;
  }
  .author-name {
    display: block;
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
    cursor: pointer;
  }
  .author-name:hover {
    text-decoration: underline;
  }
  .author-time {
    font-size: 13px;
    color: #8a8faa;
  }
  .delete-post-btn {
    padding: 4px 12px;
    border: 1px solid #e8eaf0;
    border-radius: 6px;
    background: #ffffff;
    font-size: 13px;
    color: #c41e3a;
    cursor: pointer;
    transition: all 0.2s;
  }
  .delete-post-btn:hover {
    background: #fef2f2;
    border-color: #c41e3a;
  }
  .detail-content {
    font-size: 15px;
    line-height: 1.8;
    color: #1a2b5f;
    margin-bottom: 16px;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .detail-attachments {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f0f2f5;
  }
  .detail-stats {
    display: flex;
    align-items: center;
    gap: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f0f2f5;
  }
  .stat-action {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    font-size: 14px;
    color: #8a8faa;
    transition: color 0.2s;
  }
  .stat-action:hover {
    color: #c41e3a;
  }
  .stat-label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 14px;
    color: #8a8faa;
  }
  /* === 评论区 === */
  .comment-section {
    margin-top: 16px;
  }
  .comment-section h4 {
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 12px;
  }
  .comment-list {
    display: flex;
    flex-direction: column;
    gap: 0;
  }
  .comment-item {
    padding: 10px 0;
    border-bottom: 1px solid #f8f9fc;
  }
  .comment-item.child {
    margin-left: 40px;
    border-left: 2px solid #e8eaf0;
    padding-left: 12px;
    border-bottom: none;
    padding-top: 8px;
    padding-bottom: 4px;
  }
  .comment-main {
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }
  .comment-avatar {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: linear-gradient(135deg, #eef2ff, #e0e7ff);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    cursor: pointer;
    overflow: hidden;
    transition: all 0.2s;
  }
  .comment-avatar:hover {
    box-shadow: 0 0 0 2px #c41e3a;
  }
  .avatar-img-sm {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 8px;
  }
  .avatar-text-sm {
    font-size: 14px;
    font-weight: 700;
    color: #1a2b5f;
  }
  .comment-body {
    flex: 1;
    min-width: 0;
  }
  .comment-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
  }
  .comment-author {
    font-size: 13px;
    font-weight: 600;
    color: #1a2b5f;
    cursor: pointer;
  }
  .comment-author:hover {
    text-decoration: underline;
  }
  .comment-time {
    font-size: 12px;
    color: #8a8faa;
  }
  .comment-text {
    font-size: 15px;
    color: #1a2b5f;
    line-height: 1.5;
    word-break: break-word;
    margin-bottom: 6px;
  }
  .comment-actions {
    display: flex;
    gap: 12px;
  }
  .comment-action {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 13px;
    color: #8a8faa;
    cursor: pointer;
    transition: color 0.2s;
  }
  .comment-reply:hover {
    color: #1a2b5f;
  }
  .comment-children {
    margin-top: 4px;
  }
  .comment-input-area {
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid #f0f2f5;
    position: relative;
  }
  .comment-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }
  .emoji-btn {
    border: 1px solid #e4e8f0;
    background: #f7f9fc;
    border-radius: 8px;
    width: 34px;
    height: 34px;
    font-size: 18px;
    line-height: 1;
    cursor: pointer;
    transition: all 0.2s;
  }
  .emoji-btn:hover {
    border-color: #c41e3a;
    background: #fff5f6;
  }
  .comment-toolbar-tip {
    font-size: 12px;
    color: #8a8faa;
  }
  .comment-picker {
    position: relative;
    z-index: 20;
  }
  .reply-hint {
    background: #f0f4ff;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 13px;
    color: #1a2b5f;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .cancel-reply {
    color: #c41e3a;
    cursor: pointer;
    font-weight: 700;
    font-size: 16px;
  }
  .cancel-reply:hover {
    color: #e8384f;
  }
  /* === 我的帖子 === */
  .my-post-list {
    display: flex;
    flex-direction: column;
  }
  .my-post-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #f8f9fc;
    cursor: pointer;
    transition: background 0.2s;
    gap: 8px;
  }
  .my-post-item:hover {
    background: #f8f9fc;
    margin: 0 -8px;
    padding-left: 8px;
    padding-right: 8px;
    border-radius: 6px;
  }
  .my-post-title {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 14px;
    color: #1a2b5f;
  }
  .my-post-stats {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }
  .my-stat {
    font-size: 12px;
    color: #8a8faa;
  }
  .my-posts-view-all {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #f0f2f5;
    text-align: center;
    font-size: 13px;
    color: #c41e3a;
    cursor: pointer;
    font-weight: 600;
    transition: color 0.2s;
  }
  .my-posts-view-all:hover {
    color: #e8384f;
  }
  .my-posts-full-list {
    display: flex;
    flex-direction: column;
    max-height: 50vh;
    overflow-y: auto;
  }
  .my-posts-full-list .my-post-item {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .my-post-date {
    font-size: 12px;
    color: #8a8faa;
    flex-shrink: 0;
    white-space: nowrap;
  }
</style>
