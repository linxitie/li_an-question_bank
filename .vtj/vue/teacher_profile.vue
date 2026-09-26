<template>
  <div class="teacher-profile">
    <TeacherNavHeader activeNav="profile" @logout="handleLogout" />

    <div class="page-content">
      <div class="profile-card">
        <!-- 头像区 -->
        <div class="avatar-section">
          <div class="avatar-large" @click="openAvatarPicker">
            <img v-if="profile.avatar" :src="profile.avatar" />
            <div v-else class="avatar-placeholder">{{ avatarText }}</div>
            <div class="avatar-overlay">点击更换</div>
          </div>
          <input ref="avatarInput" type="file" accept="image/*" style="display:none" @change="uploadAvatar" />
        </div>

        <!-- 信息区 -->
        <div class="info-section">
          <div class="info-row" v-if="!editing">
            <div class="info-item"><label>教师姓名</label><span>{{ profile.username }}</span></div>
            <div class="info-item"><label>工号</label><span>{{ profile.user_no || '--' }}</span></div>
            <div class="info-item"><label>手机号</label><span>{{ profile.phone || '--' }}</span></div>
            <div class="info-item"><label>邮箱</label><span>{{ profile.email || '--' }}</span></div>
            <div class="info-item"><label>所属院系</label><span>{{ profile.department || '--' }}</span></div>
            <div class="info-item"><label>入职时间</label><span>{{ profile.hire_date || '--' }}</span></div>
          </div>

          <!-- 编辑模式 -->
          <div class="info-row" v-else>
            <div class="info-item"><label>教师姓名</label><input class="form-input" v-model="editForm.username" /></div>
            <div class="info-item"><label>工号</label><span class="readonly">{{ profile.user_no || '--' }}</span></div>
            <div class="info-item"><label>手机号</label><input class="form-input" v-model="editForm.phone" /></div>
            <div class="info-item"><label>邮箱</label><input class="form-input" v-model="editForm.email" /></div>
            <div class="info-item"><label>所属院系</label><input class="form-input" v-model="editForm.department" /></div>
            <div class="info-item"><label>入职时间</label><span class="readonly">{{ profile.hire_date || '--' }}</span></div>
          </div>

          <div class="action-bar">
            <button v-if="!editing" class="btn-primary" @click="startEdit">✏️ 编辑信息</button>
            <template v-else>
              <button class="btn-save" @click="saveProfile" :disabled="saving">{{ saving ? '保存中...' : '保存修改' }}</button>
              <button class="btn-cancel" @click="editing = false">取消</button>
            </template>
          </div>
        </div>
      </div>

      <!-- 教学数据统计 -->
      <div class="stats-section">
        <h3>📊 教学数据</h3>
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-icon">🏫</div>
            <div class="stat-value">{{ profile.class_count || 0 }}</div>
            <div class="stat-label">所带班级</div>
          </div>
          <div class="stat-item">
            <div class="stat-icon">👨‍🎓</div>
            <div class="stat-value">{{ profile.student_count || 0 }}</div>
            <div class="stat-label">学生总数</div>
          </div>
          <div class="stat-item">
            <div class="stat-icon">📄</div>
            <div class="stat-value">{{ profile.paper_count || 0 }}</div>
            <div class="stat-label">累计出卷</div>
          </div>
          <div class="stat-item">
            <div class="stat-icon">✅</div>
            <div class="stat-value">{{ profile.approved_count || 0 }}</div>
            <div class="stat-label">审批通过</div>
          </div>
        </div>
      </div>

      <!-- 安全设置：修改密码 -->
      <div class="settings-section">
        <h3>🔒 安全设置</h3>
        <div class="settings-form">
          <div class="form-row">
            <label>当前密码</label>
            <input class="form-input" type="password" v-model="passwordForm.currentPassword" placeholder="请输入当前密码" />
          </div>
          <div class="form-row">
            <label>新密码</label>
            <input class="form-input" type="password" v-model="passwordForm.newPassword" placeholder="请输入新密码（至少6位）" />
          </div>
          <div class="form-row">
            <label>确认新密码</label>
            <input class="form-input" type="password" v-model="passwordForm.confirmPassword" placeholder="请再次输入新密码" />
          </div>
          <div class="form-actions">
            <button class="btn-save" @click="changePassword" :disabled="changingPassword">
              {{ changingPassword ? '修改中...' : '修改密码' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 教学偏好设置 -->
      <div class="settings-section">
        <h3>⚙️ 教学偏好</h3>
        <div class="settings-form">
          <div class="form-row">
            <label>默认科目</label>
            <select class="form-input" v-model="preferences.defaultSubject">
              <option :value="0">全部科目</option>
              <option :value="1">行测</option>
              <option :value="2">申论</option>
              <option :value="3">公专</option>
            </select>
          </div>
          <div class="form-row">
            <label>默认难度偏好</label>
            <select class="form-input" v-model="preferences.difficultyPreference">
              <option value="mixed">混合</option>
              <option value="easy">偏简单</option>
              <option value="medium">中等</option>
              <option value="hard">偏困难</option>
            </select>
          </div>
          <div class="form-row">
            <label>消息通知</label>
            <div class="toggle-row">
              <label class="toggle-label">
                <input type="checkbox" v-model="preferences.notifyExamResult" />
                <span>考试结果通知</span>
              </label>
              <label class="toggle-label">
                <input type="checkbox" v-model="preferences.notifyStudentSubmit" />
                <span>学生提交通知</span>
              </label>
              <label class="toggle-label">
                <input type="checkbox" v-model="preferences.notifySystem" />
                <span>系统通知</span>
              </label>
            </div>
          </div>
          <div class="form-actions">
            <button class="btn-save" @click="savePreferences" :disabled="savingPrefs">
              {{ savingPrefs ? '保存中...' : '保存偏好' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
    import { defineComponent, ref, computed, onMounted, useTemplateRef } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import TeacherNavHeader from './TeacherNavHeader.vue';

export default defineComponent({
  name: 'TeacherProfile',
  components: { TeacherNavHeader },
  setup() {
    const router = useRouter();
    const avatarInput = useTemplateRef<HTMLInputElement>('avatarInput');
    function openAvatarPicker() {
      avatarInput.value?.click();
    }
    const profile = ref<any>({});
    const editing = ref(false);
    const saving = ref(false);
    const editForm = ref({ username: '', phone: '', email: '', department: '' });
    const passwordForm = ref({ currentPassword: '', newPassword: '', confirmPassword: '' });
    const changingPassword = ref(false);
    const preferences = ref({
      defaultSubject: 0,
      difficultyPreference: 'mixed',
      notifyExamResult: true,
      notifyStudentSubmit: true,
      notifySystem: true,
    });
    const savingPrefs = ref(false);

    const avatarText = computed(() => {
      const name = profile.value.username || '教师';
      return name.substring(0, 1);
    });

    onMounted(async () => { await loadProfile(); });

    async function loadProfile() {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth) return;
      try {
        const res = await auth.apiFetch('/api/teacher/profile');
        const data = await res.json();
        if (data.success) profile.value = data;
      } catch (e) { console.error('加载个人信息失败:', e); }
    }

    function startEdit() {
      editForm.value = {
        username: profile.value.username || '',
        phone: profile.value.phone || '',
        email: profile.value.email || '',
        department: profile.value.department || '',
      };
      editing.value = true;
    }

    async function saveProfile() {
      saving.value = true;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/teacher/profile', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(editForm.value),
        });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('信息已更新');
          editing.value = false;
          await loadProfile();
        } else { ElMessage.error(data.detail || '更新失败'); }
      } catch (e) { ElMessage.error('网络错误'); }
      finally { saving.value = false; }
    }

    async function uploadAvatar(e: any) {
      const file = e.target.files[0];
      if (!file) return;
      if (file.size > 2 * 1024 * 1024) { ElMessage.warning('头像大小不能超过2MB'); return; }
      const auth = (window as any).__VTJ_AUTH__;
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await auth.apiFetch('/api/teacher/profile/avatar', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('头像上传成功');
          profile.value.avatar = data.avatar_url;
        } else { ElMessage.error('上传失败'); }
      } catch (e) { ElMessage.error('上传失败'); }
    }

    async function changePassword() {
      if (!passwordForm.value.currentPassword || !passwordForm.value.newPassword) {
        ElMessage.warning('请填写完整密码信息');
        return;
      }
      if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
        ElMessage.warning('两次输入的新密码不一致');
        return;
      }
      if (passwordForm.value.newPassword.length < 6) {
        ElMessage.warning('新密码长度不能少于6位');
        return;
      }
      changingPassword.value = true;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/teacher/profile/change-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            old_password: passwordForm.value.currentPassword,
            new_password: passwordForm.value.newPassword,
          }),
        });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('密码修改成功');
          passwordForm.value = { currentPassword: '', newPassword: '', confirmPassword: '' };
        } else { ElMessage.error(data.detail || '密码修改失败'); }
      } catch (e) { ElMessage.error('网络错误'); }
      finally { changingPassword.value = false; }
    }

    async function savePreferences() {
      savingPrefs.value = true;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/teacher/profile/preferences', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(preferences.value),
        });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('偏好设置已保存');
        } else { ElMessage.error(data.detail || '保存失败'); }
      } catch (e) { ElMessage.error('网络错误'); }
      finally { savingPrefs.value = false; }
    }

    function handleLogout() { const auth = (window as any).__VTJ_AUTH__; if (auth) auth.logout(); router.push('/login'); }

    return {
      profile, editing, saving, editForm, avatarText, startEdit, saveProfile, uploadAvatar,
      passwordForm, changingPassword, changePassword,
      preferences, savingPrefs, savePreferences,
      handleLogout, openAvatarPicker,
    };
  }
});
</script>

<style scoped>
.teacher-profile { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.page-content { max-width: 900px; margin: 0 auto; padding: 24px; }
.profile-card { background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); display: flex; gap: 32px; margin-bottom: 24px; }
.avatar-section { flex-shrink: 0; }
.avatar-large { width: 120px; height: 120px; border-radius: 50%; overflow: hidden; cursor: pointer; position: relative; }
.avatar-large img { width: 100%; height: 100%; object-fit: cover; }
.avatar-placeholder { width: 100%; height: 100%; background: #409EFF; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 40px; font-weight: 700; border-radius: 50%; }
.avatar-overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.5); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 13px; opacity: 0; transition: opacity 0.2s; border-radius: 50%; }
.avatar-large:hover .avatar-overlay { opacity: 1; }
.info-section { flex: 1; }
.info-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.info-item label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
.info-item span { font-size: 15px; color: #333; }
.info-item .readonly { color: #999; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
.action-bar { margin-top: 20px; display: flex; gap: 12px; }
.btn-primary { padding: 10px 22px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-save { padding: 10px 22px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-save:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-cancel { padding: 10px 22px; background: #f0f0f0; color: #666; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.stats-section { background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 24px; }
.stats-section h3 { color: #1A3C6D; margin: 0 0 20px; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
.stat-item { text-align: center; padding: 16px 0; }
.stat-icon { font-size: 28px; margin-bottom: 6px; }
.stat-value { font-size: 32px; font-weight: 700; color: #1A3C6D; }
.stat-label { font-size: 13px; color: #888; margin-top: 4px; }
.settings-section { background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 24px; }
.settings-section h3 { color: #1A3C6D; margin: 0 0 20px; font-size: 16px; }
.settings-form { max-width: 480px; }
.form-row { margin-bottom: 16px; }
.form-row label { display: block; font-size: 13px; color: #666; margin-bottom: 6px; font-weight: 600; }
.form-row .form-input { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
.form-row select.form-input { appearance: auto; }
.form-actions { margin-top: 20px; }
.toggle-row { display: flex; gap: 20px; flex-wrap: wrap; }
.toggle-label { display: flex; align-items: center; gap: 6px; font-size: 14px; color: #333; cursor: pointer; }
</style>
