<template>
  <div class="admin-questions">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>📚 题库管理</h2>
      <div class="header-actions">
        <el-button @click="fetchQuestions">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <el-button @click="exportQuestions">
          <el-icon><Download /></el-icon> 导出
        </el-button>
      </div>
    </div>

    <!-- 筛选区 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="科目">
          <el-select v-model="filters.subject_id" clearable placeholder="全部科目">
            <el-option label="行测" :value="1" />
            <el-option label="申论" :value="2" />
            <el-option label="公专" :value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="题型">
          <el-select v-model="filters.type_id" clearable placeholder="全部题型">
            <el-option v-for="t in typeList" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-select v-model="filters.difficulty" clearable placeholder="全部难度">
            <el-option label="1星" :value="1" />
            <el-option label="2星" :value="2" />
            <el-option label="3星" :value="3" />
            <el-option label="4星" :value="4" />
            <el-option label="5星" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item label="审核状态">
          <el-select v-model="filters.audit_status" clearable placeholder="全部状态">
            <el-option label="待审核" :value="0" />
            <el-option label="已通过" :value="1" />
            <el-option label="已驳回" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="搜索">
          <el-input v-model="filters.keyword" placeholder="题目内容" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchQuestions">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 统计概览 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="5">
        <el-card shadow="hover">
          <div class="stat-item">
            <span class="stat-value">{{ stats.total }}</span>
            <span class="stat-label">总题目数</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card shadow="hover">
          <div class="stat-item">
            <span class="stat-value">{{ stats.xingce }}</span>
            <span class="stat-label">行测</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card shadow="hover">
          <div class="stat-item">
            <span class="stat-value">{{ stats.shenlun }}</span>
            <span class="stat-label">申论</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card shadow="hover">
          <div class="stat-item">
            <span class="stat-value">{{ stats.gongzhuan }}</span>
            <span class="stat-label">公专</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover">
          <div class="stat-item">
            <span class="stat-value warning">{{ stats.pending }}</span>
            <span class="stat-label">待审核</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 题目列表 -->
    <el-card>
      <el-table :data="questionList" stripe v-loading="loading">
        <el-table-column prop="question_id" label="ID" width="70" sortable />
        <el-table-column label="科目" width="80">
          <template #default="{ row }">
            <el-tag>{{ row.subject_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="题目内容" min-width="300" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="question-content" @click="previewQuestion(row)">
              {{ row.question_content }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="type_name" label="题型" width="80" />
        <el-table-column label="难度" width="100">
          <template #default="{ row }">
            <el-rate v-model="row.difficulty" disabled :max="5" />
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="100" show-overflow-tooltip />
        <el-table-column label="审核状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getAuditStatusType(row.audit_status)">
              {{ getAuditStatusName(row.audit_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'">
              {{ row.status === 1 ? '正常' : '已归档' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="previewQuestion(row)">预览</el-button>
            <el-button type="warning" link @click="editQuestion(row)">编辑</el-button>
            <template v-if="row.audit_status === 0">
              <el-button type="success" link @click="auditPass(row)">通过</el-button>
              <el-button type="danger" link @click="showRejectDialog(row)">驳回</el-button>
            </template>
            <template v-else-if="row.audit_status === 1">
              <el-tag type="success" size="small">已通过</el-tag>
            </template>
            <template v-else-if="row.audit_status === 2">
              <el-tag type="danger" size="small">已驳回</el-tag>
            </template>
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
        @size-change="fetchQuestions"
        @current-change="fetchQuestions"
      />
    </el-card>

    <!-- 题目预览弹窗 -->
    <el-dialog v-model="previewVisible" title="题目预览" width="800px">
      <div class="question-preview">
        <div class="preview-header">
          <el-tag>题目ID: {{ previewData.question_id }}</el-tag>
          <el-tag type="info">{{ previewData.subject_name }}</el-tag>
          <el-tag>{{ previewData.type_name }}</el-tag>
          <el-tag :type="getAuditStatusType(previewData.audit_status)">
            {{ getAuditStatusName(previewData.audit_status) }}
          </el-tag>
        </div>

        <el-divider />

        <div class="preview-content">
          <h4>题目内容</h4>
          <div class="content-box" v-html="previewData.full_content"></div>
        </div>

        <div class="preview-options" v-if="previewData.options && previewData.options.length">
          <h4>选项</h4>
          <div v-for="(opt, index) in previewData.options" :key="index" class="option-item">
            <span class="option-label">{{ String.fromCharCode(65 + index) }}.</span>
            <span class="option-content">{{ opt }}</span>
          </div>
        </div>

        <div class="preview-answer">
          <h4>正确答案</h4>
          <div class="answer-box">{{ previewData.answer }}</div>
        </div>

        <div class="preview-analysis">
          <h4>答案解析</h4>
          <div class="analysis-box" v-html="previewData.answer_analysis"></div>
        </div>

        <div class="preview-meta">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="来源">{{ previewData.source || '-' }}</el-descriptions-item>
            <el-descriptions-item label="年份">{{ previewData.year || '-' }}</el-descriptions-item>
            <el-descriptions-item label="分值">{{ previewData.score }}分</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDateTime(previewData.create_time) }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-dialog>

    <!-- 题目编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑题目" width="900px">
      <el-form :model="editForm" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="科目">
              <el-select v-model="editForm.subject_id" @change="onSubjectChange">
                <el-option label="行测" :value="1" />
                <el-option label="申论" :value="2" />
                <el-option label="公专" :value="3" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="题型">
              <el-select v-model="editForm.type_id">
                <el-option v-for="t in filteredTypeList" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="题目内容">
          <el-input v-model="editForm.question_content" type="textarea" :rows="4" />
        </el-form-item>

        <el-form-item label="选项">
          <div v-for="(opt, index) in editForm.options" :key="index" class="option-row">
            <span class="option-prefix">{{ String.fromCharCode(65 + index) }}.</span>
            <el-input v-model="editForm.options[index]" style="flex: 1" />
            <el-button type="danger" circle @click="removeOption(index)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <el-button @click="addOption">+ 添加选项</el-button>
        </el-form-item>

        <el-form-item label="正确答案">
          <el-input v-model="editForm.answer" />
        </el-form-item>

        <el-form-item label="答案解析">
          <el-input v-model="editForm.answer_analysis" type="textarea" :rows="3" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="难度">
              <el-rate v-model="editForm.difficulty" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="来源">
              <el-input v-model="editForm.source" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="年份">
              <el-input-number v-model="editForm.year" :min="2000" :max="2030" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存修改</el-button>
      </template>
    </el-dialog>

    <!-- 驳回原因弹窗 -->
    <el-dialog v-model="rejectDialogVisible" title="驳回原因" width="500px">
      <el-form :model="rejectForm" label-width="80px">
        <el-form-item label="驳回原因" required>
          <el-select v-model="rejectForm.reason_type" placeholder="选择常见原因" style="width: 100%; margin-bottom: 10px;">
            <el-option label="题目内容有误" value="内容有误" />
            <el-option label="选项不正确" value="选项问题" />
            <el-option label="解析不准确" value="解析问题" />
            <el-option label="重复题目" value="重复题目" />
            <el-option label="难度不合适" value="难度问题" />
            <el-option label="格式不规范" value="格式问题" />
            <el-option label="其他原因" value="其他" />
          </el-select>
          <el-input
            v-model="rejectForm.comment"
            type="textarea"
            :rows="3"
            placeholder="请输入详细的驳回原因（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="submitReject">确认驳回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// 加载状态
const loading = ref(false)

// 分页
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 筛选条件
const filters = ref({
  subject_id: null,
  type_id: null,
  difficulty: null,
  audit_status: null,
  keyword: ''
})

// 题目列表
const questionList = ref([])

// 题型列表
const typeList = ref([])

// 统计数据
const stats = ref({
  total: 0,
  xingce: 0,
  shenlun: 0,
  gongzhuan: 0,
  pending: 0
})

// 预览弹窗
const previewVisible = ref(false)
const previewData = ref({})

// 编辑弹窗
const editVisible = ref(false)
const editForm = ref({
  question_id: null,
  subject_id: 1,
  type_id: null,
  question_content: '',
  options: [],
  answer: '',
  answer_analysis: '',
  difficulty: 3,
  source: '',
  year: 2026
})

// 驳回弹窗
const rejectDialogVisible = ref(false)
const rejectForm = ref({
  question_id: null,
  reason_type: '',
  comment: ''
})

// 根据科目筛选题型
const filteredTypeList = computed(() => {
  if (!filters.value.subject_id) return typeList.value
  return typeList.value.filter(t => t.subject_id === filters.value.subject_id)
})

// 获取审核状态类型
const getAuditStatusType = (status) => {
  const map = { 0: 'warning', 1: 'success', 2: 'danger' }
  return map[status] || 'info'
}

// 获取审核状态名称
const getAuditStatusName = (status) => {
  const map = { 0: '待审核', 1: '已通过', 2: '已驳回' }
  return map[status] || '未知'
}

// 格式化时间
const formatDateTime = (timeStr) => {
  if (!timeStr) return '-'
  return timeStr.replace('T', ' ').substring(0, 19)
}

// 加载题目列表
const fetchQuestions = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: currentPage.value,
      page_size: pageSize.value,
      sort_by: 'question_id',
      sort_order: 'asc'
    })
    if (filters.value.subject_id) params.append('subject_id', filters.value.subject_id)
    if (filters.value.type_id) params.append('type_id', filters.value.type_id)
    if (filters.value.difficulty) params.append('difficulty', filters.value.difficulty)
    if (filters.value.audit_status !== null) params.append('audit_status', filters.value.audit_status)
    if (filters.value.keyword) params.append('keyword', filters.value.keyword)

    const res = await fetch(`/api/admin/questions?${params}`)
    const data = await res.json()
    if (data.success) {
      questionList.value = data.items
      total.value = data.total
    }
  } catch (error) {
    ElMessage.error('加载题目列表失败')
  } finally {
    loading.value = false
  }
}

// 加载题型列表
const fetchTypes = async () => {
  try {
    const res = await fetch('/api/questions/types')
    const data = await res.json()
    if (data.success) {
      typeList.value = data.items
    }
  } catch (error) {
    console.error('加载题型失败')
  }
}

// 加载统计数据
const fetchStats = async () => {
  try {
    const res = await fetch('/api/admin/questions/stats')
    const data = await res.json()
    if (data.success) {
      stats.value = data
    }
  } catch (error) {
    console.error('加载统计数据失败')
  }
}

// 重置筛选
const resetFilters = () => {
  filters.value = {
    subject_id: null,
    type_id: null,
    difficulty: null,
    audit_status: null,
    keyword: ''
  }
  fetchQuestions()
}

// 预览题目
const previewQuestion = (row) => {
  previewData.value = { ...row }
  previewVisible.value = true
}

// 编辑题目
const editQuestion = async (row) => {
  try {
    const res = await fetch(`/api/admin/questions?keyword=${row.question_id}`)
    const data = await res.json()
    if (data.success && data.items.length > 0) {
      const question = data.items[0]
      editForm.value = {
        question_id: question.question_id,
        subject_id: question.subject_id,
        type_id: question.type_id,
        question_content: question.full_content || question.question_content,
        options: question.options || [],
        answer: question.answer,
        answer_analysis: question.answer_analysis || '',
        difficulty: question.difficulty || 3,
        source: question.source || '',
        year: question.year || 2026
      }
      editVisible.value = true
    }
  } catch (error) {
    ElMessage.error('获取题目信息失败')
  }
}

// 科目变更
const onSubjectChange = () => {
  editForm.value.type_id = null
}

// 添加选项
const addOption = () => {
  editForm.value.options.push('')
}

// 移除选项
const removeOption = (index) => {
  editForm.value.options.splice(index, 1)
}

// 提交编辑
const submitEdit = async () => {
  try {
    const res = await fetch(`/api/admin/questions/${editForm.value.question_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm.value)
    })

    const data = await res.json()
    if (data.success) {
      ElMessage.success('题目更新成功')
      editVisible.value = false
      fetchQuestions()
    } else {
      ElMessage.error(data.message || '更新失败')
    }
  } catch (error) {
    ElMessage.error('更新失败：' + error.message)
  }
}

// 审核通过
const auditPass = async (row) => {
  try {
    await ElMessageBox.confirm(`确定通过题目 ${row.question_id} 的审核吗？`, '审核确认', {
      type: 'success'
    })

    const res = await fetch(`/api/admin/questions/${row.question_id}/audit`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audit_status: 1,
        audit_comment: '审核通过'
      })
    })

    const data = await res.json()
    if (data.success) {
      ElMessage.success('审核通过')
      fetchQuestions()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

// 显示驳回弹窗
const showRejectDialog = (row) => {
  rejectForm.value = {
    question_id: row.question_id,
    reason_type: '',
    comment: ''
  }
  rejectDialogVisible.value = true
}

// 提交驳回
const submitReject = async () => {
  if (!rejectForm.value.reason_type) {
    ElMessage.warning('请选择驳回原因')
    return
  }

  try {
    const comment = rejectForm.value.reason_type +
      (rejectForm.value.comment ? '：' + rejectForm.value.comment : '')

    const res = await fetch(`/api/admin/questions/${rejectForm.value.question_id}/audit`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audit_status: 2,
        audit_comment: comment
      })
    })

    const data = await res.json()
    if (data.success) {
      ElMessage.success('已驳回')
      rejectDialogVisible.value = false
      fetchQuestions()
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 导出题目
const exportQuestions = () => {
  ElMessage.info('导出功能开发中')
}

// 页面加载
onMounted(() => {
  fetchQuestions()
  fetchTypes()
  fetchStats()
})
</script>

<style scoped>
.admin-questions {
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

.stats-row {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 10px 0;
}

.stat-value {
  display: block;
  font-size: 28px;
  font-weight: bold;
  color: #409eff;
}

.stat-value.warning {
  color: #e6a23c;
}

.stat-label {
  color: #909399;
  font-size: 14px;
}

.question-content {
  cursor: pointer;
  color: #409eff;
}

.question-content:hover {
  text-decoration: underline;
}

.el-pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 预览样式 */
.preview-header {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.preview-content,
.preview-options,
.preview-answer,
.preview-analysis {
  margin-bottom: 20px;
}

.preview-content h4,
.preview-options h4,
.preview-answer h4,
.preview-analysis h4 {
  margin-bottom: 10px;
  color: #303133;
}

.content-box,
.answer-box,
.analysis-box {
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
  line-height: 1.8;
}

.option-item {
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
  padding: 10px;
  background: #fafafa;
  border-radius: 4px;
}

.option-label {
  font-weight: bold;
  color: #409eff;
}

.preview-meta {
  margin-top: 20px;
}

/* 编辑弹窗样式 */
.option-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.option-prefix {
  font-weight: bold;
  color: #409eff;
  width: 20px;
}
</style>