<template>
  <div class="teacher-papers">
    <TeacherNavHeader activeNav="papers" @logout="handleLogout" />

    <div class="page-content">
      <div class="toolbar">
        <select class="filter-select" v-model="filterStatus" @change="loadPapers">
          <option value="">全部状态</option>
          <option value="DRAFT">草稿</option>
          <option value="PENDING">待审批</option>
          <option value="APPROVED">已审批</option>
          <option value="PUBLISHED">已发布</option>
          <option value="ENDED">回收站{{ endedCount > 0 ? ' (' + endedCount + ')' : '' }}</option>
        </select>
        <div class="toolbar-spacer"></div>
        <button class="btn-primary" @click="openCreate">+ 创建试卷</button>
        <button class="btn-ai" @click="openAiModal">🤖 AI智能组卷</button>
        <button class="btn-ai" @click="showSelfDesignModal = true">📝 自设计题目</button>
      </div>

      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr><th>试卷名称</th><th>科目</th><th>题数</th><th>总分</th><th>状态</th><th>创建时间</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="p in papers" :key="p.paper_id">
              <td>{{ p.paper_name }}</td>
              <td>{{ p.subject_name || subjectName(p.subject_id) }}</td>
              <td>{{ p.question_count }}</td>
              <td>{{ p.total_score }}</td>
              <td><span :class="statusClass(p.paper_type)">{{ statusLabel(p.paper_type) }}</span></td>
              <td>{{ formatTime(p.create_time) }}</td>
              <td class="td-actions">
                <template v-if="p.paper_type === 'ENDED'">
                  <button class="btn-sm btn-approve" @click="restorePaper(p.paper_id)">恢复</button>
                  <button class="btn-sm btn-danger" @click="permanentDelete(p.paper_id)">彻底删除</button>
                </template>
                <template v-else>
                  <button class="btn-sm" @click="openPreview(p)">预览</button>
                  <button class="btn-sm" @click="openEdit(p)" v-if="p.paper_type === 'DRAFT'">📝 编辑题目</button>
                  <button class="btn-sm btn-publish" @click="openPublish(p)" v-if="(p.paper_type === 'DRAFT' || p.paper_type === 'APPROVED') && p.question_count > 0">🚀 发布</button>
                  <button class="btn-sm btn-danger" @click="deletePaper(p)" v-if="p.paper_type !== 'PUBLISHED'">删除</button>
                  <span v-if="p.paper_type === 'PUBLISHED'" class="btn-sm btn-published" title="已发布的试卷不可删除">已发布</span>
                </template>
              </td>
            </tr>
            <tr v-if="papers.length === 0">
              <td colspan="7" style="text-align:center; color:#909399; padding:30px;">暂无试卷，点击「+ 创建试卷」开始</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="pagination" v-if="total > pageSize">
        <button class="btn-sm" :disabled="page <= 1" @click="prevPage">上一页</button>
        <span class="page-info">第 {{ page }} / {{ totalPages }} 页 · 共 {{ total }} 套</span>
        <button class="btn-sm" :disabled="page >= totalPages" @click="nextPage">下一页</button>
      </div>
    </div>

    <!-- 三步流程：编辑试卷大弹窗 -->
    <div class="modal-overlay" v-if="showEditModal" @click.self="closeEdit">
      <div class="modal-content create-paper-dialog">
        <h3>{{ editStep === 1 ? '创建试卷（步骤 1/3）' : editStep === 2 ? '添加题目（步骤 2/3）' : '预览与发布（步骤 3/3）' }}</h3>
        <div class="dialog-body">
          <!-- Step 1：基本信息 -->
          <div v-if="editStep === 1">
            <div class="form-row">
              <div class="form-group"><label>试卷名称</label><input class="form-input" v-model="createForm.paper_name" placeholder="如：2025年公安联考行测模拟卷" /></div>
              <div class="form-group"><label>考试年份</label><input class="form-input" type="number" v-model.number="createForm.year" /></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>科目</label><select class="form-input" v-model="createForm.subject_id"><option :value="1">行测</option><option :value="2">申论</option><option :value="3">公专</option></select></div>
              <div class="form-group"><label>试卷类型</label><select class="form-input" v-model="createForm.exam_type"><option value="SIMULATION">模拟考试</option><option value="PRACTICE">练习</option><option value="FORMAL">正式考试</option></select></div>
              <div class="form-group"><label>推荐用时(分钟)</label><input class="form-input" type="number" v-model.number="createForm.duration" /></div>
              <div class="form-group"><label>难度</label><select class="form-input" v-model.number="createForm.difficulty"><option :value="1">1 简单</option><option :value="2">2 较易</option><option :value="3">3 一般</option><option :value="4">4 较难</option><option :value="5">5 困难</option></select></div>
            </div>
          </div>

          <!-- Step 2：添加题目 -->
          <div v-else-if="editStep === 2" class="add-q-layout">
            <div class="add-q-left">
              <div class="add-q-search">
                <input class="search-input" v-model="pkKeyword" placeholder="搜索题干关键词..." @keyup.enter="searchPicker" />
                <button class="btn-search" @click="searchPicker">搜索</button>
              </div>
              <div class="add-q-filters">
                <select class="filter-select" v-model="pkSubject" @change="onSubjectChange"><option value="">全部科目</option><option :value="1">行测</option><option :value="2">申论</option><option :value="3">公专</option></select>
                <select class="filter-select" v-model="pkType"><option value="">全部题型</option><option v-for="t in questionTypes" :key="t.type_name" :value="t.type_name">{{ t.type_name }}</option></select>
                <select class="filter-select" v-model="pkDifficulty"><option value="">全部难度</option><option :value="1">简单</option><option :value="2">较易</option><option :value="3">一般</option><option :value="4">较难</option><option :value="5">困难</option></select>
                <select class="filter-select" v-model="pkPoint"><option value="">全部知识点</option><option v-for="kp in knowledgePoints" :key="kp.point_id" :value="kp.point_id">{{ kp.point_name }}</option></select>
                <button class="btn-sm" @click="searchPicker">筛选</button>
              </div>
              <div class="add-q-list">
                <div v-for="q in availableQuestions" :key="q.question_id" class="add-q-item">
                  <input type="checkbox" :checked="pkChecked.includes(q.question_id)" @change="toggleCheck(q.question_id)" />
                  <div class="add-q-content" @click="previewQuestionDetail(q)">{{ truncate(q.question_content, 60) }}</div>
                  <span :class="['type-badge', typeBadgeClass(q.type_name)]">{{ q.type_name || '-' }}</span>
                  <span class="pk-diff" :title="'难度' + q.difficulty">{{ '★'.repeat(q.difficulty || 0) }}</span>
                </div>
                <div v-if="availableQuestions.length === 0 && pkSearched" class="empty-hint">暂无匹配题目</div>
              </div>
              <div class="picker-bar">
                <button class="btn-sm" @click="toggleAll">{{ pkChecked.length === availableQuestions.length && availableQuestions.length > 0 ? '取消全选' : '全选当前页' }}</button>
                <button class="btn-primary" @click="addChecked" :disabled="pkChecked.length === 0">添加选中 ({{ pkChecked.length }})</button>
              </div>
            </div>
            <div class="add-q-right">
              <h4>已选题目 ({{ paperQuestions.length }})</h4>
              <div class="selected-list">
                <div v-for="(pq, idx) in paperQuestions" :key="pq.question_id" class="selected-item">
                  <span class="sq-order">{{ idx + 1 }}</span>
                  <span class="sq-content" @click="previewQuestionDetail(pq)" :title="pq.question_content">{{ truncate(pq.question_content, 40) }}</span>
                  <input class="sq-score" type="number" :value="pq.question_score" @change="updateScore(pq.question_id, $event)" min="1" max="100" />
                  <button class="sq-mini" @click="moveQuestion(idx, -1)" :disabled="idx === 0" title="上移">↑</button>
                  <button class="sq-mini" @click="moveQuestion(idx, 1)" :disabled="idx === paperQuestions.length - 1" title="下移">↓</button>
                  <button class="sq-mini" @click="replaceQuestion(pq.question_id)" title="换一题">🔄</button>
                  <span class="sq-remove" @click="removeQuestion(pq.question_id)">✕</span>
                </div>
                <div v-if="paperQuestions.length === 0" class="empty-hint">尚未添加题目</div>
              </div>
              <div class="add-q-total">题数: {{ paperQuestions.length }} / 总分: {{ paperTotalScore }}</div>
            </div>
          </div>

          <!-- Step 3：预览与发布 -->
          <div v-else>
            <div class="preview-meta">
              <span>科目：{{ subjectName(createForm.subject_id) }}</span>
              <span>时长：{{ createForm.duration }} 分钟</span>
              <span>总分：{{ paperTotalScore }}</span>
              <span>题数：{{ paperQuestions.length }}</span>
            </div>
            <div class="preview-list">
              <div v-for="(q, idx) in paperQuestions" :key="q.question_id" class="preview-item">
                <div class="preview-q-title">{{ idx + 1 }}. ({{ q.type_name }}，{{ q.question_score }}分) {{ q.question_content }}</div>
                <div class="preview-options" v-if="q.options && q.options.length">
                  <div v-for="opt in q.options" :key="opt.key">{{ opt.key }}. {{ opt.value }}</div>
                </div>
                <div class="preview-answer">正确答案：{{ q.answer }}</div>
              </div>
              <div v-if="paperQuestions.length === 0" class="empty-hint">暂无题目，请返回上一步添加</div>
            </div>
            <div class="publish-group">
              <label class="publish-label">发布选项：</label>
              <label><input type="radio" value="draft" v-model="publishChoice" /> 保存为草稿（暂不发布）</label>
              <label><input type="radio" value="past_paper" v-model="publishChoice" /> 发布到「历年试卷」（免审批）</label>
              <label><input type="radio" value="mock_exam" v-model="publishChoice" /> 发布到「小模考」（需审批）</label>
            </div>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn-sm" v-if="editStep === 2" @click="editStep = 1">← 上一步</button>
          <button class="btn-sm" v-if="editStep === 3" @click="editStep = 2">← 上一步</button>
          <button class="btn-sm" @click="closeEdit">取消</button>
          <div class="footer-spacer"></div>
          <button class="btn-primary" v-if="editStep === 1" @click="step1Next" :disabled="creating">{{ creating ? '创建中...' : '下一步 →' }}</button>
          <button class="btn-primary" v-if="editStep === 2" @click="editStep = 3">下一步 →</button>
          <button class="btn-primary" v-if="editStep === 3" @click="finishCreate">{{ publishing ? '发布中...' : '确认' }}</button>
        </div>
      </div>
    </div>

    <!-- AI 智能组卷 三步流程弹窗（设计文档 §2.3 三步流程 1500px） -->
    <div class="modal-overlay" v-if="showAiModal" @click.self="showAiModal = false">
      <div class="modal-content ai-modal-large">
        <h3>🤖 AI智能组卷 {{ aiStep === 1 ? '— 步骤 1/3：组卷参数设置' : aiStep === 2 ? '— 步骤 2/3：组卷结果预览' : '— 步骤 3/3：发布设置' }}</h3>

        <!-- 步骤1：参数设置 -->
        <div v-if="aiStep === 1" class="ai-step-body">
          <div class="ai-form-grid">
            <div class="form-group"><label>试卷名称</label><input class="form-input" v-model="aiForm.paper_name" placeholder="如：智能组卷_20260818_143022" /></div>
            <div class="form-row">
              <div class="form-group"><label>科目</label><select class="form-input" v-model="aiForm.subject_id"><option :value="1">行测</option><option :value="2">申论</option><option :value="3">公专</option></select></div>
              <div class="form-group"><label>组卷来源</label><select class="form-input" v-model="aiForm.source"><option value="all">全部题库</option><option value="approved">已审批题目</option></select></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>总分</label><input class="form-input" type="number" v-model.number="aiForm.total_score" /></div>
              <div class="form-group"><label>时长(分钟)</label><input class="form-input" type="number" v-model.number="aiForm.duration" /></div>
            </div>
            <div class="form-group">
              <label>难度分布</label>
              <div class="difficulty-bar">
                <span>简单 {{ aiForm.easy_pct }}%</span>
                <input type="range" v-model.number="aiForm.easy_pct" min="0" max="80" /> 
                <span>一般 {{ aiForm.medium_pct }}%</span>
                <input type="range" v-model.number="aiForm.medium_pct" min="0" max="80" />
                <span>困难 {{ aiForm.hard_pct }}%</span>
              </div>
            </div>
            <div class="form-group">
              <label>题型配比（题量，0 表示不抽）</label>
              <div class="config-grid">
                <div class="config-item"><span class="config-label">单选题</span><input class="form-input config-input" type="number" v-model.number="aiForm.single" min="0" /><span class="config-hint">× {{ aiForm.single_score || 2 }}分</span></div>
                <div class="config-item"><span class="config-label">多选题</span><input class="form-input config-input" type="number" v-model.number="aiForm.multi" min="0" /><span class="config-hint">× {{ aiForm.multi_score || 3 }}分</span></div>
                <div class="config-item"><span class="config-label">判断题</span><input class="form-input config-input" type="number" v-model.number="aiForm.judge" min="0" /><span class="config-hint">× {{ aiForm.judge_score || 1 }}分</span></div>
                <div class="config-item"><span class="config-label">论述题</span><input class="form-input config-input" type="number" v-model.number="aiForm.essay" min="0" /><span class="config-hint">× {{ aiForm.essay_score || 4 }}分</span></div>
              </div>
              <div class="ai-preview-score">预估总题: {{ aiForm.single + aiForm.multi + aiForm.judge + aiForm.essay }} 题 · 预估总分: {{ (aiForm.single * (aiForm.single_score||2)) + (aiForm.multi * (aiForm.multi_score||3)) + (aiForm.judge * (aiForm.judge_score||1)) + (aiForm.essay * (aiForm.essay_score||4)) }} 分</div>
            </div>
          </div>
        </div>

        <!-- 步骤2：结果预览 -->
        <div v-else-if="aiStep === 2" class="ai-step-body">
          <div v-if="aiGenerating" class="ai-loading">
            <div class="ai-spinner"></div>
            <p>AI 正在智能组卷，请稍候...</p>
          </div>
          <div v-else-if="aiResultPapers.length > 0">
            <div class="ai-result-header">
              <span>✅ 已生成 {{ aiResultPapers.length }} 套备选试卷 &nbsp; 当前查看：第 {{ aiResultIndex + 1 }}/{{ aiResultPapers.length }} 套</span>
              <div class="ai-result-nav">
                <button class="btn-sm" @click="aiResultIndex = Math.max(0, aiResultIndex - 1)" :disabled="aiResultIndex === 0">上一套</button>
                <button class="btn-sm" @click="aiResultIndex = Math.min(aiResultPapers.length - 1, aiResultIndex + 1)" :disabled="aiResultIndex >= aiResultPapers.length - 1">下一套</button>
                <button class="btn-sm" @click="aiStep = 1">重新设置参数</button>
              </div>
            </div>
            <div class="ai-result-stats" v-if="currentAiPaper">
              <span>总分 {{ currentAiPaper.total_score || aiForm.total_score }}分</span>
              <span>共 {{ (currentAiPaper.questions || []).length }}题</span>
              <span>预计用时 {{ aiForm.duration }}分钟</span>
            </div>
            <div class="ai-preview-list">
              <div v-for="(q, idx) in (currentAiPaper.questions || [])" :key="q.question_id || idx" class="ai-preview-item">
                <div class="ai-q-header">
                  <span class="ai-q-num">{{ idx + 1 }}.</span>
                  <span class="ai-q-type">（{{ q.type_name }}，{{ q.question_score || 2 }}分）</span>
                  <button class="btn-mini" @click="aiReplaceQuestion(q, idx)" title="替换此题">🔄 换一题</button>
                  <button class="btn-mini btn-mini-danger" @click="aiRemoveQuestion(idx)" title="删除此题">✕</button>
                </div>
                <div class="ai-q-content">{{ q.question_content }}</div>
                <div class="ai-q-options" v-if="q.options && q.options.length">
                  <span v-for="opt in q.options" :key="opt.key">{{ opt.key }}. {{ opt.value }}</span>
                </div>
                <div class="ai-q-answer">正确答案：{{ q.answer }}</div>
              </div>
              <div v-if="(currentAiPaper.questions || []).length === 0" class="empty-hint">该试卷暂无题目</div>
            </div>
          </div>
          <div v-else class="empty-hint">组卷失败，请返回重新设置参数</div>
        </div>

        <!-- 步骤3：发布设置 -->
        <div v-else-if="aiStep === 3" class="ai-step-body">
          <div class="ai-publish-confirm">✅ 试卷已确认，共 {{ (currentAiPaper?.questions || []).length }} 题，总分 {{ aiForm.total_score }} 分</div>
          <div class="form-group">
            <label>发布选项：</label>
            <label class="radio-label"><input type="radio" value="draft" v-model="aiPublishTarget" /> 保存为草稿（暂不发布）</label>
            <label class="radio-label"><input type="radio" value="mock_exam" v-model="aiPublishTarget" /> 发布到「小模考」（需管理员审批）</label>
          </div>
          <div v-if="aiPublishTarget === 'mock_exam'" class="form-group">
            <label>模考开始时间：</label><input class="form-input" type="datetime-local" v-model="aiMockStartTime" />
            <label>规定完成时间：</label><input class="form-input" type="number" v-model.number="aiMockDuration" style="width:80px" /> 分钟
          </div>
        </div>

        <div class="dialog-footer">
          <button class="btn-sm" v-if="aiStep > 1 && !aiGenerating" @click="aiStep--">← 上一步</button>
          <button class="btn-sm" @click="showAiModal = false">取消</button>
          <div class="footer-spacer"></div>
          <button class="btn-primary" v-if="aiStep === 1" @click="doAiGenerate" :disabled="aiGenerating">{{ aiGenerating ? '组卷中...' : '生成试卷 →' }}</button>
          <button class="btn-primary" v-if="aiStep === 2 && !aiGenerating && aiResultPapers.length > 0" @click="aiStep = 3">下一步：发布 →</button>
          <button class="btn-primary" v-if="aiStep === 3" @click="doAiPublish" :disabled="aiPublishing">{{ aiPublishing ? '发布中...' : '确认发布' }}</button>
        </div>
      </div>
    </div>

    <!-- 自设计题目弹窗 -->
    <div class="modal-overlay" v-if="showSelfDesignModal" @click.self="showSelfDesignModal = false">
      <div class="modal-content self-design-modal">
        <h3>自设计题目</h3>
        <div class="form-row">
          <div class="form-group"><label>科目</label><select class="form-input" v-model="selfDesignForm.subject_id"><option :value="1">行测</option><option :value="2">申论</option><option :value="3">公专</option></select></div>
          <div class="form-group"><label>题型</label><select class="form-input" v-model="selfDesignForm.type_name" @change="onSelfTypeChange"><option>单选题</option><option>多选题</option><option>判断题</option><option>填空题</option><option>论述题</option><option>写作题</option><option>情境题</option></select></div>
          <div class="form-group"><label>难度</label><select class="form-input" v-model.number="selfDesignForm.difficulty"><option :value="1">1 简单</option><option :value="2">2 较易</option><option :value="3">3 一般</option><option :value="4">4 较难</option><option :value="5">5 困难</option></select></div>
          <div class="form-group"><label>分值</label><input class="form-input" type="number" v-model.number="selfDesignForm.score" min="1" max="100" /></div>
        </div>
        <div class="form-group"><label>题干{{ selfDesignForm.type_name === '情境题' ? '（情境描述）' : '' }}</label><textarea class="form-input textarea" v-model="selfDesignForm.question_content" rows="3"></textarea></div>
        <div class="form-group" v-if="needOptions(selfDesignForm.type_name)">
          <label>选项</label>
          <div v-for="(opt, idx) in selfDesignForm.options" :key="idx" class="option-row">
            <span class="option-key">{{ opt.key }}</span>
            <input class="form-input" v-model="opt.value" :placeholder="'选项 ' + opt.key" />
            <span class="sq-remove" @click="removeOption(idx)" v-if="selfDesignForm.options.length > 2">✕</span>
          </div>
          <button class="btn-sm" @click="addOption" v-if="selfDesignForm.options.length < 6">+ 添加选项</button>
        </div>
        <div class="form-group"><label>正确答案 <span v-if="needOptions(selfDesignForm.type_name)" class="hint">(单选填 A，多选填 ABD)</span></label><input class="form-input" v-model="selfDesignForm.answer" /></div>
        <div class="form-group"><label>答案解析</label><textarea class="form-input textarea" v-model="selfDesignForm.answer_analysis" rows="2"></textarea></div>
        <button class="btn-primary" @click="doSelfDesign" :disabled="selfDesignSubmitting">{{ selfDesignSubmitting ? '保存中...' : '保存题目' }}</button>
      </div>
    </div>

    <!-- 发布目标弹窗 -->
    <div class="modal-overlay" v-if="showPublishModal" @click.self="showPublishModal = false">
      <div class="modal-content publish-modal">
        <h3>发布试卷</h3>
        <p class="publish-desc">选择发布目标：</p>
        <div :class="['publish-option', { active: publishTarget === 'past_paper' }]" @click="publishTarget = 'past_paper'">
          <strong>📋 历年试卷</strong><span>免审批，学生可自主练习</span>
        </div>
        <div :class="['publish-option', { active: publishTarget === 'mock_exam' }]" @click="publishTarget = 'mock_exam'">
          <strong>📝 小模考</strong><span>需管理员审批后统一发布</span>
        </div>
        <div class="modal-actions">
          <button class="btn-sm" @click="showPublishModal = false">取消</button>
          <button class="btn-primary" @click="doPublish">确认发布</button>
        </div>
      </div>
    </div>

    <!-- 试卷预览弹窗（只读） -->
    <div class="modal-overlay" v-if="showPreviewModal" @click.self="showPreviewModal = false">
      <div class="modal-content preview-modal">
        <h3>{{ previewPaper.paper_name }}</h3>
        <div class="preview-meta">
          <span>科目：{{ previewPaper.subject_name }}</span>
          <span>时长：{{ previewPaper.duration }} 分钟</span>
          <span>总分：{{ previewPaper.total_score }}</span>
          <span>题数：{{ previewPaper.question_count }}</span>
          <span>状态：{{ statusLabel(previewPaper.paper_type) }}</span>
        </div>
        <div class="preview-list" v-if="previewQuestions.length > 0">
          <div v-for="(q, idx) in previewQuestions" :key="q.question_id" class="preview-item">
            <div class="preview-q-title">{{ idx + 1 }}. ({{ q.type_name }}，{{ q.question_score }}分) {{ q.question_content }}</div>
            <div class="preview-options" v-if="q.options && q.options.length">
              <div v-for="opt in q.options" :key="opt.key">{{ opt.key }}. {{ opt.value }}</div>
            </div>
            <div class="preview-answer">正确答案：{{ q.answer }}</div>
            <div class="preview-analysis" v-if="q.answer_analysis">解析：{{ q.answer_analysis }}</div>
          </div>
        </div>
        <div class="empty-hint" v-else-if="!previewLoading">该试卷暂无题目</div>
        <div class="empty-hint" v-else>加载中...</div>
        <button class="btn-primary" @click="showPreviewModal = false">关闭</button>
      </div>
    </div>

    <!-- 题目详情弹窗 -->
    <div class="modal-overlay" v-if="showQuestionDetail" @click.self="showQuestionDetail = false">
      <div class="modal-content preview-modal">
        <h3>题目详情</h3>
        <div class="preview-q-title">{{ detailQuestion.type_name }} · 难度 {{ detailQuestion.difficulty }} · {{ detailQuestion.subject_name }}</div>
        <div class="preview-q-title" style="font-weight:400">{{ detailQuestion.question_content }}</div>
        <div class="preview-options" v-if="detailQuestion.options && detailQuestion.options.length">
          <div v-for="opt in detailQuestion.options" :key="opt.key">{{ opt.key }}. {{ opt.value }}</div>
        </div>
        <div class="preview-answer">正确答案：{{ detailQuestion.answer }}</div>
        <div class="preview-analysis" v-if="detailQuestion.answer_analysis">解析：{{ detailQuestion.answer_analysis }}</div>
        <button class="btn-primary" @click="showQuestionDetail = false">关闭</button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useProvider } from '@vtj/renderer';
import TeacherNavHeader from './TeacherNavHeader.vue';

export default defineComponent({
  name: 'TeacherPapers',
  components: { TeacherNavHeader },
  setup() {
    const provider = useProvider({ id: 'teacher_papers', version: '1787100000000' });
    const router = useRouter();
    const auth = (window as any).__VTJ_AUTH__;
    const papers: any = ref([]);
    const filterStatus = ref('');
    const page = ref(1);
    const pageSize = ref(20);
    const total = ref(0);
    const endedCount = ref(0);

    // 三步流程编辑
    const showEditModal = ref(false);
    const editStep = ref(1);
    const editorPaperId = ref(0);
    const creating = ref(false);
    const publishing = ref(false);
    const publishChoice = ref('draft');
    const createForm = ref({ paper_name: '', year: new Date().getFullYear(), subject_id: 1, exam_type: 'SIMULATION', duration: 120, difficulty: 3, total_score: 100 });
    const paperQuestions: any = ref([]);

    // 题目选择器
    const questionTypes: any = ref([]);
    const knowledgePoints: any = ref([]);
    const pkKeyword = ref('');
    const pkSubject = ref('');
    const pkType = ref('');
    const pkDifficulty = ref('');
    const pkPoint = ref('');
    const pkChecked: any = ref([]);
    const pkSearched = ref(false);
    const availableQuestions: any = ref([]);

    // AI 组卷（三步流程）
    const showAiModal = ref(false);
    const aiStep = ref(1);
    const aiGenerating = ref(false);
    const aiPublishing = ref(false);
    const aiPublishTarget = ref('draft');
    const aiMockStartTime = ref('');
    const aiMockDuration = ref(120);
    const aiResultPapers: any = ref([]);
    const aiResultIndex = ref(0);
    const currentAiPaper = computed(() => aiResultPapers.value[aiResultIndex.value] || null);
    const aiForm = ref({
      paper_name: '', subject_id: 1, source: 'all', total_score: 100, duration: 120,
      easy_pct: 20, medium_pct: 60, hard_pct: 20,
      single: 30, multi: 10, judge: 10, essay: 5,
      single_score: 2, multi_score: 3, judge_score: 1, essay_score: 4,
    });

    // 自设计
    const showSelfDesignModal = ref(false);
    const selfDesignSubmitting = ref(false);
    const selfDesignForm = ref({
      subject_id: 1, type_name: '单选题', question_content: '',
      options: [{ key: 'A', value: '' }, { key: 'B', value: '' }, { key: 'C', value: '' }, { key: 'D', value: '' }],
      answer: '', answer_analysis: '', difficulty: 3, score: 5,
    });

    // 发布
    const showPublishModal = ref(false);
    const publishTarget = ref('past_paper');
    const publishingPaperId = ref(0);

    // 预览
    const showPreviewModal = ref(false);
    const previewLoading = ref(false);
    const previewPaper: any = ref({});
    const previewQuestions: any = ref([]);

    // 题目详情
    const showQuestionDetail = ref(false);
    const detailQuestion: any = ref({});

    // 题目统计
    const questionStats = ref({ total: 0, published: 0 });

    const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
    const paperTotalScore = computed(() => paperQuestions.value.reduce((s: number, q: any) => s + (Number(q.question_score) || 0), 0));

    onMounted(async () => {
      await Promise.all([loadPapers(), loadQuestionTypes(), loadQuestionStats(), loadEndedCount()]);
    });

    function apiFetch(url: string, options?: any) {
      return auth.apiFetch(url, options);
    }

    // ========== 题目统计 ==========
    async function loadQuestionStats() {
      try {
        const res = await apiFetch('/api/teacher/questions/stats');
        const data = await res.json();
        if (data.success) {
          questionStats.value = { total: data.total, published: data.published };
        }
      } catch (e) { console.error('加载题目统计失败:', e); }
    }

    // ========== 回收站统计 ==========
    async function loadEndedCount() {
      try {
        const res = await apiFetch('/api/teacher/papers/stats');
        const data = await res.json();
        if (data.success) { endedCount.value = data.ended || 0; }
      } catch (e) { console.error('加载试卷统计失败:', e); }
    }

    // ========== 列表 ==========
    async function loadPapers() {
      try {
        const params = new URLSearchParams();
        params.append('page', String(page.value));
        params.append('page_size', String(pageSize.value));
        if (filterStatus.value) params.append('status', filterStatus.value);
        const res = await apiFetch('/api/teacher/papers?' + params.toString());
        const data = await res.json();
        if (data.success) { papers.value = data.items || []; total.value = data.total || 0; }
      } catch (e) { console.error('加载试卷失败:', e); }
    }
    function prevPage() { if (page.value > 1) { page.value--; loadPapers(); } }
    function nextPage() { if (page.value < totalPages.value) { page.value++; loadPapers(); } }

    function statusLabel(t: string) {
      const map: Record<string, string> = { DRAFT: '草稿', PENDING: '待审批', APPROVED: '已审批', PUBLISHED: '已发布', ENDED: '已结束' };
      return map[t] || t;
    }
    function statusClass(t: string) {
      const map: Record<string, string> = { DRAFT: 'tag-gray', PENDING: 'tag-orange', APPROVED: 'tag-blue', PUBLISHED: 'tag-green', ENDED: 'tag-red' };
      return map[t] || '';
    }
    function subjectName(id: number) { const m: Record<number, string> = { 1: '行测', 2: '申论', 3: '公专' }; return m[id] || '-'; }
    function formatTime(t: string) { if (!t) return '-'; return t.substring(0, 16).replace('T', ' '); }
    function truncate(text: string, len: number) { return text && text.length > len ? text.substring(0, len) + '...' : text || ''; }
    function typeBadgeClass(name: string) {
      const map: Record<string, string> = { '单选题': 'badge-single', '多选题': 'badge-multi', '判断题': 'badge-single', '填空题': 'badge-single', '论述题': 'badge-essay', '写作题': 'badge-writing', '情境题': 'badge-essay' };
      return map[name] || 'badge-single';
    }

    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) auth.logout();
      router.push('/login');
    }

    // ========== 三步流程 ==========
    function openCreate() {
      editStep.value = 1;
      editorPaperId.value = 0;
      publishChoice.value = 'draft';
      createForm.value = { paper_name: '', year: new Date().getFullYear(), subject_id: 1, exam_type: 'SIMULATION', duration: 120, difficulty: 3, total_score: 100 };
      paperQuestions.value = [];
      pkChecked.value = [];
      showEditModal.value = true;
    }
    function openEdit(p: any) {
      editStep.value = 2;
      editorPaperId.value = p.paper_id;
      publishChoice.value = 'draft';
      createForm.value = { paper_name: p.paper_name, year: new Date().getFullYear(), subject_id: p.subject_id, exam_type: p.exam_type, duration: p.duration, difficulty: p.difficulty || 3, total_score: p.total_score };
      showEditModal.value = true;
      loadPaperQuestions(p.paper_id);
      searchPicker();
    }
    function closeEdit() { showEditModal.value = false; }

    async function step1Next() {
      if (!createForm.value.paper_name.trim()) { ElMessage.warning('请输入试卷名称'); return; }
      creating.value = true;
      try {
        const res = await apiFetch('/api/teacher/papers', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(createForm.value) });
        const data = await res.json();
        if (data.success) {
          editorPaperId.value = data.paper_id;
          editStep.value = 2;
          pkSubject.value = String(createForm.value.subject_id);
          onSubjectChange();
          searchPicker();
        } else { ElMessage.error(data.message || '创建失败'); }
      } catch (e) { ElMessage.error('创建失败'); }
      finally { creating.value = false; }
    }

    async function finishCreate() {
      publishing.value = true;
      try {
        if (publishChoice.value === 'past_paper') {
          await apiFetch(`/api/teacher/papers/${editorPaperId.value}/publish`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ publish_target: 'past_paper' }) });
          ElMessage.success('已发布到历年试卷');
        } else if (publishChoice.value === 'mock_exam') {
          await apiFetch(`/api/teacher/papers/${editorPaperId.value}/submit-approval`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paper_id: editorPaperId.value }) });
          ElMessage.success('已提交审批，待管理员审核');
        } else {
          ElMessage.success('已保存为草稿');
        }
        closeEdit();
        loadPapers();
      } catch (e) { ElMessage.error('操作失败'); }
      finally { publishing.value = false; }
    }

    // ========== 题目编辑器 ==========
    async function loadQuestionTypes() {
      try {
        const res = await apiFetch('/api/teacher/question-types');
        const data = await res.json();
        if (data.success) questionTypes.value = data.items || [];
      } catch (e) { console.error('加载题型失败:', e); }
    }
    async function onSubjectChange() {
      knowledgePoints.value = [];
      pkPoint.value = '';
      if (pkSubject.value) {
        try {
          const res = await apiFetch(`/api/teacher/knowledge-points?subject_id=${pkSubject.value}`);
          const data = await res.json();
          if (data.success) knowledgePoints.value = data.items || [];
        } catch (e) { console.error('加载知识点失败:', e); }
      }
    }
    async function searchPicker() {
      const params = new URLSearchParams();
      if (pkKeyword.value) params.append('keyword', pkKeyword.value);
      if (pkSubject.value) params.append('subject_id', pkSubject.value);
      if (pkType.value) params.append('type_name', pkType.value);
      if (pkDifficulty.value) params.append('difficulty', pkDifficulty.value);
      if (pkPoint.value) params.append('point_id', pkPoint.value);
      params.append('page_size', '50');
      try {
        const res = await apiFetch(`/api/teacher/questions?${params.toString()}`);
        const data = await res.json();
        if (data.success) { availableQuestions.value = data.items || []; pkSearched.value = true; }
      } catch (e) { console.error('搜索题目失败:', e); }
    }
    function toggleCheck(qid: number) {
      const i = pkChecked.value.indexOf(qid);
      if (i >= 0) pkChecked.value.splice(i, 1); else pkChecked.value.push(qid);
    }
    function toggleAll() {
      if (pkChecked.value.length === availableQuestions.value.length && availableQuestions.value.length > 0) pkChecked.value = [];
      else pkChecked.value = availableQuestions.value.map((q: any) => q.question_id);
    }
    async function addChecked() {
      if (editorPaperId.value === 0) { ElMessage.warning('请先完成上一步'); return; }
      const items = pkChecked.value.map((qid: number, idx: number) => ({ question_id: qid, question_order: paperQuestions.value.length + idx + 1, question_score: 5 }));
      try {
        await apiFetch(`/api/teacher/papers/${editorPaperId.value}/questions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ questions: items }) });
        pkChecked.value = [];
        await loadPaperQuestions(editorPaperId.value);
      } catch (e) { ElMessage.error('添加失败'); }
    }
    async function loadPaperQuestions(paperId: number) {
      try {
        const res = await apiFetch(`/api/teacher/papers/${paperId}`);
        const data = await res.json();
        if (data.success) { paperQuestions.value = data.questions || []; createForm.value.total_score = data.paper?.total_score || 0; }
      } catch (e) { console.error('加载试卷题目失败:', e); }
    }
    async function removeQuestion(qid: number) {
      try {
        await apiFetch(`/api/teacher/papers/${editorPaperId.value}/questions/${qid}`, { method: 'DELETE' });
        await loadPaperQuestions(editorPaperId.value);
      } catch (e) { ElMessage.error('移除失败'); }
    }
    async function replaceQuestion(qid: number) {
      try {
        const res = await apiFetch(`/api/teacher/papers/${editorPaperId.value}/questions/${qid}/replace`, { method: 'POST' });
        const data = await res.json();
        if (data.success) { ElMessage.success('已换一题'); await loadPaperQuestions(editorPaperId.value); }
        else ElMessage.error(data.message || '换一题失败');
      } catch (e) { ElMessage.error('换一题失败'); }
    }
    async function updateScore(qid: number, ev: any) {
      const score = Number(ev.target.value);
      if (!score || score <= 0) return;
      try {
        await apiFetch(`/api/teacher/papers/${editorPaperId.value}/questions/${qid}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question_score: score }) });
        await loadPaperQuestions(editorPaperId.value);
      } catch (e) { ElMessage.error('更新分值失败'); }
    }
    async function moveQuestion(idx: number, dir: number) {
      const arr = paperQuestions.value.map((q: any) => q.question_id);
      const j = idx + dir;
      if (j < 0 || j >= arr.length) return;
      [arr[idx], arr[j]] = [arr[j], arr[idx]];
      try {
        await apiFetch(`/api/teacher/papers/${editorPaperId.value}/questions/order`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question_ids: arr }) });
        await loadPaperQuestions(editorPaperId.value);
      } catch (e) { ElMessage.error('排序失败'); }
    }
    function previewQuestionDetail(q: any) {
      detailQuestion.value = { ...q, subject_name: subjectName(q.subject_id || createForm.value.subject_id) };
      showQuestionDetail.value = true;
    }

    // ========== AI 组卷（三步流程） ==========
    function openAiModal() {
      aiStep.value = 1;
      aiResultPapers.value = [];
      aiResultIndex.value = 0;
      aiPublishTarget.value = 'draft';
      showAiModal.value = true;
    }
    async function doAiGenerate() {
      const config: Record<string, number> = {};
      if (aiForm.value.single > 0) config['单选题'] = aiForm.value.single;
      if (aiForm.value.multi > 0) config['多选题'] = aiForm.value.multi;
      if (aiForm.value.judge > 0) config['判断题'] = aiForm.value.judge;
      if (aiForm.value.essay > 0) config['论述题'] = aiForm.value.essay;
      if (Object.keys(config).length === 0) { ElMessage.warning('请至少设置一种题型题量'); return; }
      aiGenerating.value = true;
      aiStep.value = 2;
      try {
        const res = await apiFetch('/api/teacher/papers/auto-generate', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            paper_name: aiForm.value.paper_name || `智能组卷_${Date.now()}`, subject_id: aiForm.value.subject_id,
            total_score: aiForm.value.total_score, duration: aiForm.value.duration,
            exam_type: 'SIMULATION', question_config: config,
          })
        });
        const data = await res.json();
        if (data.success) {
          // 加载生成的试卷题目，作为"备选试卷"
          const paperRes = await apiFetch(`/api/teacher/papers/${data.paper_id}`);
          const paperData = await paperRes.json();
          if (paperData.success) {
            aiResultPapers.value = [{ paper_id: data.paper_id, paper_name: data.paper_name || aiForm.value.paper_name, questions: paperData.questions || [], total_score: aiForm.value.total_score }];
          } else {
            aiResultPapers.value = [{ paper_id: data.paper_id, paper_name: aiForm.value.paper_name, questions: [], total_score: aiForm.value.total_score }];
          }
          aiResultIndex.value = 0;
        } else { ElMessage.error(data.message || '组卷失败'); aiStep.value = 1; }
      } catch (e) { ElMessage.error('组卷失败'); aiStep.value = 1; }
      finally { aiGenerating.value = false; }
    }
    function aiReplaceQuestion(q: any, idx: number) {
      ElMessage.info('替换功能开发中...');
    }
    function aiRemoveQuestion(idx: number) {
      if (currentAiPaper.value && currentAiPaper.value.questions) {
        currentAiPaper.value.questions.splice(idx, 1);
      }
    }
    async function doAiPublish() {
      if (!currentAiPaper.value) return;
      aiPublishing.value = true;
      try {
        if (aiPublishTarget.value === 'draft') {
          ElMessage.success('已保存为草稿');
        } else {
          await apiFetch(`/api/teacher/papers/${currentAiPaper.value.paper_id}/submit-approval`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paper_id: currentAiPaper.value.paper_id }) });
          ElMessage.success('已提交审批，待管理员审核');
        }
        showAiModal.value = false;
        loadPapers();
      } catch (e) { ElMessage.error('发布失败'); }
      finally { aiPublishing.value = false; }
    }

    // ========== 自设计 ==========
    function needOptions(t: string) { return t === '单选题' || t === '多选题' || t === '判断题'; }
    function addOption() { const keys = ['A', 'B', 'C', 'D', 'E', 'F']; const k = keys[selfDesignForm.value.options.length]; if (k) selfDesignForm.value.options.push({ key: k, value: '' }); }
    function removeOption(idx: number) { selfDesignForm.value.options.splice(idx, 1); }
    function onSelfTypeChange() {
      if (selfDesignForm.value.type_name === '判断题') {
        selfDesignForm.value.options = [{ key: 'A', value: '正确' }, { key: 'B', value: '错误' }];
        selfDesignForm.value.answer = '';
      } else if (selfDesignForm.value.type_name === '填空题') {
        selfDesignForm.value.options = [];
        selfDesignForm.value.answer = '';
      } else if (selfDesignForm.value.options.length === 0) {
        selfDesignForm.value.options = [{ key: 'A', value: '' }, { key: 'B', value: '' }, { key: 'C', value: '' }, { key: 'D', value: '' }];
      }
    }
    async function doSelfDesign() {
      if (!selfDesignForm.value.question_content.trim()) { ElMessage.warning('请输入题干'); return; }
      if (!selfDesignForm.value.answer.trim()) { ElMessage.warning('请输入正确答案'); return; }
      selfDesignSubmitting.value = true;
      try {
        let options = null;
        if (needOptions(selfDesignForm.value.type_name)) {
          options = selfDesignForm.value.options.filter((o: any) => o.value.trim() !== '').map((o: any) => ({ key: o.key, value: o.value }));
        }
        const res = await apiFetch('/api/teacher/questions', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            subject_id: selfDesignForm.value.subject_id, type_name: selfDesignForm.value.type_name,
            question_content: selfDesignForm.value.question_content, options,
            answer: selfDesignForm.value.answer, answer_analysis: selfDesignForm.value.answer_analysis,
            difficulty: selfDesignForm.value.difficulty, score: selfDesignForm.value.score,
          })
        });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('题目已保存到题库');
          showSelfDesignModal.value = false;
          selfDesignForm.value = {
            subject_id: 1, type_name: '单选题', question_content: '',
            options: [{ key: 'A', value: '' }, { key: 'B', value: '' }, { key: 'C', value: '' }, { key: 'D', value: '' }],
            answer: '', answer_analysis: '', difficulty: 3, score: 5,
          };
        } else { ElMessage.error(data.message || '保存失败'); }
      } catch (e) { ElMessage.error('保存失败'); }
      finally { selfDesignSubmitting.value = false; }
    }

    // ========== 发布 ==========
    function openPublish(p: any) { publishingPaperId.value = p.paper_id; publishTarget.value = 'past_paper'; showPublishModal.value = true; }
    async function doPublish() {
      const id = publishingPaperId.value;
      try {
        if (publishTarget.value === 'past_paper') {
          const res = await apiFetch(`/api/teacher/papers/${id}/publish`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ publish_target: 'past_paper' }) });
          const data = await res.json();
          if (data.success) { ElMessage.success('已发布到历年试卷'); showPublishModal.value = false; loadPapers(); }
          else ElMessage.error(data.message || '发布失败');
        } else {
          const res = await apiFetch(`/api/teacher/papers/${id}/submit-approval`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paper_id: id }) });
          const data = await res.json();
          if (data.success) { ElMessage.success('已提交审批'); showPublishModal.value = false; loadPapers(); }
          else ElMessage.error(data.message || '提交失败');
        }
      } catch (e) { ElMessage.error('操作失败'); }
    }

    // ========== 删除/回收站 =========
    async function deletePaper(p: any) {
      const statusText = statusLabel(p.paper_type);
      if (!confirm(`确定删除试卷「${p.paper_name}」？\n当前状态：${statusText}\n删除后可在回收站恢复。`)) {
        return;
      }
      try {
        const res = await apiFetch(`/api/teacher/papers/${p.paper_id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('已移入回收站');
          loadPapers();
        } else {
          ElMessage.error(data.detail || data.message || '删除失败');
        }
      } catch (e: any) {
        ElMessage.error('删除失败：' + (e.message || '未知错误'));
      }
    }
    async function restorePaper(id: number) {
      try { await apiFetch(`/api/teacher/papers/${id}/restore`, { method: 'POST' }); ElMessage.success('已恢复为草稿'); loadPapers(); }
      catch (e) { ElMessage.error('恢复失败'); }
    }
    async function permanentDelete(id: number) {
      if (confirm('彻底删除后不可恢复，确定？')) {
        try { await apiFetch(`/api/teacher/papers/${id}/permanent`, { method: 'DELETE' }); ElMessage.success('已彻底删除'); loadPapers(); }
        catch (e) { ElMessage.error('删除失败'); }
      }
    }

    // ========== 预览 ==========
    async function openPreview(p: any) {
      showPreviewModal.value = true; previewLoading.value = true; previewPaper.value = p; previewQuestions.value = [];
      try {
        const res = await apiFetch(`/api/teacher/papers/${p.paper_id}`);
        const data = await res.json();
        if (data.success) { previewPaper.value = data.paper; previewQuestions.value = data.questions || []; }
      } catch (e) { console.error('加载预览失败:', e); }
      finally { previewLoading.value = false; }
    }

    return {
      provider, papers, filterStatus, page, pageSize, total, totalPages,
      endedCount,
      questionStats,
      showEditModal, editStep, editorPaperId, creating, publishing, publishChoice, createForm, paperQuestions, paperTotalScore,
      questionTypes, knowledgePoints, pkKeyword, pkSubject, pkType, pkDifficulty, pkPoint, pkChecked, pkSearched, availableQuestions,
      showAiModal, aiStep, aiGenerating, aiPublishing, aiPublishTarget, aiMockStartTime, aiMockDuration, aiResultPapers, aiResultIndex, currentAiPaper, aiForm,
      showSelfDesignModal, selfDesignSubmitting, selfDesignForm,
      showPublishModal, publishTarget, publishingPaperId,
      showPreviewModal, previewLoading, previewPaper, previewQuestions,
      showQuestionDetail, detailQuestion,
      loadPapers, loadQuestionStats, loadEndedCount, prevPage, nextPage, statusLabel, statusClass, subjectName, formatTime, truncate, typeBadgeClass,
      openCreate, openEdit, closeEdit, step1Next, finishCreate,
      loadQuestionTypes, onSubjectChange, searchPicker, toggleCheck, toggleAll, addChecked, loadPaperQuestions,
      removeQuestion, replaceQuestion, updateScore, moveQuestion, previewQuestionDetail,
      openAiModal, doAiGenerate, aiReplaceQuestion, aiRemoveQuestion, doAiPublish, needOptions, addOption, removeOption, onSelfTypeChange, doSelfDesign,
      openPublish, doPublish, deletePaper, restorePaper, permanentDelete, openPreview, handleLogout,
    };
  }
});
</script>

<style scoped>
.teacher-papers { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.page-content { max-width: 1300px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; }
.toolbar-spacer { flex: 1; }
.filter-select { padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; }
.btn-primary { padding: 10px 22px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ai { padding: 10px 22px; background: #409EFF; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-search { padding: 8px 20px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.search-input { flex: 1; min-width: 180px; padding: 8px 14px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; }
.table-wrap { background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { padding: 12px 14px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; white-space: nowrap; }
.data-table td { padding: 12px 14px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.td-actions { white-space: nowrap; }
.btn-sm { padding: 5px 10px; border: 1px solid #d9d9d9; background: #fff; border-radius: 4px; cursor: pointer; margin-right: 4px; font-size: 13px; }
.btn-sm:hover { background: #f0f0f0; }
.btn-sm:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-sm.btn-approve { color: #409EFF; border-color: #b3d8ff; }
.btn-sm.btn-publish { color: #22c55e; border-color: #86efac; font-weight: 600; }
.btn-sm.btn-danger { color: #C41E3A; border-color: #f5c6cb; }
.btn-sm.btn-published { color: #909399; border-color: #dcdfe6; cursor: default; background: #f5f7fa; }
.tag-gray { padding: 3px 10px; border-radius: 10px; background: #f0f0f0; color: #666; font-size: 13px; }
.tag-orange { padding: 3px 10px; border-radius: 10px; background: #fff3e0; color: #E6A23C; font-size: 13px; }
.tag-blue { padding: 3px 10px; border-radius: 10px; background: #e3f2fd; color: #409EFF; font-size: 13px; }
.tag-green { padding: 3px 10px; border-radius: 10px; background: #e8f5e9; color: #22c55e; font-size: 13px; }
.tag-red { padding: 3px 10px; border-radius: 10px; background: #fce4ec; color: #C41E3A; font-size: 13px; }

.pagination { display: flex; gap: 12px; align-items: center; justify-content: center; margin-top: 16px; }
.page-info { font-size: 14px; color: #666; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: #fff; border-radius: 12px; padding: 28px; max-width: 500px; width: 90%; max-height: 85vh; overflow-y: auto; }
.modal-content h3 { color: #1A3C6D; margin: 0 0 20px; }
.modal-content h4 { color: #1A3C6D; margin: 0 0 10px; font-size: 15px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; margin-bottom: 6px; font-weight: 600; color: #1A3C6D; font-size: 14px; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; box-sizing: border-box; }
.textarea { resize: vertical; }
.form-row { display: flex; gap: 12px; }
.form-row .form-group { flex: 1; }
.hint { color: #909399; font-weight: 400; font-size: 12px; }
.option-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.option-key { font-weight: 600; color: #1A3C6D; min-width: 20px; }
.option-row .form-input { flex: 1; }
.config-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.config-label { font-size: 13px; color: #666; white-space: nowrap; }
.config-input { width: 70px; }

/* 大弹窗（三步流程） */
.create-paper-dialog { max-width: 1500px; max-height: 100vh; width: 95vw; height: 95vh; display: flex; flex-direction: column; margin: 0 auto; border-radius: 12px; overflow: hidden; }
.create-paper-dialog .dialog-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.create-paper-dialog .dialog-footer { padding: 14px 20px; border-top: 1px solid #ebeef5; background: #fafafa; display: flex; align-items: center; gap: 8px; }
.footer-spacer { flex: 1; }

/* 题目选择器 */
.add-q-layout { display: flex; gap: 20px; height: 100%; }
.add-q-left { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.add-q-right { width: 360px; flex-shrink: 0; display: flex; flex-direction: column; }
.add-q-search { display: flex; gap: 8px; margin-bottom: 8px; }
.add-q-filters { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.add-q-list { flex: 1; overflow-y: auto; border: 1px solid #e8e8e8; border-radius: 8px; min-height: 200px; }
.add-q-item { display: flex; align-items: center; gap: 8px; padding: 9px 12px; border-bottom: 1px solid #f0f0f0; cursor: pointer; }
.add-q-item:hover { background: #f0f7ff; }
.add-q-content { flex: 1; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pk-diff { color: #E6A23C; font-size: 12px; white-space: nowrap; }
.picker-bar { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.selected-list { flex: 1; overflow-y: auto; border: 1px solid #e8e8e8; border-radius: 8px; min-height: 200px; }
.selected-item { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.sq-order { color: #909399; font-weight: 600; min-width: 20px; }
.sq-content { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
.sq-score { padding: 2px 6px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 13px; width: 55px; }
.sq-mini { border: 1px solid #d9d9d9; background: #fff; border-radius: 4px; cursor: pointer; font-size: 12px; padding: 2px 5px; }
.sq-mini:hover { background: #f0f0f0; }
.sq-remove { color: #C41E3A; cursor: pointer; font-weight: 700; }
.sq-remove:hover { color: #ff0000; }
.add-q-total { margin: 10px 0; font-size: 14px; color: #666; font-weight: 600; }
.empty-hint { padding: 30px; text-align: center; color: #909399; }

/* 发布 */
.publish-modal { max-width: 420px; }
.publish-desc { color: #666; margin: 0 0 12px; }
.publish-option { border: 1px solid #d9d9d9; border-radius: 8px; padding: 14px; margin-bottom: 10px; cursor: pointer; display: flex; flex-direction: column; gap: 4px; }
.publish-option:hover { border-color: #409EFF; }
.publish-option.active { border-color: #409EFF; background: #f0f7ff; }
.publish-option strong { color: #1A3C6D; }
.publish-option span { color: #909399; font-size: 13px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
.publish-group { margin-top: 14px; display: flex; flex-direction: column; gap: 8px; }
.publish-label { font-weight: 600; color: #1A3C6D; margin-bottom: 4px; }
.publish-group label { display: flex; align-items: center; gap: 6px; cursor: pointer; }

/* 预览 */
.preview-modal { max-width: 800px; }
.preview-meta { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 16px; color: #666; font-size: 13px; }
.preview-list { max-height: 55vh; overflow-y: auto; border: 1px solid #e8e8e8; border-radius: 8px; padding: 12px; }
.preview-item { padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.preview-item:last-child { border-bottom: none; }
.preview-q-title { font-weight: 600; color: #1A3C6D; margin-bottom: 6px; }
.preview-options { color: #333; font-size: 14px; margin-bottom: 6px; }
.preview-answer { color: #22c55e; font-size: 13px; font-weight: 600; }
.preview-analysis { color: #909399; font-size: 13px; margin-top: 4px; }

.self-design-modal { max-width: 700px; }

/* AI 智能组卷 大弹窗（设计文档 §2.3 1500px） */
.ai-modal-large { max-width: 1500px; max-height: 100vh; width: 95vw; height: 95vh; display: flex; flex-direction: column; padding: 24px 28px; }
.ai-modal-large h3 { color: #1A3C6D; margin: 0 0 16px; font-size: 18px; flex-shrink: 0; }
.ai-step-body { flex: 1; overflow-y: auto; padding: 8px 0; }
.ai-form-grid { max-width: 900px; }
.config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.config-item { display: flex; align-items: center; gap: 8px; }
.config-hint { font-size: 12px; color: #909399; }
.difficulty-bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 13px; color: #666; }
.difficulty-bar input[type="range"] { flex: 1; min-width: 100px; }
.ai-preview-score { margin-top: 10px; font-size: 14px; color: #409EFF; font-weight: 600; }
.ai-loading { text-align: center; padding: 60px 0; }
.ai-spinner { width: 40px; height: 40px; border: 4px solid #e8e8e8; border-top-color: #409EFF; border-radius: 50%; margin: 0 auto 16px; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.ai-result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding: 12px 16px; background: #f0f9ff; border-radius: 8px; font-size: 14px; }
.ai-result-nav { display: flex; gap: 6px; }
.ai-result-stats { display: flex; gap: 20px; margin-bottom: 12px; font-size: 14px; color: #666; }
.ai-preview-list { max-height: 55vh; overflow-y: auto; border: 1px solid #e8e8e8; border-radius: 8px; padding: 12px; }
.ai-preview-item { padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.ai-preview-item:last-child { border-bottom: none; }
.ai-q-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.ai-q-num { font-weight: 700; color: #1A3C6D; }
.ai-q-type { font-size: 13px; color: #909399; }
.btn-mini { padding: 2px 8px; border: 1px solid #d9d9d9; background: #fff; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-mini:hover { background: #f0f0f0; }
.btn-mini-danger { color: #C41E3A; }
.btn-mini-danger:hover { background: #fce4ec; }
.ai-q-content { font-size: 14px; color: #333; margin-bottom: 6px; }
.ai-q-options { font-size: 13px; color: #666; margin-bottom: 4px; display: flex; flex-wrap: wrap; gap: 12px; }
.ai-q-answer { font-size: 13px; color: #22c55e; font-weight: 600; }
.ai-publish-confirm { padding: 16px; background: #f0f9ff; border-radius: 8px; margin-bottom: 20px; font-size: 16px; color: #1A3C6D; font-weight: 600; }
.radio-label { display: flex; align-items: center; gap: 8px; padding: 8px 0; cursor: pointer; font-size: 15px; }

.type-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 500; color: #fff; }
.badge-single { background: #409EFF; }
.badge-multi { background: #67C23A; }
.badge-essay { background: #E6A23C; }
.badge-writing { background: #F56C6C; }
</style>
