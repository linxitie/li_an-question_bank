<template>
  <div class="admin-profile">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>个人信息</h2>
    </div>

    <!-- 基本信息卡片 -->
    <el-card class="profile-card">
      <template #header>
        <span class="card-title">基本信息</span>
      </template>

      <el-form
        ref="profileFormRef"
        :model="profileForm"
        :rules="profileRules"
        label-width="100px"
        style="max-width: 600px"
      >
        <!-- 头像 -->
        <el-form-item label="头像">
          <div class="avatar-section">
            <el-avatar :size="100" :src="profileForm.avatar || defaultAvatar">
              {{ profileForm.username?.charAt(0)?.toUpperCase() }}
            </el-avatar>
            <div class="avatar-actions">
              <el-upload
                class="avatar-uploader"
                action="/api/admin/upload/image"
                :show-file-list="false"
                :on-success="handleAvatarSuccess"
                :before-upload="beforeAvatarUpload"
                accept="image/*"
              >
                <el-button size="small" type="primary">上传新头像</el-button>
              </el-upload>
              <el-button size="small" @click="resetAvatar">重置默认</el-button>
            </div>
          </div>
        </el-form-item>

        <!-- 用户名 -->
        <el-form-item label="用户名" prop="username">
          <el-input v-model="profileForm.username" disabled />
        </el-form-item>

        <!-- 真实姓名 -->
        <el-form-item label="真实姓名" prop="real_name">
          <el-input v-model="profileForm.real_name" placeholder="请输入真实姓名" />
        </el-form-item>

        <!-- 手机号 -->
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="profileForm.phone" placeholder="请输入手机号" />
        </el-form-item>

        <!-- 邮箱 -->
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
        </el-form-item>

        <!-- 性别 -->
        <el-form-item label="性别" prop="gender">
          <el-select v-model="profileForm.gender" placeholder="请选择性别">
            <el-option label="男" value="男" />
            <el-option label="女" value="女" />
            <el-option label="未知" value="未知" />
          </el-select>
        </el-form-item>

        <!-- 保存按钮 -->
        <el-form-item>
          <el-button type="primary" @click="saveProfile" :loading="saving">
            保存修改
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 账号信息卡片 -->
    <el-card class="profile-card">
      <template #header>
        <span class="card-title">账号信息</span>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户编号">{{ accountInfo.user_no }}</el-descriptions-item>
        <el-descriptions-item label="角色类型">
          <el-tag :type="getRoleType(accountInfo.user_type)">{{ getRoleName(accountInfo.user_type) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="所属部门">{{ accountInfo.department || '-' }}</el-descriptions-item>
        <el-descriptions-item label="注册时间">{{ formatDateTime(accountInfo.register_time) }}</el-descriptions-item>
        <el-descriptions-item label="最后登录">{{ formatDateTime(accountInfo.last_login) }}</el-descriptions-item>
        <el-descriptions-item label="登录IP">{{ accountInfo.last_login_ip || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 安全设置卡片 -->
    <el-card class="profile-card">
      <template #header>
        <span class="card-title">安全设置</span>
      </template>

      <el-form label-width="100px" style="max-width: 600px">
        <el-form-item label="修改密码">
          <el-button type="warning" @click="showChangePasswordDialog">
            修改密码
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 操作日志卡片 -->
    <el-card class="profile-card">
      <template #header>
        <span class="card-title">最近操作记录</span>
      </template>

      <el-table :data="recentLogs" stripe>
        <el-table-column label="时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.operation_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="operation_type" label="操作类型" width="100" />
        <el-table-column prop="module_name" label="模块" width="100" />
        <el-table-column prop="operation_desc" label="操作描述" show-overflow-tooltip />
        <el-table-column prop="ip_address" label="IP地址" width="140" />
      </el-table>
    </el-card>

    <!-- 修改密码弹窗 -->
    <el-dialog v-model="passwordDialogVisible" title="修改密码" width="400px">
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="100px"
      >
        <el-form-item label="当前密码" prop="current_password">
          <el-input
            v-model="passwordForm.current_password"
            type="password"
            show-password
            placeholder="请输入当前密码"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="passwordForm.new_password"
            type="password"
            show-password
            placeholder="请输入新密码（至少6位）"
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input
            v-model="passwordForm.confirm_password"
            type="password"
            show-password
            placeholder="请再次输入新密码"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="changePassword" :loading="changingPassword">
          确认修改
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// 默认头像
const defaultAvatar = 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png'

// 表单引用
const profileFormRef = ref(null)
const passwordFormRef = ref(null)

// 加载状态
const saving = ref(false)
const changingPassword = ref(false)

// 个人信息表单
const profileForm = ref({
  user_id: null,
  username: '',
  real_name: '',
  phone: '',
  email: '',
  gender: '未知',
  avatar: ''
})

// 账号信息
const accountInfo = ref({
  user_no: '',
  user_type: '',
  department: '',
  register_time: '',
  last_login: '',
  last_login_ip: ''
})

// 最近操作记录
const recentLogs = ref([])

// 修改密码弹窗
const passwordDialogVisible = ref(false)
const passwordForm = ref({
  current_password: '',
  new_password: '',
  confirm_password: ''
})

// 表单验证规则
const profileRules = {
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ]
}

// 密码验证规则
const passwordRules = {
  current_password: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.value.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 获取角色名称
const getRoleName = (type) => {
  const map = { admin: '管理员', teacher: '教师', student: '学生' }
  return map[type] || type
}

// 获取角色类型
const getRoleType = (type) => {
  const map = { admin: 'danger', teacher: 'warning', student: '' }
  return map[type] || ''
}

// 格式化时间
const formatDateTime = (timeStr) => {
  if (!timeStr) return '-'
  return timeStr.replace('T', ' ').substring(0, 19)
}

// 加载个人信息
const loadProfile = async () => {
  try {
    const auth = window.__VTJ_AUTH__
    const userInfo = auth?.getUserInfo?.() || {}
    const userId = userInfo.user_id

    if (userId) {
      const res = await fetch(`/api/admin/users/${userId}`)
      const data = await res.json()
      if (data.success) {
        profileForm.value = {
          user_id: data.user.user_id,
          username: data.user.username,
          real_name: data.user.real_name || data.user.username,
          phone: data.user.phone || '',
          email: data.user.email || '',
          gender: data.user.gender || '未知',
          avatar: data.user.avatar || ''
        }
        accountInfo.value = {
          user_no: data.user.user_no,
          user_type: data.user.user_type,
          department: data.user.department,
          register_time: data.user.register_time,
          last_login: data.user.last_login,
          last_login_ip: data.user.last_login_ip
        }
      }
    }
  } catch (error) {
    ElMessage.error('加载个人信息失败')
  }
}

// 加载最近操作记录
const loadRecentLogs = async () => {
  try {
    const res = await fetch('/api/admin/logs?page=1&page_size=10')
    const data = await res.json()
    if (data.success) {
      recentLogs.value = data.items
    }
  } catch (error) {
    console.error('加载操作记录失败')
  }
}

// 保存个人信息
const saveProfile = async () => {
  try {
    await profileFormRef.value.validate()
    saving.value = true

    const res = await fetch(`/api/admin/users/${profileForm.value.user_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        real_name: profileForm.value.real_name,
        phone: profileForm.value.phone,
        email: profileForm.value.email,
        gender: profileForm.value.gender,
        avatar: profileForm.value.avatar
      })
    })

    const data = await res.json()
    if (data.success) {
      ElMessage.success('个人信息更新成功')
    } else {
      ElMessage.error(data.message || '更新失败')
    }
  } catch (error) {
    ElMessage.error('保存失败：' + error.message)
  } finally {
    saving.value = false
  }
}

// 头像上传成功回调
const handleAvatarSuccess = (response) => {
  if (response.success) {
    profileForm.value.avatar = response.url
    ElMessage.success('头像上传成功')
  } else {
    ElMessage.error('头像上传失败')
  }
}

// 头像上传前校验
const beforeAvatarUpload = (file) => {
  const isImage = file.type.startsWith('image/')
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isImage) {
    ElMessage.error('只能上传图片文件')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('头像大小不能超过 2MB')
    return false
  }
  return true
}

// 重置头像
const resetAvatar = () => {
  profileForm.value.avatar = ''
  ElMessage.success('已重置为默认头像')
}

// 显示修改密码弹窗
const showChangePasswordDialog = () => {
  passwordForm.value = {
    current_password: '',
    new_password: '',
    confirm_password: ''
  }
  passwordDialogVisible.value = true
}

// 修改密码
const changePassword = async () => {
  try {
    await passwordFormRef.value.validate()
    changingPassword.value = true

    const res = await fetch(`/api/admin/users/${profileForm.value.user_id}/reset-password`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: passwordForm.value.current_password,
        new_password: passwordForm.value.new_password
      })
    })

    const data = await res.json()
    if (data.success) {
      ElMessage.success('密码修改成功，请重新登录')
      passwordDialogVisible.value = false
      // 清除登录状态
      localStorage.removeItem('token')
      window.location.href = '/login'
    } else {
      ElMessage.error(data.message || '密码修改失败')
    }
  } catch (error) {
    ElMessage.error('修改失败：' + error.message)
  } finally {
    changingPassword.value = false
  }
}

// 页面加载
onMounted(() => {
  loadProfile()
  loadRecentLogs()
})
</script>

<style scoped>
.admin-profile {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  color: #303133;
}

.profile-card {
  margin-bottom: 20px;
}

.card-title {
  font-weight: bold;
  font-size: 16px;
}

.avatar-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

.avatar-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>