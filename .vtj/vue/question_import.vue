<template>
  <div class="import-page">
    <div class="import-header">
      <div class="header-left">
        <XIcon :icon="UploadFilled" :size="22" color="#ffffff"></XIcon>
        <span class="header-title">题目导入</span>
        <span class="header-sub">单题录入 / 批量解析 / 图片 OCR</span>
      </div>
      <div class="header-right">
        <button class="back-btn" @click="goHome">
          <XIcon :icon="ArrowLeft" :size="16" color="#ffffff"></XIcon>
          <span>返回首页</span>
        </button>
      </div>
    </div>

    <!-- 阶段进度条 -->
    <div class="import-progress-wrap" v-if="state.progressSteps.length">
      <div class="import-progress-steps">
        <template v-for="(step, si) in state.progressSteps" :key="si">
          <span :class="['progress-step', step.status]">
            <span class="step-check" v-if="step.status==='done'">✓</span>
            <span class="step-num" v-else>{{ si + 1 }}</span>
            {{ step.label }}
          </span>
          <span class="progress-step-arrow" v-if="si < state.progressSteps.length-1">→</span>
        </template>
      </div>
      <div class="import-progress-bar">
        <div class="import-progress-fill"
          :class="{done: state.progressPercent >= 100}"
          :style="{width: Math.max(state.progressPercent, 2) + '%'}">
        </div>
      </div>
      <!-- 后端上报的真实阶段文案（如「提取图片（已用 12 秒）」），
           配合单调递增的百分比，避免长耗时解析时用户误判为卡死 -->
      <div class="import-progress-phase" v-if="state.progressPhaseLabel">
        {{ state.progressPhaseLabel }} · {{ state.progressPercent }}%
      </div>
    </div>

    <div class="import-body">
      <div class="card-wrapper">
        <div class="card-nav">
          <div
            v-for="tab in cardTabs"
            :key="tab.key"
            :class="['nav-tab', { active: activeTab === tab.key }]"
            @click="activeTab = tab.key">
            <XIcon :icon="tab.icon" :size="16" :color="activeTab === tab.key ? '#c41e3a' : '#8a8faa'"></XIcon>
            <span>{{ tab.title }}</span>
          </div>
        </div>

        <!-- 单题录入 -->
        <div class="card-content" v-show="activeTab === 'single'">
          <div class="form-row">
            <div class="form-item">
              <label>试卷名称</label>
              <input v-model="state.form.paper_name" placeholder="如：2024 国考行测真题" />
            </div>
            <div class="form-item form-item-sm">
              <label>考试年份</label>
              <input v-model="state.form.year" type="number" placeholder="可空" />
            </div>
            <div class="form-item form-item-md">
              <label>考试省份</label>
              <select v-model="state.form.province">
                <option value="">可空</option>
                <option v-for="p in provinceList" :key="p" :value="p">{{ p }}</option>
              </select>
            </div>
            <div class="form-item form-item-md">
              <label>考试类型</label>
              <select v-model="state.form.exam_type">
                <option value="">可空</option>
                <option v-for="t in examTypeList" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
          </div>
          <div class="form-row">
            <div class="form-item">
              <label>科目</label>
              <select v-model="state.form.subject_category">
                <option value="行测">行测</option>
                <option value="申论">申论</option>
                <option value="公专">公专</option>
                <option value="其他">其他</option>
              </select>
            </div>
            <div class="form-item">
              <label>题型</label>
              <select v-model="state.form.question_type_detail">
                <option value="单选题">单选题</option>
                <option value="多选题">多选题</option>
                <option value="论述题">论述题</option>
                <option value="写作题">写作题</option>
              </select>
            </div>
            <div class="form-item form-item-sm">
              <label>分值</label>
              <input v-model="state.form.score" type="number" min="0" max="100" step="0.5" />
            </div>
            <div class="form-item form-item-sm">
              <label>难度</label>
              <select v-model="state.form.difficulty">
                <option :value="1">简单</option>
                <option :value="2">较易</option>
                <option :value="3">中等</option>
                <option :value="4">较难</option>
                <option :value="5">困难</option>
              </select>
            </div>
          </div>
          <div class="form-item">
            <label>题干内容 <span class="required">*</span></label>
            <textarea v-model="state.form.question_content" rows="3" placeholder="输入题目内容（必填）"></textarea>
          </div>
          <div class="form-item">
            <label>选项</label>
            <div class="option-row" v-for="(opt, idx) in state.form.options" :key="idx">
              <span class="option-key">{{ opt.key }}</span>
              <input v-model="opt.value" :placeholder="'选项 ' + opt.key" />
              <button class="btn-icon" @click="removeOption(idx)" v-show="state.form.options.length > 2">
                <XIcon :icon="Delete" :size="14" color="#c41e3a"></XIcon>
              </button>
            </div>
            <button class="btn-link" @click="addOption">+ 添加选项</button>
          </div>
          <div class="form-row">
            <div class="form-item">
              <label>答案 <span class="required" v-show="state.importMode === 'combined'">*</span></label>
              <input v-model="state.form.answer" :placeholder="state.importMode === 'combined' ? '答案内容（必填）' : '答案内容（可空，后续补录）'" />
            </div>
            <div class="form-item">
              <label>题目来源</label>
              <input v-model="state.form.source" placeholder="如：2024国考真题" />
            </div>
          </div>
          <div class="form-item">
            <label>答案解析</label>
            <textarea v-model="state.form.analysis" rows="2" placeholder="答案解析（可空）"></textarea>
          </div>
          <div class="form-actions">
            <button class="btn-secondary" @click="resetForm">重置</button>
            <button class="btn-primary" @click="submitSingle" :disabled="state.loading">
              <XIcon :icon="Check" :size="16" color="#ffffff"></XIcon>
              <span>{{ state.loading ? '提交中...' : '提交入库' }}</span>
            </button>
          </div>
        </div>

        <!-- 批量导入 -->
        <div class="card-content" v-show="activeTab === 'batch'">
          <div class="mode-switch" style="margin-bottom:16px;">
            <button :class="['mode-btn', { active: state.importMode === 'combined' }]" @click="state.importMode = 'combined'">
              合并导入
            </button>
            <button :class="['mode-btn', { active: state.importMode === 'separate' }]" @click="state.importMode = 'separate'">
              分离导入
            </button>
          </div>
          <!-- ========== 合并导入模式 ========== -->
          <div v-if="state.importMode === 'combined'">
            <div class="batch-upload">
              <div class="upload-zone" @click="uploadBatchFile">
                <XIcon :icon="Upload" :size="28" color="#c41e3a"></XIcon>
                <p>点击选择文件上传</p>
                <span class="upload-hint">支持 docx / pdf / xlsx / xls / csv 格式</span>
              </div>
              <div class="form-item">
                <label>试卷名称</label>
                <input v-model="state.batchPaperName" placeholder="可选，自动从文档标题提取" />
              </div>
            </div>
            <div class="form-actions">
              <button class="btn-primary" @click="uploadBatchFile">选择文件并解析</button>
            </div>
            <!-- Excel/CSV 结构化预览 -->
            <div class="batch-preview" v-if="state.batchPreviewData.length">
              <div class="preview-header">
                <span>解析预览：共 {{ state.batchPreviewData.length }} 题</span>
              </div>
              <div class="preview-list">
                <div class="preview-item" v-for="(q, idx) in state.batchPreviewData.slice(0, 5)" :key="idx">
                  <span class="preview-idx">{{ idx + 1 }}</span>
                  <!-- P0-3 修复：原用 {{ }} 文本插值，把 <img src="/static/questions/..."> 当文字打印。
                       改走 renderQuestionContent 统一渲染口径（与试卷管理/题目管理一致）。 -->
                  <span class="preview-text" v-html="renderQuestionContent(q.question_content || q.题目内容 || '')"></span>
                </div>
              </div>
              <button class="btn-primary" @click="confirmBatchImport" :disabled="state.loading || hasBlockedQuestions">
                {{ state.loading ? '导入中...' : (hasBlockedQuestions ? '存在阻断问题，无法入库' : '确认入库 ' + state.batchPreviewData.length + ' 题') }}
              </button>
              <!-- 阻断原因：把内部原因码翻译成可读文案，让用户知道该去核对什么 -->
              <div v-if="hasBlockedQuestions" class="blocked-hint">
                有 {{ blockedQuestionList.length }} 题存在阻断问题（{{ blockedReasonText }}），已禁止入库。请核对原卷后重新导入。
              </div>
            </div>
            <!-- Word/PDF 智能提取（合并模式） -->
            <div class="batch-preview" v-if="state.rawTextPreview">
              <div class="preview-header">
                <span>文件原文已加载（{{ state.rawTextPreview.length }} 字符）</span>
                <span v-if="state.combinedSubMode !== 'auto'" style="font-size:15px;color:#8899aa;margin-left:10px;">
                  检测模式：{{ state.combinedSubMode === 'inline' ? '答案内嵌（每题含“本题考查”字样）' : '答案在末尾（先题后答）' }}
                </span>
              </div>
              <div class="form-actions" style="justify-content:space-between;padding-top:0;border-top:none;margin-top:0;">
                <button class="btn-primary" @click="parseRawTextToQuestions" :disabled="state.parsedDocsQuestions.length > 0">
                  <XIcon :icon="Check" :size="14" color="#ffffff"></XIcon>
                  <span>智能提取题目</span>
                </button>
                <button class="btn-secondary" @click="state.rawTextPreview = ''; state.parsedDocsQuestions = []; state.combinedSubMode = 'auto'">关闭预览</button>
              </div>
              <!-- 统一标准预览 -->
              <div v-if="state.parsedDocsQuestions.length" style="margin-top:16px;">
                <QuestionPreviewList
                  :questions="state.parsedDocsQuestions"
                  :groups="state.previewGroups || []"
                  <!-- 复合题组总题干：按给定材料聚合，缺省为空数组时行为与旧版完全一致 -->
                  :mode="'combined'"
                  @import-one="importSingleParsedQuestion"
                  @import-all="importAllParsedQuestions"
                  @reverify="reVerifyQuestion"
                  @edit-question="handleEditQuestion"
                  @delete-question="handleDeleteParsedQuestion"
                  @attach-image="handleAttachImage"
                  ref="previewListRef"
                  @close="state.parsedDocsQuestions = []; state.rawTextPreview = ''; state.combinedSubMode = 'auto'"
                  :loading="state.loading"
                ></QuestionPreviewList>
              </div>
            </div>
          </div>

          <!-- ========== 分离导入模式 ========== -->
          <div v-if="state.importMode === 'separate'">
            <div style="display:flex;gap:16px;margin-bottom:12px;">
              <!-- 题目文件上传 -->
              <div class="batch-upload" style="flex:1;">
                <div class="upload-zone" @click="uploadSeparateQuestionFile" :style="state.separateQuestionsLoaded ? 'border-color:#52c41a;' : ''">
                  <XIcon :icon="Upload" :size="24" :color="state.separateQuestionsLoaded ? '#52c41a' : '#c41e3a'"></XIcon>
                  <p v-if="!state.separateQuestionsFileName">上传题目文件</p>
                  <p v-else style="color:#52c41a;">{{ state.separateQuestionsFileName }}</p>
                  <span class="upload-hint">docx / pdf / txt</span>
                </div>
              </div>
              <!-- 答案文件上传 -->
              <div class="batch-upload" style="flex:1;">
                <div class="upload-zone" @click="uploadSeparateAnswerFile" :style="state.separateAnswersLoaded ? 'border-color:#52c41a;' : ''">
                  <XIcon :icon="Upload" :size="24" :color="state.separateAnswersLoaded ? '#52c41a' : '#c41e3a'"></XIcon>
                  <p v-if="!state.separateAnswersFileName">上传答案解析文件</p>
                  <p v-else style="color:#52c41a;">{{ state.separateAnswersFileName }}</p>
                  <span class="upload-hint">含"解析"字样的文档</span>
                </div>
              </div>
            </div>
            <div class="form-item">
              <label>试卷名称</label>
              <input v-model="state.batchPaperName" placeholder="可选，自动从文档标题提取" />
            </div>
            <!-- 匹配按钮 -->
            <div class="form-actions" v-if="state.separateQuestionsLoaded && state.separateAnswersLoaded && !state.parsedDocsQuestions.length">
              <button class="btn-primary" @click="matchSeparateQuestionsAnswers">
                <XIcon :icon="Check" :size="14" color="#ffffff"></XIcon>
                <span>匹配题目与解析</span>
              </button>
              <button class="btn-secondary" @click="state.separateQuestionsLoaded = false; state.separateAnswersLoaded = false; state.separateQuestionsFileName = ''; state.separateAnswersFileName = ''; state.separateQuestionsRawText = ''; state.separateAnswersRawText = ''">重置</button>
            </div>
            <!-- 分离导入统一预览 -->
            <div v-if="state.parsedDocsQuestions.length" style="margin-top:16px;">
              <div class="preview-header" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
                <div>
                  <span>匹配完成：共 {{ state.parsedDocsQuestions.length }} 道题目</span>
                  <span v-if="state.parsedDocsQuestions.filter(function(q){return q.answer && q.answer !== '待补充'}).length" style="font-size:15px;color:#52c41a;margin-left:10px;">
                    其中 {{ state.parsedDocsQuestions.filter(function(q){return q.answer && q.answer !== '待补充'}).length }} 题已匹配答案
                  </span>
                  <span style="font-size:13px;font-weight:600;margin-left:10px;"
                    :style="{color: state.separateMatchRate >= 99 ? '#52c41a' : state.separateMatchRate >= 90 ? '#f59e0b' : '#f56c6c'}">
                    匹配率 {{ state.separateMatchRate }}%
                  </span>
                </div>
                <!-- 导入按钮区域 -->
                <div style="display:flex;align-items:center;gap:8px;">
                  <button v-if="state.separateMatchRate >= 99"
                    class="btn-primary"
                    style="background:linear-gradient(135deg,#c41e3a 0%,#e8384f 100%);padding:8px 24px;font-size:14px;font-weight:600;"
                    @click="importAllParsedQuestions"
                    :disabled="state.loading">
                    <XIcon :icon="Upload" :size="14" color="#ffffff"></XIcon>
                    <span>{{ state.loading ? '导入中...' : '导入到题库（' + state.parsedDocsQuestions.filter(function(q){return !q._imported && !q._is_duplicate}).length + ' 题）' }}</span>
                  </button>
                  <button v-else-if="state.separateMatchRate >= 70"
                    class="btn-primary"
                    style="background:linear-gradient(135deg,#f59e0b 0%,#f97316 100%);padding:8px 24px;font-size:14px;font-weight:600;"
                    @click="showManualMatchDialog">
                    <span>手动匹配（当前 {{ state.separateMatchRate }}%）</span>
                  </button>
                  <button v-else
                    class="btn-primary"
                    style="background:rgba(100,100,120,0.5);padding:8px 24px;font-size:14px;font-weight:600;cursor:not-allowed;border:1px solid rgba(245,108,108,0.4);"
                    disabled
                    :title="'匹配率仅 ' + state.separateMatchRate + '%，低于70%最低要求'">
                    <span>匹配率太低，请修改后重新导入</span>
                  </button>
                </div>
              </div>
              <QuestionPreviewList
                :questions="state.parsedDocsQuestions"
                :groups="state.previewGroups || []"
                <!-- 复合题组总题干：按给定材料聚合，缺省为空数组时行为与旧版完全一致 -->
                :mode="'separate'"
                @import-one="importSingleParsedQuestion"
                @import-all="importAllParsedQuestions"
                @reverify="reVerifyQuestion"
                @edit-question="handleEditQuestion"
                @delete-question="handleDeleteParsedQuestion"
                @close="state.parsedDocsQuestions = []; state.separateQuestionsLoaded = false; state.separateAnswersLoaded = false; state.separateQuestionsFileName = ''; state.separateAnswersFileName = ''; state.separateQuestionsRawText = ''; state.separateAnswersRawText = ''; state.separateMatchRate = 0"
                :loading="state.loading"
              ></QuestionPreviewList>
            </div>
          </div>
        </div>

        <!-- 图片导入 -->
        <div class="card-content" v-show="activeTab === 'image'">
          <div class="image-upload">
            <div class="upload-zone" @click="selectImage">
              <XIcon :icon="PictureFilled" :size="28" color="#c41e3a"></XIcon>
              <p v-if="!state.imagePreviewUrl">点击选择图片上传</p>
              <p v-else style="color:#4ade80;">已选择图片</p>
              <span class="upload-hint">支持 jpg / png / bmp 格式，可多选</span>
            </div>
          </div>
          <div class="image-preview" v-if="state.imagePreviewUrl">
            <img :src="state.imagePreviewUrl" alt="preview" />
          </div>
          <!-- 多图片提示 -->
          <div v-if="state.selectedImageFiles.length > 1" style="margin-top:8px;color:#8899aa;font-size:15px;text-align:center;">
            已选择 {{ state.selectedImageFiles.length }} 张图片（预览显示第一张）
          </div>
          <div class="form-actions" v-if="!state.ocrQuestions.length" style="flex-wrap:wrap;gap:8px;">
            <button class="btn-primary" @click="selectImage" v-if="!state.imagePreviewUrl">选择图片</button>
            <button class="btn-primary" @click="ocrRecognize" v-if="state.imagePreviewUrl && !state.ocrLoading" :disabled="!state.imagePreviewUrl">
              <XIcon :icon="PictureFilled" :size="14" color="#ffffff"></XIcon>
              <span>PaddleOCR 智能识别</span>
            </button>
            <!-- 一键识别并入库（增强版：含自动分类） -->
            <button class="btn-primary" @click="ocrAndImportStructured"
              v-if="state.imagePreviewUrl && !state.ocrLoading"
              style="background:linear-gradient(135deg, #c41e3a 0%, #e8384f 100%);">
              <span>⚡ 一键识别并入库</span>
            </button>
            <button class="btn-primary" v-if="state.ocrLoading" disabled>
              <span>{{ state.importProgress > 0 ? '导入中 ' + state.importProgress + '%' : '识别中...' }}</span>
            </button>
          </div>
          <!-- 导入进度条 -->
          <div v-if="state.loading && state.importProgress > 0" style="margin-top:8px;background:rgba(26,43,95,0.5);border-radius:8px;height:8px;overflow:hidden;">
            <div :style="{width: state.importProgress + '%', height:'100%', background:'linear-gradient(90deg, #c41e3a, #e8384f)', transition:'width 0.3s ease'}"></div>
          </div>
          <!-- OCR 识别结果 -->
          <div v-if="state.ocrText" style="margin-top:16px;">
            <div class="preview-header">
              <span>OCR 识别结果（{{ state.ocrText.length }} 字符）</span>
              <button class="btn-secondary" @click="parseOcrTextToQuestions" :disabled="state.parsedDocsQuestions.length > 0" style="margin-left:10px;font-size:15px;">
                智能提取题目
              </button>
            </div>
            <details>
              <summary style="color:#8899aa;font-size:15px;cursor:pointer;">查看识别文本</summary>
              <pre class="raw-text" style="margin-top:8px;max-height:300px;">{{ state.ocrText }}</pre>
            </details>
          </div>
          <!-- OCR 题目预览（增强版：含分类信息） -->
          <div v-if="state.ocrQuestions.length" style="margin-top:16px;">
            <div class="preview-header" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
              <div>
                <span>识别成功：共 {{ state.ocrQuestions.length }} 道题目</span>
                <span v-if="state.ocrAutoSubject" style="font-size:15px;color:#4ade80;margin-left:10px;">
                  🏷 自动分类：{{ state.ocrAutoSubject }}
                  <span v-if="state.ocrAutoSubcategories && state.ocrAutoSubcategories.length" style="color:#8899aa;">
                    （{{ state.ocrAutoSubcategories.join('、') }}）
                  </span>
                </span>
              </div>
              <!-- 预览确认导入按钮 -->
              <div style="display:flex;align-items:center;gap:8px;">
                <button class="btn-primary" @click="importAllOcrQuestionsConfirmed"
                  style="background:linear-gradient(135deg,#c41e3a 0%,#e8384f 100%);padding:8px 20px;font-size:13px;font-weight:600;"
                  :disabled="state.ocrLoading">
                  <span>{{ state.ocrLoading ? '导入中...' : '✅ 确认入库（' + state.ocrQuestions.filter(function(q){return !q._imported && !q._is_duplicate}).length + ' 题）' }}</span>
                </button>
              </div>
            </div>
            <QuestionPreviewList
              :questions="state.ocrQuestions"
              :groups="state.previewGroups || []"
              <!-- 复合题组总题干：按给定材料聚合，缺省为空数组时行为与旧版完全一致 -->
              :mode="'image'"
              @import-one="importSingleOcrQuestion"
              @import-all="importAllOcrQuestionsConfirmed"
              @reverify="reVerifyOcrQuestion"
              @edit-question="handleEditQuestion"
              @delete-question="handleDeleteOcrQuestion"
              @close="state.ocrQuestions = []; state.ocrText = ''; state.imagePreviewUrl = ''; state.ocrAutoSubject = ''; state.ocrAutoSubcategories = []"
              :loading="state.ocrLoading"
            ></QuestionPreviewList>
          </div>
        </div>
      </div>

      <div class="records-section" v-if="state.records.length">
        <div class="section-title">
          <XIcon :icon="List" :size="16" color="#c41e3a"></XIcon>
          <span>最近导入记录</span>
        </div>
        <div class="records-list">
          <div class="record-row" v-for="r in state.records" :key="r.import_id">
            <span class="record-file">{{ r.original_filename }}</span>
            <span class="record-count">成功 {{ r.success_count }} / 重复 {{ r.duplicate_count }}</span>
            <span class="record-time">{{ r.complete_time }}</span>
          </div>
        </div>
      </div>
    </div>
    <!-- 双轨入库结果摘要卡（《导入结果展示》原型落地） -->
    <div v-if="state.importSummary" class="import-summary-card">
      <div class="summary-header">
        <span class="summary-title">✅ 导入完成</span>
        <button class="btn-summary-close" @click="dismissImportSummary" title="关闭">✕</button>
      </div>
      <div class="summary-body">
        <div class="summary-row">
          <span class="s-label">文档类型：</span>
          <span class="s-value">{{ state.importSummary.paperName || (state.importSummary.mode === 'separate' ? '分离导入试卷' : 'Word批量导入') }}</span>
        </div>
        <div class="summary-row">
          <span class="s-label">总题目数：</span>
          <span class="s-value">{{ state.importSummary.total }} 题</span>
        </div>
        <div class="summary-row" v-if="state.importSummary.mode === 'separate'">
          <span class="s-label">自动匹配：</span>
          <span class="s-value">{{ state.importSummary.matchRate }}%（{{ state.importSummary.success + state.importSummary.dup }}/{{ state.importSummary.total }}）</span>
        </div>
        <div class="summary-row" v-if="state.importSummary.needConfirm > 0">
          <span class="s-label s-warn">⚠️ 待确认项：</span>
          <span class="s-value s-warn">{{ state.importSummary.needConfirm }} 题（缺答案/低置信度，建议确认后再发布试卷）</span>
        </div>
        <!-- P0-3: 异常题清单面板（失败题 + 待确认题，点击定位） -->
        <div class="summary-row" v-if="state.abnormalItems.length > 0">
          <div class="abnormal-list">
            <div class="abnormal-list-header">🔍 异常题清单（点击定位到题目）：</div>
            <div
              v-for="(item, ai) in state.abnormalItems"
              :key="'abn_' + ai"
              class="abnormal-item"
              :class="{ 'abnormal-failed': item.kind === 'failed' }"
              @click="locateAbnormalItem(item)"
              :title="'点击定位到第 ' + item.question_number + ' 题'"
            >
              <span class="abnormal-num">第{{ item.question_number }}题</span>
              <span class="abnormal-tag">{{ item.kind === 'failed' ? '❌ 失败' : '⚠️ 待确认' }}</span>
              <span class="abnormal-reason">{{ item.reason }}</span>
            </div>
          </div>
        </div>
        <div class="summary-row" v-if="state.importSummary.paperId">
          <span class="s-label s-ok">✅ 试卷已保存：</span>
          <span class="s-value s-ok">试卷ID #{{ state.importSummary.paperId }}（草稿状态，可在"试卷管理"中编辑完善并发布）</span>
        </div>
        <div class="summary-row">
          <span class="s-label s-ok">✅ 题目已入库：</span>
          <span class="s-value">新增 {{ state.importSummary.success }} 题 · 复用 {{ state.importSummary.dup }} 题<template v-if="state.importSummary.failed"> · 失败 {{ state.importSummary.failed }} 题（见控制台明细）</template></span>
        </div>
      </div>
      <div class="summary-actions">
        <button class="btn-primary btn-sm-primary" v-if="state.importSummary.paperId" @click="goViewPaper">查看试卷</button>
        <button class="btn-secondary" @click="goViewBank">查看题库</button>
        <button class="btn-secondary" @click="continueImport">继续导入</button>
        <button class="btn-secondary" @click="dismissImportSummary">稍后处理</button>
      </div>
    </div>
    <!-- 手动匹配弹窗 -->
    <div v-if="state.manualMatchVisible" class="manual-match-overlay" @click.self="onManualMatchCancel">
      <div class="manual-match-modal">
        <ManualMatchDialog
          :questions="state.parsedDocsQuestions"
          :answers="state.separateAnswerList || []"
          @confirm="onManualMatchConfirm"
          @cancel="onManualMatchCancel"
        ></ManualMatchDialog>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
import { defineComponent, reactive } from 'vue';
import { XIcon } from '@vtj/ui';
import { ElMessage, ElMessageBox } from 'element-plus';
import { UploadFilled, ArrowLeft, Delete, Upload, Check, PictureFilled, List } from '@vtj/icons';
import { useProvider } from '@vtj/renderer';
import ManualMatchDialog from './manual_match_dialog.vue';
import QuestionPreviewList from './question_preview_list.vue';
import { renderQuestionContent } from '@/utils/questionRender';
  export default defineComponent({
    name: 'QuestionImport',
    components: { XIcon, QuestionPreviewList, ManualMatchDialog },
  setup(props) {
    const provider = useProvider({ id: 'question_import', version: '1790329880372' });
    // PDF 扫描件 OCR 超时预算（ms）——单一事实来源，勿在别处硬编码
    // 后端最坏耗时 = GPU串行锁排队60s + MinerU子进程600s + PaddleOCR兜底240s = 900s
    // 取 960s = 900s + 60s 余量。改后端任一超时必须同步改此值。
    const PDF_OCR_TIMEOUT_MS = 960000;
    const state = reactive({
        importMode: 'combined',
        activeTab: 'single',
        form: {
          paper_name: '',
          year: null,
          province: '',
          exam_type: '',
          subject_category: '公专',
          question_type_detail: '单选题',
          question_content: '',
          options: [{ key: 'A', value: '' }, { key: 'B', value: '' }, { key: 'C', value: '' }, { key: 'D', value: '' }],
          answer: '',
          source: '',
          analysis: '',
          score: 1,
          difficulty: 3
        },
        batchPaperName: '',
        batchPreviewData: [],
        // 复合题组总题干：后端按「给定材料」聚合，缺省空数组时行为与旧版一致
        previewGroups: [],
        rawTextPreview: '',
        parsedDocsQuestions: [],
        importId: null,
        imagePreviewUrl: '',
        selectedImageFiles: [],       // 多图片支持
        ocrText: '',
        ocrQuestions: [],
        ocrLoading: false,
        records: [],
        loading: false,
        importProgress: 0,            // 导入进度
        duplicateCount: 0,           // 重复题目计数
        // 分离导入
        separateQuestionsLoaded: false,
        separateAnswersLoaded: false,
        separateQuestionsFileName: '',
        separateAnswersFileName: '',
        separateQuestionsRawText: '',
        separateAnswersRawText: '',
        // 合并导入子场景
        combinedSubMode: 'auto',
        // 分离导入匹配率
        separateMatchRate: 0,
        // 中等匹配率待确认
        separateNeedConfirm: false,
        // 手动匹配弹窗
        manualMatchVisible: false,
        // 图片导入自动分类结果
        ocrAutoSubject: '',
        ocrAutoSubcategories: [],
        stats: { total_questions: 0, subject_stats: [], type_stats: [], latest_import: null },
        // 统一后端解析
        parseResult: null,
        parseLoading: false,
        parseError: '',
        // 头部进度条
        progressPhase: 0,         // 当前阶段索引 0-based
        progressPercent: 0,       // 当前阶段进度 0-100
        progressSteps: [],        // [{label:'文档解析', status:'done'|'active'|'pending'}]
        // 2026-09-29 新增：后端上报的解析阶段中文提示（如「提取图片（已用 12 秒）」）
        progressPhaseLabel: '',
        // 批量导入结果摘要（双轨入库展示：试卷ID/新增复用/待确认）
        importSummary: null,
        // P0-3: 异常题清单（含题号/类型/原因，点击可定位到题目卡片）
        abnormalItems: [],
        // P0-3: 定位高亮标记的题目索引
        highlightIndex: -1,
      });
      return {
        state, props, provider,
        PDF_OCR_TIMEOUT_MS,
        UploadFilled, ArrowLeft, Delete, Upload, Check, PictureFilled, List,
        // P0-3：模板中的 v-html 渲染入口（统一走 @/utils/questionRender）
        renderQuestionContent,
        cardTabs: [
          { key: 'single', title: '单题录入', icon: UploadFilled },
          { key: 'batch', title: '批量导入', icon: Upload },
          { key: 'image', title: '图片导入', icon: PictureFilled }
        ]
      };
    },
    data() {
      return {
        activeTab: 'single',
        provinceList: ['北京市','天津市','河北省','山西省','内蒙古自治区','辽宁省','吉林省','黑龙江省','上海市','江苏省','浙江省','安徽省','福建省','江西省','山东省','河南省','湖北省','湖南省','广东省','广西壮族自治区','海南省','重庆市','四川省','贵州省','云南省','西藏自治区','陕西省','甘肃省','青海省','宁夏回族自治区','新疆维吾尔自治区'],
        examTypeList: ['国考','省考','联考','模拟考试','事业单位','招警考试']
      };
    },
    computed: {
      // ★ 申论阻断检测
      //   后端解析器对「题号邻近找不到分值」「答案段数与题目数不等」的题块会置
      //   blocked=true。这类题一旦入库就是错配数据，事后无法与正确数据区分，
      //   因此前端必须在**提交前**拦住，而不是等后端 400。
      //   用户硬约束：宁可阻断报错交人工，也不允许把错配数据写进题库。
      blockedQuestionList() {
        const list = this.state.batchPreviewData || [];
        return list.filter(function (q) {
          return q && (q.blocked === true || q.blocked === 1 || q.blocked === 'true');
        });
      },
      hasBlockedQuestions() {
        return this.blockedQuestionList.length > 0;
      },
      // 内部原因码 → 中文可读文案。未识别的码原样显示，便于排查而不丢失信息。
      blockedReasonText() {
        const LABEL = {
          missing_score: '缺少分值信息',
          answer_block_count_mismatch: '答案段数与题目数不匹配',
          answer_missing_for_question: '答案卷缺少该题号',
          stem_fingerprint_mismatch: '题干与答案卷不匹配（可能传错文件）',
          score_mismatch: '题目与答案分值不一致'
        };
        const seen = {};
        this.blockedQuestionList.forEach(function (q) {
          const reasons = q.block_reasons || [];
          (Array.isArray(reasons) ? reasons : [reasons]).forEach(function (r) {
            if (!r) return;
            seen[r] = LABEL[r] || r;
          });
        });
        const keys = Object.keys(seen);
        if (!keys.length) return '';
        return keys.map(function (k) { return seen[k]; }).join('；');
      }
    },
    methods: {
      goHome() {
        const auth = window.__VTJ_AUTH__;
        const role = auth ? auth.getUserRole() : null;
        if (role === 'teacher' || role === 'admin') {
          this.$router.push('/teacher/questions');
        } else {
          this.$router.push('/');
        }
      },
      async ensureLogin() {
        return window.__VTJ_AUTH__.ensureAuth();
      },
      getAuthHeaders() {
        return window.__VTJ_AUTH__.getAuthHeaders();
      },
      getJsonHeaders() {
        return window.__VTJ_AUTH__.getJsonHeaders();
      },
      /**
       * 带超时和重试的 fetch 封装
       * @param {string} url 请求地址
       * @param {object} options fetch 选项
       * @param {number} timeoutMs 超时毫秒数 (默认 30000)
       * @param {number} retries 重试次数 (默认 1)
       */
      async fetchWithRetry(url, options, timeoutMs, retries) {
        timeoutMs = timeoutMs || 30000;
        retries = retries || 1;
        var lastError = null;
        for (var attempt = 0; attempt <= retries; attempt++) {
          var controller = new AbortController();
          var timer = setTimeout(function() { controller.abort(); }, timeoutMs);
          try {
            var fetchOpts = Object.assign({}, options, { signal: controller.signal });
            var res = await fetch(url, fetchOpts);
            clearTimeout(timer);
            return res;
          } catch (e) {
            clearTimeout(timer);
            lastError = e;
            if (e.name === 'AbortError') {
              console.warn('[fetchWithRetry] Timeout after ' + timeoutMs + 'ms, attempt ' + (attempt + 1) + '/' + (retries + 1));
            } else {
              console.warn('[fetchWithRetry] Error on attempt ' + (attempt + 1) + ': ' + (e.message || e));
            }
            if (attempt < retries) {
              // 等待后重试
              await new Promise(function(r) { setTimeout(r, 1000 * (attempt + 1)); });
            }
          }
        }
        throw lastError || new Error('请求失败，已重试 ' + retries + ' 次');
      },
      /**
       * 预处理 fetch 错误，生成用户友好的错误信息
       */
      handleFetchError(e, context) {
        context = context || '请求';
        var msg = e.message || '';
        if (msg.indexOf('Failed to fetch') !== -1 || msg.indexOf('NetworkError') !== -1) {
          return context + '失败：无法连接到服务器，请确认服务已启动 (npm run dev / python start.py)';
        }
        if (e.name === 'AbortError' || msg.indexOf('abort') !== -1 || msg.indexOf('timeout') !== -1) {
          return context + '超时：服务器响应过慢，请稍后重试';
        }
        return context + '出错：' + msg;
      },

      /**
       * 从后端错误响应体中提取**可读**的错误文案。
       *
       * 后端统一错误封装（backend/app/exceptions.py create_error_response）：
       *   { "error": { "code": "...", "message": "...", "details": {...} } }
       * 注意：FastAPI HTTPException 的 `detail` 会被搬进 `error.message`，
       * 顶层**不存在** `detail` 字段。
       * 历史教训：直接 `new Error(data.detail || data.error || ...)` 中
       * `data.error` 是对象，Error 构造会 String() 成 "[object Object]"，
       * 用户只看到无意义的 "[object Object]"，完全看不到真实原因。
       */
      _extractErrorMessage(data, fallback) {
        fallback = fallback || '请求失败';
        if (data == null) return fallback;
        if (typeof data === 'string') return data || fallback;
        // 1) 校验错误明细：比泛化的"数据验证失败"更有用，需与 message 拼接而非二选一
        var d = (data.error && data.error.details) || data.details;
        var extra = '';
        if (d && Array.isArray(d.errors) && d.errors.length) {
          try {
            extra = d.errors.map(function (x) {
              return (x && (x.msg || x.message)) || JSON.stringify(x);
            }).join('；');
          } catch (e) { extra = ''; }
        }
        // 2) 标准封装 error.message
        if (data.error && typeof data.error === 'object' && typeof data.error.message === 'string' && data.error.message) {
          return extra ? (data.error.message + '：' + extra) : data.error.message;
        }
        // 3) 兼容：detail 为字符串（未挂中间件时的 FastAPI 原始形态）
        if (typeof data.detail === 'string' && data.detail) {
          return extra ? (data.detail + '：' + extra) : data.detail;
        }
        // 4) 兼容：error 本身是字符串
        if (typeof data.error === 'string' && data.error) {
          return extra ? (data.error + '：' + extra) : data.error;
        }
        // 5) 兼容：message 字段
        if (typeof data.message === 'string' && data.message) {
          return extra ? (data.message + '：' + extra) : data.message;
        }
        if (extra) return extra;
        // 6) 最后兜底：绝不返回 [object Object]
        try {
          var s = JSON.stringify(data);
          return (s && s !== '{}' && s !== '[]') ? s : fallback;
        } catch (e) {
          return fallback;
        }
      },

      /**
       * 轮询异步导入的解析状态，直到 PREVIEW / FAILED / 超出总预算。
       * 退避策略：1.5s 起，每次 ×1.3 递增，上限 8s（避免频繁请求又不拖慢体感）。
       * 每次轮询都是短请求（10s 超时）—— 因为后端已改为后台执行，
       * 代理层默认 60s 超时不再是瓶颈。
       */
      async _pollImportStatus(importId, budgetMs, onTick) {
        var deadline = Date.now() + (budgetMs || (this.PDF_OCR_TIMEOUT_MS || 960000));
        var delay = 1500;
        var waited = 0;
        while (Date.now() < deadline) {
          await new Promise(function (r) { setTimeout(r, delay); });
          waited += delay;
          var res = await this.fetchWithRetry(
            '/api/questions/import/records/' + importId + '/status',
            { method: 'GET', headers: this.getAuthHeaders() },
            10000, 0
          );
          var st = await res.json();
          if (!res.ok) {
            throw new Error(this._extractErrorMessage(st, '查询解析状态失败 (HTTP ' + res.status + ')'));
          }
          if (st.status === 'PREVIEW') return st.result || st;
          if (st.status === 'FAILED') throw new Error(this._extractErrorMessage(st, '解析失败'));
          // PARSING / CONFIRMED / COMPLETED：继续等
          if (onTick) onTick(st, waited);
          delay = Math.min(Math.round(delay * 1.3), 8000);
        }
        var mins = Math.round(waited / 60000);
        throw new Error('解析超时（已等待 ' + (mins > 0 ? mins + ' 分钟' : Math.round(waited / 1000) + ' 秒') +
          '）。若文档很大请稍后重试；若反复超时，可能是服务重启导致任务中断，请重新上传。');
      },

      /**
       * 上传文件并等待解析完成（后端 /upload 已改为异步：立即返回 import_id）。
       * 返回值与**原同步接口完全同构**，因此调用方的消费逻辑无需改动。
       */
      async _uploadAndPoll(formData, isPdf) {
        var self = this;
        // 上传本身很快（实测 <1s），60s 足够容纳 50MB 传输
        var upRes = await this.fetchWithRetry('/api/questions/import/upload', {
          method: 'POST',
          headers: this.getAuthHeaders(),
          body: formData
        }, 60000, 0);
        var data = await upRes.json();
        if (!upRes.ok) {
          // 必须经 _extractErrorMessage 提取：后端 error 是对象，直接拼接会得到 [object Object]
          throw new Error(this._extractErrorMessage(data, '上传失败 (HTTP ' + upRes.status + ')'));
        }
        // 兼容：后端未升级时仍会直接返回预览数据
        if (!data.import_id || data.status !== 'PARSING') return data;
        return await this._pollImportStatus(data.import_id, this.PDF_OCR_TIMEOUT_MS, function (st, waited) {
          var secs = Math.round(waited / 1000);
          var tip = secs >= 60 ? Math.round(secs / 60) + ' 分钟' : secs + ' 秒';
          if (self.state && self.state.loading) self.state.loading = false;   // 避免按钮转圈卡死观感
          // ★ 2026-09-29 修复：此前是 `Math.min(45, 10 + Math.round(waited / 4000))`
          //   —— 纯按等待时间伪造百分比，与后端真实解析进度毫无关系，
          //   表现为「百分比停在 45% 不动，等解析结束突然跳到 100」。
          //   后端 _process_import_async 现按六阶段写库 progress_percent/current_phase，
          //   此处直接采信；后端未升级（无该字段）时不写任何值，绝不再伪造。
          self.applyBackendProgress(st, tip);
        });
      },

      /**
       * 用后端上报的真实进度刷新进度条与阶段提示。
       * @param st   状态接口响应（已含 progress_percent / current_phase）
       * @param tip  已等待时长文案，用于扫描件等长耗时场景的安抚提示
       */
      applyBackendProgress(st, tip) {
        if (!st) return;
        var pct = st.progress_percent;
        if (typeof pct !== 'number' || isNaN(pct)) return;   // 旧后端无此字段 -> 不伪造
        pct = Math.max(0, Math.min(100, pct));
        this.setProgress(0, pct);
        // 阶段名映射为中文；扫描件 OCR 阶段耗时可达数分钟，补一句提示避免误判卡死
        var labels = {
          READING: '读取文件', EXTRACTING: '提取文本', IMAGES: '提取图片',
          SPLITTING: '切分题目', MATCHING: '匹配答案', BUILDING: '构建预览',
          DONE: '解析完成'
        };
        var label = labels[st.current_phase] || '';
        if (label && pct < 100) {
          this.state.importProgress = pct;
          this.state.progressPhaseLabel = label + '（已用 ' + (tip || '') + '）';
        }
      },
      addOption() {
        const keys = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        const next = keys[this.state.form.options.length];
        if (next) this.state.form.options.push({ key: next, value: '' });
      },
      removeOption(idx) {
        this.state.form.options.splice(idx, 1);
      },
      resetForm() {
        this.state.form = {
          paper_name: '', year: null, province: '', exam_type: '',
          subject_category: '公专', question_type_detail: '单选题',
          question_content: '',
          options: [{ key: 'A', value: '' }, { key: 'B', value: '' }, { key: 'C', value: '' }, { key: 'D', value: '' }],
          answer: '', source: '', analysis: '', score: 1, difficulty: 3
        };
      },
      async submitSingle() {
        const mode = this.state.importMode;
        if (!this.state.form.question_content) {
          ElMessage.warning('题目内容为必填项');
          return;
        }
        if (mode === 'combined' && !this.state.form.answer) {
          ElMessage.warning('合并模式下答案为必填项');
          return;
        }
        this.state.loading = true;
        try {
          const res = await this.fetchWithRetry('/api/questions/import/single', {
            method: 'POST',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({
              paper_name: this.state.form.paper_name,
              year: this.state.form.year,
              province: this.state.form.province,
              exam_type: this.state.form.exam_type,
              subject_category: this.state.form.subject_category,
              question_type_detail: this.state.form.question_type_detail,
              question_content: this.state.form.question_content,
              options: this.state.form.options,
              answer: this.state.form.answer,
              source: this.state.form.source,
              answer_analysis: this.state.form.analysis,
              score: this.state.form.score,
              difficulty: this.state.form.difficulty,
              import_mode: mode
            })
          });
          const data = await res.json();
          if (res.ok && data.import_status === 'SUCCESS') {
            ElMessage.success('题目导入成功 (ID: ' + data.question_id + ')');
            this.resetForm();
            this.loadRecords();
            // 通知题库首页刷新数据
            this.notifyBankRefresh();
          } else if (data.import_status === 'DUPLICATE') {
            ElMessage.warning(data.message || '题目已存在');
          } else {
            ElMessage.warning(data.detail || data.message || '导入失败');
          }
        } catch (e) {
          ElMessage.error(this.handleFetchError(e, '单题导入'));
        }
        this.state.loading = false;
      },
      // ========== 后端文本提取辅助（用于分离导入的docx/pdf文件） ==========
      async _readDocViaBackend(file, callback) {
        var self = this;
        var formData = new FormData();
        formData.append('file', file);
        // PDF扫描件OCR超时预算：后端已改为异步（立即返回 import_id），
        // 此处不再是"单次请求超时"，而是"整体轮询预算"。
        // 后端最坏耗时 = GPU排队60s + MinerU600s + PaddleOCR兜底240s = 900s
        // 出处: mineru_service.py _SEM_WAIT_SECONDS=60 / config.py MINERU_TIMEOUT=600
        //       config.py OCR_SUBPROCESS_TIMEOUT=240
        // ⚠️ 改后端任一超时必须同步改这里
        // 注: 提取文本已按文件md5缓存(perf: backend/app/services/text_cache.py)，
        //     重复导入同一文件仅需 ~0.006s；本预算仅作用于"首次导入新文件"
        var isPdf = file.name && file.name.toLowerCase().endsWith('.pdf');
        if (isPdf) {
          ElMessage.info('正在解析文件：' + file.name + '（扫描件将启用MinerU高精度OCR，约需1-3分钟，请耐心等待）');
        }
        try {
          // 使用 getAuthHeaders() 携带认证token（不含 Content-Type，让浏览器自动设置 multipart boundary）
          var data = await this._uploadAndPoll(formData, isPdf);
          if (!data) {
            ElMessage.error('文件解析失败：未返回结果');
            return;
          }
          // Word/PDF → 返回 raw_text_preview
          if (data.raw_text_preview) {
            callback(data.raw_text_preview);
            return;
          }
          // Excel/CSV → 返回 questions 数组
          if (data.questions && data.questions.length > 0) {
            var text = '';
            for (var di = 0; di < data.questions.length; di++) {
              var item = data.questions[di];
              text += (text ? '\n' : '') + (item.question_content || '');
              if (item.options) {
                try {
                  var opts = typeof item.options === 'string' ? JSON.parse(item.options) : item.options;
                  for (var oi = 0; oi < opts.length; oi++) {
                    text += ' ' + opts[oi].key + '. ' + opts[oi].value;
                  }
                } catch(e) {}
              }
            }
            callback(text);
            return;
          }
          // 扫描件PDF特殊处理（此时系统已尝试MinerU高精度OCR + PaddleOCR逐页识别两级引擎）
          if (data.scanned_pdf) {
            ElMessage.warning('检测到扫描件PDF，自动识别未产出内容。请确认扫描清晰度，或改用"图片导入"标签页；若多次失败请联系管理员检查MinerU服务状态。');
            callback('');
            return;
          }
          // 回退：尝试从response中提取任何文本内容
          if (data.detail || data.message) {
            callback(data.detail || data.message);
            return;
          }
          // 终极回退：显示引导信息
          ElMessage.warning('文件解析返回空内容。扫描件PDF已尝试MinerU高精度OCR仍无结果时，请改用"图片导入"标签页；Word文档请确认包含可选择文本。');
          callback('');
        } catch (e) {
          ElMessage.error('文件上传异常：' + (e.message || '网络错误'));
        }
      },
      async uploadBatchFile() {
        var self = this;
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.docx,.pdf,.xlsx,.xls,.csv';
        input.onchange = async (e) => {
          const file = e.target.files[0];
          if (!file) return;
          self.resetProgress('combined');
          self.stepActive(0); self.setProgress(0, 10);
          ElMessage.info('正在解析文件：' + file.name + '...');
          try {
            const formData = new FormData();
            formData.append('file', file);
            if (self.state.batchPaperName) formData.append('paper_name', self.state.batchPaperName);
            // 后端 /upload 已异步化：立即返回 import_id，这里轮询等待解析完成。
            // 轮询总预算 PDF_OCR_TIMEOUT_MS(=后端最坏900s+余量)，非单次请求超时。
            var batchIsPdf = file.name && file.name.toLowerCase().endsWith('.pdf');
            const data = await self._uploadAndPoll(formData, batchIsPdf);
            if (!data) {
              ElMessage.warning('上传失败：未返回结果');
              self.resetProgress('');
              return;
            }
            self.setProgress(0, 50);
            // Excel/CSV 返回结构化 questions 数组
            if (data.questions && data.questions.length > 0) {
              self.state.batchPreviewData = data.questions;
              self.state.previewGroups = data.groups || [];
              self.state.rawTextPreview = '';
              self.state.importId = data.import_id;
              self.stepDone(0); self.setProgress(0, 100);
              ElMessage.success('解析完成：' + (data.success_count || 0) + ' 题可导入，' + (data.failed_count || 0) + ' 题跳过');
            }
            // Word/PDF 返回 raw_text_preview → 自动智能提取题目
            else if (data.raw_text_preview) {
              self.state.batchPreviewData = [];
              self.state.rawTextPreview = data.raw_text_preview;
              self.state.importId = data.import_id;
              self.stepDone(0); self.setProgress(0, 80);
              // 自动提取题目结构，直接显示导入按钮
              self.parseRawTextToQuestions();
              if (self.state.parsedDocsQuestions.length) {
                self.setProgress(0, 100);
                ElMessage.success('已自动提取 ' + self.state.parsedDocsQuestions.length + ' 道题目，可直接导入');
              } else {
                ElMessage.info('文件已解析，但未自动识别出题目结构。请点击"智能提取题目"或检查文件格式');
              }
            }
            else {
              self.resetProgress('');
              ElMessage.warning('文件无有效题目数据');
            }
          } catch (e) {
            self.resetProgress('');
            ElMessage.error(self.handleFetchError(e, '文件上传'));
          }
        };
        input.click();
      },
      async confirmBatchImport() {
        // ★ 程序性守卫：不能只靠按钮 disabled —— disabled 可被绕过
        //   （控制台直接调方法、Enter 提交表单、并发点击都会击穿 UI 层）。
        //   阻断是数据正确性闸门，必须在真正发请求前再拦一次。
        if (this.hasBlockedQuestions) {
          ElMessage.error(
            '存在阻断问题，无法入库：' + this.blockedReasonText +
            '。已阻断 ' + this.blockedQuestionList.length + ' 题，请核对原卷后重新导入。'
          );
          return;
        }
        if (!this.state.batchPreviewData.length) {
          ElMessage.warning('无可导入的题目数据');
          return;
        }
        this.state.loading = true;
        try {
          const res = await this.fetchWithRetry('/api/questions/import/confirm', {
            method: 'POST',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({
              import_id: this.state.importId,
              paper_name: this.state.batchPaperName,
              questions: this.state.batchPreviewData
            })
          });
          const data = await res.json();
          if (res.ok) {
            // 增强导入结果展示
            var msg = '导入完成：成功 ' + (data.success_count || 0) + ' 题，跳过 ' + (data.skipped_count || 0);
            if (data.paper_id) {
              msg += ' | 试卷ID: #' + data.paper_id;
            }
            if (data.match_rate !== undefined) {
              msg += ' | 匹配率: ' + data.match_rate + '%';
            }
            ElMessage.success(msg);
            // 通知题库首页刷新数据
            this.notifyBankRefresh();
          } else {
            ElMessage.warning(data.detail || '导入失败');
          }
          this.state.batchPreviewData = [];
          this.state.rawTextPreview = '';
          this.loadRecords();
        } catch (e) {
          ElMessage.error(this.handleFetchError(e, '批量导入'));
        }
        this.state.loading = false;
      },
      selectImage() {
        const self = this;
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/jpeg,image/png,image/bmp';
        input.multiple = true;
        input.onchange = function(e) {
          var files = Array.from(e.target.files);
          if (!files.length) return;
          self.state.selectedImageFiles = files;
          // 显示第一张预览
          var reader = new FileReader();
          reader.onload = function(ev) {
            self.state.imagePreviewUrl = ev.target.result;
            self.state.ocrText = '';
            self.state.ocrQuestions = [];
          };
          reader.readAsDataURL(files[0]);
          if (files.length > 1) {
            ElMessage.info('已选择 ' + files.length + ' 张图片（预览显示第一张）');
          }
        };
        input.click();
      },
      // ========== 图片 OCR 识别 → 调用后端 PaddleOCR ==========
      async ocrRecognize() {
        if (!this.state.imagePreviewUrl) {
          ElMessage.warning('请先选择图片');
          return;
        }
        this.state.ocrLoading = true;
        try {
          var res = await this.fetchWithRetry('/api/questions/import/ocr', {
            method: 'POST',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({
              image_base64: this.state.imagePreviewUrl
            })
          }, 120000, 0);  // OCR 可能耗时较长，设置 120s 超时
          var data = await res.json();
          if (!res.ok) {
            ElMessage.warning(data.detail || data.message || 'OCR识别失败 (HTTP ' + res.status + ')');
            this.state.ocrLoading = false;
            return;
          }
          if (data.status === 'success' && data.ocr_text) {
            this.state.ocrText = data.ocr_text;
            ElMessage.success(data.message || 'OCR 识别完成，请点击"智能提取题目"进行结构化');
          } else {
            ElMessage.warning(data.message || '未能识别到文字，请确认图片清晰度');
          }
        } catch (e) {
          ElMessage.error(this.handleFetchError(e, 'OCR识别') +
            '。提示：需要在用户目录安装 PaddleOCR 依赖');
        }
        this.state.ocrLoading = false;
      },
      // ========== 解析 OCR 文本 → 题目列表（后端Pipeline） ==========
      parseOcrTextToQuestions() {
        if (!this.state.ocrText) {
          ElMessage.warning('无 OCR 文本可解析');
          return;
        }
        // 调用后端统一解析（OCR模式）
        this.callBackendParse(
          this.state.ocrText,
          '',  // OCR无独立答案文本
          'ocr',
          this.state.batchPaperName || '图片OCR导入'
        ).then((function(result) {
          if (result && result.questions && result.questions.length) {
            this.state.ocrQuestions = this.state.parsedDocsQuestions.slice();
            this.state.parsedDocsQuestions = [];
            this.state.ocrAutoSubject = result.auto_detected_subject || '';
            this.state.ocrAutoSubcategories = [];
            ElMessage.success('已提取 ' + this.state.ocrQuestions.length + ' 道题目，请补充答案后导入');
          } else {
            // 回退到前端解析
            ElMessage.warning('后端解析未返回结果，尝试本地解析...');
            this.state.rawTextPreview = this.state.ocrText;
            this.state.importMode = 'separate';
            this.parseRawTextToQuestions();
            this.state.ocrQuestions = this.state.parsedDocsQuestions.slice();
            this.state.parsedDocsQuestions = [];
            if (!this.state.ocrQuestions.length) {
              ElMessage.warning('未能从OCR文本中提取题目结构，请确认图片包含标准题号格式');
            }
          }
        }).bind(this));
      },
      // ========== 一键识别并入库（OCR + 智能提取 + 自动分类 + 预览确认 + 导入） ==========
      async ocrAndImportStructured() {
        if (!this.state.imagePreviewUrl) {
          ElMessage.warning('请先选择图片');
          return;
        }
        this.state.ocrLoading = true;
        this.state.importProgress = 0;
        this.resetProgress('image');
        try {
          // 步骤1: OCR识别
          this.stepActive(0); this.setProgress(0, 10);
          ElMessage.info('正在OCR识别...');
          await this.ocrRecognize();
          this.state.importProgress = 25; this.setProgress(0, 50);
          if (!this.state.ocrText) {
            this.state.ocrLoading = false;
            this.resetProgress('');
            return;
          }
          this.stepDone(0); this.setProgress(0, 100);
          // 步骤2: 智能提取题目
          this.stepActive(1); this.setProgress(1, 30);
          this.parseOcrTextToQuestions();
          this.state.importProgress = 50; this.setProgress(1, 70);
          if (!this.state.ocrQuestions.length) {
            this.state.ocrLoading = false;
            this.resetProgress('');
            return;
          }
          this.stepDone(1); this.setProgress(1, 100);
          // 步骤3: 自动检测科目和子分类
          this.stepActive(2); this.setProgress(2, 20);
          var allText = this.state.ocrText;
          var detectedSubject = this.detectSubjectCategory([], allText);
          var subcategories = this.detectSubcategories(detectedSubject, allText);
          this.state.ocrAutoSubject = detectedSubject;
          this.state.ocrAutoSubcategories = subcategories;
          this.state.form.subject_category = detectedSubject;
          this.state.importProgress = 75; this.setProgress(2, 40);
          // 更新 ocrQuestions 中的科目和子分类
          for (var i = 0; i < this.state.ocrQuestions.length; i++) {
            this.state.ocrQuestions[i].subject_category = detectedSubject;
            var qText = this.state.ocrQuestions[i].question_content || '';
            var subcat = this.detectSubcategoryForQuestion(detectedSubject, qText);
            this.state.ocrQuestions[i].subcategory = subcat;
          }
          this.state.importProgress = 90;
          // 步骤4: 批量导入（使用后端结构化导入端点）
          var self = this;
          var res = await this.fetchWithRetry('/api/questions/import/image', {
            method: 'POST',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({
              image_base64: this.state.imagePreviewUrl,
              subject_category: detectedSubject,
              paper_name: this.state.batchPaperName || '图片OCR导入',
              structured_questions: this.state.ocrQuestions.map(function(q) {
                return {
                  content: q.question_content || q.content || '',
                  options: q.options || [],
                  answer: q.answer || '',
                  analysis: q.analysis || '',
                  question_type: q.question_type_detail || '单选题',
                  subcategory: q.subcategory || '',
                };
              }),
              auto_save: true
            })
          }, 60000, 2);
          var data = await res.json();
          this.state.importProgress = 100; this.setProgress(2, 100); this.stepDone(2);
          if (res.ok && (data.import_status === 'SUCCESS' || data.import_status === 'PARTIAL')) {
            ElMessage.success('图片导入完成：成功 ' + data.imported + ' 题' +
              (data.duplicates > 0 ? '，重复 ' + data.duplicates + ' 题（已跳过）' : '') +
              ' | 分类：' + detectedSubject + (subcategories.length ? ' - ' + subcategories.join('、') : ''));
            // 标记全部已导入
            for (var j = 0; j < self.state.ocrQuestions.length; j++) {
              self.state.ocrQuestions[j]._imported = true;
            }
            this.loadRecords();
            this.notifyBankRefresh();
          } else {
            ElMessage.warning(data.detail || data.message || '导入结果：成功' + (data.imported || 0) + '题');
          }
        } catch (e) {
          ElMessage.error(this.handleFetchError(e, '一键导入'));
        }
        this.state.ocrLoading = false;
        this.state.importProgress = 0;
      },
      // ========== OCR 题目单题导入 ==========
      async importSingleOcrQuestion(idx) {
        this.state.parsedDocsQuestions = this.state.ocrQuestions;
        await this.importSingleParsedQuestion(idx);
        this.state.ocrQuestions = this.state.parsedDocsQuestions;
        this.state.parsedDocsQuestions = [];
      },
      // ========== OCR 题目批量导入 ==========
      async importAllOcrQuestions() {
        this.state.parsedDocsQuestions = this.state.ocrQuestions;
        // 强制分离导入模式（OCR识别结果答案不可靠）
        var prevMode = this.state.importMode;
        this.state.importMode = 'separate';
        await this.importAllParsedQuestions();
        this.state.importMode = prevMode;
        this.state.ocrQuestions = this.state.parsedDocsQuestions;
        this.state.parsedDocsQuestions = [];
      },
      // ========== OCR 题目确认入库（预览确认后） ==========
      async importAllOcrQuestionsConfirmed() {
        // 检查是否有未填答案的题目
        var noAnswer = this.state.ocrQuestions.filter(function(q) {
          return (!q.answer || q.answer === '待补充') && !q._imported && !q._is_duplicate;
        });
        if (noAnswer.length > 0) {
          ElMessage.warning('有 ' + noAnswer.length + ' 道题目缺少答案，请手动补充后再导入');
          return;
        }
        // 通过单题导入接口逐题导入（保证去重和分类）
        this.state.parsedDocsQuestions = this.state.ocrQuestions;
        var prevMode = this.state.importMode;
        this.state.importMode = 'separate';
        await this.importAllParsedQuestions();
        this.state.importMode = prevMode;
        this.state.ocrQuestions = this.state.parsedDocsQuestions;
        this.state.parsedDocsQuestions = [];
        // 导入后更新自动分类状态
        var imported = this.state.ocrQuestions.filter(function(q) { return q._imported; }).length;
        if (imported > 0) {
          ElMessage.success('图片题目导入完成：成功 ' + imported + ' 题 | 分类：' + (this.state.ocrAutoSubject || '自动检测'));
        }
      },
      // ========== 二级分类检测（科目 -> 子类型） ==========
      detectSubcategories(subject, text) {
        if (!text) return [];
        var sample = text.substring(0, 3000);
        var result = [];
        if (subject === '行测') {
          var xcMap = {
            '常识判断': ['常识', '历史', '地理', '生物', '化学', '物理', '文化', '科技'],
            '言语理解与表达': ['语言', '理解', '表达', '阅读', '填空', '成语', '语句', '排序', '主旨', '意图'],
            '数量关系': ['数量', '数学', '计算', '方程', '几何', '排列组合', '概率', '数列', '行程'],
            '判断推理': ['判断', '推理', '逻辑', '类比', '定义', '削弱', '加强', '前提', '结论'],
            '资料分析': ['资料分析', '图表', '增长率', '百分比', '同比', '数据', '统计', '比重'],
            '政治理论': ['政治', '马克思', '习近平', '党建', '时政', '党史', '理论', '中特'],
          };
          for (var cat in xcMap) {
            for (var ki = 0; ki < xcMap[cat].length; ki++) {
              if (sample.indexOf(xcMap[cat][ki]) >= 0) { result.push(cat); break; }
            }
          }
        } else if (subject === '申论') {
          var slMap = {
            '归纳概括': ['概括', '归纳', '总结', '概述'],
            '综合分析': ['分析', '综合', '评析', '评述', '理解'],
            '提出对策': ['对策', '措施', '建议', '方案', '办法'],
            '应用文写作': ['应用文', '通知', '报告', '请示', '函', '简报'],
            '议论文写作': ['议论文', '论证', '论点', '论据', '作文'],
          };
          for (var cat2 in slMap) {
            for (var kj = 0; kj < slMap[cat2].length; kj++) {
              if (sample.indexOf(slMap[cat2][kj]) >= 0) { result.push(cat2); break; }
            }
          }
        } else if (subject === '公专') {
          var gzMap = {
            '职业素养': ['职业', '素养', '道德', '纪律', '规范', '警风', '廉洁', '作风'],
            '基础知识': ['基础', '法律', '法规', '治安', '刑事', '交通', '消防', '公安', '警察', '机关', '侦查', '取证', '拘留', '逮捕', '犯罪', '刑罚', '诉讼', '证据', '宪法', '民法', '行政'],
            '基本警务能力': ['警务', '勤务', '巡逻', '盘查', '处置', '控制', '应急', '实战', '战术', '武器', '警械'],
          };
          for (var cat3 in gzMap) {
            for (var kk = 0; kk < gzMap[cat3].length; kk++) {
              if (sample.indexOf(gzMap[cat3][kk]) >= 0) { result.push(cat3); break; }
            }
          }
        }
        return result;
      },
      // ========== 单题子分类检测 ==========
      detectSubcategoryForQuestion(subject, questionText) {
        if (!questionText) return '';
        var sample = questionText.substring(0, 500);
        if (subject === '行测') {
          var xcMap = {
            '常识判断': ['常识', '历史', '地理', '生物', '化学', '物理', '文化', '科技'],
            '言语理解与表达': ['语言', '理解', '表达', '阅读', '填空', '成语', '语句', '排序', '主旨'],
            '数量关系': ['数量', '数学', '计算', '方程', '几何', '排列组合', '概率', '数列'],
            '判断推理': ['判断', '推理', '逻辑', '类比', '定义', '削弱', '加强', '前提'],
            '资料分析': ['资料分析', '图表', '增长率', '百分比', '同比', '数据'],
            '政治理论': ['政治', '马克思', '习近平', '党建', '时政'],
          };
          for (var cat in xcMap) {
            for (var ki = 0; ki < xcMap[cat].length; ki++) {
              if (sample.indexOf(xcMap[cat][ki]) >= 0) return cat;
            }
          }
        } else if (subject === '申论') {
          if (/概括|归纳|总结|概述/.test(sample)) return '归纳概括';
          if (/分析|综合|评析|评述/.test(sample)) return '综合分析';
          if (/对策|措施|建议|方案|办法/.test(sample)) return '提出对策';
          if (/应用文|通知|报告|请示|函|简报/.test(sample)) return '应用文写作';
          if (/议论文|论证|论点|论据|作文/.test(sample)) return '议论文写作';
        } else if (subject === '公专') {
          if (/职业|素养|道德|纪律|规范|警风|廉洁|作风/.test(sample)) return '职业素养';
          if (/警务|勤务|巡逻|盘查|处置|控制|应急|实战|战术|武器|警械/.test(sample)) return '基本警务能力';
          return '基础知识'; // 公专默认
        }
        return '';
      },
      // ========== OCR 题目二次校验 ==========
      reVerifyOcrQuestion(idx) {
        this.state.parsedDocsQuestions = this.state.ocrQuestions;
        this.state.rawTextPreview = this.state.ocrText;
        this.reVerifyQuestion(idx);
        this.state.ocrQuestions = this.state.parsedDocsQuestions;
        this.state.parsedDocsQuestions = [];
      },
      // 自动检测科目大类
      detectSubjectCategory(headerLines, blocksText) {
        var sample = (headerLines || []).join(' ') + ' ' + (blocksText || '').substring(0, 2000);
        if (/公安|公专|警务|治安|刑事|法律基础/i.test(sample)) return '公专';
        if (/申论|概括|对策|议论文|应用文|综合分析/i.test(sample)) return '申论';
        if (/行测|数量|资料分析|判断推理|言语|常识|速度与知觉/i.test(sample)) return '行测';
        return '公专'; // 默认
      },
      // P0-3 题型判定：降级为**兜底**，不再在前端重新裁决
      //
      // 历史事故（本函数是第 3 套题型判定实现，与后端 text_parser._detect_question_type
      // 各写各的）。两个调用点都是 `q.question_type_detail = this.detectQuestionType(...)`
      // 无条件覆盖，把后端算好的结果丢掉，于是：
      //   1) `/多选|多项选择|不定项/.test(text) → 多选题`
      //      会命中**粘连进题干的分节指令段**（"二、多项选择题。请从每题…"），
      //      把一道单选题误判为多选题 —— 这正是"试卷里显示多选题"但答案只有 1 个字母的成因；
      //   2) `text.length > 200 → 写作题` / `> 80 → 论述题`
      //      使选项解析失败的长选择题被误判为主观题。
      //
      // 新策略：题型以**后端返回的 question_type_detail 为准**；
      // 仅当后端未给值时才用下面的保守规则兜底，且规则不再依赖文本长度。
      _stripSectionDirective(text) {
        if (!text) return '';
        // 去掉粘连的分节指令段与材料头，避免其关键词污染题型判定
        return String(text)
          .replace(/[一二三四五六七八九十]{1,3}\s*[、，．.]\s*(?:单项选择题|多项选择题|不定项选择题|选择题|判断题|情景分析题|案例分析题|简答题|简述题|论述题|写作题|材料题)[^\n]{0,120}/g, ' ')
          .replace(/(?:根据|阅读)(?:以下|下面)[^\n]{0,20}?回答[ \t]*\d+[ \t]*[-~—－至][ \t]*\d+[ \t]*题/g, ' ');
      },
      _judgeOptionText(o) {
        var s = '';
        if (o == null) return s;
        if (typeof o === 'string') s = o;
        else if (typeof o === 'object') s = o.value || o.text || o.label || '';
        return String(s).replace(/^[A-H]\s*[.、．)）\]]\s*/, '').trim();
      },
      // 兜底题型判定（仅在后端未提供 question_type_detail 时使用）
      detectQuestionType(questionContent, options, answer = '', backendType = '') {
        // 1) 后端结论优先
        if (backendType) return backendType;

        var text = this._stripSectionDirective(questionContent);
        var opts = (options && Array.isArray(options)) ? options : [];
        var optCount = opts.filter(function (o) { return this._judgeOptionText(o); }, this).length;
        var ans = String((answer || '')).trim().toUpperCase();
        var letters = ans.replace(/[^A-H]/g, '');
        var JUDGE_WORDS = ['正确', '错误', '对', '错', 'TRUE', 'FALSE', 'T', 'F'];

        // 2) 答案格式是硬信号，优先级最高
        if (letters.length >= 2) return '多选题';
        if (letters.length === 1 && optCount >= 2) return '单选题';
        if (JUDGE_WORDS.indexOf(ans) >= 0) return '判断题';

        // 3) 判断题：选项恰好是 {正确,错误} 或 {对,错}
        if (optCount === 2) {
          var texts = opts.map(this._judgeOptionText, this);
          var isJudgePair =
            (texts.some(function (t) { return /正确|对/.test(t); }) &&
             texts.some(function (t) { return /错误|错/.test(t); }));
          if (isJudgePair) return '判断题';
        }

        // 4) 有选项但无答案 → 走题干关键词，仍无结论则保守判单选
        if (optCount >= 2) {
          if (/多选|多项选择|不定项|正确的有|错误的有/.test(text)) return '多选题';
          return '单选题';
        }

        // 5) 无选项 → 主观题，按关键词细分（不再用文本长度当信号）
        if (/判断|对错|是否正确|正确还是错误/.test(text)) return '判断题';
        if (/作文|写作|撰写|写一篇|请以.{0,20}为题|自拟标题|议论文|应用文|不少于\d{2,4}字/.test(text)) return '写作题';
        if (/论述|试述|评析|阐述|论证|如何理解|谈谈你的/.test(text)) return '论述题';
        if (/简述|简答|列举|概括|归纳/.test(text)) return '简答题';
        if (/填空|_{3,}|＿{3,}|横线处/.test(text)) return '填空题';
        return '简答题';
      },
      /** ========== 进度条控制 ========== */
      setProgress(phase, percent, steps) {
        this.state.progressPhase = phase;
        this.state.progressPercent = percent;
        if (steps) this.state.progressSteps = steps;
      },
      resetProgress(mode) {
        var steps;
        if (mode === 'combined') {
          steps = [
            { label: '文档解析', status: 'pending' },
            { label: '导入入库', status: 'pending' }
          ];
        } else if (mode === 'separate') {
          steps = [
            { label: '题目解析', status: 'pending' },
            { label: '答案解析', status: 'pending' },
            { label: '智能匹配', status: 'pending' },
            { label: '导入入库', status: 'pending' }
          ];
        } else {
          steps = [
            { label: 'OCR识别', status: 'pending' },
            { label: '题目提取', status: 'pending' },
            { label: '导入入库', status: 'pending' }
          ];
        }
        this.state.progressSteps = steps;
        this.state.progressPhase = 0;
        this.state.progressPercent = 0;
      },
      stepDone(idx) {
        if (this.state.progressSteps[idx]) this.state.progressSteps[idx].status = 'done';
      },
      stepActive(idx) {
        for (var i = 0; i < this.state.progressSteps.length; i++) {
          this.state.progressSteps[i].status = i < idx ? 'done' : (i === idx ? 'active' : 'pending');
        }
        this.state.progressPhase = idx;
      },

      /**
       * ========== 统一后端解析（替代所有前端本地解析逻辑） ==========
       * 调用 POST /api/questions/import/parse，返回 ParseResult
       */
      async callBackendParse(questionsText, answersText, mode, paperName) {
        mode = mode || 'combined';
        paperName = paperName || this.state.batchPaperName || '';
        this.state.parseLoading = true;
        this.state.parseError = '';
        try {
          var res = await this.fetchWithRetry('/api/questions/import/parse', {
            method: 'POST',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({
              questions_text: questionsText || '',
              answers_text: answersText || '',
              mode: mode,
              paper_name: paperName,
              subject_category: this.state.form.subject_category || ''
            })
          }, 30000, 1);
          var data = await res.json();
          if (!res.ok) {
            this.state.parseError = data.detail || '解析失败 (HTTP ' + res.status + ')';
            ElMessage.error(this.state.parseError);
            this.state.parseLoading = false;
            return null;
          }
          // 转换为前端兼容格式（附加 _imported, _is_duplicate 等UI状态字段）
          var questions = (data.questions || []).map(function(q, i) {
            return {
              question_number: q.question_number || (i + 1),
              question_content: q.question_content || '',
              options: q.options || [],
              answer: q.answer || '待补充',
              analysis: q.analysis || '',
              question_type_detail: q.question_type || '单选题',
              subject_category: q.subject_category || '公专',
              images: q.images || [],
              _imported: false,
              _is_duplicate: false,
              _similarity: 0,
              _existing_id: null,
              _source: 'backend_pipeline'
            };
          });
          this.state.parseResult = data;
          this.state.parsedDocsQuestions = questions;
          this.state.separateMatchRate = data.match_rate || 0;
          if (data.auto_detected_subject) {
            this.state.form.subject_category = data.auto_detected_subject;
          }
          // 从后端返回结果中提取试卷标题
          if (data.paper_name && data.paper_name !== '分离导入试卷' && data.paper_name !== 'Word批量导入' && data.paper_name !== '图片OCR导入') {
            this.state.batchPaperName = data.paper_name;
          }
          if (data.warnings && data.warnings.length) {
            for (var wi = 0; wi < data.warnings.length; wi++) {
              ElMessage.warning(data.warnings[wi]);
            }
          }
          this.state.parseLoading = false;
          return data;
        } catch (e) {
          this.state.parseError = this.handleFetchError(e, '文档解析');
          ElMessage.error(this.state.parseError);
          this.state.parseLoading = false;
          return null;
        }
      },
      parseRawTextToQuestions() {
        var text = this.state.rawTextPreview;
        if (!text) {
          ElMessage.warning('无文本可解析');
          return;
        }
        // Line-by-line streaming parser: scan each line,
        // start new question block on "N." / "N、" / "N．" / "N)" at line start,
        // accumulate all subsequent lines until next question number.
        var lines = text.split(/\n/);
        var blocks = [];
        var currentNum = null;
        var currentLines = [];
        var headerLines = [];
        // 支持更多题号格式：1.  1、  1．  1)   (1)  [1]  第1题
        var questionHeaderRe = /^\s*(?:第\s*)?(\d+)\s*(?:[\.\u3001\uff0e\)\]）]|\s*题)/;

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i];
          var m = line.match(questionHeaderRe);
          if (m) {
            // Start new question: save previous block first
            if (currentNum !== null && currentLines.length > 0) {
              blocks.push({ num: currentNum, lines: currentLines.slice() });
            }
            currentNum = parseInt(m[1]);
            // Remove the question number prefix from first line
            var rest = line.replace(questionHeaderRe, '').trim();
            currentLines = rest ? [rest] : [];
          } else if (currentNum === null) {
            // Before first question number: collect header info
            var trimmed = line.trim();
            if (trimmed) headerLines.push(trimmed);
          } else {
            // Continue current question block
            currentLines.push(line);
          }
        }
        // Save last block
        if (currentNum !== null && currentLines.length > 0) {
          blocks.push({ num: currentNum, lines: currentLines.slice() });
        }

        if (!blocks.length) {
          ElMessage.warning('未能识别出题目结构，请检查文档格式');
          return;
        }

        // 汇总所有题目文本用于检测全局科目
        var allBlocksText = blocks.map(function(b) { return b.lines.join('\n'); }).join('\n');
        var detectedSubject = this.detectSubjectCategory(headerLines, allBlocksText);

        // Parse each block into structured question
        var questions = [];
        for (var j = 0; j < blocks.length; j++) {
          var fullText = blocks[j].lines.join('\n').trim();
          if (!fullText || fullText.length < 4) continue;
          var q = this.extractQuestionFromBlock(fullText);
          if (q && q.question_content) {
            // 附加来源题号（用于分离导入的题号精确匹配）
            q.question_number = blocks[j].num;
            // P0-3：仅在后端未给出题型时才用前端兜底规则，不再无条件覆盖
            q.question_type_detail = this.detectQuestionType(
              q.question_content, q.options, q.answer || '', q.question_type_detail
            );
            // 自动检测科目
            q.subject_category = detectedSubject;
            q.score = 1;
            q.difficulty = 3;
            q._imported = false;
            questions.push(q);
          }
        }

        if (!questions.length) {
          ElMessage.warning('未能提取有效题目，请检查文档格式');
          return;
        }
        this.state.parsedDocsQuestions = questions;
        this.state._lastParseCount = questions.length;
        // 合并导入：检测并处理尾部答案模式
        if (this.state.importMode === 'combined') {
          var subMode = this._detectCombinedSubMode(text);
          this.state.combinedSubMode = subMode;
          if (subMode === 'tail') {
            // 尾部答案模式：匹配题目与答案
            var answerMap = this.parseAnswerTextToMap(this.splitQuestionsAndAnswersSection(text).answersText);
            var tailMatched = 0;
            for (var tk = 0; tk < questions.length; tk++) {
              var ansEntry = answerMap[tk + 1];
              if (ansEntry) {
                if (ansEntry.answer && !questions[tk].answer) {
                  questions[tk].answer = ansEntry.answer;
                  tailMatched++;
                }
                if (ansEntry.analysis) {
                  questions[tk].analysis = ansEntry.analysis;
                }
              }
            }
            if (tailMatched > 0) {
              ElMessage.success('尾部答案匹配：' + tailMatched + ' 题已匹配');
            }
          }
        }
        var withAnswer = questions.filter(function(q) { return q.answer && q.answer !== '待补充'; }).length;
        var withoutAnswer = questions.length - withAnswer;
        ElMessage.success('已提取 ' + questions.length + ' 道题目（含答案 ' + withAnswer + ' 题' +
          (withoutAnswer ? '，其中 ' + withoutAnswer + ' 题缺少答案' : '') + '）');
        
        // 自动提取试卷标题
        this.extractAndSetPaperTitle(text, questions);
      },
      extractAndSetPaperTitle(rawText, questions) {
        if (!rawText) return;
        // 从文档首行提取标题
        var lines = rawText.trim().split('\n');
        for (var i = 0; i < Math.min(5, lines.length); i++) {
          var line = lines[i].trim();
          if (line && line.length > 3 && !/^UTB[a-f0-9]{16}/i.test(line) && !/^第\s*\d+\s*题[：:]/.test(line)) {
            this.state.batchPaperName = line.substring(0, 100);
            break;
          }
        }
        // 如果首行没有有效标题，尝试从第一题内容推断
        if (!this.state.batchPaperName && questions.length > 0) {
          var firstQ = questions[0].question_content || questions[0].content || '';
          var match = firstQ.match(/^([^第]+?(?:考试|测验|真题|模拟|练习))/);
          if (match) this.state.batchPaperName = match[1].trim();
        }
      },
      extractQuestionFromBlock(block) {
        if (!block) return null;
        var allLines = block.split(/\n/).map(function(l) { return l.trim(); }).filter(Boolean);
        if (!allLines.length) return null;

        var questionContent = '';
        var options = [];
        var answer = '';

        for (var i = 0; i < allLines.length; i++) {
          var line = allLines[i];

          // === 答案识别（多种模式，放在最前面优先匹配） ===
          // 模式1: 【答案】C / 【答案】 CD / 答案：C / <答案>C
          var ansBracket = line.match(/[\u3010\u300a<\[]?\s*\u7b54\u6848\s*[\u3011\u300b>\]\uff1a:]?\s*[:.\uff1a\uff1a]?\s*([A-Da-d\u5bf9\u9519\u6b63\u786e\u9519\u8bef\u662f\u5426]+)/);
          if (ansBracket) {
            var aRaw = ansBracket[1].toUpperCase();
            // 处理中文答案
            if (aRaw === '\u5bf9' || aRaw === '\u6b63\u786e' || aRaw === '\u662f') aRaw = 'A';
            else if (aRaw === '\u9519' || aRaw === '\u9519\u8bef' || aRaw === '\u5426') aRaw = 'B';
            answer = aRaw;
            continue;
          }

          // 模式2: 参考答案：C / 答案：D / Answer: C
          var ansLabel = line.match(/^(?:\u53c2\u8003)?\u7b54\u6848\s*[:.\uff1a\uff1a]\s*([A-Da-d\u5bf9\u9519\u6b63\u786e\u9519\u8bef\u662f\u5426]+)/i);
          if (ansLabel) {
            var aRaw2 = ansLabel[1].toUpperCase();
            if (aRaw2 === '\u5bf9' || aRaw2 === '\u6b63\u786e' || aRaw2 === '\u662f') aRaw2 = 'A';
            else if (aRaw2 === '\u9519' || aRaw2 === '\u9519\u8bef' || aRaw2 === '\u5426') aRaw2 = 'B';
            answer = aRaw2;
            continue;
          }

          // 模式3: Answer: C (英文)
          var ansEng = line.match(/^answer\s*[:.\uff1a]\s*([A-Da-d]+)/i);
          if (ansEng) {
            answer = ansEng[1].toUpperCase();
            continue;
          }

          // 模式4: 正确选项：C / 正确答案: C
          var ansCorrect = line.match(/(?:\u6b63\u786e\u9009\u9879|\u6b63\u786e\u7b54\u6848)\s*[:.\uff1a]\s*([A-Da-d]+)/);
          if (ansCorrect) {
            answer = ansCorrect[1].toUpperCase();
            continue;
          }

          // === 选项识别（支持更多格式） ===
          // A. xxx / A、xxx / A．xxx / A) xxx / A）xxx / (A) xxx / [A] xxx
          //
          // 先检测同行多选项（如 "A. xxx B. xxx C. xxx D. xxx"）
          // 用 replace+回调 提取所有选项标记，避免选项间内容错误拼接
          var multiOpts = [];
          var contentBeforeOpts = '';
          line.replace(/\s*([A-Ha-h])\s*[\)\]\.\u3001\uff0e\uff09\)]\s*(.+?)(?=\s*[A-Ha-h]\s*[\)\]\.\u3001\uff0e\uff09\)]|$)/g, function(m, letter, val, offset) {
            if (multiOpts.length === 0) contentBeforeOpts = line.substring(0, offset).trim();
            multiOpts.push({ key: letter.toUpperCase(), value: val.replace(/[;\uff1b]$/, '').trim() });
            return '';
          });
          // 同行多选项分离：≥2 个选项标记时视为同行多选项
          if (multiOpts.length >= 2) {
            if (contentBeforeOpts) {
              questionContent += (questionContent ? '\n' : '') + contentBeforeOpts;
            }
            for (var mi = 0; mi < multiOpts.length; mi++) {
              options.push(multiOpts[mi]);
            }
            continue;
          }
          // 仅1个选项标记 → 回退到精确行首匹配（避免误匹配段落中的字母）
          var optMatch = line.match(/^[\(\[]?\s*([A-Ha-h])\s*[\)\]\.\u3001\uff0e\uff09\)]\s*(.+)/);
          if (optMatch && optMatch[2].length > 0) {
            options.push({ key: optMatch[1].toUpperCase(), value: optMatch[2].replace(/[;\uff1b]$/, '').trim() });
            continue;
          }

          // 模式5: 末尾孤立的单个大写字母（可能是答案）
          if (options.length >= 2 && /^[A-Da-d]$/.test(line) && questionContent) {
            answer = line.toUpperCase();
            continue;
          }

          // 模式6: 末尾行是 正确/错误/对/错（对错型单选题）
          if (options.length >= 1 && /^[\u5bf9\u9519\u6b63\u786e\u9519\u8bef\u662f\u5426]$/.test(line) && questionContent) {
            answer = /[\u5bf9\u6b63\u786e\u662f]/.test(line) ? 'A' : 'B';
            continue;
          }

          // Otherwise, part of question content
          questionContent += (questionContent ? '\n' : '') + line;
        }

        // Clean question content: remove leading section headers
        questionContent = questionContent
          .replace(/^[\u4e00-\u9fff]{1,3}[、.)）]\s*(?:单项选择|多项选择|不定项选择|判断|填空|简答|论述|案例分析).*?\n?/g, '')
          .replace(/^一[、.]\s*\u5355\u9879\u9009\u62e9.*?\n?/g, '')
          .replace(/^二[、.]\s*\u591a\u9879\u9009\u62e9.*?\n?/g, '')
          .replace(/^三[、.]\s*\u5224\u65ad\u9898.*?\n?/g, '')
          .trim();

        // 回退：若选项不足3个，从questionContent中尝试重新提取
        if (options.length < 3 && questionContent) {
          var retryOpts = [];
          // 在questionContent中搜索所有A/B/C/D选项标记
          var retryRe = /([A-D])\s*[.、．)）]\s*(.+?)(?=\s*[A-D]\s*[.、．)）]|$)/g;
          var retryMatch;
          while ((retryMatch = retryRe.exec(questionContent)) !== null) {
            var rkey = retryMatch[1].toUpperCase();
            var rval = retryMatch[2].trim().replace(/[;；\s]+$/, '');
            if (rval) retryOpts.push({ key: rkey, value: rval });
          }
          if (retryOpts.length >= 3) {
            options = retryOpts;
            // 从questionContent中移除选项行
            questionContent = questionContent.replace(/\n?\s*[A-D]\s*[.、．)）]\s*.+/g, ' ').trim();
          }
        }

        if (!questionContent && options.length) {
          questionContent = '（请查看选项内容）';
        }

        // 提供默认空选项确保结构化完整
        var finalOptions = options.length >= 2
          ? options
          : [{ key: 'A', value: '' }, { key: 'B', value: '' }, { key: 'C', value: '' }, { key: 'D', value: '' }];

        return {
          question_content: questionContent.substring(0, 2000),
          options: finalOptions,
          answer: answer || '',
          analysis: ''
        };
      },
      // ========== 分离导入：上传题目文件 ==========
      uploadSeparateQuestionFile() {
        var self = this;
        var input = document.createElement('input');
        input.type = 'file';
        input.accept = '.docx,.pdf,.txt,.xlsx,.xls,.csv';
        input.onchange = function(e) {
          var file = e.target.files[0];
          if (!file) return;
          self.state.separateQuestionsFileName = file.name;
          self.state.separateAnswersLoaded = false;
          self.state.separateAnswersFileName = '';
          self.state.parsedDocsQuestions = [];
          var reader = new FileReader();
          reader.onload = function(ev) {
            var text = ev.target.result;
            self.state.separateQuestionsRawText = text;
            // 解析题目
            self.state.rawTextPreview = text;
            self.parseRawTextToQuestions();
            // 将解析结果保存到分离导入上下文
            self.state.separateQuestionsLoaded = true;
            self.state.parsedDocsQuestions = [];
            ElMessage.success('题目文件已解析：' + self.state._lastParseCount + ' 题，请上传答案解析文件');
          };
          // 根据文件类型选择读取方式
          if (file.name.endsWith('.txt')) {
            reader.readAsText(file, 'UTF-8');
          } else if (file.name.endsWith('.docx') || file.name.endsWith('.pdf')) {
            // 非txt文件通过后端提取文本
            self._readDocViaBackend(file, function(text) {
              self.state.separateQuestionsRawText = text;
              self.state.rawTextPreview = text;
              self.parseRawTextToQuestions();
              self.state.separateQuestionsLoaded = true;
              self.state.parsedDocsQuestions = [];
              ElMessage.success('题目文件已解析：' + self.state._lastParseCount + ' 题，请上传答案解析文件');
            });
          } else {
            reader.readAsText(file, 'UTF-8');
          }
        };
        input.click();
      },
      // ========== 分离导入：上传答案文件 ==========
      uploadSeparateAnswerFile() {
        var self = this;
        if (!this.state.separateQuestionsLoaded) {
          ElMessage.warning('请先上传题目文件');
          return;
        }
        var input = document.createElement('input');
        input.type = 'file';
        input.accept = '.docx,.pdf,.txt,.xlsx,.xls,.csv';
        input.onchange = function(e) {
          var file = e.target.files[0];
          if (!file) return;
          self.state.separateAnswersFileName = file.name;
          var reader = new FileReader();
          reader.onload = function(ev) {
            var text = ev.target.result;
            self.state.separateAnswersRawText = text;
            self.state.separateAnswersLoaded = true;
            ElMessage.success('答案解析文件已加载，点击"匹配题目与解析"进行配对');
          };
          if (file.name.endsWith('.txt')) {
            reader.readAsText(file, 'UTF-8');
          } else if (file.name.endsWith('.docx') || file.name.endsWith('.pdf')) {
            self._readDocViaBackend(file, function(text) {
              self.state.separateAnswersRawText = text;
              self.state.separateAnswersLoaded = true;
              ElMessage.success('答案解析文件已加载，点击"匹配题目与解析"进行配对');
            });
          } else {
            reader.readAsText(file, 'UTF-8');
          }
        };
        input.click();
      },
      // ========== 统一题号提取器（支持多种格式） ==========
      // 返回 [{ index, number, format, lineStart, lineEnd }]，按出现顺序排列
      _extractQuestionNumbers(rawText) {
        if (!rawText) return [];
        var results = [];
        var lines = rawText.split(/\n/);
        // 5种格式按优先级检测，每个位置只取第一个命中
        var patterns = [
          { name: '第N题',  re: /^\s*第\s*(\d+)\s*题/ },
          { name: 'N.',     re: /^\s*(\d+)\s*[.\u3001\uff0e]/ },
          { name: '(N)',    re: /^\s*[（(]\s*(\d+)\s*[）)]/ },
          { name: '[N]',   re: /^\s*[\[【]\s*(\d+)\s*[\]】]/ },
          { name: 'N)',     re: /^\s*(\d+)\s*[)）]/ },
        ];
        for (var li = 0; li < lines.length; li++) {
          var line = lines[li];
          for (var pi = 0; pi < patterns.length; pi++) {
            var m = line.match(patterns[pi].re);
            if (m) {
              var num = parseInt(m[1]);
              // 去重：同一题号可能因格式被多次识别
              var dup = false;
              for (var ri = results.length - 1; ri >= 0 && ri >= results.length - 3; ri--) {
                if (results[ri].number === num && (li - results[ri].lineStart) <= 2) {
                  dup = true; break;
                }
              }
              if (!dup) {
                results.push({ index: results.length, number: num, format: patterns[pi].name, lineStart: li, lineEnd: li });
              }
              break; // 每种格式只取第一个命中，跳到下一行
            }
          }
        }
        return results;
      },
      // ========== 分离导入：答案文本解析（使用统一题号提取） ==========
      parseAnswerTextToMap(rawText) {
        if (!rawText) return {};
        var answerMap = {};
        var dupWarnings = [];
        var lines = rawText.split(/\n/);
        // 使用统一题号提取器找到所有题号位置
        var numPositions = this._extractQuestionNumbers(rawText);
        if (!numPositions.length) {
          // 回退：尝试按行扫描独立大写字母作为答案（无题号的纯答案序列）
          return this._parseAnswerSequence(rawText);
        }
        for (var ni = 0; ni < numPositions.length; ni++) {
          var pos = numPositions[ni];
          var startLine = pos.lineStart;
          // 计算结束行：下一个题号位置的前一行，或文件末尾
          var endLine = (ni < numPositions.length - 1)
            ? numPositions[ni + 1].lineStart - 1
            : lines.length - 1;
          if (endLine < startLine) endLine = startLine;
          // 提取该题号对应的文本块（首行去掉题号前缀）
          var blockLines = [];
          for (var li = startLine; li <= endLine; li++) {
            if (li === startLine) {
              // 去掉首行的题号部分，保留后续内容
              var cleaned = lines[li].replace(/^\s*(?:第\s*\d+\s*题|（?\d+）?|[\[【]\d+[\]】]|\d+\s*[.\u3001\uff0e)）])\s*/, '').trim();
              if (cleaned) blockLines.push(cleaned);
            } else {
              blockLines.push(lines[li]);
            }
          }
          var fullBlock = blockLines.join('\n').trim();
          // 如果该文本块为空，尝试合并到下一个题号（可能是题号连续标注）
          if (!fullBlock && ni < numPositions.length - 1) continue;
          var extracted = this._extractAnswerFromLines(blockLines);
          var ans = extracted.answer;
          // 如果没提取到答案，尝试在整个原始文本范围内搜索该题号的答案
          if (!ans) {
            var looseRe = new RegExp('(?:^|\\n)\\s*' + this._escapeRegExp(String(pos.number)) + '\\s*[.、．)）]\\s*([A-Da-d]+)', 'm');
            var looseM = rawText.match(looseRe);
            if (looseM) ans = looseM[1].toUpperCase().replace(/[^A-D]/g, '');
          }
          // 重复检测
          if (answerMap.hasOwnProperty(pos.number)) {
            dupWarnings.push(pos.number);
            // 保留第一条
            if (!answerMap[pos.number].answer && ans) {
              answerMap[pos.number] = { answer: ans, analysis: extracted.analysis || fullBlock };
            }
          } else {
            answerMap[pos.number] = { answer: ans, analysis: extracted.analysis || fullBlock };
          }
        }
        // 存储重复警告供 matchSeparateQuestionsAnswers 使用
        this._answerDupWarnings = dupWarnings;
        return answerMap;
      },
      // 从解析文本行中提取答案和解析内容
      _extractAnswerFromLines(lines) {
        var fullText = lines.join('\n').trim();
        var answer = '';
        var analysis = fullText;
        // 答案模式匹配
        var ansPatterns = [
          /[\u3010\u300a<\[]?\s*\u7b54\u6848\s*[\u3011\u300b>\]\uff1a:]?\s*[:.\uff1a]?\s*([A-Da-d\u5bf9\u9519\u6b63\u786e\u9519\u8bef\u662f\u5426]+)/,
          /^(?:\u53c2\u8003)?\u7b54\u6848\s*[:.\uff1a]\s*([A-Da-d]+)/i,
          /(\u6b63\u786e\u9009\u9879|\u6b63\u786e\u7b54\u6848)\s*[:.\uff1a]\s*([A-Da-d]+)/
        ];
        for (var pi = 0; pi < ansPatterns.length; pi++) {
          var am = fullText.match(ansPatterns[pi]);
          if (am) {
            var raw = (am[2] || am[1]).toUpperCase();
            if (raw === '\u5bf9' || raw === '\u6b63\u786e' || raw === '\u662f') raw = 'A';
            else if (raw === '\u9519' || raw === '\u9519\u8bef' || raw === '\u5426') raw = 'B';
            answer = raw.replace(/[^A-D]/g, '');
            // 尝试去掉答案行保留解析
            var ansLineIdx = -1;
            for (var li = 0; li < lines.length; li++) {
              if (lines[li].indexOf(am[0]) >= 0) { ansLineIdx = li; break; }
            }
            if (ansLineIdx >= 0) {
              analysis = lines.slice(ansLineIdx + 1).join('\n').trim();
              if (!analysis) analysis = lines.slice(0, ansLineIdx).join('\n').trim();
            }
            break;
          }
        }
        // 末行孤立大写字母
        if (!answer && lines.length > 0) {
          var lastLine = lines[lines.length - 1].trim();
          if (/^[A-Da-d]$/.test(lastLine)) {
            answer = lastLine.toUpperCase();
            analysis = lines.slice(0, lines.length - 1).join('\n').trim();
          }
        }
        return { answer: answer, analysis: analysis || fullText };
      },
      // ========== 正则特殊字符转义 ==========
      _escapeRegExp(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      },
      // ========== 字符串相似度计算（用于检测重复文件） ==========
      _textSimilarity(a, b) {
        if (!a || !b) return 0;
        // 简单Jaccard相似度：基于字符3-gram
        var gramsA = new Set();
        var gramsB = new Set();
        var maxLen = Math.min(a.length, b.length);
        for (var i = 0; i < Math.min(a.length - 2, 8000); i++) gramsA.add(a.substring(i, i + 3));
        for (var j = 0; j < Math.min(b.length - 2, 8000); j++) gramsB.add(b.substring(j, j + 3));
        var intersection = 0;
        gramsA.forEach(function(g) { if (gramsB.has(g)) intersection++; });
        var union = gramsA.size + gramsB.size - intersection;
        return union > 0 ? intersection / union : 0;
      },
      // ========== 解析连续答案序列：1-5: ABCCD / 6-10: DABCD ==========
      _parseAnswerSequence(rawText) {
        if (!rawText) return {};
        var map = {};
        // 模式1: 1-5: ABCCD 或 1～5：ABCCD
        var rangeRe = /(\d+)\s*[-～~]\s*(\d+)\s*[:：\uff1a]\s*([A-Da-d]+)/g;
        var m;
        while ((m = rangeRe.exec(rawText)) !== null) {
          var start = parseInt(m[1]);
          var answers = m[3].toUpperCase().split('');
          for (var i = 0; i < answers.length && (start + i) <= parseInt(m[2]); i++) {
            if (/[A-D]/.test(answers[i])) {
              map[start + i] = { answer: answers[i], analysis: '' };
            }
          }
        }
        // 模式2: 1.C 2.B 3.A 4.D (单行逐个)
        var singleRe = /(\d+)\s*[\.\u3001\uff0e\)\]）]\s*([A-Da-d\u5bf9\u9519\u6b63\u786e\u9519\u8bef\u662f\u5426])/g;
        while ((m = singleRe.exec(rawText)) !== null) {
          var num = parseInt(m[1]);
          var raw = m[2].toUpperCase();
          if (raw === '\u5bf9' || raw === '\u6b63\u786e' || raw === '\u662f') raw = 'A';
          else if (raw === '\u9519' || raw === '\u9519\u8bef' || raw === '\u5426') raw = 'B';
          if (/[A-D]/.test(raw) && !map[num]) {
            map[num] = { answer: raw, analysis: '' };
          }
        }
        // 模式3: 纯答案序列（无题号，按顺序匹配）: A B C D A B C D
        var pureSeqRe = /^[\s\n]*([A-Da-d\u5bf9\u9519\u6b63\u786e\u9519\u8bef\u662f\u5426]+)[\s\n]*$/;
        var pureMatch = rawText.trim().match(pureSeqRe);
        if (pureMatch && Object.keys(map).length === 0) {
          var chars = pureMatch[1].split('');
          var clean = [];
          for (var ci = 0; ci < chars.length; ci++) {
            var ch = chars[ci].toUpperCase();
            if (ch === '\u5bf9' || ch === '\u6b63\u786e' || ch === '\u662f') clean.push('A');
            else if (ch === '\u9519' || ch === '\u9519\u8bef' || ch === '\u5426') clean.push('B');
            else if (/[A-D]/.test(ch)) clean.push(ch);
          }
          for (var ni = 0; ni < clean.length; ni++) {
            map[ni + 1] = { answer: clean[ni], analysis: '' };
          }
        }
        return map;
      },
      // ========== 从完整试卷文本中提取每个题块的内联答案 ==========
      _reExtractInlineAnswers(rawText) {
        // 使用统一题号提取器定位所有题块
        var numPositions = this._extractQuestionNumbers(rawText);
        if (!numPositions.length) return {};
        var lines = rawText.split(/\n/);
        var result = {};
        for (var ni = 0; ni < numPositions.length; ni++) {
          var pos = numPositions[ni];
          var startLine = pos.lineStart;
          var endLine = (ni < numPositions.length - 1)
            ? numPositions[ni + 1].lineStart - 1
            : lines.length - 1;
          if (endLine < startLine) endLine = startLine;
          var blockLines = [];
          for (var li = startLine; li <= endLine; li++) {
            blockLines.push(lines[li]);
          }
          var fullText = blockLines.join('\n').trim();
          if (!fullText) continue;
          var parsed = this.extractQuestionFromBlock(fullText);
          if (parsed && parsed.answer) {
            result[pos.number] = { answer: parsed.answer, analysis: parsed.analysis || '' };
          }
        }
        return result;
      },
      // ========== 分离导入：后端智能匹配（策略0） ==========
      async _backendSmartMatch() {
        if (!this.state.separateQuestionsRawText || !this.state.separateAnswersRawText) {
          return null;
        }
        try {
          var res = await this.fetchWithRetry('/api/questions/import/separate-match', {
            method: 'POST',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({
              questions_text: this.state.separateQuestionsRawText,
              answers_text: this.state.separateAnswersRawText,
              paper_name: this.state.batchPaperName || '',
              subject_category: this.state.form.subject_category
            })
          }, 30000, 1);
          if (res.ok) {
            var data = await res.json();
            if (data.questions && data.questions.length) {
              // 转换为前端格式
              var converted = [];
              for (var i = 0; i < data.questions.length; i++) {
                var q = data.questions[i];
                converted.push({
                  question_number: q.question_number || (i + 1),
                  question_content: q.content || q.question_content || '',
                  content: q.content || '',
                  options: (q.options || []).map(function(o, oi) {
                    return { key: String.fromCharCode(65 + oi), value: typeof o === 'string' ? o : o };
                  }),
                  answer: q.answer || '待补充',
                  analysis: q.analysis || '',
                  question_type: q.question_type || '单选题',
                  subject_category: data.auto_detected_subject || '行测',
                  _source: 'backend_match',
                  _is_duplicate: q.is_duplicate || false,
                  _similarity: q.similarity || 0,
                  _existing_id: q.existing_id || null,
                  _imported: false
                });
              }
              return {
                questions: converted,
                match_rate: data.match_rate,
                matched_count: data.matched_count,
                total_questions: data.total_questions,
                analysis_count: data.analysis_count,
                strategy_used: data.strategy_used,
                unmatched: data.unmatched_question_numbers || [],
                auto_detected_subject: data.auto_detected_subject
              };
            }
          }
        } catch (e) {
          console.warn('后端智能匹配失败，回退到前端策略:', e);
        }
        return null;
      },
      // ========== 将后端答案映射到前端题目 ==========
      _applyBackendAnswersToLocalQuestions(localQuestions, backendQuestions) {
        // 按question_number匹配：后端题目数据可能少于前端，但题号对应
        var byNumber = {};
        for (var i = 0; i < backendQuestions.length; i++) {
          var bq = backendQuestions[i];
          var bn = bq.question_number || (i + 1);
          byNumber[bn] = bq;
        }
        var matched = 0;
        for (var j = 0; j < localQuestions.length; j++) {
          var lq = localQuestions[j];
          var ln = lq.question_number || (j + 1);
          var bq = byNumber[ln];
          if (bq && bq.answer && bq.answer !== '待补充') {
            lq.answer = bq.answer;
            if (bq.analysis && bq.analysis.length > 10) {
              lq.analysis = bq.analysis;
            }
            lq._is_duplicate = bq._is_duplicate || false;
            lq._similarity = bq._similarity || 0;
            matched++;
          }
        }
        return matched;
      },
      // ========== 分离导入：位置兜底匹配（当所有策略失败时） ==========
      _positionBasedFallbackMatch(questions, rawAnswerText) {
        // 从答案文本中提取所有独立A-D字母
        var allAnswers = [];
        var re = /\b([A-Da-d])\b/g;
        var m;
        while ((m = re.exec(rawAnswerText)) !== null) {
          allAnswers.push(m[1].toUpperCase());
        }
        // 如果答案数量与题目数量接近（误差 < 20%），按位置映射
        if (allAnswers.length === 0) return 0;
        var lenDiff = Math.abs(allAnswers.length - questions.length);
        var tolerance = Math.max(2, Math.floor(questions.length * 0.2));
        if (lenDiff > tolerance) return 0;

        var matched = 0;
        for (var i = 0; i < Math.min(questions.length, allAnswers.length); i++) {
          if (!questions[i].answer || questions[i].answer === '待补充') {
            questions[i].answer = allAnswers[i];
            matched++;
          }
        }
        return matched;
      },
      // ========== 分离导入：匹配题目与答案（统一后端Pipeline） ==========
      matchSeparateQuestionsAnswers: async function() {
        if (!this.state.separateQuestionsRawText || !this.state.separateAnswersRawText) {
          ElMessage.warning('请确保题目和答案文件都已上传');
          return;
        }

        // 初始化进度条
        this.resetProgress('separate');
        this.stepActive(0); this.setProgress(0, 20);  // 题目解析完成
        this.stepDone(0); this.stepActive(1); this.setProgress(1, 40);  // 答案解析完成

        // 策略0（优先）：调用后端统一解析 Pipeline
        this.stepDone(1); this.stepActive(2); this.setProgress(2, 60);  // 智能匹配中
        var result = await this.callBackendParse(
          this.state.separateQuestionsRawText,
          this.state.separateAnswersRawText,
          'separate',
          this.state.batchPaperName
        );

        if (result && result.questions && result.questions.length > 0) {
          var matchRate = result.match_rate || 0;
          this.state.separateMatchRate = matchRate;
          this.stepDone(2); this.setProgress(2, 100);  // 匹配完成

          var withAnswer = this.state.parsedDocsQuestions.filter(function(q) {
            return q.answer && q.answer !== '待补充';
          }).length;

          if (matchRate >= 80) {
            ElMessage.success('后端Pipeline匹配完成：匹配率 ' + matchRate + '%（' +
              withAnswer + '/' + result.total_questions + '）| 策略：' + (result.strategy_used || '智能'));
          } else if (matchRate >= 50) {
            ElMessage.warning('后端匹配率 ' + matchRate + '%（' + withAnswer + '/' +
              result.total_questions + '）。已自动合并，部分题目待人工确认。');
            // 中等匹配率：标记待确认
            this.state.separateNeedConfirm = true;
          } else {
            ElMessage.error('匹配率偏低（' + matchRate + '%）。请使用手动匹配界面进行人工匹配。');
            // 低匹配率：打开手动匹配界面
            this.showManualMatchDialog();
          }
          return;
        }

        // 回退：后端解析失败，使用本地解析
        ElMessage.warning('后端解析未返回结果，使用本地解析...');
        // 重新解析题目
        this.state.rawTextPreview = this.state.separateQuestionsRawText;
        this.parseRawTextToQuestions();
        var questions = this.state.parsedDocsQuestions;
        if (!questions.length) {
          ElMessage.warning('题目文件未能解析出有效题目');
          return;
        }
        // 尝试本地匹配（简化版：仅使用纯序列匹配）
        var answerMap = this._parseAnswerSequence(this.state.separateAnswersRawText);
        var matchedCount = 0;
        for (var qi = 0; qi < questions.length; qi++) {
          var ansEntry = answerMap[qi + 1];
          if (ansEntry && ansEntry.answer) {
            questions[qi].answer = ansEntry.answer;
            matchedCount++;
          }
        }
        var ratio = questions.length > 0 ? Math.round(matchedCount * 100 / questions.length) : 0;
        this.state.separateMatchRate = ratio;
        if (ratio >= 99) {
          ElMessage.success('本地匹配完成：匹配率 ' + ratio + '%');
        } else {
          ElMessage.warning('本地匹配率 ' + ratio + '%。建议检查答案文档格式。');
        }
      },
      showManualMatchDialog() {
        this.state.manualMatchVisible = true;
      },
      onManualMatchConfirm(data) {
        this.state.manualMatchVisible = false;
        if (data && data.questions) {
          this.state.parsedDocsQuestions = data.questions;
          this.state.separateMatchRate = data.matchRate || 0;
        }
        ElMessage.success('手动匹配完成，匹配率 ' + (data.matchRate || 0) + '%');
      },
      onManualMatchCancel() {
        this.state.manualMatchVisible = false;
      },
      // 处理预览列表中的编辑操作（来自 question_preview_list 的 @edit-question 事件）
      handleEditQuestion(payload) {
        if (!payload || payload.index < 0) return;
        var q = this.state.parsedDocsQuestions[payload.index];
        if (!q) return;
        var data = payload.data || {};
        // 更新本地数据
        if (data.question_content !== undefined) q.question_content = data.question_content;
        if (data.question_type_detail !== undefined) q.question_type_detail = data.question_type_detail;
        if (data.difficulty !== undefined) q.difficulty = data.difficulty;
        if (data.options !== undefined) q.options = data.options;
        if (data.answer !== undefined) q.answer = data.answer;
        if (data.analysis !== undefined) q.analysis = data.analysis;
        ElMessage.success('第 ' + (payload.index + 1) + ' 题已更新');
      },
      // ===== 逐题删除（识别匹配后剔除解析出错的题）=====
      // 序号重排由预览列表的索引驱动显示（第 {{idx+1}} 题）自动完成；
      // 答案与解析是题目对象自身的字段，随对象整体移除，
      // 不存在"删了题干却把别的题的答案留下"的错位风险。
      // question_number 保留原文档编号：异常面板依赖它回溯原文位置。
      _removeQuestionAt(list, idx, label) {
        if (!list || idx < 0 || idx >= list.length) return;
        var target = list[idx];
        if (target && target._imported) {
          ElMessage.warning('该题已导入库，无法在此删除');
          return;
        }
        var self = this;
        ElMessageBox.confirm(
          '确定删除第 ' + (idx + 1) + ' 题吗？删除后其余题目序号会自动重排。',
          '删除题目',
          { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
        ).then(function () {
          list.splice(idx, 1);
          ElMessage.success('已删除' + label + '第 ' + (idx + 1) + ' 题，剩余 ' + list.length + ' 题');
          void self;
        }).catch(function () { /* 取消删除，不做任何改动 */ });
      },
      handleDeleteParsedQuestion(idx) {
        this._removeQuestionAt(this.state.parsedDocsQuestions, idx, '');
      },

      /**
       * 预览态为某道题添加图片（题干或指定选项）。
       * 预览态题目尚未落库，后端改写的是 QuestionImportRecord.preview_data，
       * 因此成功后仅就地更新本地题目对象，**不重新拉取整个预览** ——
       * 否则会覆盖教师已经做过的答案/解析编辑。
       * @param payload {idx, target:'content'|'option', optionKey, file}
       */
      async handleAttachImage(payload) {
        if (!payload || !payload.file) return;
        var idx = payload.idx;
        var importId = this.state.importId;
        var self = this;
        if (!importId) {
          ElMessage.error('缺少导入记录 ID，无法添加图片');
          this._finishAttach();
          return;
        }
        var q = this.state.parsedDocsQuestions[idx];
        if (!q) { this._finishAttach(); return; }

        try {
          var fd = new FormData();
          fd.append('file', payload.file);
          fd.append('target', payload.target || 'content');
          if (payload.optionKey) fd.append('option_key', payload.optionKey);
          fd.append('question_index', String(idx));

          var res = await fetch(
            '/api/questions/import/records/' + importId + '/attach-image',
            { method: 'POST', headers: this.getAuthHeaders(), body: fd }
          );
          var data = await res.json().catch(function () { return {}; });
          if (!res.ok) {
            throw new Error(this._extractErrorMessage(data, '图片添加失败 (HTTP ' + res.status + ')'));
          }

          var tag = '<img src="' + data.url + '" class="q-img" loading="lazy" />';
          if ((payload.target || 'content') === 'content') {
            q.question_content = (q.question_content || '') + tag;
            ElMessage.success('已为该题题干添加图片');
          } else {
            var opts = q.options || [];
            var hit = false;
            for (var i = 0; i < opts.length; i++) {
              if (opts[i] && opts[i].key === payload.optionKey) {
                opts[i].value = (opts[i].value || '') + tag;
                hit = true;
                break;
              }
            }
            if (!hit) throw new Error('未找到选项 ' + payload.optionKey);
            // 触发 Vue 响应式更新
            this.state.parsedDocsQuestions[idx] = Object.assign({}, q, { options: opts });
            ElMessage.success('已为选项 ' + payload.optionKey + ' 添加图片');
          }
        } catch (e) {
          ElMessage.error(this.handleFetchError(e, '图片添加'));
        } finally {
          this._finishAttach();
        }
      },
      _finishAttach() {
        var ref = this.$refs && this.$refs.previewListRef;
        if (Array.isArray(ref)) ref = ref[0];
        if (ref && typeof ref.finishAttach === 'function') ref.finishAttach();
      },
      handleDeleteOcrQuestion(idx) {
        this._removeQuestionAt(this.state.ocrQuestions, idx, '图片识别');
      },
      reVerifyQuestion(idx) {
        var q = this.state.parsedDocsQuestions[idx];
        if (!q) return;
        // 从原始文本中重新定位并解析该题
        var rawText = this.state.rawTextPreview || this.state.separateQuestionsRawText;
        if (!rawText) {
          ElMessage.warning('原始文本已清除，无法重检');
          return;
        }
        // 切割题目块
        var lines = rawText.split(/\n/);
        var blocks = [];
        var currentNum = null;
        var currentLines = [];
        var questionHeaderRe = /^\s*(?:第\s*)?(\d+)\s*(?:[\.\u3001\uff0e\)\]）]|\s*题)/;
        for (var li = 0; li < lines.length; li++) {
          var m = lines[li].match(questionHeaderRe);
          if (m) {
            if (currentNum !== null && currentLines.length > 0) {
              blocks.push({ num: currentNum, lines: currentLines.slice() });
            }
            currentNum = parseInt(m[1]);
            var rest = lines[li].replace(questionHeaderRe, '').trim();
            currentLines = rest ? [rest] : [];
          } else if (currentNum !== null) {
            currentLines.push(lines[li]);
          }
        }
        if (currentNum !== null && currentLines.length > 0) {
          blocks.push({ num: currentNum, lines: currentLines.slice() });
        }
        // 找到对应题号的块
        var targetBlock = null;
        for (var bi = 0; bi < blocks.length; bi++) {
          if (blocks[bi].num === idx + 1) {
            targetBlock = blocks[bi];
            break;
          }
        }
        if (!targetBlock) {
          ElMessage.warning('未找到第 ' + (idx + 1) + ' 题的原始文本块');
          return;
        }
        // 重新解析
        var fullText = targetBlock.lines.join('\n').trim();
        var reParsed = this.extractQuestionFromBlock(fullText);
        if (!reParsed || !reParsed.question_content) {
          ElMessage.error('重检失败：无法解析题目内容');
          return;
        }
        // 对比检查
        var oldOptCount = (q.options || []).length;
        var newOptCount = (reParsed.options || []).length;
        var hasChange = false;
        if (newOptCount !== oldOptCount) {
          hasChange = true;
        } else {
          for (var oi = 0; oi < oldOptCount; oi++) {
            if ((q.options[oi].value || '') !== ((reParsed.options[oi] || {}).value || '')) {
              hasChange = true;
              break;
            }
          }
        }
        if (!hasChange && q.answer === (reParsed.answer || '')) {
          ElMessage.success('第 ' + (idx + 1) + ' 题校验通过，选项无异常');
          return;
        }
        // 刷新
        q.options = reParsed.options;
        if (reParsed.answer && !q.answer) q.answer = reParsed.answer;
        // 保留已有的 analysis
        ElMessage.warning('第 ' + (idx + 1) + ' 题已刷新（选项数：' + oldOptCount + ' → ' + newOptCount + '）');
      },
      // ========== 合并导入：尾部答案模式分割 ==========
      splitQuestionsAndAnswersSection(rawText) {
        // 检测分隔标记
        var sepPatterns = [
          /\n\s*(?:参\s*考\s*)?答\s*案\s*(?:解\s*析)?\s*[:：\n]/i,
          /\n\s*Answer\s*(?:Key)?\s*[:：\n]/i,
          /\n\s*\u89e3\u6790\s*[:：\n]/,
          /\n\s*二[、.]\s*\u7b54\u6848/,
          /\n\s*三[、.]\s*\u7b54\u6848/
        ];
        var bestIdx = -1;
        for (var si = 0; si < sepPatterns.length; si++) {
          var m = rawText.match(sepPatterns[si]);
          if (m) {
            bestIdx = m.index;
            break;
          }
        }
        if (bestIdx < 0) return { questionsText: rawText, answersText: '' };
        return {
          questionsText: rawText.substring(0, bestIdx).trim(),
          answersText: rawText.substring(bestIdx).trim()
        };
      },
      // ========== 合并导入：检测子场景 ==========
      _detectCombinedSubMode(rawText) {
        // 先检测尾部答案模式
        var split = this.splitQuestionsAndAnswersSection(rawText);
        if (split.answersText && split.answersText.length > 50) {
          return 'tail';
        }
        // 检测是否有内嵌答案特征（每题块内含"答案"/"解析"字样比例>50%）
        var lines = rawText.split(/\n/);
        var questionHeaderRe = /^\s*(?:第\s*)?(\d+)\s*(?:[\.\u3001\uff0e\)\]）]|\s*题)/;
        var blocks = [];
        var currentNum = null;
        var currentLines = [];
        for (var i = 0; i < lines.length; i++) {
          var m = lines[i].match(questionHeaderRe);
          if (m) {
            if (currentNum !== null && currentLines.length > 0) {
              blocks.push({ num: currentNum, text: currentLines.join('\n') });
            }
            currentNum = parseInt(m[1]);
            var rest = lines[i].replace(questionHeaderRe, '').trim();
            currentLines = rest ? [rest] : [];
          } else if (currentNum !== null) {
            currentLines.push(lines[i]);
          }
        }
        if (currentNum !== null && currentLines.length > 0) {
          blocks.push({ num: currentNum, text: currentLines.join('\n') });
        }
        if (blocks.length === 0) return 'auto';
        var inlineCount = 0;
        for (var bi = 0; bi < blocks.length; bi++) {
          if (/\u7b54\u6848|\u89e3\u6790|【\u7b54\u6848】/.test(blocks[bi].text)) {
            inlineCount++;
          }
        }
        if (inlineCount > blocks.length * 0.5) return 'inline';
        return 'auto';
      },
      async importSingleParsedQuestion(idx) {
        const q = this.state.parsedDocsQuestions[idx];
        if (!q || q._imported) return;
        const mode = this.state.importMode;
        if (mode === 'combined' && !(q.answer || '').trim()) {
          ElMessage.warning('合并模式下请先填写第 ' + (idx + 1) + ' 题的答案');
          return;
        }
        try {
          const res = await this.fetchWithRetry('/api/questions/import/single', {
            method: 'POST',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({
              paper_name: this.state.batchPaperName || 'Word导入',
              subject_category: q.subject_category || '公专',
              question_type_detail: q.question_type_detail || '单选题',
              question_content: q.question_content,
              options: q.options,
              answer: q.answer || '',
              answer_analysis: q.analysis || '',
              score: q.score || 1,
              difficulty: q.difficulty || 3,
              import_mode: mode
            })
          });
          const data = await res.json();
          if (res.ok && data.import_status === 'SUCCESS') {
            q._imported = true;
            ElMessage.success('第 ' + (idx + 1) + ' 题导入成功');
            this.loadRecords();
          } else if (data.import_status === 'DUPLICATE') {
            q._imported = true;
            ElMessage.warning('第 ' + (idx + 1) + ' 题已存在（ID: ' + data.question_id + '）');
          } else {
            ElMessage.warning(data.detail || data.message || '导入失败');
          }
        } catch (e) {
          ElMessage.error(this.handleFetchError(e, '第' + (idx + 1) + '题'));
        }
      },
      async importAllParsedQuestions() {
        const mode = this.state.importMode;
        var rate = Number(this.state.separateMatchRate || 0);
        // 匹配率分档（流程图：≥80自动合并 / 50-80合并+待确认 / <50手动匹配）
        if (mode === 'separate' && rate < 50) {
          ElMessage.error('匹配率仅 ' + rate + '%（低于50%）。请使用"手动匹配"界面建立对应关系后再导入。');
          this.showManualMatchDialog();
          return;
        }
        // 过滤掉已导入和标记为重复的题目
        const pending = this.state.parsedDocsQuestions.filter(function(q) {
          return !q._imported && !q._is_duplicate;
        });
        if (!pending.length) {
          var already = this.state.parsedDocsQuestions.filter(function(q) { return q._imported; }).length;
          var dups = this.state.parsedDocsQuestions.filter(function(q) { return q._is_duplicate; }).length;
          if (dups > 0) {
            ElMessage.info('所有新题目已处理完毕（已导入 ' + already + ' 题，跳过 ' + dups + ' 题重复）');
          } else {
            ElMessage.info('所有题目已导入');
          }
          return;
        }
        if (mode === 'combined') {
          const noAnswer = pending.filter(function(q) { return !(q.answer || '').trim() || q.answer === '待补充'; });
          if (noAnswer.length) {
            ElMessage.warning('合并模式下有 ' + noAnswer.length + ' 道题目缺少答案，请填写后导入或切换到分离导入模式');
            return;
          }
        }
        this.state.loading = true;
        this.state.importProgress = 0;
        // 进度条进入最后阶段(导入入库)
        var lastStepIdx = this.state.progressSteps.length - 1;
        if (lastStepIdx >= 0) { this.stepActive(lastStepIdx); this.setProgress(lastStepIdx, 30); }
        try {
          // ===== 新增：验证题目类型 =====
          ElMessage.info('正在验证题目类型...');
          for (let i = 0; i < pending.length; i++) {
            const q = pending[i];
            // P0-3：仅在后端未给出题型时才用前端兜底规则，不再无条件覆盖
            q.question_type_detail = this.detectQuestionType(
              q.question_content, q.options, q.answer, q.question_type_detail
            );
            this.state.importProgress = Math.floor((i + 1) / pending.length * 50);
          }
          
          // ===== 单请求批量入库（双轨：题库 + 试卷管理）=====
          // 替代旧的逐题POST /single循环（97题=97请求 → 触发限流429）
          ElMessage.info('正在导入题目...');
          this.state.importProgress = 50;
          
          const res = await this.fetchWithRetry('/api/questions/import/batch-parsed', {
            method: 'POST',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({
              paper_name: this.state.batchPaperName || (mode === 'separate' ? '分离导入试卷' : 'Word批量导入'),
              subject_category: (pending[0] && pending[0].subject_category) || '公专',
              import_mode: mode,
              match_rate: mode === 'separate' ? rate : 0,
              questions: pending.map(function(q) {
                return {
                  question_content: q.question_content,
                  options: q.options,
                  answer: q.answer || '',
                  answer_analysis: q.analysis || '',
                  question_type_detail: q.question_type_detail || '单选题',
                  subject_category: q.subject_category,
                  score: q.score || 1,
                  difficulty: q.difficulty || 3
                };
              })
            })
          }, 600000); // 单事务整卷处理，超时放宽至10分钟
          const data = await res.json();
          if (!res.ok) {
            ElMessage.error(data.detail || ('批量导入失败 (HTTP ' + res.status + ')'));
          } else {
            this.state.duplicateCount = data.duplicate_count || 0;
            pending.forEach(function(q) { q._imported = true; });
            this.state.importSummary = {
              total: data.total || 0,
              success: data.success_count || 0,
              dup: data.duplicate_count || 0,
              failed: (data.failed_items || []).length,
              needConfirm: data.need_confirm_count || 0,
              matchRate: data.match_rate || rate,
              paperId: data.paper_id,
              paperName: data.paper_name || this.state.batchPaperName || '',
              mode: mode
            };
            // P0-3: 收集异常题清单（失败题 + 待确认题），供前端定位面板展示
            this.state.abnormalItems = [];
            var self = this;
            (data.failed_items || []).forEach(function(f) {
              self.state.abnormalItems.push({
                index: f.index,
                question_number: f.question_number || String((f.index || 0) + 1),
                reason: f.reason || '导入失败',
                kind: 'failed'
              });
            });
            (data.need_confirm_items || []).forEach(function(nc) {
              self.state.abnormalItems.push({
                index: nc.index,
                question_number: nc.question_number || String((nc.index || 0) + 1),
                reason: nc.reason || '待确认',
                kind: 'confirm'
              });
            });
            if ((data.failed_items || []).length) {
              console.warn('[batch-parsed] 失败明细:', data.failed_items);
            }
            if (lastStepIdx >= 0) { this.stepDone(lastStepIdx); this.setProgress(lastStepIdx, 100); }
            this.state.importProgress = 100;
            ElMessage.success(data.message || ('导入完成：成功 ' + data.success_count + ' 题'));
            if (data.need_confirm_count > 0) {
              ElMessage.warning(data.need_confirm_count + ' 题缺答案/低置信度，建议在试卷编辑中人工确认后再发布');
            }
            
            // 新增：验证试卷预览
            if (data.paper_id) {
              await this.verifyPaperPreview(data.paper_id);
            }
          }
        } catch (e) {
          ElMessage.error(this.handleFetchError(e, '批量导入'));
        }
        this.loadRecords();
        // 通知题库首页刷新数据
        this.notifyBankRefresh();
        this.state.loading = false;
        this.state.importProgress = 0;
      },
      // 新增：试卷预览验证方法
      async verifyPaperPreview(paperId) {
        try {
          const res = await this.fetchWithRetry(`/api/papers/${paperId}/preview`, {
            method: 'GET',
            headers: this.getJsonHeaders()
          }, 10000, 1);
          const data = await res.json();
          if (res.ok && data.questions && data.questions.length > 0) {
            ElMessage.success('试卷预览验证通过，共 ' + data.questions.length + ' 道题目');
            return true;
          } else {
            ElMessage.warning('试卷预览验证失败：无题目内容');
            return false;
          }
        } catch (e) {
          console.error('[verifyPreview] 试卷预览验证失败:', e);
          ElMessage.warning('试卷预览验证失败，请手动检查试卷管理');
          return false;
        }
      },
      goViewPaper() {
        // 跳转教师端试卷管理查看刚导入的整卷
        if (this.$router && this.$router.push) this.$router.push('/teacher/papers');
        else window.location.href = '/teacher/papers';
      },
      goViewBank() {
        this.notifyBankRefresh();
        if (this.$router && this.$router.push) this.$router.push('/');
        else window.location.href = '/';
      },
      dismissImportSummary() { this.state.importSummary = null; },
      // P0-3: 异常题清单点击定位到对应题目卡片（scrollIntoView + 高亮）
      locateAbnormalItem(item) {
        var idx = (item && item.index !== undefined) ? item.index : -1;
        if (idx < 0) return;
        this.state.highlightIndex = idx;
        var el = document.getElementById('qcard_' + idx);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.classList.add('qcard-highlight');
          setTimeout(function() { el.classList.remove('qcard-highlight'); }, 2500);
          ElMessage.info('已定位到第 ' + (item.question_number || (idx + 1)) + ' 题');
        } else {
          // 卡片可能尚未渲染或预览列表已关闭
          ElMessage.warning('题目预览列表已关闭，无法定位。请重新解析后再试。');
        }
      },
      continueImport() {
        this.state.importSummary = null;
        this.state.parsedDocsQuestions = [];
        this.state.rawTextPreview = '';
        this.state.separateMatchRate = 0;
        this.state.separateNeedConfirm = false;
        ElMessage.info('已重置，可继续导入下一份文档');
      },
      notifyBankRefresh() {
        // 通过 sessionStorage 标记通知 QuestionBank 首页刷新数据
        try {
          sessionStorage.setItem('__VTJ_BANK_NEEDS_REFRESH__', Date.now().toString());
        } catch(e) {}
      },
      async loadRecords() {
        try {
          const res = await this.fetchWithRetry('/api/questions/import/records?page=1&page_size=10', {
            headers: this.getAuthHeaders()
          }, 10000, 0);
          const data = await res.json();
          if (res.ok) this.state.records = data.items || [];
        } catch (e) {
          console.warn('[loadRecords]', e.message || e);
        }
      },
      mounted() {
        this.ensureLogin().then(function(ok) {
          if (ok) {
            this.loadRecords();
          } else {
            ElMessage.warning('请先登录后再使用题目导入功能');
          }
        }.bind(this));
      }
    }
  })
</script>
<style lang="css" scoped>
  * { box-sizing: border-box; }
  .import-page {
    min-height: 100vh;
    background: linear-gradient(180deg, #0a1628 0%, #12233f 30%, #1a2a4a 100%);
    color: #ffffff;
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif;
  }
  .import-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 32px;
    background: linear-gradient(135deg, rgba(10,22,40,0.95) 0%, rgba(20,30,55,0.9) 100%);
    border-bottom: 2px solid rgba(200,22,30,0.25);
    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .header-title {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 1px;
  }
  .header-sub {
    font-size: 12px;
    color: #8899aa;
    margin-left: 8px;
  }
  .header-center {
    display: flex;
    align-items: center;
  }
  .mode-switch {
    display: flex;
    gap: 0;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    overflow: hidden;
  }
  .mode-btn {
    padding: 7px 18px;
    background: transparent;
    border: none;
    color: #8899aa;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
    white-space: nowrap;
  }
  .mode-btn.active {
    background: linear-gradient(135deg, #c41e3a 0%, #e8384f 100%);
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(200,22,30,0.3);
  }
  .mode-btn:hover:not(.active) {
    color: #cfd8e3;
    background: rgba(200,22,30,0.1);
  }
  .header-right { display: flex; gap: 10px; }
  .back-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: rgba(200,22,30,0.3);
    border: 1px solid rgba(200,22,30,0.5);
    border-radius: 8px;
    color: #ffffff;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.3s;
  }
  .back-btn:hover {
    background: rgba(200,22,30,0.6);
    border-color: #c41e3a;
    box-shadow: 0 0 12px rgba(200,22,30,0.3);
  }
  /* ====== 头部阶段进度条 ====== */
  .import-progress-wrap {
    padding: 0 32px 8px;
    background: linear-gradient(135deg, rgba(10,22,40,0.95) 0%, rgba(20,30,55,0.9) 100%);
  }
  .import-progress-steps {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 12px;
    padding: 8px 0 4px;
    font-size: 13px;
    font-weight: 500;
  }
  .progress-step {
    display: flex;
    align-items: center;
    gap: 4px;
    color: rgba(255,255,255,0.25);
    transition: color 0.3s;
  }
  .progress-step.done { color: #22c55e; }
  .progress-step.active { color: #c41e3a; font-weight: 700; }
  .progress-step-arrow { color: rgba(255,255,255,0.15); font-size: 11px; }
  .step-check { font-size: 12px; font-weight: 700; }
  .import-progress-bar {
    height: 6px;
    background: rgba(255,255,255,0.06);
    border-radius: 3px;
    overflow: hidden;
    margin: 0;
  }
  .import-progress-phase {
    margin-top: 6px;
    font-size: 12px;
    color: #8899aa;
    line-height: 1.5;
  }
  .import-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #c41e3a, #e8384f);
    border-radius: 3px;
    transition: width 0.5s ease;
  }
  .import-progress-fill.done {
    background: linear-gradient(90deg, #22c55e, #16a34a);
  }
  .import-body {
    max-width: 1000px;
    margin: 24px auto;
    padding: 0 24px 40px;
  }
  .card-wrapper {
    background: rgba(255,255,255,0.04);
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.08);
    overflow: hidden;
  }
  .card-nav {
    display: flex;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .nav-tab {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 14px 20px;
    font-size: 14px;
    font-weight: 600;
    color: #8899aa;
    cursor: pointer;
    transition: all 0.3s;
    border-bottom: 2px solid transparent;
  }
  .nav-tab:hover { color: #cfd8e3; background: rgba(255,255,255,0.03); }
  .nav-tab.active {
    color: #ffffff;
    background: rgba(200,22,30,0.12);
    border-bottom-color: #c41e3a;
  }
  .card-content {
    padding: 24px;
  }
  .form-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 16px;
  }
  .form-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 16px;
  }
  .form-item label {
    font-size: 12px;
    font-weight: 600;
    color: #8899aa;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .form-item label .required { color: #c41e3a; }
  .form-item input,
  .form-item select,
  .form-item textarea {
    padding: 10px 14px;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px;
    color: #ffffff;
    font-size: 14px;
    font-family: inherit;
    transition: all 0.3s;
    outline: none;
  }
  .form-item input:focus,
  .form-item select:focus,
  .form-item textarea:focus {
    border-color: #c41e3a;
    box-shadow: 0 0 0 3px rgba(200,22,30,0.15);
  }
  .form-item input::placeholder,
  .form-item textarea::placeholder { color: #556677; }
  .form-item select { cursor: pointer; }
  .form-item select option { background: #1a2a4a; color: #ffffff; }
  .form-item textarea { resize: vertical; min-height: 80px; }
  .option-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }
  .option-key {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(200,22,30,0.2);
    border: 1px solid rgba(200,22,30,0.3);
    border-radius: 6px;
    font-size: 14px;
    font-weight: 700;
    color: #c41e3a;
  }
  .option-row input { flex: 1; }
  .btn-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    background: transparent;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.3s;
  }
  .btn-icon:hover { background: rgba(200,22,30,0.15); }
  .btn-link {
    display: inline-flex;
    padding: 6px 12px;
    background: transparent;
    border: 1px dashed rgba(255,255,255,0.2);
    border-radius: 6px;
    color: #8a8faa;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.3s;
  }
  .btn-link:hover { border-color: #c41e3a; color: #c41e3a; }
  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid rgba(255,255,255,0.08);
  }
  .btn-primary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 24px;
    background: linear-gradient(135deg, #c41e3a 0%, #e8384f 100%);
    border: none;
    border-radius: 8px;
    color: #ffffff;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
  }
  .btn-primary:hover {
    box-shadow: 0 4px 16px rgba(200,22,30,0.4);
    transform: translateY(-1px);
  }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-secondary {
    padding: 10px 20px;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    color: #8899aa;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.3s;
  }
  .btn-secondary:hover { background: rgba(255,255,255,0.12); color: #ffffff; }
  .batch-upload,
  .image-upload { margin-bottom: 16px; }
  .upload-zone {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 32px 20px;
    border: 2px dashed rgba(255,255,255,0.15);
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.3s;
    margin-bottom: 16px;
  }
  .upload-zone:hover {
    border-color: #c41e3a;
    background: rgba(200,22,30,0.06);
  }
  .upload-zone p { font-size: 14px; color: #cfd8e3; margin: 0; }
  .upload-hint { font-size: 11px; color: #556677; }
  .batch-preview {
    margin-top: 16px;
    padding: 16px;
    background: rgba(255,255,255,0.04);
    border-radius: 8px;
  }
  .preview-header {
    font-size: 14px;
    font-weight: 600;
    color: #c41e3a;
    margin-bottom: 12px;
  }
  .preview-list { display: flex; flex-direction: column; gap: 8px; }
  .preview-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    background: rgba(255,255,255,0.03);
    border-radius: 6px;
    font-size: 13px;
  }
  .preview-idx {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(200,22,30,0.2);
    border-radius: 4px;
    font-size: 12px;
    font-weight: 700;
    color: #c41e3a;
  }
  /* P0-3：预览项改走 v-html 后需要允许换行与图片显示。
   原样式 `white-space: nowrap` 会把渲染后的 HTML 压成一行并截断，
   现改为多行自适应 + 给 img 设定尺寸约束。 */
.preview-text { color: #b0b8c4; overflow: hidden; text-overflow: ellipsis; white-space: normal; line-height: 1.7; }
.preview-text :deep(img), .preview-text img { max-width: 100%; max-height: 220px; height: auto; object-fit: contain; display: block; margin: 6px 0; border-radius: 6px; }
  .raw-text {
    width: 100%;
    max-height: 400px;
    overflow-y: auto;
    padding: 14px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px;
    color: #b0b8c4;
    font-size: 13px;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .image-preview {
    margin: 16px 0;
    text-align: center;
  }
  .image-preview img {
    max-width: 100%;
    max-height: 300px;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.1);
  }
  .records-section {
    margin-top: 24px;
    background: rgba(255,255,255,0.04);
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.08);
    padding: 20px 24px;
  }
  .section-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 14px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .records-list { display: flex; flex-direction: column; gap: 6px; }
  .record-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: rgba(255,255,255,0.03);
    border-radius: 6px;
    font-size: 13px;
  }
  .record-file { color: #cfd8e3; flex: 1; }
  .record-count { color: #c41e3a; margin: 0 16px; font-weight: 600; }
  .record-time { color: #556677; font-size: 11px; }
  .docs-question-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-height: 70vh;
    overflow-y: auto;
    padding-right: 4px;
  }
  .docs-q-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    overflow: visible;
    transition: border-color 0.3s, box-shadow 0.3s;
  }
  .docs-q-card:hover { border-color: rgba(200,22,30,0.4); box-shadow: 0 2px 16px rgba(200,22,30,0.12); }
  .docs-q-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: rgba(200,22,30,0.1);
    border-bottom: 1px solid rgba(200,22,30,0.18);
    border-radius: 12px 12px 0 0;
  }
  .docs-q-num {
    font-size: 14px;
    font-weight: 700;
    color: #e8384f;
    min-width: 60px;
  }
  .docs-q-type {
    font-size: 12px;
    color: #8899aa;
    flex: 1;
    background: rgba(200,22,30,0.08);
    padding: 2px 10px;
    border-radius: 10px;
  }
  .docs-q-subject {
    font-size: 11px;
    color: #8899aa;
    background: rgba(26,43,95,0.3);
    padding: 2px 8px;
    border-radius: 8px;
  }
  .btn-mini-import {
    padding: 6px 16px;
    background: linear-gradient(135deg, #c41e3a 0%, #e8384f 100%);
    border: none;
    border-radius: 6px;
    color: #ffffff;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
    white-space: nowrap;
  }
  .btn-mini-import:hover {
    box-shadow: 0 2px 10px rgba(200,22,30,0.4);
    transform: translateY(-1px);
  }
  .btn-mini-import:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    background: rgba(255,255,255,0.1);
    color: #556677;
  }
  .docs-q-body {
    padding: 16px 18px;
  }
  .docs-q-content {
    font-size: 14px;
    color: #e8ecf4;
    line-height: 1.8;
    margin-bottom: 12px;
    word-break: break-word;
    white-space: pre-wrap;
    max-height: 200px;
    overflow-y: auto;
    background: rgba(0,0,0,0.15);
    padding: 12px 14px;
    border-radius: 8px;
    border-left: 3px solid rgba(200,22,30,0.3);
  }
  .docs-q-options {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 24px;
    margin-bottom: 10px;
    padding: 10px 14px;
    background: rgba(0,0,0,0.1);
    border-radius: 8px;
  }
  .docs-q-opt {
    font-size: 13px;
    color: #b0b8c4;
    line-height: 1.6;
    max-width: 45%;
    word-break: break-word;
  }
  .docs-q-answer-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 10px;
    padding-top: 12px;
    border-top: 1px solid rgba(255,255,255,0.08);
  }
  .docs-q-ans-label {
    color: #8899aa;
    font-size: 13px;
    font-weight: 600;
  }
  .docs-q-answer {
    font-size: 13px;
    color: #4ade80;
    margin-top: 4px;
  }
  .docs-q-ans-input {
    width: 72px;
    padding: 6px 10px;
    background: rgba(26,43,95,0.4);
    border: 1px solid rgba(200,22,30,0.3);
    border-radius: 6px;
    color: #4ade80;
    font-size: 14px;
    font-weight: 700;
    text-align: center;
    text-transform: uppercase;
    outline: none;
    transition: border-color 0.3s, box-shadow 0.3s;
  }
  .docs-q-ans-input:focus {
    border-color: #c41e3a;
    box-shadow: 0 0 0 3px rgba(200,22,30,0.2);
    background: rgba(26,43,95,0.6);
  }
  .docs-q-ans-input::placeholder {
    color: #556677;
    font-weight: 400;
    font-size: 12px;
  }
  .docs-q-ans-hint {
    color: #e8384f;
    font-size: 12px;
  }
  /* ====== 预览列表顶部工具栏 ====== */
  .docs-list-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: linear-gradient(135deg, rgba(26,43,95,0.5), rgba(20,30,55,0.4));
    border: 1px solid rgba(200,22,30,0.15);
    border-radius: 10px;
    margin-bottom: 12px;
    flex-wrap: wrap;
    gap: 10px;
  }
  .docs-list-stats {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  .docs-stat-total {
    font-size: 13px;
    font-weight: 700;
    color: #e8ecf4;
    background: rgba(200,22,30,0.15);
    padding: 4px 12px;
    border-radius: 6px;
  }
  .docs-stat-answered {
    font-size: 12px;
    color: #4ade80;
    background: rgba(74,222,128,0.1);
    padding: 4px 10px;
    border-radius: 6px;
  }
  .docs-stat-missing {
    font-size: 12px;
    color: #f59e0b;
    background: rgba(245,158,11,0.1);
    padding: 4px 10px;
    border-radius: 6px;
  }
  .docs-stat-imported {
    font-size: 12px;
    color: #8899aa;
    background: rgba(255,255,255,0.05);
    padding: 4px 10px;
    border-radius: 6px;
  }
  .docs-list-actions-top {
    display: flex;
    gap: 8px;
  }
  .btn-top-import {
    padding: 8px 20px;
    font-size: 13px;
  }
  .btn-top-close {
    padding: 8px 16px;
    font-size: 13px;
  }
  /* ====== 无答案卡片高亮 ====== */
  .docs-q-card-noans {
    border-color: rgba(245, 158, 11, 0.3);
  }
  .docs-q-card-noans .docs-q-header {
    background: rgba(245, 158, 11, 0.08);
    border-bottom-color: rgba(245, 158, 11, 0.18);
  }
  .docs-q-ans-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
  }
  .docs-q-ans-badge-warn {
    animation: pulse-warn 2s ease-in-out infinite;
  }
  @keyframes pulse-warn {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
  .docs-q-answer-row-warn {
    background: rgba(245, 158, 11, 0.05);
    border-radius: 6px;
  }
  /* ====== 重检按钮 ====== */
  .btn-mini-reverify {
    padding: 3px 10px;
    background: rgba(255, 165, 0, 0.15);
    border: 1px solid rgba(255, 165, 0, 0.4);
    border-radius: 6px;
    color: #ffa500;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.3s;
    white-space: nowrap;
  }
  .btn-mini-reverify:hover {
    background: rgba(255, 165, 0, 0.3);
    box-shadow: 0 2px 10px rgba(255, 165, 0, 0.3);
  }
  /* ====== 解析展示 ====== */
  .docs-q-analysis {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px dashed rgba(255,255,255,0.1);
  }
  .docs-q-analysis-text {
    font-size: 13px;
    color: #a0aab4;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-word;
    background: rgba(0,0,0,0.15);
    padding: 8px 12px;
    border-radius: 6px;
    margin-top: 4px;
  }
  /* ====== 手动匹配弹窗遮罩层 ====== */
  .manual-match-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
  }
  .manual-match-modal {
    width: 90%;
    height: 80%;
    max-width: 1200px;
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }

  /* ====== 双轨入库结果摘要卡 ====== */
  .import-summary-card {
    margin: 20px auto 0;
    max-width: 760px;
    background: linear-gradient(160deg, rgba(16,40,28,0.92), rgba(10,26,18,0.95));
    border: 1px solid rgba(74,222,128,0.35);
    border-radius: 14px;
    box-shadow: 0 10px 36px rgba(0,0,0,0.45);
    overflow: hidden;
  }
  .summary-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 18px;
    background: rgba(74,222,128,0.12);
    border-bottom: 1px solid rgba(74,222,128,0.25);
  }
  .summary-title { font-size: 15px; font-weight: 700; color: #4ade80; letter-spacing: 1px; }
  .btn-summary-close {
    background: transparent; border: none; color: #8899aa;
    font-size: 14px; cursor: pointer; padding: 2px 6px; border-radius: 6px;
  }
  .btn-summary-close:hover { color: #ffffff; background: rgba(255,255,255,0.08); }
  .summary-body { padding: 14px 18px 6px; }
  .summary-row { display: flex; gap: 8px; padding: 5px 0; font-size: 13px; line-height: 1.55; }
  .s-label { min-width: 96px; color: #8899aa; flex-shrink: 0; }
  .s-value { color: #dfe7f2; word-break: break-all; }
  .s-ok, .s-value.s-ok { color: #4ade80; font-weight: 600; }
  .s-warn, .s-value.s-warn { color: #f59e0b; font-weight: 600; }
  .summary-actions {
    display: flex; gap: 10px; flex-wrap: wrap;
    padding: 12px 18px 16px; justify-content: flex-end;
  }
  .btn-sm-primary { padding: 8px 22px; font-size: 13px; }

  /* P0-3: 异常题清单面板 */
  .abnormal-list {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px 10px;
    background: rgba(245,108,108,0.06);
    border: 1px solid rgba(245,108,108,0.22);
    border-radius: 8px;
  }
  .abnormal-list-header {
    font-size: 13px;
    font-weight: 700;
    color: #f56c6c;
    margin-bottom: 2px;
  }
  .abnormal-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 8px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    transition: background 0.2s;
  }
  .abnormal-item:hover { background: rgba(245,108,108,0.14); }
  .abnormal-failed { background: rgba(245,108,108,0.08); }
  .abnormal-num { color: #e8ecf4; font-weight: 600; white-space: nowrap; }
  .abnormal-tag { color: #f59e0b; font-weight: 600; white-space: nowrap; }
  .abnormal-failed .abnormal-tag { color: #f56c6c; }
  .abnormal-reason {
    color: #8899aa;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }
  /* 申论阻断提示：这是数据正确性告警，不是普通提示，必须醒目。
     用警示色 + 左侧竖条，避免被当作可忽略的灰色小字。 */
  .blocked-hint {
    margin-top: 8px;
    padding: 8px 12px;
    border-left: 3px solid #f56c6c;
    background: rgba(245, 108, 108, 0.08);
    color: #f56c6c;
    font-size: 13px;
    line-height: 1.6;
    border-radius: 2px;
  }

</style>
