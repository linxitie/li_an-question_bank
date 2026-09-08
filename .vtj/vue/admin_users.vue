<template>
  <div class="admin-users">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>用户管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showAddUserDialog">
          <el-icon><Plus /></el-icon> 新增用户
        </el-button>
        <el-button @click="exportUsers">
          <el-icon><Download /></el-icon> 导出
        </el-button>
      </div>
    </div>

    <!-- 筛选区 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="角色">
          <el-select v-model="filters.user_type" clearable placeholder="全部角色">
            <el-option label="学生" value="student" />
            <el-option label="教师" value="teacher" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.is_disabled" clearable placeholder="全部状态">
            <el-option label="正常" :value="0" />
            <el-option label="禁用" :value="1" />
          </el-select>
        </el-form-item>
        <el-form-item label="搜索">
          <el-input v-model="filters.keyword" placeholder="用户名/手机号" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchUsers">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 用户列表 -->
    <el-card>
      <el-table :data="userList" stripe v-loading="loading">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="user_id" label="ID" width="60" />
        <el-table-column label="头像" width="70">
          <template #default="{ row }">
            <el-avatar :size="40" :src="row.avatar || defaultAvatar">
              {{ row.username?.charAt(0)?.toUpperCase() }}
            </el-avatar>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column label="角色" width="80">
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.user_type)">{{ getRoleName(row.user_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="手机号" width="120" />
        <el-table-column prop="department" label="所属部门" width="120" show-overflow-tooltip />
        <el-table-column prop="class_name" label="班级" width="120" show-overflow-tooltip />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_disabled ? 'danger' : 'success'">
              {{ row.is_disabled ? '禁用' : '正常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.register_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button
              v-if="!row.is_disabled"
              type="warning"
              link
              @click="handleDisable(row)"
            >
              禁用
            </el-button>
            <el-button v-else type="success" link @click="handleEnable(row)">启用</el-button>
            <el-button type="info" link @click="handleResetPassword(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchUsers"
        @current-change="fetchUsers"
      />
    </el-card>

    <!-- 编辑用户弹窗（含头像编辑功能） -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑用户信息"
      width="650px"
      @close="resetEditForm"
    >
      <el-form
        ref="editFormRef"
        :model="editForm"
        :rules="editRules"
        label-width="100px"
      >
        <!-- 头像编辑区域 -->
        <el-form-item label="用户头像">
          <div class="avatar-editor">
            <el-avatar :size="80" :src="editForm.avatar || defaultAvatar">
              {{ editForm.username?.charAt(0)?.toUpperCase() }}
            </el-avatar>
            <div class="avatar-actions">
              <el-upload
                class="avatar-uploader"
                action="/api/admin/upload/image"
                :show-file-list="false"
                :on-success="handleEditAvatarSuccess"
                :before-upload="beforeAvatarUpload"
                accept="image/*"
              >
                <el-button size="small" type="primary">
                  <el-icon><Upload /></el-icon> 上传头像
                </el-button>
              </el-upload>
              <el-button size="small" @click="selectAvatarFromGallery">
                <el-icon><Picture /></el-icon> 从图库选择
              </el-button>
              <el-button size="small" type="danger" @click="resetEditAvatar">
                <el-icon><Delete /></el-icon> 重置默认
              </el-button>
            </div>
            <div class="avatar-tips">
              <span>支持 JPG/PNG 格式，建议尺寸 200x200 像素，不超过 2MB</span>
            </div>
          </div>
        </el-form-item>

        <el-divider />

        <!-- 基本信息 -->
        <el-form-item label="用户编号" prop="user_no">
          <el-input v-model="editForm.user_no" disabled />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="editForm.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="editForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="性别" prop="gender">
          <el-select v-model="editForm.gender" placeholder="请选择性别">
            <el-option label="男" value="男" />
            <el-option label="女" value="女" />
            <el-option label="未知" value="未知" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户类型" prop="user_type">
          <el-select v-model="editForm.user_type" placeholder="请选择用户类型">
            <el-option label="学生" value="student" />
            <el-option label="教师" value="teacher" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属部门" prop="department">
          <el-input v-model="editForm.department" placeholder="请输入所属部门" />
        </el-form-item>
        <el-form-item label="班级" prop="class_name">
          <el-input v-model="editForm.class_name" placeholder="请输入班级" />
        </el-form-item>
        <el-form-item label="状态" prop="is_disabled">
          <el-switch
            v-model="editForm.is_disabled"
            :active-value="1"
            :inactive-value="0"
            active-text="禁用"
            inactive-text="正常"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEdit" :loading="submitting">
          保存修改
        </el-button>
      </template>
    </el-dialog>

    <!-- 头像图库选择弹窗 -->
    <el-dialog v-model="galleryVisible" title="选择头像" width="500px">
      <div class="avatar-gallery">
        <div
          v-for="(avatar, index) in avatarGallery"
          :key="index"
          class="gallery-item"
          :class="{ active: tempSelectedAvatar === avatar }"
          @click="tempSelectedAvatar = avatar"
        >
          <el-avatar :size="60" :src="avatar" />
        </div>
      </div>
      <template #footer>
        <el-button @click="galleryVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmGallerySelect">确定</el-button>
      </template>
    </el-dialog>

    <!-- 新增用户弹窗 -->
    <el-dialog v-model="addDialogVisible" title="新增用户" width="600px">
      <el-form
        ref="addFormRef"
        :model="addForm"
        :rules="addRules"
        label-width="100px"
      >
        <el-form-item label="用户编号" prop="user_no">
          <el-input v-model="addForm.user_no" placeholder="请输入用户编号" />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="addForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="addForm.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="addForm.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="用户类型" prop="user_type">
          <el-select v-model="addForm.user_type" placeholder="请选择用户类型">
            <el-option label="学生" value="student" />
            <el-option label="教师" value="teacher" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属部门" prop="department">
          <el-input v-model="addForm.department" placeholder="请输入所属部门" />
        </el-form-item>
        <el-form-item label="班级" prop="class_name">
          <el-input v-model="addForm.class_name" placeholder="请输入班级" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAddUser" :loading="submitting">
          确认创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// 默认头像
const defaultAvatar = 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png'

// 预设头像图库
const avatarGallery = ref([
  'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png',
  'https://cube.elemecdn.com/9/c2/c0ee869b014ed80fb2d39de5c69fcpng.png',
  'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png',
  'https://cube.elemecdn.com/6/94/4d55c6e1d983726e4943c25562ecfpng.png',
  'https://cube.elemecdn.com/8/07/82e0c4de6c8b9a2d8c8f3b08e4f1cpng.png'
])

// 临时选中的头像
const tempSelectedAvatar = ref('')

// 加载状态
const loading = ref(false)
const submitting = ref(false)

// 分页
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 筛选条件
const filters = reactive({
  user_type: '',
  is_disabled: null,
  keyword: ''
})

// 用户列表
const userList = ref([])

// 表单引用
const editFormRef = ref(null)
const addFormRef = ref(null)

// 编辑弹窗
const editDialogVisible = ref(false)
const editForm = ref({
  user_id: null,
  user_no: '',
  username: '',
  phone: '',
  email: '',
  gender: '未知',
  user_type: 'student',
  department: '',
  class_name: '',
  is_disabled: 0,
  avatar: ''
})

// 新增弹窗
const addDialogVisible = ref(false)
const addForm = ref({
  user_no: '',
  username: '',
  password: '',
  phone: '',
  user_type: 'student',
  department: '',
  class_name: ''
})

// 图库弹窗
const galleryVisible = ref(false)

// 验证规则
const editRules = {
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ]
}

const addRules = {
  user_no: [{ required: true, message: '请输入用户编号', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ],
  user_type: [{ required: true, message: '请选择用户类型', trigger: 'change' }]
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

// 加载用户列表
const fetchUsers = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: currentPage.value,
      page_size: pageSize.value
    })
    if (filters.user_type) params.append('user_type', filters.user_type)
    if (filters.is_disabled !== null) params.append('is_disabled', filters.is_disabled)
    if (filters.keyword) params.append('keyword', filters.keyword)

    const res = await fetch(`/api/admin/users?${params}`)
    const data = await res.json()
    if (data.success) {
      userList.value = data.items
      total.value = data.total
    }
  } catch (error) {
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

// 重置筛选
const resetFilters = () => {
  filters.user_type = ''
  filters.is_disabled = null
  filters.keyword = ''
  fetchUsers()
}

// 显示新增用户弹窗
const showAddUserDialog = () => {
  addForm.value = {
    user_no: '',
    username: '',
    password: '',
    phone: '',
    user_type: 'student',
    department: '',
    class_name: ''
  }
  addDialogVisible.value = true
}

// 提交新增用户
const submitAddUser = async () => {
  try {
    await addFormRef.value.validate()
    submitting.value = true

    const res = await fetch('/api/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(addForm.value)
    })

    const data = await res.json()
    if (data.success) {
      ElMessage.success('用户创建成功')
      addDialogVisible.value = false
      fetchUsers()
    } else {
      ElMessage.error(data.message || '创建失败')
    }
  } catch (error) {
    ElMessage.error('创建失败：' + error.message)
  } finally {
    submitting.value = false
  }
}

// 编辑用户
const handleEdit = async (row) => {
  try {
    const res = await fetch(`/api/admin/users/${row.user_id}`)
    const data = await res.json()
    if (data.success) {
      editForm.value = {
        user_id: data.user.user_id,
        user_no: data.user.user_no,
        username: data.user.username,
        phone: data.user.phone || '',
        email: data.user.email || '',
        gender: data.user.gender || '未知',
        user_type: data.user.user_type,
        department: data.user.department || '',
        class_name: data.user.class_name || '',
        is_disabled: data.user.is_disabled || 0,
        avatar: data.user.avatar || ''
      }
      editDialogVisible.value = true
    }
  } catch (error) {
    ElMessage.error('获取用户信息失败')
  }
}

// 提交编辑
const submitEdit = async () => {
  try {
    await editFormRef.value.validate()
    submitting.value = true

    const res = await fetch(`/api/admin/users/${editForm.value.user_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm.value)
    })

    const data = await res.json()
    if (data.success) {
      ElMessage.success('用户信息更新成功')
      editDialogVisible.value = false
      fetchUsers()
    } else {
      ElMessage.error(data.message || '更新失败')
    }
  } catch (error) {
    ElMessage.error('更新失败：' + error.message)
  } finally {
    submitting.value = false
  }
}

// 重置编辑表单
const resetEditForm = () => {
  editForm.value = {
    user_id: null,
    user_no: '',
    username: '',
    phone: '',
    email: '',
    gender: '未知',
    user_type: 'student',
    department: '',
    class_name: '',
    is_disabled: 0,
    avatar: ''
  }
}

// 编辑弹窗头像上传成功
const handleEditAvatarSuccess = (response) => {
  if (response.success) {
    editForm.value.avatar = response.url
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

// 从图库选择头像
const selectAvatarFromGallery = () => {
  tempSelectedAvatar.value = editForm.value.avatar || ''
  galleryVisible.value = true
}

// 确认图库选择
const confirmGallerySelect = () => {
  editForm.value.avatar = tempSelectedAvatar.value
  galleryVisible.value = false
  ElMessage.success('头像已更新')
}

// 重置编辑头像
const resetEditAvatar = () => {
  editForm.value.avatar = ''
  ElMessage.success('已重置为默认头像')
}

// 禁用用户
const handleDisable = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要禁用用户 ${row.username} 吗？`, '确认禁用', {
      type: 'warning'
    })

    const res = await fetch(`/api/admin/users/${row.user_id}/disable`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_disabled: 1, reason: '管理员操作禁用' })
    })

    const data = await res.json()
    if (data.success) {
      ElMessage.success('用户已禁用')
      fetchUsers()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

// 启用用户
const handleEnable = async (row) => {
  try {
    const res = await fetch(`/api/admin/users/${row.user_id}/disable`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_disabled: 0, reason: '' })
    })

    const data = await res.json()
    if (data.success) {
      ElMessage.success('用户已启用')
      fetchUsers()
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 重置密码
const handleResetPassword = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要重置用户 ${row.username} 的密码吗？`, '确认重置', {
      type: 'warning'
    })

    const res = await fetch(`/api/admin/users/${row.user_id}/reset-password`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    })

    const data = await res.json()
    if (data.success) {
      ElMessage.success(`密码已重置为: ${data.new_password}`)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重置失败')
    }
  }
}

// 导出用户
const exportUsers = () => {
  ElMessage.info('导出功能开发中')
}

// 页面加载
onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.admin-users {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.filter-card {
  margin-bottom: 20px;
}

.avatar-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.avatar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.avatar-tips {
  color: #909399;
  font-size: 12px;
}

.avatar-gallery {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.gallery-item {
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  border: 2px solid transparent;
  transition: all 0.3s;
  display: flex;
  justify-content: center;
}

.gallery-item:hover {
  border-color: #409eff;
  background: #ecf5ff;
}

.gallery-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.el-pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>