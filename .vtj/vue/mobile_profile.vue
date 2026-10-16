<!-- 手机端我的页 - VTJ规范版 -->
<template>
  <div class="mobile-profile-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left">
        <XIcon :icon="ArrowLeft" :size="22" color="#1A365D" class="nav-back" @click="goBack"></XIcon>
      </div>
      <h1 class="nav-title">我的</h1>
      <div class="nav-right">
        <XIcon :icon="Setting" :size="22" color="#1A365D" class="nav-icon" @click="goToSettings"></XIcon>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 用户信息卡片 -->
      <section class="user-card">
        <div class="user-avatar" @click="triggerAvatarUpload">
          <img v-if="userAvatar" :src="userAvatar" class="user-avatar-img" alt="头像" />
          <XIcon v-else :icon="UserFilled" :size="40" color="#ffffff"></XIcon>
          <input ref="avatarInput" type="file" accept="image/jpeg,image/png,image/gif,image/webp" style="display:none" @change="handleAvatarChange" />
        </div>
        <div class="user-info">
          <h2 class="user-name">{{ userName }}</h2>
          <p class="user-role">公安联考备考学员</p>
          <div class="user-stats">
            <div class="stat-item">
              <span class="stat-value">{{ streakDays }}</span>
              <span class="stat-label">连续天数</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ totalQuestions }}</span>
              <span class="stat-label">总做题</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ accuracy }}%</span>
              <span class="stat-label">正确率</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 学习数据 -->
      <section class="data-section">
        <div class="section-header">
          <h2 class="section-title">
            <XIcon :icon="DataLine" :size="20" color="#1A365D"></XIcon>
            学习数据
          </h2>
        </div>
        <div class="data-grid">
          <div class="data-card" @click="goToWrongQuestions">
            <XIcon :icon="Warning" :size="24" color="#f59e0b"></XIcon>
            <span class="data-value">{{ wrongCount }}</span>
            <span class="data-label">错题本</span>
          </div>
          <div class="data-card" @click="goToCollection">
            <XIcon :icon="Star" :size="24" color="#f59e0b"></XIcon>
            <span class="data-value">{{ collectionCount }}</span>
            <span class="data-label">收藏</span>
          </div>
          <div class="data-card" @click="goToHistory">
            <XIcon :icon="Clock" :size="24" color="#1A365D"></XIcon>
            <span class="data-value">{{ historyCount }}</span>
            <span class="data-label">历史记录</span>
          </div>
          <div class="data-card" @click="goToNotes">
            <XIcon :icon="Notebook" :size="24" color="#10b981"></XIcon>
            <span class="data-value">{{ notesCount }}</span>
            <span class="data-label">笔记</span>
          </div>
        </div>
      </section>

      <!-- 个人小目标统计记录
           需求：目标模块需提供统计记录，并在「我的」中展示。数据来自既有
           GET /api/goals/stats/summary（不新增后端接口）。 -->
      <section class="data-section">
        <div class="section-header">
          <h2>
            我的目标
            <span class="section-sub" v-if="goalTotal > 0">共 {{ goalTotal }} 个 · 完成率 {{ goalCompletionRate }}%</span>
          </h2>
        </div>
        <div class="data-grid" v-if="goalTotal > 0" @click="goToGoals">
          <div class="data-card">
            <XIcon :icon="Aim" :size="24" color="#1A365D"></XIcon>
            <span class="data-value">{{ goalTotal }}</span>
            <span class="data-label">目标总数</span>
          </div>
          <div class="data-card">
            <XIcon :icon="CircleCheck" :size="24" color="#10b981"></XIcon>
            <span class="data-value">{{ goalCompleted }}</span>
            <span class="data-label">已完成</span>
          </div>
          <div class="data-card">
            <XIcon :icon="Clock" :size="24" color="#f59e0b"></XIcon>
            <span class="data-value">{{ goalTodayCompleted }}</span>
            <span class="data-label">今日完成</span>
          </div>
          <div class="data-card">
            <XIcon :icon="DataLine" :size="24" color="#8b5cf6"></XIcon>
            <span class="data-value">{{ goalAverageProgress }}%</span>
            <span class="data-label">平均进度</span>
          </div>
        </div>
        <div class="goal-empty" v-else-if="goalLoaded" @click="goToGoals">
          <span class="goal-empty-text">还没有学习目标，去制定第一个吧</span>
          <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
        </div>
      </section>

      <!-- 功能列表 -->
      <section class="menu-section">
        <div class="menu-list">
          <div class="menu-item" @click="goToAchievements">
            <div class="menu-icon">
              <XIcon :icon="Trophy" :size="20" color="#f59e0b"></XIcon>
            </div>
            <span class="menu-name">我的成就</span>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="menu-item" @click="goToDownloads">
            <div class="menu-icon">
              <XIcon :icon="Download" :size="20" color="#1A365D"></XIcon>
            </div>
            <span class="menu-name">离线下载</span>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="menu-item" @click="goToFeedback">
            <div class="menu-icon">
              <XIcon :icon="ChatDotRound" :size="20" color="#10b981"></XIcon>
            </div>
            <span class="menu-name">意见反馈</span>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="menu-item" @click="openProfileEdit">
            <div class="menu-icon">
              <XIcon :icon="Edit" :size="20" color="#1A365D"></XIcon>
            </div>
            <span class="menu-name">编辑个人资料</span>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="menu-item" @click="openPwdEdit">
            <div class="menu-icon">
              <XIcon :icon="Lock" :size="20" color="#8b5cf6"></XIcon>
            </div>
            <span class="menu-name">修改密码</span>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="menu-item" @click="goToScoreAnalysis">
            <div class="menu-icon">
              <XIcon :icon="TrendCharts" :size="20" color="#3b82f6"></XIcon>
            </div>
            <span class="menu-name">成绩分析</span>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="menu-item" @click="goToGoldPurchase">
            <div class="menu-icon">
              <XIcon :icon="ShoppingCart" :size="20" color="#f59e0b"></XIcon>
            </div>
            <span class="menu-name">金币购</span>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="menu-item" @click="goToHelp">
            <div class="menu-icon">
              <XIcon :icon="QuestionFilled" :size="20" color="#8b5cf6"></XIcon>
            </div>
            <span class="menu-name">帮助中心</span>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="menu-item" @click="goToAbout">
            <div class="menu-icon">
              <XIcon :icon="InfoFilled" :size="20" color="#8899aa"></XIcon>
            </div>
            <span class="menu-name">关于砺安题库</span>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
        </div>
      </section>

      <!-- 退出登录 -->
      <section class="logout-section">
        <button class="logout-btn" @click="handleLogout">
          <XIcon :icon="SwitchButton" :size="18" color="#c41e3a"></XIcon>
          退出登录
        </button>
      </section>
    </main>

    <!-- 资料编辑弹层（字段对齐后端 ProfileUpdateForm: email/phone/gender/department/class_name/school） -->
    <div v-if="showProfileEdit" class="modal-mask" @click="showProfileEdit = false">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <span class="modal-title">编辑个人资料</span>
          <button class="modal-close" @click="showProfileEdit = false" aria-label="关闭">✕</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span class="field-label">手机号</span>
            <input v-model="profileForm.phone" class="field-input" type="tel" inputmode="numeric" placeholder="请输入手机号" />
          </label>
          <label class="field">
            <span class="field-label">邮箱</span>
            <input v-model="profileForm.email" class="field-input" type="email" placeholder="请输入邮箱" />
          </label>
          <label class="field">
            <span class="field-label">学院 / 学校</span>
            <input v-model="profileForm.school" class="field-input" type="text" placeholder="请输入学院名称" />
          </label>
          <label class="field">
            <span class="field-label">班级</span>
            <input v-model="profileForm.class_name" class="field-input" type="text" placeholder="请输入班级" />
          </label>
          <label class="field">
            <span class="field-label">部门</span>
            <input v-model="profileForm.department" class="field-input" type="text" placeholder="请输入部门" />
          </label>
          <label class="field">
            <span class="field-label">性别</span>
            <select v-model="profileForm.gender" class="field-input">
              <option value="">未设置</option>
              <option value="男">男</option>
              <option value="女">女</option>
            </select>
          </label>
        </div>
        <div class="modal-actions">
          <button class="action-btn" :disabled="savingProfile" @click="saveProfile">
            {{ savingProfile ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 修改密码弹层 -->
    <div v-if="showPwdEdit" class="modal-mask" @click="showPwdEdit = false">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <span class="modal-title">修改密码</span>
          <button class="modal-close" @click="showPwdEdit = false" aria-label="关闭">✕</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span class="field-label">当前密码</span>
            <input v-model="pwdForm.old_password" class="field-input" type="password" autocomplete="current-password" placeholder="请输入当前密码" />
          </label>
          <label class="field">
            <span class="field-label">新密码</span>
            <input v-model="pwdForm.new_password" class="field-input" type="password" autocomplete="new-password" placeholder="至少 6 位" />
          </label>
          <label class="field">
            <span class="field-label">确认新密码</span>
            <input v-model="pwdForm.confirm_password" class="field-input" type="password" autocomplete="new-password" placeholder="再次输入新密码" />
          </label>
        </div>
        <div class="modal-actions">
          <button class="action-btn" :disabled="savingPwd" @click="savePassword">
            {{ savingPwd ? '提交中...' : '确认修改' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 底部Tab栏 -->
    <!-- 底部Tab栏：统一使用单一真源组件 src/components/MobileTabBar.vue -->
    <MobileTabBar active="profile" />
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import { ElMessage } from 'element-plus';
import MobileTabBar from '@/components/mobile/MobileTabBar.vue';
import {
  ArrowLeft,
  ArrowRight,
  Setting,
  UserFilled,
  DataLine,
  Warning,
  Star,
  Clock,
  Notebook,
  Trophy,
  Download,
  ChatDotRound,
  QuestionFilled,
  InfoFilled,
  SwitchButton,
  HomeFilled,
  Reading,
  Edit,
  ChatLineRound,
  User,
  Lock,
  TrendCharts,
  ShoppingCart,
  Aim,
  CircleCheck
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'MobileProfile',
    components: {
      XIcon,
      MobileTabBar
    },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'mobile_profile', version: '1788919369989' });
    
    // 用户数据
    const userName = ref('同学');
    const userAvatar = ref('');
    const avatarInput = ref(null);
    const streakDays = ref(15);
    const totalQuestions = ref(1289);
    const accuracy = ref(70.2);
    
    // 学习数据
    const wrongCount = ref(45);
    const collectionCount = ref(128);
    const historyCount = ref(567);
    const notesCount = ref(32);

    // ===== 资料编辑 =====
    // 字段严格对齐后端 ProfileUpdateForm（auth.py:374-382），
    // 只提交后端允许编辑的非敏感字段；username/role 不可改。
    const showProfileEdit = ref(false);
    const savingProfile = ref(false);
    const profileForm = ref({
      email: '', phone: '', gender: '', department: '', class_name: '', school: ''
    });

    // ===== 修改密码 =====
    const showPwdEdit = ref(false);
    const savingPwd = ref(false);
    const pwdForm = ref({ old_password: '', new_password: '', confirm_password: '' });

    const openProfileEdit = async () => {
      showProfileEdit.value = true;
      try {
        const auth = window.__VTJ_AUTH__;
        const res = await auth.apiFetch('/api/auth/profile');
        if (res.ok) {
          const d = await res.json();
          profileForm.value = {
            email: d.email || '',
            phone: d.phone || '',
            gender: d.gender || '',
            department: d.department || '',
            class_name: d.class_name || '',
            school: d.school || ''
          };
        }
      } catch (e) {
        ElMessage.error('加载资料失败');
      }
    };

    const saveProfile = async () => {
      savingProfile.value = true;
      try {
        const auth = window.__VTJ_AUTH__;
        const payload: Record<string, string> = {};
        // 只提交实际填写了的字段，配合后端 exclude_unset，避免把未填项覆盖为 null
        if (profileForm.value.email) payload.email = profileForm.value.email;
        if (profileForm.value.phone) payload.phone = profileForm.value.phone;
        if (profileForm.value.gender) payload.gender = profileForm.value.gender;
        if (profileForm.value.department) payload.department = profileForm.value.department;
        if (profileForm.value.class_name) payload.class_name = profileForm.value.class_name;
        if (profileForm.value.school) payload.school = profileForm.value.school;

        if (Object.keys(payload).length === 0) {
          ElMessage.info('请至少填写一项要修改的资料');
          return;
        }
        const res = await auth.apiFetch('/api/auth/profile', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          ElMessage.success('资料已更新');
          showProfileEdit.value = false;
        } else {
          const err = await res.json().catch(() => ({}));
          ElMessage.error(err.detail || '保存失败');
        }
      } catch (e) {
        ElMessage.error('保存失败，请稍后重试');
      } finally {
        savingProfile.value = false;
      }
    };

    const openPwdEdit = () => {
      pwdForm.value = { old_password: '', new_password: '', confirm_password: '' };
      showPwdEdit.value = true;
    };

    const savePassword = async () => {
      const { old_password, new_password, confirm_password } = pwdForm.value;
      if (!old_password) {
        ElMessage.warning('请输入当前密码');
        return;
      }
      if (!new_password || new_password.length < 6) {
        ElMessage.warning('新密码至少 6 位');
        return;
      }
      if (new_password !== confirm_password) {
        ElMessage.warning('两次输入的新密码不一致');
        return;
      }
      if (new_password === old_password) {
        ElMessage.warning('新密码不能与当前密码相同');
        return;
      }
      savingPwd.value = true;
      try {
        const auth = window.__VTJ_AUTH__;
        // 必须始终携带 old_password：后端 change_password 的 old_password 为 Optional，
        // 缺省时会跳过旧密码校验直接改密（auth.py:412-415），前端不可依赖该宽松行为。
        const res = await auth.apiFetch('/api/auth/change-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ old_password, new_password })
        });
        if (res.ok) {
          ElMessage.success('密码修改成功');
          showPwdEdit.value = false;
        } else {
          const err = await res.json().catch(() => ({}));
          ElMessage.error(err.detail || '修改失败');
        }
      } catch (e) {
        ElMessage.error('修改失败，请稍后重试');
      } finally {
        savingPwd.value = false;
      }
    };

    // ===== 个人小目标统计 =====
    // 数据源：既有 GET /api/goals/stats/summary（goals.py:645）
    // 返回字段：total_goals / completed_goals / pending_goals /
    //           completion_rate / average_progress / today_completed
    const goalTotal = ref(0);
    const goalCompleted = ref(0);
    const goalCompletionRate = ref(0);
    const goalAverageProgress = ref(0);
    const goalTodayCompleted = ref(0);
    const goalLoaded = ref(false);

    const loadGoalStats = async () => {
      try {
        const auth = window.__VTJ_AUTH__;
        if (!auth || !auth.apiFetch) return;
        const res = await auth.apiFetch('/api/goals/stats/summary');
        if (!res.ok) return;
        const d = await res.json();
        goalTotal.value = d.total_goals || 0;
        goalCompleted.value = d.completed_goals || 0;
        goalCompletionRate.value = d.completion_rate || 0;
        goalAverageProgress.value = d.average_progress || 0;
        goalTodayCompleted.value = d.today_completed || 0;
      } catch (e) {
        // 目标统计加载失败不阻塞「我的」主流程
        console.error('加载目标统计失败:', e);
      } finally {
        goalLoaded.value = true;
      }
    };

    // 目标编辑仍在首页「今日目标」，此处跳首页对应模块
    const goToGoals = () => router.push('/mobile/home');

    // 加载用户数据
    onMounted(async () => {
      try {
        const auth = window.__VTJ_AUTH__;
        if (auth && auth.isLoggedIn()) {
          const uname = auth.getUsername();
          if (uname) userName.value = uname;
          // 头像
          try {
            const pRes = await auth.apiFetch('/api/auth/profile');
            const pData = await pRes.json();
            userAvatar.value = pData.avatar || '';
          } catch (e) { /* 头像加载失败不影响主流程 */ }
          // 学习统计
          const res = await auth.apiFetch('/api/stats/');
          const data = await res.json();
          totalQuestions.value = data.totalQuestions || 0;
          accuracy.value = data.accuracyRate || 0;
          streakDays.value = data.streak || 0;
          historyCount.value = data.totalQuestions || 0;

          // 计数（错题/收藏/笔记）
          try {
            const [wq, coll, note] = await Promise.all([
              auth.apiFetch('/api/wrong-questions?page=1&page_size=1'),
              auth.apiFetch('/api/collection?page=1&page_size=1'),
              auth.apiFetch('/api/notes'),
            ]);
            const wqData = await wq.json();
            const collData = await coll.json();
            const noteData = await note.json();
            wrongCount.value = wqData.total || 0;
            collectionCount.value = collData.total || 0;
            notesCount.value = noteData.total || 0;
          } catch (e) {
            console.error('加载计数失败:', e);
          }
          // 个人小目标统计（复用既有 /api/goals/stats/summary，不新增后端接口）
          await loadGoalStats();
        }
      } catch (error) {
        console.error('加载数据失败:', error);
      }
    });
    
    // 方法
    const goBack = () => router.back();
    
    const goToSettings = () => router.push('/profile');
    
    const goToWrongQuestions = () => router.push('/mobile/wrong-questions');
    const goToCollection = () => router.push('/mobile/favorites');
    const goToHistory = () => router.push('/mobile/history');
    const goToNotes = () => router.push('/mobile/notes');
    
    // 手机端使用独立移动端页面（含返回键），不再跳电脑端页面
    const goToAchievements = () => router.push('/mobile/achievements');
    const goToDownloads = () => router.push('/mobile/materials');
    const goToScoreAnalysis = () => router.push('/mobile/score-analysis');
    const goToGoldPurchase = () => router.push('/mobile/gold-purchase');
    const goToFeedback = () => router.push('/mobile/feedback');
    const goToHelp = () => router.push('/mobile/help');
    const goToAbout = () => router.push('/mobile/profile');
    
    const handleLogout = () => {
      if (window.__VTJ_AUTH__) window.__VTJ_AUTH__.logout();
      router.push('/login');
    };

    const triggerAvatarUpload = () => {
      if (avatarInput.value) avatarInput.value.click();
    };

    const handleAvatarChange = async (event: any) => {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      if (file.size > 2 * 1024 * 1024) {
        console.warn('头像超过2MB');
        return;
      }
      const fd = new FormData();
      fd.append('file', file);
      try {
        const auth = window.__VTJ_AUTH__;
        const res = await auth.apiFetch('/api/auth/avatar', { method: 'POST', body: fd });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          alert(err.detail || '上传失败');
          return;
        }
        const data = await res.json();
        if (data.success) {
          userAvatar.value = data.avatar_url;
        }
      } catch (e) {
        alert('上传失败，请重试');
      } finally {
        event.target.value = '';
      }
    };
    
    return {
      userName,
      userAvatar,
      avatarInput,
      streakDays,
      totalQuestions,
      accuracy,
      wrongCount,
      collectionCount,
      historyCount,
      notesCount,
      goalTotal,
      goalCompleted,
      goalCompletionRate,
      goalAverageProgress,
      goalTodayCompleted,
      goalLoaded,
      loadGoalStats,
      goToGoals,
      goBack,
      goToSettings,
      goToWrongQuestions,
      goToCollection,
      goToHistory,
      goToNotes,
      goToAchievements,
      goToDownloads,
      goToScoreAnalysis,
      goToGoldPurchase,
      goToFeedback,
      goToHelp,
      goToAbout,
      handleLogout,
      triggerAvatarUpload,
      handleAvatarChange,
      ArrowLeft,
      ArrowRight,
      Setting,
      UserFilled,
      DataLine,
      Warning,
      Star,
      Clock,
      Notebook,
      Trophy,
      Download,
      ChatDotRound,
      QuestionFilled,
      InfoFilled,
      SwitchButton,
      Aim,
      CircleCheck,
      HomeFilled,
      Reading,
      Edit,
      ChatLineRound,
      User,
      Lock,
      TrendCharts,
      ShoppingCart,
      // 资料编辑 / 修改密码
      showProfileEdit,
      savingProfile,
      profileForm,
      openProfileEdit,
      saveProfile,
      showPwdEdit,
      savingPwd,
      pwdForm,
      openPwdEdit,
      savePassword
    };
  }
});
</script>

<style lang="css" scoped>
.mobile-profile-page {
  min-height: 100vh;
  background: #f5f7fa;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}

/* 顶部导航 */
.top-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 16px;
  background: #ffffff;
  border-bottom: 1px solid #f0f2f5;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-left,
.nav-right {
  width: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-back,
.nav-icon {
  cursor: pointer;
  transition: opacity 0.2s;
}

.nav-back:hover,
.nav-icon:hover {
  opacity: 0.7;
}

.nav-title {
  font-size: 18px;
  font-weight: 700;
  color: #1A365D;
  margin: 0;
}

/* 主内容区 */
.main-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  padding-bottom: 80px;
}

/* 用户信息卡片 */
.user-card {
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  border-radius: 16px;
  padding: 24px;
  color: #ffffff;
  margin-bottom: 20px;
}

.user-avatar {
  width: 80px;
  height: 80px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  overflow: hidden;
  cursor: pointer;
}
.user-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-info {
  text-align: center;
}

.user-name {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 4px;
}

.user-role {
  font-size: 14px;
  opacity: 0.8;
  margin: 0 0 20px;
}

.user-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.stat-item {
  text-align: center;
}

.stat-item .stat-value {
  display: block;
  font-size: 22px;
  font-weight: 700;
}

.stat-item .stat-label {
  display: block;
  font-size: 12px;
  opacity: 0.8;
  margin-top: 4px;
}

/* 学习数据 */
.data-section {
  margin-bottom: 20px;
}

.section-header {
  margin-bottom: 16px;
}

/* 目标统计区块副标题（总数 · 完成率） */
.section-sub {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 400;
  color: #8899aa;
}

/* 目标为空时的引导行 */
.goal-empty {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: var(--touch-target-min, 44px);
  padding: 12px 16px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
  transition: all 0.3s ease;
}

.goal-empty-text {
  font-size: 13px;
  color: #8899aa;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #1a2b5f;
  margin: 0;
}

.data-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.data-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px 16px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.data-card:hover {
  box-shadow: 0 4px 16px rgba(26, 54, 95, 0.1);
  transform: translateY(-2px);
}

.data-value {
  font-size: 24px;
  font-weight: 700;
  color: #1a2b5f;
}

.data-label {
  font-size: 13px;
  color: #8899aa;
}

/* 功能列表 */
.menu-section {
  margin-bottom: 20px;
}

.menu-list {
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  overflow: hidden;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid #f0f2f5;
  cursor: pointer;
  transition: background 0.2s ease;
}

.menu-item:last-child {
  border-bottom: none;
}

.menu-item:hover {
  background: #f8f9fc;
}

.menu-icon {
  width: 36px;
  height: 36px;
  background: #f5f7fa;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu-name {
  flex: 1;
  font-size: 15px;
  font-weight: 500;
  color: #1a2b5f;
}

/* 退出登录 */
.logout-section {
  margin-top: 20px;
}

.logout-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px;
  background: #ffffff;
  border: 1px solid #ffccc7;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  color: #c41e3a;
  cursor: pointer;
  transition: all 0.3s ease;
}

.logout-btn:hover {
  background: #fff2f0;
}

/* 底部Tab栏样式已收敛到单一真源组件 src/components/MobileTabBar.vue */

@media (max-width: 375px) {
  .user-card {
    padding: 20px 16px;
  }
  
  .user-avatar {
    width: 64px;
    height: 64px;
  }
  
  .user-name {
    font-size: 20px;
  }
  
  .stat-item .stat-value {
    font-size: 20px;
  }
  
  .data-card {
    padding: 16px 12px;
  }
  
  .data-value {
    font-size: 20px;
  }
}

/* ===== 资料编辑 / 修改密码 弹层 ===== */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 1000;
}
.modal {
  background: #fff;
  border-radius: 14px;
  width: 100%;
  max-width: 420px;
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #eef1f5;
  flex-shrink: 0;
}
.modal-title {
  font-size: 15px;
  font-weight: 600;
  color: #1A365D;
}
.modal-close {
  background: none;
  border: none;
  font-size: 18px;
  color: #8899aa;
  cursor: pointer;
  min-width: var(--touch-target-min, 44px);
  min-height: var(--touch-target-min, 44px);
}
.modal-body {
  padding: 16px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  flex: 1;
}
.field {
  display: block;
  margin-bottom: 14px;
}
.field-label {
  display: block;
  font-size: 13px;
  color: #5a6488;
  margin-bottom: 6px;
}
.field-input {
  width: 100%;
  min-height: var(--touch-target-min, 44px);
  padding: 10px 12px;
  border: 1px solid #e8ecf1;
  border-radius: 8px;
  font-size: 14px;
  color: #1a2a3a;
  background: #fff;
  box-sizing: border-box;
}
.field-input:focus {
  outline: none;
  border-color: #1A365D;
}
.modal-actions {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid #eef1f5;
  flex-shrink: 0;
}
.action-btn {
  flex: 1;
  min-height: var(--touch-target-min, 44px);
  border: 1px solid #1A365D;
  background: #1A365D;
  color: #fff;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}
.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
