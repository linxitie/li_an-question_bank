<template>
  <div class="teacher-nav-header">
    <div class="nav-bar">
      <span class="nav-logo">砺安题库 · 教师端</span>
      <div class="nav-links">
        <span v-for="tab in navTabs" :key="tab.key"
          :class="['nav-tab', { active: activeNav === tab.key }]"
          @click="goTab(tab.key)">
          {{ tab.label }}
          <span v-if="tab.key === 'messages' && unreadCount > 0" class="msg-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
        </span>
      </div>
      <div class="nav-user-area" @click.stop="toggleUserMenu">
        <div class="avatar-wrap">
          <img v-if="userInfo.avatar" :src="userInfo.avatar" class="avatar-img" />
          <div v-else class="avatar-placeholder">{{ avatarText }}</div>
        </div>
        <span class="user-name">{{ userInfo.username || '教师' }}</span>
        <span class="role-tag">教师</span>
        <span class="dropdown-arrow">▼</span>

        <!-- 下拉菜单 -->
        <div class="user-dropdown" v-if="showUserMenu" @click.stop>
          <div class="dropdown-item" @click.stop="goProfile">👤 个人信息</div>
          <div class="dropdown-item" @click.stop="showPasswordModal = true">🔒 修改密码</div>
          <div class="dropdown-item" @click.stop="goTab('classes')">🏫 我的班级</div>
          <div class="dropdown-item" @click.stop="goTab('messages')">
            💬 消息中心
            <span v-if="unreadCount > 0" class="msg-dot">{{ unreadCount }}</span>
          </div>
          <div class="dropdown-item" @click.stop="showHelp">📖 帮助文档</div>
          <div class="dropdown-divider"></div>
          <div class="dropdown-item logout" @click.stop="handleLogout">🚪 退出登录</div>
        </div>
      </div>
    </div>

    <!-- 修改密码弹窗 -->
    <div class="modal-overlay" v-if="showPasswordModal" @click.self="showPasswordModal = false">
      <div class="modal-content password-modal">
        <h3>修改密码</h3>
        <div class="form-group">
          <label>当前密码</label>
          <input class="form-input" type="password" v-model="passwordForm.old_password" placeholder="请输入当前密码" />
        </div>
        <div class="form-group">
          <label>新密码</label>
          <input class="form-input" type="password" v-model="passwordForm.new_password" placeholder="请输入新密码（至少6位）" />
        </div>
        <div class="form-group">
          <label>确认新密码</label>
          <input class="form-input" type="password" v-model="passwordForm.confirm_password" placeholder="请再次输入新密码" />
        </div>
        <div class="modal-footer">
          <button class="btn-save" @click="changePassword" :disabled="changingPassword">
            {{ changingPassword ? '修改中...' : '确认修改' }}
          </button>
          <button class="btn-close" @click="showPasswordModal = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 个人信息弹窗（设计文档 §2.6.5） -->
    <div class="modal-overlay" v-if="showProfileModal" @click.self="showProfileModal = false">
      <div class="modal-content profile-modal">
        <div class="profile-modal-header">
          <h3>👤 个人信息</h3>
          <button class="modal-close-btn" @click="showProfileModal = false">✕</button>
        </div>

        <div class="profile-modal-body">
          <!-- 头像区 -->
          <div class="profile-avatar-section">
            <div class="profile-avatar-large" @click="openProfileAvatarPicker">
              <img v-if="profileData.avatar" :src="profileData.avatar" />
              <div v-else class="profile-avatar-placeholder">{{ profileAvatarText }}</div>
              <div class="profile-avatar-overlay">点击更换</div>
            </div>
            <input ref="profileAvatarInput" type="file" accept="image/*" style="display:none" @change="uploadProfileAvatar" />
          </div>

          <!-- 基本信息 -->
          <div class="profile-info-section">
            <div v-if="!profileEditMode">
              <div class="profile-info-grid">
                <div class="profile-info-item"><label>教师姓名</label><span>{{ profileData.username || '--' }}</span></div>
                <div class="profile-info-item"><label>工号</label><span>{{ profileData.user_no || '--' }}</span></div>
                <div class="profile-info-item"><label>任教科目</label><span>{{ profileData.subject || '--' }}</span></div>
                <div class="profile-info-item"><label>手机号</label><span>{{ profileData.phone || '--' }}</span></div>
                <div class="profile-info-item"><label>邮箱</label><span>{{ profileData.email || '--' }}</span></div>
                <div class="profile-info-item"><label>所属院系</label><span>{{ profileData.department || '--' }}</span></div>
                <div class="profile-info-item"><label>入职时间</label><span>{{ profileData.hire_date || '--' }}</span></div>
              </div>
            </div>
            <!-- 编辑模式 -->
            <div v-else>
              <div class="profile-info-grid">
                <div class="profile-info-item"><label>教师姓名</label><input class="form-input" v-model="profileEditForm.username" /></div>
                <div class="profile-info-item"><label>工号</label><span class="readonly">{{ profileData.user_no || '--' }}</span></div>
                <div class="profile-info-item"><label>手机号</label><input class="form-input" v-model="profileEditForm.phone" /></div>
                <div class="profile-info-item"><label>邮箱</label><input class="form-input" v-model="profileEditForm.email" /></div>
                <div class="profile-info-item"><label>所属院系</label><input class="form-input" v-model="profileEditForm.department" /></div>
              </div>
            </div>
          </div>

          <!-- 教学数据统计 -->
          <div class="profile-stats-section">
            <h4>📊 教学数据</h4>
            <div class="profile-stats-grid">
              <div class="profile-stat-item">
                <div class="profile-stat-value">{{ profileData.paper_count || 0 }}</div>
                <div class="profile-stat-label">累计出卷</div>
              </div>
              <div class="profile-stat-item">
                <div class="profile-stat-value">{{ profileData.approved_count || 0 }}</div>
                <div class="profile-stat-label">审批通过</div>
              </div>
              <div class="profile-stat-item">
                <div class="profile-stat-value">{{ profileData.class_count || 0 }}个（{{ profileData.student_count || 0 }}名学生）</div>
                <div class="profile-stat-label">所带班级</div>
              </div>
            </div>
          </div>
        </div>

        <div class="profile-modal-footer">
          <template v-if="!profileEditMode">
            <button class="btn-save" @click="startProfileEdit">✏️ 编辑信息</button>
            <button class="btn-secondary" @click="showProfileModal = false; showPasswordModal = true">🔒 修改密码</button>
            <button class="btn-close" @click="showProfileModal = false">关闭</button>
          </template>
          <template v-else>
            <button class="btn-save" @click="saveProfile" :disabled="profileSaving">{{ profileSaving ? '保存中...' : '保存修改' }}</button>
            <button class="btn-close" @click="profileEditMode = false">取消</button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
    import { defineComponent, ref, computed, onMounted, onUnmounted, useTemplateRef } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

export default defineComponent({
  name: 'TeacherNavHeader',
  props: {
    activeNav: { type: String, default: 'dashboard' }
  },
  emits: ['logout'],
  setup(props, { emit }) {
    const router = useRouter();
    const profileAvatarInput = useTemplateRef<HTMLInputElement>('profileAvatarInput');
    function openProfileAvatarPicker() {
      profileAvatarInput.value?.click();
    }
    const showUserMenu = ref(false);
    const showPasswordModal = ref(false);
    const showProfileModal = ref(false);
    const changingPassword = ref(false);
    const profileSaving = ref(false);
    const unreadCount = ref(0);
    const userInfo = ref<any>({ username: '', avatar: '' });
    const passwordForm = ref({ old_password: '', new_password: '', confirm_password: '' });

    // 个人信息弹窗数据
    const profileData = ref<any>({});
    const profileEditMode = ref(false);
    const profileEditForm = ref({ username: '', phone: '', email: '', department: '' });

    const profileAvatarText = computed(() => {
      const name = profileData.value.username || '教师';
      return name.substring(0, 1);
    });

    const navTabs = [
      { key: 'dashboard', label: '工作台', path: '/teacher/dashboard' },
      { key: 'questions', label: '题目管理', path: '/teacher/questions' },
      { key: 'papers', label: '试卷管理', path: '/teacher/papers' },
      { key: 'scores', label: '成绩管理', path: '/teacher/scores' },
      { key: 'classes', label: '班级管理', path: '/teacher/classes' },
      { key: 'analytics', label: '数据分析', path: '/teacher/analytics' },
      { key: 'messages', label: '消息中心', path: '/teacher/messages' },
    ];

    const avatarText = computed(() => {
      const name = userInfo.value.username || '教师';
      return name.substring(0, 1);
    });

    onMounted(async () => {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) {
        userInfo.value.username = auth.getUsername() || '教师';
      }
      await loadProfile();
      await loadUnreadCount();
      document.addEventListener('click', closeMenu);
    });

    onUnmounted(() => {
      document.removeEventListener('click', closeMenu);
    });

    async function loadProfile() {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth) return;
      try {
        const res = await auth.apiFetch('/api/teacher/profile');
        const data = await res.json();
        if (data.success) {
          userInfo.value = data;
        }
      } catch (e) { /* ignore */ }
    }

    async function loadUnreadCount() {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth) return;
      try {
        const res = await auth.apiFetch('/api/teacher/messages/unread-count');
        const data = await res.json();
        if (data.success) {
          unreadCount.value = data.unread_count || 0;
        }
      } catch (e) { /* ignore */ }
    }

    function toggleUserMenu() {
      showUserMenu.value = !showUserMenu.value;
    }

    function closeMenu() {
      showUserMenu.value = false;
    }

    function goTab(key: string) {
      const tab = navTabs.find(t => t.key === key);
      if (tab) {
        router.push(tab.path);
        showUserMenu.value = false;
      }
    }

    function goProfile() {
      showUserMenu.value = false;
      showProfileModal.value = true;
      loadProfileData();
    }

    async function loadProfileData() {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth) return;
      try {
        const res = await auth.apiFetch('/api/teacher/profile');
        const data = await res.json();
        if (data.success) {
          profileData.value = data;
        }
      } catch (e) { /* ignore */ }
    }

    function startProfileEdit() {
      profileEditForm.value = {
        username: profileData.value.username || '',
        phone: profileData.value.phone || '',
        email: profileData.value.email || '',
        department: profileData.value.department || '',
      };
      profileEditMode.value = true;
    }

    async function saveProfile() {
      profileSaving.value = true;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/teacher/profile', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(profileEditForm.value),
        });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('信息已更新');
          profileEditMode.value = false;
          await loadProfileData();
          await loadProfile();
        } else {
          ElMessage.error(data.detail || '更新失败');
        }
      } catch (e) {
        ElMessage.error('网络错误');
      } finally {
        profileSaving.value = false;
      }
    }

    async function uploadProfileAvatar(e: any) {
      const file = e.target.files[0];
      if (!file) return;
      if (file.size > 2 * 1024 * 1024) {
        ElMessage.warning('头像大小不能超过2MB');
        return;
      }
      const auth = (window as any).__VTJ_AUTH__;
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await auth.apiFetch('/api/teacher/profile/avatar', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('头像上传成功');
          profileData.value.avatar = data.avatar_url;
          await loadProfile();
        } else {
          ElMessage.error('上传失败');
        }
      } catch (e) {
        ElMessage.error('上传失败');
      }
    }

    function showHelp() {
      showUserMenu.value = false;
      ElMessage.info('帮助文档功能开发中...');
    }

    async function changePassword() {
      if (!passwordForm.value.old_password || !passwordForm.value.new_password) {
        ElMessage.warning('请填写完整');
        return;
      }
      if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
        ElMessage.warning('两次输入的密码不一致');
        return;
      }
      if (passwordForm.value.new_password.length < 6) {
        ElMessage.warning('新密码至少6位');
        return;
      }
      changingPassword.value = true;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/teacher/profile/change-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            old_password: passwordForm.value.old_password,
            new_password: passwordForm.value.new_password,
          }),
        });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('密码修改成功，请重新登录');
          showPasswordModal.value = false;
          passwordForm.value = { old_password: '', new_password: '', confirm_password: '' };
          if (auth) auth.logout();
          router.push('/login');
        } else {
          ElMessage.error(data.detail || '修改失败');
        }
      } catch (e) {
        ElMessage.error('网络错误');
      } finally {
        changingPassword.value = false;
      }
    }

    function handleLogout() {
      showUserMenu.value = false;
      emit('logout');
    }

    return {
      navTabs, showUserMenu, showPasswordModal, showProfileModal,
      changingPassword, profileSaving, unreadCount, userInfo, passwordForm, avatarText,
      profileData, profileEditMode, profileEditForm, profileAvatarText,
      toggleUserMenu, goTab, goProfile, loadProfileData, startProfileEdit, saveProfile, uploadProfileAvatar,
      showHelp, changePassword, handleLogout, openProfileAvatarPicker,
    };
  }
});
</script>

<style scoped>
.nav-bar { display: flex; align-items: center; padding: 0 24px; height: 56px; background: #1A3C6D; color: #fff; position: relative; z-index: 100; }
.nav-logo { font-size: 16px; font-weight: 600; margin-right: 32px; white-space: nowrap; }
.nav-links { display: flex; gap: 4px; flex: 1; }
.nav-tab { padding: 8px 16px; border-radius: 6px; cursor: pointer; color: rgba(255,255,255,0.7); font-size: 15px; position: relative; white-space: nowrap; }
.nav-tab:hover, .nav-tab.active { color: #fff; background: rgba(255,255,255,0.15); font-weight: 600; }
.msg-badge { position: absolute; top: 2px; right: 2px; background: #F56C6C; color: #fff; font-size: 10px; padding: 1px 5px; border-radius: 10px; font-weight: 600; }
.nav-user-area { display: flex; align-items: center; gap: 8px; cursor: pointer; padding: 6px 12px; border-radius: 8px; position: relative; }
.nav-user-area:hover { background: rgba(255,255,255,0.1); }
.avatar-wrap { width: 32px; height: 32px; border-radius: 50%; overflow: hidden; flex-shrink: 0; }
.avatar-img { width: 100%; height: 100%; object-fit: cover; }
.avatar-placeholder { width: 100%; height: 100%; background: #409EFF; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; border-radius: 50%; }
.user-name { font-size: 14px; }
.role-tag { font-size: 11px; background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 10px; }
.dropdown-arrow { font-size: 10px; opacity: 0.6; }

.user-dropdown { position: absolute; top: 100%; right: 0; margin-top: 8px; background: #fff; border-radius: 10px; box-shadow: 0 6px 24px rgba(0,0,0,0.15); min-width: 180px; padding: 8px 0; z-index: 1000; }
.dropdown-item { padding: 10px 20px; cursor: pointer; color: #333; font-size: 14px; display: flex; align-items: center; gap: 8px; }
.dropdown-item:hover { background: #f5f7fa; }
.dropdown-item.logout { color: #F56C6C; }
.dropdown-divider { height: 1px; background: #e8e8e8; margin: 4px 0; }
.msg-dot { background: #F56C6C; color: #fff; font-size: 10px; padding: 1px 6px; border-radius: 10px; margin-left: auto; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 2000; }
.modal-content { background: #fff; border-radius: 12px; padding: 28px; }
.modal-content h3 { color: #1A3C6D; margin: 0 0 20px; }
.password-modal { max-width: 420px; width: 90%; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; margin-bottom: 6px; font-weight: 600; color: #1A3C6D; font-size: 14px; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; box-sizing: border-box; }
.modal-footer { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; }
.btn-save { padding: 10px 28px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-save:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-close { padding: 10px 28px; background: #f0f0f0; color: #666; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }

/* 个人信息弹窗 */
.profile-modal { max-width: 640px; width: 92%; }
.profile-modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.profile-modal-header h3 { margin: 0; color: #1A3C6D; font-size: 18px; }
.modal-close-btn { background: none; border: none; font-size: 20px; color: #999; cursor: pointer; padding: 4px 8px; border-radius: 4px; }
.modal-close-btn:hover { background: #f0f0f0; color: #333; }
.profile-modal-body { display: flex; flex-direction: column; gap: 20px; }
.profile-avatar-section { display: flex; justify-content: center; }
.profile-avatar-large { width: 100px; height: 100px; border-radius: 50%; overflow: hidden; cursor: pointer; position: relative; }
.profile-avatar-large img { width: 100%; height: 100%; object-fit: cover; }
.profile-avatar-placeholder { width: 100%; height: 100%; background: #409EFF; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 36px; font-weight: 700; border-radius: 50%; }
.profile-avatar-overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.5); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 12px; opacity: 0; transition: opacity 0.2s; border-radius: 50%; }
.profile-avatar-large:hover .profile-avatar-overlay { opacity: 1; }
.profile-info-section { background: #f9fafb; border-radius: 10px; padding: 16px 20px; }
.profile-info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 20px; }
.profile-info-item label { display: block; font-size: 12px; color: #888; margin-bottom: 2px; }
.profile-info-item span { font-size: 14px; color: #333; }
.profile-info-item .readonly { color: #999; }
.profile-info-item .form-input { width: 100%; padding: 6px 10px; border: 1px solid #d9d9d9; border-radius: 5px; font-size: 13px; box-sizing: border-box; }
.profile-stats-section { background: #f0f5ff; border-radius: 10px; padding: 16px 20px; }
.profile-stats-section h4 { margin: 0 0 12px; color: #1A3C6D; font-size: 14px; }
.profile-stats-grid { display: flex; gap: 24px; }
.profile-stat-item { text-align: center; flex: 1; }
.profile-stat-value { font-size: 20px; font-weight: 700; color: #1A3C6D; }
.profile-stat-label { font-size: 12px; color: #888; margin-top: 2px; }
.profile-modal-footer { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; padding-top: 16px; border-top: 1px solid #eee; }
.btn-secondary { padding: 10px 22px; background: #fff; color: #1A3C6D; border: 1px solid #1A3C6D; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-secondary:hover { background: #f0f5ff; }
</style>
