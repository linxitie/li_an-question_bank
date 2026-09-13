<template>
  <div class="admin-content">
    <div v-if="loading" class="skeleton-wrap">
      <div class="sk-bar"></div>
      <div class="sk-table"></div>
    </div>
    <div v-else>
      <div class="action-bar">
        <h2 class="page-title">👤 个人信息</h2>
        <div class="action-buttons">
          <button class="btn-primary" @click="saveProfile">💾 保存修改</button>
        </div>
      </div>

      <!-- 基本信息卡片 -->
      <div class="profile-card">
        <h3>基本信息</h3>
        <div class="profile-form">
          <!-- 头像区域 -->
          <div class="avatar-section">
            <div class="avatar-large" :style="{backgroundImage: profileForm.avatar ? `url(${profileForm.avatar})` : 'none'}">
              {{ !profileForm.avatar ? profileForm.username?.charAt(0)?.toUpperCase() : '' }}
            </div>
            <div class="avatar-actions">
              <label class="btn-secondary" for="avatar-upload">📤 上传新头像</label>
              <input type="file" id="avatar-upload" accept="image/*" @change="handleAvatarUpload" style="display:none"/>
              <button class="btn-secondary" @click="resetAvatar">🔄 重置默认</button>
            </div>
          </div>

          <!-- 表单字段 -->
          <div class="form-grid">
            <div class="fg">
              <label>用户名</label>
              <input class="fi" v-model="profileForm.username" disabled />
            </div>
            <div class="fg">
              <label>真实姓名</label>
              <input class="fi" v-model="profileForm.real_name" placeholder="请输入真实姓名"/>
            </div>
            <div class="fg">
              <label>手机号</label>
              <input class="fi" v-model="profileForm.phone" placeholder="请输入手机号"/>
            </div>
            <div class="fg">
              <label>邮箱</label>
              <input class="fi" v-model="profileForm.email" placeholder="请输入邮箱"/>
            </div>
            <div class="fg">
              <label>性别</label>
              <select class="fi" v-model="profileForm.gender">
                <option value="男">男</option>
                <option value="女">女</option>
                <option value="未知">未知</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <!-- 账号信息卡片 -->
      <div class="profile-card">
        <h3>账号信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">用户编号</span>
            <span class="info-value">{{ accountInfo.user_no }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">角色类型</span>
            <span class="role-tag" :class="'role-' + accountInfo.user_type">
              {{ {admin:'管理员',teacher:'教师',student:'学生'}[accountInfo.user_type] || accountInfo.user_type }}
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">所属部门</span>
            <span class="info-value">{{ accountInfo.department || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">注册时间</span>
            <span class="info-value">{{ formatDateTime(accountInfo.register_time) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">最后登录</span>
            <span class="info-value">{{ formatDateTime(accountInfo.last_login) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">登录IP</span>
            <span class="info-value">{{ accountInfo.last_login_ip || '-' }}</span>
          </div>
        </div>
      </div>

      <!-- 安全设置卡片 -->
      <div class="profile-card">
        <h3>安全设置</h3>
        <div class="security-actions">
          <button class="btn-warning" @click="showChangePasswordDialog">🔑 修改密码</button>
        </div>
      </div>

      <!-- 操作日志卡片 -->
      <div class="profile-card">
        <h3>最近操作记录</h3>
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>操作类型</th>
                <th>模块</th>
                <th>操作描述</th>
                <th>IP地址</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in recentLogs" :key="log.log_id">
                <td>{{ formatDateTime(log.operation_time) }}</td>
                <td>{{ log.operation_type }}</td>
                <td>{{ log.module_name }}</td>
                <td class="desc-cell">{{ log.operation_desc }}</td>
                <td>{{ log.ip_address }}</td>
              </tr>
              <tr v-if="!recentLogs.length">
                <td colspan="5" class="empty-row">暂无操作记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 修改密码弹窗 -->
      <div class="modal-overlay" v-if="showPasswordModal" @click.self="showPasswordModal = false">
        <div class="modal-content">
          <h3>修改密码</h3>
          <div class="form-grid">
            <div class="fg">
              <label>当前密码 <span class="required">*</span></label>
              <input class="fi" type="password" v-model="passwordForm.current_password" placeholder="请输入当前密码"/>
            </div>
            <div class="fg">
              <label>新密码 <span class="required">*</span></label>
              <input class="fi" type="password" v-model="passwordForm.new_password" placeholder="请输入新密码（至少6位）"/>
            </div>
          </div>
          <div class="fg">
            <label>确认密码 <span class="required">*</span></label>
            <input class="fi" type="password" v-model="passwordForm.confirm_password" placeholder="请再次输入新密码"/>
          </div>
          <div class="modal-actions">
            <button class="btn-secondary" @click="showPasswordModal = false">取消</button>
            <button class="btn-primary" @click="changePassword">确认修改</button>
          </div>
        </div>
      </div>

      <div class="msg" v-if="msg">{{ msg }}</div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'AdminProfile',
  setup() {
    const provider = useProvider({ id: 'admin_profile', version: '1' });
    const loading = ref(true);
    const msg = ref('');
    const saving = ref(false);

    const profileForm = ref({
      user_id: null,
      username: '',
      real_name: '',
      phone: '',
      email: '',
      gender: '未知',
      avatar: ''
    });

    const accountInfo = ref({
      user_no: '',
      user_type: '',
      department: '',
      register_time: '',
      last_login: '',
      last_login_ip: ''
    });

    const recentLogs = ref<any[]>([]);

    const showPasswordModal = ref(false);
    const passwordForm = ref({
      current_password: '',
      new_password: '',
      confirm_password: ''
    });

    const auth = () => (window as any).__VTJ_AUTH__;

    const formatDateTime = (timeStr: string) => {
      if (!timeStr) return '-';
      return timeStr.replace('T', ' ').substring(0, 19);
    };

    const loadProfile = async () => {
      try {
        const userInfo = auth()?.getUserInfo?.() || {};
        const userId = userInfo.user_id;
        if (userId) {
          const r = await auth().apiFetch('/api/admin/users/' + userId);
          const d = await r.json();
          if (d.success && d.user) {
            profileForm.value = {
              user_id: d.user.user_id,
              username: d.user.username,
              real_name: d.user.real_name || d.user.username,
              phone: d.user.phone || '',
              email: d.user.email || '',
              gender: d.user.gender || '未知',
              avatar: d.user.avatar || ''
            };
            accountInfo.value = {
              user_no: d.user.user_no,
              user_type: d.user.user_type,
              department: d.user.department || '',
              register_time: d.user.register_time,
              last_login: d.user.last_login,
              last_login_ip: d.user.last_login_ip
            };
          }
        }
      } catch (e) {
        msg.value = '❌ 加载个人信息失败';
        setTimeout(() => msg.value = '', 3000);
      }
    };

    const loadRecentLogs = async () => {
      try {
        const r = await auth().apiFetch('/api/admin/logs?page=1&page_size=10');
        const d = await r.json();
        if (d.success) recentLogs.value = d.items || [];
      } catch (e) {
        console.error('加载操作记录失败');
      }
    };

    const saveProfile = async () => {
      saving.value = true;
      try {
        const r = await auth().apiFetch('/api/admin/users/' + profileForm.value.user_id, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            real_name: profileForm.value.real_name,
            phone: profileForm.value.phone,
            email: profileForm.value.email,
            gender: profileForm.value.gender,
            avatar: profileForm.value.avatar
          })
        });
        const d = await r.json();
        if (d.success) {
          msg.value = '✅ 个人信息更新成功';
        } else {
          msg.value = '❌ ' + (d.message || '更新失败');
        }
        setTimeout(() => msg.value = '', 3000);
      } catch (e) {
        msg.value = '❌ 保存失败';
        setTimeout(() => msg.value = '', 3000);
      }
      saving.value = false;
    };

    const handleAvatarUpload = async (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      if (!file.type.startsWith('image/')) {
        msg.value = '❌ 只能上传图片文件';
        setTimeout(() => msg.value = '', 3000);
        return;
      }
      if (file.size / 1024 / 1024 > 2) {
        msg.value = '❌ 头像大小不能超过 2MB';
        setTimeout(() => msg.value = '', 3000);
        return;
      }
      const fd = new FormData();
      fd.append('file', file);
      try {
        const r = await auth().apiFetch('/api/materials/admin/upload/image', {
          method: 'POST',
          body: fd
        });
        const d = await r.json();
        if (d.url) {
          profileForm.value.avatar = d.url;
          msg.value = '✅ 头像上传成功';
        } else {
          msg.value = '❌ 头像上传失败';
        }
        setTimeout(() => msg.value = '', 3000);
      } catch (e) {
        msg.value = '❌ 头像上传失败';
        setTimeout(() => msg.value = '', 3000);
      }
    };

    const resetAvatar = () => {
      profileForm.value.avatar = '';
      msg.value = '✅ 已重置为默认头像';
      setTimeout(() => msg.value = '', 3000);
    };

    const showChangePasswordDialog = () => {
      passwordForm.value = { current_password: '', new_password: '', confirm_password: '' };
      showPasswordModal.value = true;
    };

    const changePassword = async () => {
      if (!passwordForm.value.current_password || !passwordForm.value.new_password) {
        msg.value = '❌ 请填写密码';
        setTimeout(() => msg.value = '', 3000);
        return;
      }
      if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
        msg.value = '❌ 两次输入的密码不一致';
        setTimeout(() => msg.value = '', 3000);
        return;
      }
      if (passwordForm.value.new_password.length < 6) {
        msg.value = '❌ 密码至少6位';
        setTimeout(() => msg.value = '', 3000);
        return;
      }
      try {
        const r = await auth().apiFetch('/api/admin/users/' + profileForm.value.user_id + '/reset-password', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            current_password: passwordForm.value.current_password,
            new_password: passwordForm.value.new_password
          })
        });
        const d = await r.json();
        if (d.success) {
          msg.value = '✅ 密码修改成功，请重新登录';
          showPasswordModal.value = false;
          localStorage.removeItem('token');
          setTimeout(() => window.location.href = '/login', 1500);
        } else {
          msg.value = '❌ ' + (d.message || '密码修改失败');
        }
        setTimeout(() => msg.value = '', 3000);
      } catch (e) {
        msg.value = '❌ 修改失败';
        setTimeout(() => msg.value = '', 3000);
      }
    };

    onMounted(async () => {
      await loadProfile();
      await loadRecentLogs();
      loading.value = false;
    });

    return {
      provider, loading, msg, saving, profileForm, accountInfo, recentLogs,
      showPasswordModal, passwordForm, formatDateTime, saveProfile,
      handleAvatarUpload, resetAvatar, showChangePasswordDialog, changePassword
    };
  }
});
</script>

<style scoped>
.admin-content { padding: 20px; }
.skeleton-wrap { display: flex; flex-direction: column; gap: 20px; }
.sk-bar, .sk-table {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: sk 1.5s infinite;
  border-radius: 10px;
}
.sk-bar { height: 60px; }
.sk-table { height: 400px; }
@keyframes sk { 0% { background-position: 200% 0 } 100% { background-position: -200% 0 } }

.action-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { margin: 0; color: #1A3C6D; }
.action-buttons { display: flex; gap: 10px; }

.profile-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.profile-card h3 { margin: 0 0 20px; color: #1A3C6D; font-size: 18px; }

.avatar-section { display: flex; align-items: center; gap: 20px; margin-bottom: 24px; }
.avatar-large {
  width: 100px; height: 100px; border-radius: 50%;
  background: #409eff; color: #fff; font-size: 36px; font-weight: bold;
  display: flex; align-items: center; justify-content: center;
  background-size: cover; background-position: center;
}
.avatar-actions { display: flex; flex-direction: column; gap: 8px; }

.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.fg { margin-bottom: 16px; }
.fg label { display: block; margin-bottom: 6px; font-weight: 500; color: #333; }
.fg .required { color: #f56c6c; }
.fi { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
.fi:disabled { background: #f5f5f5; color: #999; }

.info-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.info-item { display: flex; flex-direction: column; gap: 4px; }
.info-label { font-size: 13px; color: #909399; }
.info-value { font-size: 14px; color: #303133; }

.role-tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; display: inline-block; width: fit-content; }
.role-student { background: #f0f9eb; color: #67C23A; }
.role-teacher { background: #ecf5ff; color: #409eff; }
.role-admin { background: #fef0f0; color: #f56c6c; }

.security-actions { display: flex; gap: 12px; }

.table-container { background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06); overflow: hidden; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { padding: 12px 16px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; }
.data-table td { padding: 12px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.data-table tr:hover { background: #f5f7fa; }
.desc-cell { max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-row { text-align: center; color: #999; padding: 40px 0 !important; }

.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: #fff; border-radius: 12px; padding: 24px; min-width: 400px; max-width: 90vw; }
.modal-content h3 { margin: 0 0 20px; color: #1A3C6D; }
.modal-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 20px; }

.btn-primary { padding: 8px 16px; background: #C41E3A; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-primary:hover { background: #a01830; }
.btn-secondary { padding: 8px 16px; background: #fff; color: #333; border: 1px solid #d9d9d9; border-radius: 6px; cursor: pointer; }
.btn-warning { padding: 8px 16px; background: #e6a23c; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-warning:hover { background: #cf9236; }

.msg { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); padding: 12px 24px; background: #f0f9eb; color: #67C23A; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 2000; }
</style>