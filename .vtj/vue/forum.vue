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
        <div class="forum-search-bar in-header">
        <input
        v-model="state.searchKeyword"
        class="search-input"
        placeholder="搜索帖子标题或内容…"
        @keyup.enter="applySearch" />
        <input v-model="state.searchDateFrom" type="date" class="search-date" title="开始日期" />
        <span class="search-tilde">~</span>
        <input v-model="state.searchDateTo" type="date" class="search-date" title="结束日期" />
        <button class="search-btn" @click="applySearch">搜索</button>
        <button class="search-reset" @click="resetSearch">重置</button>
        </div>

        <!-- 校园 / 班级论坛筛选（2026-11-03）：作用域 ALL=校园、CLASSES=班级 -->
        <div class="scope-filter" role="group" aria-label="论坛范围筛选">
          <button
            v-for="opt in scopeOptions"
            :key="opt.key"
            :class="['scope-chip', { on: state.scopeFilter === opt.key }]"
            @click="selectScope(opt.key)">{{ opt.label }}</button>
        </div>

        <div class="forum-header-actions">
          <button class="post-btn ghost star-only" title="我的收藏 / 我的喜欢" @click="openFavorites('favorites')">
            <XIcon :icon="Star" :size="18" color="#c41e3a"></XIcon>
          </button>
          <button class="post-btn" @click="openNewPost">
            <XIcon :icon="EditPen" :size="16" color="#ffffff"></XIcon>
            <span> 发布新帖</span>
          </button>
        </div>
      </div>
      <div class="forum-body">
        <div class="forum-left">
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
                <div class="post-author-line" @click.stop="viewUser(post.userId)">
                  <span class="meta-author">{{ post.author }}</span>
                  <span class="meta-dot"> ·</span>
                  <span class="meta-date">{{ post.date }}</span>
                </div>
                <h4 class="post-title" :style="{ color: titleColorValue(post.titleColor) }">{{ post.title }}</h4>
                <p class="post-excerpt"><ForumContent :content="post.content" :format="post.contentFormat" /></p>
                <AttachmentList
                  v-if="post.attachments && post.attachments.length"
                  :attachments="post.attachments"
                  mode="post" />

                <div class="post-meta">
                  <span class="meta-likes" @click.stop="toggleHeart(post)" title="喜欢">
                    <span class="heart-icon" :class="{ active: post.liked }">{{ post.liked ? '❤' : '♡' }}</span>
                    <span> {{ post.likeCount }}</span>
                  </span>
                  <span class="meta-dot"> ·</span>
                  <span class="meta-favs" @click.stop="toggleFavorite(post)" title="收藏">
                    <XIcon
                      :icon="post.favorited ? StarFilled : Star"
                      :size="13"
                      :color="post.favorited ? '#f59e0b' : '#8a8faa'"></XIcon>
                    <span> {{ post.favoriteCount }}</span>
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
              <span> 今日热门（{{ state.hotIsWeek ? '近 7 天' : '当天' }}）</span>
            </h4>
            <div
              v-for="(hot, index) in hotPosts"
              :key="hot.id"
              class="hot-item"
              @click="viewPost(hot)">
              <span class="hot-rank" :class="'rank-' + hot.rank">{{ hot.rank }}</span>
              <span class="hot-main">
                <span class="hot-title">{{ hot.title }}</span>
                <!-- 2026-11-03：列表只显示标题已不够用，补 2 行正文摘要（后端已带 200 字 content） -->
                <span class="list-excerpt">{{ excerptOf(hot) }}</span>
              </span>
              <span class="hot-replies">
                <span> {{ hot.commentCount }} </span>
                <span> 回复</span>
              </span>
            </div>
            <div v-if="!hotPosts.length" class="empty-tip-mini">暂无热门</div>
            <div v-if="hotPosts.length" class="my-posts-view-all" @click="openHotAll">
              查看更多 →
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
      <!-- 发帖弹窗：与教师端/管理员端共用 PostComposer（含可见范围、附件、草稿）
           注：本页为 raw 页，模板改动经用户明确授权（2026-11-02），改前已备份
           forum.vue.bak_20261102_p2composer -->
      <PostComposer
        v-model:visible="state.showNewPost"
        title="发布新帖"
        :initial="state.postDraftInitial"
        :classes="state.myClasses"
        :submitting="state.submitting"
        :saving-draft="state.savingDraft"
        @submit="submitPostFromComposer"
        @save-draft="savePostDraft"
      />
      <!-- 我的收藏 / 我的喜欢（P2 为空态外壳，列表数据在 P3 接入） -->
      <div
        v-if="state.showFavorites"
        class="modal-overlay modal-l1"
        @click.self="closeFavorites">
        <div class="modal-card fav-modal">
          <h3>{{ state.favoriteTab === 'favorites' ? '我的收藏' : '我的喜欢' }}</h3>
          <div class="fav-tabs">
            <button
              :class="['fav-tab', { active: state.favoriteTab === 'favorites' }]"
              @click="switchFavoritesTab('favorites')">
              我的收藏
            </button>
            <button
              :class="['fav-tab', { active: state.favoriteTab === 'likes' }]"
              @click="switchFavoritesTab('likes')">
              我的喜欢
            </button>
          </div>
          <div v-if="state.favoriteLoading" class="fav-empty">加载中...</div>
          <div v-else-if="!state.favoriteList.length" class="fav-empty">
            {{ state.favoriteTab === 'favorites' ? '还没有收藏的帖子' : '还没有喜欢的帖子' }}
          </div>
          <div v-else class="fav-list">
            <div
              v-for="fp in state.favoriteList"
              :key="fp.id"
              class="fav-item"
              @click="openPostDetail(fp)">
              <span class="fav-item-title" :style="{ color: titleColorValue(fp.titleColor) }">{{ fp.title }}</span>
              <!-- 2026-11-03：补正文摘要，避免「只有标题、看不到内容」 -->
              <span class="list-excerpt">{{ excerptOf(fp) }}</span>
              <span class="fav-item-meta">
                <span class="heart-icon" :class="{ active: fp.liked }">{{ fp.liked ? '❤' : '♡' }}</span>
                <span>{{ fp.likeCount }}</span>
                <span class="fav-sep">·</span>
                <XIcon
                  :icon="StarFilled"
                  :size="12"
                  color="#f59e0b"></XIcon>
                <span>{{ fp.favoriteCount }}</span>
              </span>
            </div>
          </div>
          <div class="modal-actions">
            <button class="cancel-btn" @click="closeFavorites">关闭</button>
          </div>
        </div>
      </div>
      <div
        v-if="state.showUserProfile"
        class="modal-overlay modal-l3"
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
        class="modal-overlay modal-l2"
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
            <div class="detail-content"><ForumContent :content="state.currentPost.content" :format="state.currentPost.contentFormat" /></div>
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
                      <div class="comment-text"><ForumContent :content="comment.content" :format="comment.contentFormat" /></div>
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
                          <div class="comment-text"><ForumContent :content="child.content" :format="child.contentFormat" /></div>
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
      <!-- 热门帖子前 100 条 Modal -->
      <div v-if="state.showHotAll" class="modal-overlay modal-l1" @click.self="closeHotAll">
        <div class="modal-card post-detail-card">
          <h3>热门帖子 · 前 100 条</h3>
          <div class="hot-range">
            <input v-model="state.hotFrom" type="date" />
            <span>~</span>
            <input v-model="state.hotTo" type="date" />
            <button @click="openHotAll">查询</button>
          </div>
          <div v-if="state.hotAllLoading" class="empty-tip-mini">加载中...</div>
          <div v-else-if="!state.hotAll.length" class="empty-tip-mini">暂无热门</div>
          <div v-else class="my-posts-full-list">
            <div
              v-for="hp in state.hotAll"
              :key="hp.id"
              class="my-post-item"
              @click="viewPost(hp)">
              <span class="hot-rank" :class="'rank-' + (hp.rank <= 3 ? hp.rank : '')">{{ hp.rank }}</span>
              <span class="my-post-title">{{ hp.title }}</span>
              <span class="my-post-stats">
                <span class="my-stat">❤️ {{ hp.likeCount }}</span>
                <span class="my-stat">💬 {{ hp.commentCount }}</span>
              </span>
            </div>
          </div>
          <div class="modal-actions">
            <button @click="closeHotAll">关闭</button>
          </div>
        </div>
      </div>

      <!-- 我的帖子完整列表 Modal -->
      <div
        v-if="state.showMyPosts"
        class="modal-overlay modal-l1"
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
              <!-- 2026-11-03：补正文摘要，避免「只有标题、看不到内容」 -->
              <span class="list-excerpt">{{ excerptOf(mp) }}</span>
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
  // P3：收藏（五角星）/ 我的喜欢（爱心）
  import {
    toggleForumFavorite,
    fetchMyForumFavorites,
    fetchMyForumLikes,
    fetchForumPosts
  } from '@/modules/community/api';
  import EmojiStickerPicker from '@/components/forum/EmojiStickerPicker.vue';
  import ForumContent from '@/components/forum/ForumContent.vue';
  import ImageGrid from '@/components/forum/ImageGrid.vue';
  import ImageUploader from '@/components/forum/ImageUploader.vue';
  import FileUploader from '@/components/forum/FileUploader.vue';
  import PostComposer from '@/components/forum/PostComposer.vue';
  import { fetchMyForumDraft, saveMyForumDraft } from '@/modules/community/api';
  import { loadMyClasses } from '@/modules/community/classScope';
  import AttachmentList from '@/components/forum/AttachmentList.vue';
  import CommentSortBar from '@/components/forum/CommentSortBar.vue';
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
      PostComposer,
      AttachmentList,
      CommentSortBar,
      UserBadge
    },
    setup(props) {
      const provider = useProvider({ id: 'forum', version: '1785094400000' });
      const community = useCommunityStore();
      const state = reactive({
        page: 1,
        pageSize: 8,
        activeCategory: 'all',
        /** 校园/班级论坛筛选：'' 全部 / 'ALL' 校园 / 'CLASSES' 班级（2026-11-03） */
        scopeFilter: '' as '' | 'ALL' | 'CLASSES',
        // P3：搜索与日期筛选
        searchKeyword: '',
        searchDateFrom: '',
        searchDateTo: '',
        showCommentPicker: false,
        posts: [] as any[],
        total: 0,
        loading: false,
        submitting: false,
        showNewPost: false,
        showUserProfile: false,
        userProfile: {} as any,
        savingDraft: false,
        postDraftInitial: null as any,
        myClasses: [] as string[],
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
        // 今日热门
        hotToday: [],
        hotIsWeek: false,
        hotFrom: new Date().toISOString().slice(0, 10),
        hotTo: new Date().toISOString().slice(0, 10),
        // 热门帖子「查看更多」
        hotAll: [],
        showHotAll: false,
        hotAllLoading: false,
        showMyPosts: false,
        // === 我的收藏 / 我的喜欢（P2 仅外壳，数据 P3 接入）===
        showFavorites: false,
        favoriteTab: 'favorites' as 'favorites' | 'likes',
        favoriteList: [] as any[],
        favoriteTotal: 0,
        favoriteLoading: false,
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
      /**
       * 列表正文摘要（2026-11-03）：收藏/喜欢/热门/我的帖子 这些弹窗此前只显示标题，
       * 用户看不到任何正文。后端 `_serialize_post` 已带 200 字 content，这里只需截断展示。
       * - 去掉表情包占位符 [[sticker:url]]，否则列表里会出现一长串 URL
       * - 压平空白，避免换行把两行摘要撑成一行空行
       */
      const excerptOf = (post: any): string => {
        const raw = String(post?.content ?? post?.excerpt ?? '');
        const text = raw
          // 富文本正文先去掉标签再截断，否则列表里会出现 <p style=...>
          .replace(/<[^>]+>/g, ' ')
          .replace(/\[\[sticker:[^\]]+\]\]/g, ' ')
          .replace(/\s+/g, ' ')
          .trim();
        if (!text) return '（无正文）';
        return text.length > 120 ? `${text.slice(0, 120)}…` : text;
      };
      return {
        state,
        props,
        provider,
        community,
        excerptOf,
        // 校园 / 班级论坛筛选项（2026-11-03）
        scopeOptions: [
          { key: '', label: '全部' },
          { key: 'ALL', label: '校园论坛' },
          { key: 'CLASSES', label: '班级论坛' }
        ],
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
      /** 今日热门：只取当天按点赞量前 5（B 方案：当天无帖则为空） */
      hotPosts(): any[] {
        return (this.state.hotToday || []).slice(0, 5).map((p: any, i: number) => ({
          ...p,
          rank: i + 1
        }));
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
      /** 搜索：关键词 + 日期区间（复用 GET /api/forum/posts 的 keyword/date_from/date_to） */
      async applySearch() {
        this.state.loading = true;
        try {
          const res: any = await fetchForumPosts({
            limit: this.state.pageSize,
            offset: (this.state.page - 1) * this.state.pageSize,
            shareType: toShareTypeParam(this.state.activeCategory),
            keyword: this.state.searchKeyword || undefined,
            dateFrom: this.state.searchDateFrom || undefined,
            dateTo: this.state.searchDateTo || undefined
          });
          this.state.posts = (res.posts || []).map((p: any) => this._mapPost(p));
          this.state.total = res.total || 0;
        } catch (e) {
          this._safeMsg('error', '搜索失败，请稍后重试');
        } finally {
          this.state.loading = false;
        }
      },
      resetSearch() {
        this.state.searchKeyword = '';
        this.state.searchDateFrom = '';
        this.state.searchDateTo = '';
        this.state.page = 1;
        this.loadPosts();
      },
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
      /** 校园 / 班级 论坛筛选：先写进 store 再重拉第一页（2026-11-03） */
      async selectScope(key: '' | 'ALL' | 'CLASSES') {
        if (this.state.scopeFilter === key) return;
        this.state.scopeFilter = key;
        this.state.page = 1;
        this.community.setVisibilityFilter(key);
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
        // 2026-10-31：标题 / 正文 / 附件(图片或文件) 至少一项即可发布
        const np: any = this.state.newPost;
        const hasAtt = (np.images?.length || 0) + (np.attachments?.length || 0) > 0;
        if (!np.title.trim() && !np.content.trim() && !hasAtt) {
          ElMessage.warning('标题、正文、附件至少填写一项');
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
        // 班级候选的事实来源是 /api/auth/profile（JWT 里没有班级字段）。
        // 2026-11-03 修正：此前读 auth.parseUserInfo().className 恒为空，
        // 导致「仅指定班级」显示「当前账号没有可选班级」。
        this.state.myClasses = [];
        this.state.postDraftInitial = null;
        this.state.showNewPost = true;
        loadMyClasses()
          .then((scope) => {
            this.state.myClasses = scope.classes;
          })
          .catch(() => {
            this.state.myClasses = [];
          });
        fetchMyForumDraft()
          .then((draft) => {
            if (!draft) return;
            this.state.postDraftInitial = {
              title: draft.title,
              content: draft.content,
              attachments: draft.attachments,
              visibility: draft.visibility,
              visibleClasses: draft.visibleClasses,
              isTop: false
            };
            ElMessage.info('已载入上次保存的草稿');
          })
          .catch(() => {
            /* 草稿读取失败不阻塞发帖 */
          });
      },
      async submitPostFromComposer(payload: any) {
        const hasAtt = (payload.attachments || []).length > 0;
        if (!payload.title && !payload.content && !hasAtt) {
          ElMessage.warning('标题、正文、附件至少填写一项');
          return;
        }
        this.state.submitting = true;
        try {
          const created = await this.community.createPost({
            title: payload.title,
            content: payload.content,
            shareType: 'EXPERIENCE',
            attachments: payload.attachments,
            visibility: payload.visibility,
            visibleClasses: payload.visibleClasses,
            contentFormat: payload.contentFormat
          });
          if (!created) return;
          this.state.posts.unshift(this._mapPost(created));
          this.state.total += 1;
          this.state.myPosts.unshift(this._mapPost(created, false));
          this.state.myPostsTotal = (this.state.myPostsTotal || 0) + 1;
          this.state.showNewPost = false;
          this.state.postDraftInitial = null;
          ElMessage.success('发布成功!');
        } catch (e) {
          this._safeMsg('error', this.community.error || '发布失败,请稍后重试');
        } finally {
          this.state.submitting = false;
        }
      },
      async savePostDraft(payload: any) {
        this.state.savingDraft = true;
        try {
          await saveMyForumDraft({
            title: payload.title,
            content: payload.content,
            attachments: payload.attachments,
            visibility: payload.visibility,
            visible_classes: payload.visibleClasses,
            is_top: false
          });
          ElMessage.success('已保存到草稿箱');
        } catch (e) {
          this._safeMsg('error', '保存草稿失败');
        } finally {
          this.state.savingDraft = false;
        }
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
      openFavorites(tab?: 'favorites' | 'likes') {
        this.state.favoriteTab = tab || 'favorites';
        this.state.showFavorites = true;
        this.loadFavoriteTab();
      },
      closeFavorites() {
        this.state.showFavorites = false;
      },
      switchFavoritesTab(tab: 'favorites' | 'likes') {
        this.state.favoriteTab = tab;
        this.loadFavoriteTab();
      },
      async loadFavoriteTab() {
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) {
          this.state.favoriteList = [];
          this.state.favoriteTotal = 0;
          return;
        }
        this.state.favoriteLoading = true;
        try {
          const isFav = this.state.favoriteTab === 'favorites';
          const res = isFav
            ? await fetchMyForumFavorites(20, 0)
            : await fetchMyForumLikes(20, 0);
          const list = (res && res.posts) || [];
          this.state.favoriteList = list.map((p: any) => this._mapPost(p));
          this.state.favoriteTotal = (res && res.total) || list.length;
        } catch (e) {
          this.state.favoriteList = [];
          this.state.favoriteTotal = 0;
        } finally {
          this.state.favoriteLoading = false;
        }
      },
      /** 爱心：喜欢（复用点赞接口，reaction 固定 like） */
      toggleHeart(post: any) {
        return this.toggleLike(post);
      },
      /** 五角星：收藏 */
      async toggleFavorite(post: any) {
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn()) {
          ElMessage.warning('请先登录后收藏');
          return;
        }
        try {
          const res = await toggleForumFavorite(post.id);
          if (res) {
            post.favorited = res.favorited;
            post.favoriteCount = res.favoriteCount;
          }
        } catch (e) {
          /* 静默 */
        }
      },
      /** 热门帖子查看更多：按点赞量取前 100 条 */
      /** 拉今日热门（标题卡片） */
      async loadHotToday() {
        const today = new Date().toISOString().slice(0, 10);
        const weekAgo = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10);
        try {
          const res: any = await fetchForumPosts({
            sortBy: 'likes', order: 'desc', dateFrom: today, dateTo: today, limit: 5
          });
          let list = (res.posts || []).map((p: any) => this._mapPost(p));
          this.state.hotIsWeek = false;
          if (list.length < 5) {
            const week: any = await fetchForumPosts({
              sortBy: 'likes', order: 'desc', dateFrom: weekAgo, dateTo: today, limit: 5
            });
            const merged = [...list];
            for (const item of (week.posts || [])) {
              if (merged.length >= 5) break;
              if (!merged.some((x: any) => x.id === item.id)) merged.push(this._mapPost(item));
            }
            list = merged;
            this.state.hotIsWeek = list.length > 0;
          }
          this.state.hotToday = list.slice(0, 5);
        } catch (e) {
          this.state.hotToday = [];
        }
      },

      async openHotAll() {
        this.state.showHotAll = true;
        this.state.hotAllLoading = true;
        try {
          const res: any = await fetchForumPosts({
            sortBy: 'likes',
            order: 'desc',
            dateFrom: this.state.hotFrom || undefined,
            dateTo: this.state.hotTo || undefined,
            limit: 100
          });
          this.state.hotAll = (res.posts || []).map((p: any, i: number) => ({
            ...this._mapPost(p),
            rank: i + 1
          }));
        } catch (e) {
          this.state.hotAll = [];
        } finally {
          this.state.hotAllLoading = false;
        }
      },
      closeHotAll() {
        this.state.showHotAll = false;
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
          // 正文格式（2026-11-03）：后端下发 TEXT/HTML，渲染时据此选纯文本还是富文本
          contentFormat: p?.contentFormat === 'HTML' ? 'HTML' : 'TEXT',
          author: (p?.user && p.user.nickname) || '匿名',
          avatar: (p?.user && p.user.avatar) || '',
          date: this.formatTime(p?.createTime),
          // 只用数字：原先用 formatReactionSummary 会显示 "👍1"，与爱心图标重复
          likeCount: total,
          reactionTotal: total,
          reactions,
          myReaction: p?.myReaction ?? null,
          commentCount: p?.commentCount ?? 0,
          viewCount: p?.viewCount ?? 0,
          liked: p?.liked ?? false,
          // P3：收藏（五角星）状态与计数
          favorited: p?.favorited ?? false,
          favoriteCount: p?.favoriteCount ?? 0,
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
      },
      /**
       * 关闭「最上层」的弹窗（2026-11-03）。
       * 顺序必须从高到低：用户卡片(3) → 帖子详情(2) → 我的帖子/热门/收藏(1) → 发帖弹窗。
       * 为什么要有：二三级弹窗叠在一级之上时，Esc/遮罩只应关掉最上层那一个，
       * 否则用户按一次就把三层全关了，或者反过来关了底层留着顶层。
       */
      closeTopModal() {
        if (this.state.showUserProfile) {
          this.state.showUserProfile = false;
          return;
        }
        if (this.state.showPostDetail) {
          this.closePostDetail();
          return;
        }
        if (this.state.showMyPosts) {
          this.closeMyPosts();
          return;
        }
        if (this.state.showHotAll) {
          this.closeHotAll();
          return;
        }
        if (this.state.showFavorites) {
          this.closeFavorites();
          return;
        }
        if (this.state.showNewPost) {
          this.state.showNewPost = false;
        }
      }
    },
    mounted() {
      // 分类状态以当前页面为准，避免 store 里残留上次的分类筛选
      this.state.activeCategory = 'all';
      this.community.setShareType('');
      this.loadPosts();
      this.loadHotToday();
      this.loadStats();
      this.loadMyPosts();
      this.state._visibilityHandler = () => {
        if (document.visibilityState === 'visible') this.refreshSilently();
      };
      this.state._refreshTimer = setInterval(() => this.refreshSilently(), 15000);
      window.addEventListener('focus', this.state._visibilityHandler);
      document.addEventListener('visibilitychange', this.state._visibilityHandler);
      // Esc 只关最上层弹窗（层级见 closeTopModal 注释）
      this.state._escHandler = (e) => {
        if (e.key === 'Escape') this.closeTopModal();
      };
      window.addEventListener('keydown', this.state._escHandler);
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
      if (this.state._escHandler) {
        window.removeEventListener('keydown', this.state._escHandler);
        this.state._escHandler = null;
      }
    }
  })
</script>
<style lang="css" scoped>
  /* 弹窗层级（2026-11-03）：一级列表弹窗 < 二级帖子详情 < 三级用户卡片。
   * 背景：此前收藏/热门/我的（一级）与帖子详情（二级）共用 z-index:2000，
   * 同层里谁后插入谁在上，导致二级被一级盖住、必须先关一级才能看到详情。 */
  .modal-overlay.modal-l1 { z-index: 2000; }
  .modal-overlay.modal-l2 { z-index: 2200; }
  .modal-overlay.modal-l3 { z-index: 2400; }

  .forum-page {
    /* 自己成为滚动容器：VTJ 外壳存在 overflow 祖先，sticky 绑不到视口 */
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    /* 全局字体统一 15px */
    font-size: 15px;
  }
  .forum-main {
    max-width: 1300px;
    margin: 0 auto;
    padding: 0 32px 40px;
    width: 100%;
    flex: 1;
    overflow-y: auto;
    overscroll-behavior: contain;
  }
  .forum-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
    /* 滚动容器是 .forum-main，这里贴其顶部常驻 */
    position: sticky;
    top: 0;
    z-index: 20;
    padding: 12px 0;
    background: #f8f9fc;
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
  /* P2：我的收藏 / 我的喜欢。几何尺寸完全继承 .post-btn（不改 padding/border/字体），
     仅用 inset box-shadow 画描边，保证三个按钮同高同宽 */
  .forum-header-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .post-btn.ghost {
    background: #ffffff;
    color: #c41e3a;
    box-shadow: inset 0 0 0 1px #f0c4cc;
  }
  .post-btn.ghost:hover {
    background: #fff5f7;
    box-shadow: inset 0 0 0 1px #f0c4cc, 0 4px 12px rgba(196, 30, 58, 0.12);
  }
  .fav-tabs {
    display: flex;
    gap: 8px;
    margin: 12px 0 16px;
  }
  .fav-tab {
    padding: 8px 16px;
    border-radius: 999px;
    border: 1px solid #e3e8ef;
    background: #ffffff;
    color: #475569;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
  }
  .fav-tab.active {
    background: #fdf2f4;
    border-color: #f0c4cc;
    color: #c41e3a;
  }
  /* P3：搜索栏 */
  .forum-search-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    /* 2026-11-03：与右侧范围筛选同行排布，不再独占整行 */
    flex: 1 1 auto;
    min-width: 0;
    margin: 0 0 12px;
    padding: 10px 12px;
    background: #ffffff;
    border-radius: 12px;
  }
  /* 校园 / 班级 论坛筛选（2026-11-03） */
  .scope-filter {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px;
    background: #f1f5fb;
    border-radius: 9px;
    flex: 0 0 auto;
  }
  .scope-chip {
    height: 28px;
    padding: 0 12px;
    border: none;
    border-radius: 7px;
    background: transparent;
    color: #5a6488;
    font-size: 12.5px;
    cursor: pointer;
    white-space: nowrap;
  }
  .scope-chip:hover { color: #1a365d; }
  .scope-chip.on {
    background: #ffffff;
    color: #1a365d;
    font-weight: 600;
    box-shadow: 0 1px 3px rgba(23, 35, 58, .12);
  }

  /* 列表正文摘要（2026-11-03）：2 行截断 */
  .list-excerpt {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-size: 12px;
    line-height: 1.5;
    color: #6b7896;
    text-align: left;
    width: 100%;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  .hot-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .search-input {
    /* 2026-11-03：搜索框缩短，给右侧「校园/班级论坛」筛选让位 */
    flex: 0 1 260px;
    max-width: 260px;
    min-width: 0;
    height: 34px;
    padding: 0 12px;
    border: 1px solid #e3e8ef;
    border-radius: 8px;
    font-size: 13px;
    outline: none;
  }
  .search-input:focus {
    border-color: #c41e3a;
  }
  .search-date {
    height: 34px;
    padding: 0 8px;
    border: 1px solid #e3e8ef;
    border-radius: 8px;
    font-size: 12px;
    color: #475569;
  }
  .search-tilde {
    color: #94a3b8;
  }
  .search-btn {
    height: 34px;
    padding: 0 16px;
    border: none;
    border-radius: 8px;
    background: #c41e3a;
    color: #fff;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
  }
  .search-reset {
    height: 34px;
    padding: 0 12px;
    border: 1px solid #e3e8ef;
    border-radius: 8px;
    background: #fff;
    color: #475569;
    font-size: 13px;
    cursor: pointer;
  }
  /* P3：爱心（喜欢）/ 五角星（收藏）/ 收藏弹窗列表 */
  .heart-icon {
    font-size: 13px;
    line-height: 1;
    color: #8a8faa;
  }
  .heart-icon.active {
    color: #e5484d;
  }
  .meta-favs {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    cursor: pointer;
  }
  .meta-favs:hover {
    color: #b8860b;
  }
  .fav-list {
    max-height: 380px;
    overflow-y: auto;
    margin: 8px 0;
  }
  .fav-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 10px;
    cursor: pointer;
    transition: background 0.2s;
  }
  .fav-item:hover {
    background: #f5f7fb;
  }
  .fav-item-title {
    font-size: 14px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .fav-item-meta {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: #8a8faa;
    font-size: 12px;
    flex: 0 0 auto;
  }
  .fav-sep {
    color: #d5d9e5;
  }
  .fav-empty {
    padding: 40px 0;
    text-align: center;
    color: #94a3b8;
    font-size: 14px;
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
    /* grid 子项默认 stretch 会被拉成与左栏等高（实测 2552px），
       align-self: start 才能让 sticky 有可粘空间 */
    position: sticky;
    top: 72px;
    align-self: start;
    max-height: calc(100vh - 140px);
    overflow-y: auto;
    overscroll-behavior: contain;
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
  /* 用户信息卡片必须盖在帖子详情之上：两者默认同为 z-index 2000，
     由 DOM 顺序决定，用户卡片节点在详情之前，会被详情压住 */
  @supports selector(:has(*)) {
    .modal-overlay:has(.profile-card) {
      z-index: 2100;
    }
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
    /* 与新 FileUploader 重复，且 accept 只含 doc/docx/pdf/xls/xlsx(不含 png)，
       容易让用户以为不能传图片；隐藏后历史附件回显不受影响 */
    display: none;
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
    height: 85vh;          /* 固定高度，底部固定条才能与弹窗底边精确对齐 */
    max-height: 85vh;
    overflow-y: auto;
    /* 底部留出固定输入区的高度，最后一条评论仍可滚到可见位置 */
    padding-bottom: 90px;
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
    /* 吸底：详情弹窗(.post-detail-card)是滚动容器，输入区常驻可视底部，
       否则上传/表情/发送位于内容末尾(2100px+)，用户看不到。
       负外边距抵消 .modal-card 的 28px 内边距，让吸底条铺到卡片底边与两侧，
       否则下方会露出 28px 的滚动内容。 */
    margin: 0;
    padding: 12px 28px;
    border-top: 1px solid #f0f2f5;
    /* 弹窗高度固定为 85vh 且垂直居中，所以其底边恒在 92.5vh；
       固定条贴同一条线，打开即在视口内，不依赖滚动 */
    position: fixed;
    left: 50%;
    transform: translateX(-50%);
    bottom: 7.5vh;
    width: 680px;
    max-width: 95vw;
    background: #ffffff;
    z-index: 2100;
    box-shadow: 0 -8px 16px rgba(26, 54, 93, 0.06);
    border-radius: 0 0 16px 16px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
  /* 单行：😊 → ＋ → 输入框 → 发表评论（DOM 顺序不变，仅改视觉顺序） */
  .comment-input-area textarea {
    order: 3;
    flex: 1 1 0;
    width: auto;          /* 覆盖 .modal-textarea 的 width:100%，否则整行被占满导致换行 */
    min-width: 120px;
    height: 40px;
    min-height: 40px;
    max-height: 120px;
    resize: vertical;
  }
  .comment-input-area .comment-toolbar { order: 1; margin: 0; }
  .comment-input-area .comment-image-upload { order: 2; margin: 0; }
  .comment-input-area .modal-actions { order: 4; margin: 0 0 0 auto; }
  .comment-input-area .reply-hint,
  .comment-input-area .comment-picker { order: 0; flex: 0 0 100%; }
  /* 表情面板浮在输入区上方，不把整条吸底区顶高 */
  .comment-input-area .comment-picker {
    position: absolute;
    left: 28px;
    bottom: calc(100% + 8px);
    flex: 0 0 auto;
  }
  .comment-toolbar-tip { display: none; }
  /* 关闭按钮隐藏而非删除：删 DOM 要改 <template>（R3）；弹窗仍可点遮罩/Esc 关闭 */
  .comment-input-area .cancel-btn { display: none; }

  /* 上传：76×76 虚线框 → 36×36 圆形「＋」；原文字视觉隐藏，读屏仍可读 */
  .comment-input-area :deep(.fu-add) {
    width: 36px;
    height: 36px;
    padding: 0;
    border-radius: 50%;
    font-size: 0;
    position: relative;
  }
  .comment-input-area :deep(.fu-add::before) {
    content: '+';
    font-size: 20px;
    line-height: 1;
    color: #1a2b5f;
  }
  .comment-input-area :deep(.fu-add span) {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }
  .comment-input-area :deep(.fu-thumb) { width: 40px; height: 40px; }
  .comment-input-area :deep(.fu-doc) { max-width: 140px; padding: 6px 8px; font-size: 12px; }
  .comment-input-area .confirm-btn { padding: 8px 16px; font-size: 13px; }
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

/* 2026-10-30：分类与搜索固定（学生 PC）——标题行 68px 之下依次吸附 */
.category-bar { position: sticky; top: var(--forum-toolbar-h, 84px); z-index: 24; background: #fff;
  padding-top: 8px; padding-bottom: 8px; margin-bottom: 0; }
/* in-header：搜索栏并入标题行后不再单独吸顶 */
.forum-search-bar.in-header { position: static; flex: 1 1 auto; min-width: 320px; background: #fff;
  padding-bottom: 8px; margin-bottom: 8px;
  box-shadow: 0 8px 10px -12px rgba(15,23,42,.45); }

/* 2026-10-30：窄屏（平板/小笔记本）压缩标题行，避免拥挤与标题换行 */
@media (max-width: 1560px) {
  .forum-header { gap: 10px; }
  .forum-header h2 { font-size: 22px; white-space: nowrap; }
  .forum-search-bar.in-header { min-width: 0; gap: 6px; }
  .forum-search-bar.in-header .search-input { min-width: 130px; padding: 7px 10px; font-size: 13px; }
  .forum-search-bar.in-header .search-date { width: 116px; padding: 6px 6px; font-size: 12px; }
  .forum-search-bar.in-header .search-btn,
  .forum-search-bar.in-header .search-reset {
    padding: 6px 10px; font-size: 13px; white-space: nowrap; }
  .forum-header-actions { gap: 6px; }
  .forum-header-actions .post-btn { padding: 6px 10px; font-size: 13px; white-space: nowrap; }
}
@media (max-width: 1280px) {
  .forum-header h2 { font-size: 19px; }
  .forum-search-bar.in-header .search-input { min-width: 100px; }
  .forum-search-bar.in-header .search-date { width: 104px; }
  .forum-header-actions .post-btn { padding: 6px 8px; font-size: 12px; }
}
/* 收藏/喜欢合并为单个五角星 */
.post-btn.star-only { padding: 0; width: 38px; height: 38px; display: inline-flex;
  align-items: center; justify-content: center; border-radius: 50%; }
/* 2026-10-31：整页固定高度，左右两栏各自滚动（互不带动） */
.forum-page { height: 100vh; overflow: hidden; }
.forum-main { height: calc(100vh - 0px); overflow: hidden; }
.forum-body { display: flex; gap: 20px; align-items: flex-start;
  height: calc(100vh - 148px); overflow: hidden; }
.forum-left { flex: 1 1 auto; min-width: 0; height: 100%;
  overflow-y: auto; overscroll-behavior: contain; padding-right: 6px; }
.forum-right { flex: 0 0 300px; height: 100%;
  overflow-y: auto; overscroll-behavior: contain; }
.post-author-line { display: flex; align-items: center; gap: 4px;
  font-size: 13px; color: #6b7896; margin-bottom: 4px; }
.post-author-line .meta-author { font-weight: 600; color: #1a2b5f; }
</style>
