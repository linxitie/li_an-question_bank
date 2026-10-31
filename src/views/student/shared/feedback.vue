<!-- 意见反馈（桌面端） -->
<template>
  <div class="feedback-page">
    <NavBar />
    <main class="fb-main">
      <header class="fb-header">
        <h2><XIcon :icon="ChatDotRound" :size="26" color="#1A365D" /> 意见反馈</h2>
      </header>

      <div class="fb-layout">
        <!-- 左侧：提交反馈 -->
        <section class="card">
          <h3 class="card-title">提交反馈</h3>
          <div class="form-row">
            <label>反馈分类</label>
            <select v-model="form.category">
              <option>功能异常</option>
              <option>内容错误</option>
              <option>意见建议</option>
              <option>其他</option>
            </select>
          </div>
          <div class="form-row">
            <label>联系方式</label>
            <input v-model="form.contact" placeholder="选填，便于回复" />
          </div>
          <div class="form-row">
            <label>反馈内容</label>
            <textarea v-model="form.content" rows="5" placeholder="请描述遇到的问题或建议，我们会认真阅读并回复"></textarea>
          </div>
          <button class="btn-submit" @click="submitFeedback">提交反馈</button>
        </section>

        <!-- 右侧：我的反馈 -->
        <section class="card">
          <h3 class="card-title">我的反馈（{{ list.length }}）</h3>
          <div v-if="list.length === 0" class="empty">暂无反馈</div>
          <div v-for="f in list" :key="f.feedback_id" class="fb-item">
            <div class="fb-head">
              <span class="fb-cat">{{ f.category }}</span>
              <span v-if="f.ticket_no" class="fb-ticket">{{ f.ticket_no }}</span>
              <span :class="['fb-status', 'st-' + f.status]">{{ statusLabel(f.status) }}</span>
            </div>
            <div class="fb-content">{{ f.content }}</div>
            <div class="fb-reply" v-if="f.reply">
              <strong>回复：</strong>{{ f.reply }}
              <span class="fb-time">{{ (f.replied_at || '').slice(0, 10) }}</span>
            </div>
            <div class="fb-time">{{ (f.created_at || '').slice(0, 10) }}</div>
            <button class="fb-detail-btn" @click="openDetail(f.feedback_id)">查看详情</button>
          </div>
        </section>
      </div>
    </main>

    <div v-if="showDetail" class="fb-modal" @click.self="showDetail = false">
      <div class="fb-modal-card">
        <button class="fb-modal-close" @click="showDetail = false">×</button>
        <h3>工单详情</h3>
        <p class="fb-ticket-line" v-if="detail?.ticket_no">工单号：{{ detail.ticket_no }}</p>
        <p class="fb-detail-content">{{ detail?.content }}</p>
        <div class="fb-timeline">
          <div v-for="r in detail?.replies || []" :key="r.reply_id" class="fb-reply-row">
            <span class="fb-reply-role">{{ r.role }}</span>
            <span>{{ r.content }}</span>
          </div>
          <p v-if="!(detail?.replies || []).length" class="empty">暂无回复</p>
        </div>
        <textarea v-model="replyText" rows="3" class="fb-modal-textarea" placeholder="追加说明…"></textarea>
        <button class="btn-submit" :disabled="!replyText.trim()" @click="submitReply">追加回复</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { XIcon } from '@vtj/ui';
import { ElMessage } from 'element-plus';
import { ChatDotRound } from '@vtj/icons';
import NavBar from '$vtj/vue/navbar.vue';

const auth: any = (window as any).__VTJ_AUTH__;
const form = reactive<any>({ category: '功能异常', content: '', contact: '' });
const list = ref<any[]>([]);
const showDetail = ref(false);
const detail = ref<any>(null);
const replyText = ref('');

async function openDetail(feedbackId: number) {
  try {
    const res = await auth.apiFetch(`/api/feedback/${feedbackId}`);
    detail.value = await res.json();
    showDetail.value = true;
  } catch (e) {
    ElMessage.error('加载工单详情失败');
  }
}

async function submitReply() {
  if (!detail.value || !replyText.value.trim()) return;
  try {
    await auth.apiFetch(`/api/feedback/${detail.value.feedback_id}/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: replyText.value.trim() })
    });
    replyText.value = '';
    await openDetail(detail.value.feedback_id);
    ElMessage.success('已追加');
  } catch (e) {
    ElMessage.error('追加失败');
  }
}

function statusLabel(s: string) {
  return ({ pending: '待处理', processing: '处理中', replied: '已回复', closed: '已关闭' } as any)[s] || s;
}

async function loadMy() {
  try {
    const res = await auth.apiFetch('/api/feedback/my');
    const data = await res.json();
    list.value = data.items || [];
  } catch (e) {
    console.error('加载反馈列表失败', e);
  }
}

async function submitFeedback() {
  if (!form.content.trim()) {
    ElMessage.warning('请填写反馈内容');
    return;
  }
  try {
    const res = await auth.apiFetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    });
    const data = await res.json();
    if (data.feedback_id) {
      ElMessage.success('反馈已提交，感谢你的建议');
      form.content = '';
      form.contact = '';
      loadMy();
    }
  } catch (e) {
    ElMessage.error('提交失败，请重试');
  }
}

onMounted(loadMy);
</script>

<style scoped>
.feedback-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.fb-main { max-width: 1100px; margin: 0 auto; padding: 24px 32px 40px; }
.fb-header { margin-bottom: 20px; }
.fb-header h2 { display: flex; align-items: center; gap: 10px; font-size: 22px; font-weight: 800; color: #1a2b5f; margin: 0; }
.fb-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start; }
@media (max-width: 768px) {
  .fb-main { padding: 16px; }
  .fb-layout { grid-template-columns: 1fr; }
}
.card { background: #fff; border-radius: 16px; padding: 24px; box-shadow: 0 2px 14px rgba(26, 43, 95, 0.05); }
.card-title { font-size: 16px; font-weight: 700; color: #1a2b5f; margin: 0 0 16px; }
.form-row { display: flex; flex-direction: column; margin-bottom: 14px; }
.form-row label { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 6px; }
.form-row input, .form-row select, .form-row textarea { padding: 9px 12px; border: 1px solid #d9d9d9; border-radius: 8px; font-size: 14px; font-family: inherit; }
.btn-submit { width: 100%; padding: 11px; background: linear-gradient(135deg, #c41e3a, #d42945); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; }
.empty { text-align: center; color: #8a8faa; padding: 30px 0; }
.fb-item { border-bottom: 1px solid #f0f2f5; padding: 14px 0; }
.fb-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.fb-cat { font-size: 12px; color: #1A365D; background: #1A365D12; padding: 2px 8px; border-radius: 10px; }
.fb-ticket { font-size: 11px; color: #6b7896; margin-left: 6px; }
.fb-detail-btn { margin-top: 6px; border: none; background: none; color: #1A365D; font-size: 12px; cursor: pointer; padding: 0; }
.fb-modal { position: fixed; inset: 0; z-index: 9000; background: rgba(8,12,24,.45); display: flex; align-items: center; justify-content: center; padding: 20px; }
.fb-modal-card { position: relative; width: min(520px, 94vw); max-height: 86vh; overflow-y: auto; background: #fff; border-radius: 16px; padding: 22px; }
.fb-modal-close { position: absolute; top: 8px; right: 12px; border: none; background: none; font-size: 22px; color: #8a94ad; cursor: pointer; }
.fb-ticket-line { color: #6b7896; font-size: 12px; margin: 4px 0 12px; }
.fb-detail-content { color: #1a2b5f; font-size: 14px; line-height: 1.6; }
.fb-timeline { margin: 14px 0; display: flex; flex-direction: column; gap: 8px; }
.fb-reply-row { display: flex; gap: 8px; font-size: 13px; color: #3b4a6b; }
.fb-reply-role { flex-shrink: 0; color: #6b7896; font-size: 11px; }
.fb-modal-textarea { width: 100%; box-sizing: border-box; border: 1px solid #d9e1ee; border-radius: 8px; padding: 8px; font-family: inherit; }
.fb-status { font-size: 12px; }
.st-pending { color: #f59e0b; }
.st-processing { color: #1890ff; }
.st-replied { color: #10b981; }
.st-closed { color: #8a8faa; }
.fb-content { font-size: 14px; color: #333; margin: 6px 0; }
.fb-reply { font-size: 13px; color: #1a2b5f; background: #f8f9fc; border-radius: 8px; padding: 10px 12px; margin: 8px 0; }
.fb-time { font-size: 11px; color: #8a8faa; }
</style>
