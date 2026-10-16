<!-- 手机端意见反馈（独立移动端壳层：含返回键，不复用电脑端 NavBar） -->
<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">意见反馈</h1>
      <span class="spacer"></span>
    </header>

    <main class="list">
      <!-- 提交反馈 -->
      <section class="card">
        <h2 class="card-title">提交反馈</h2>
        <label class="field">
          <span class="field-label">反馈分类</span>
          <select v-model="form.category" class="field-input">
            <option>功能异常</option>
            <option>内容错误</option>
            <option>意见建议</option>
            <option>其他</option>
          </select>
        </label>
        <label class="field">
          <span class="field-label">联系方式</span>
          <input v-model="form.contact" class="field-input" type="text" placeholder="选填，便于回复" />
        </label>
        <label class="field">
          <span class="field-label">反馈内容</span>
          <textarea
            v-model="form.content"
            class="field-input"
            rows="4"
            placeholder="请描述遇到的问题或建议"
          ></textarea>
        </label>
        <button class="btn-submit" :disabled="submitting" @click="submitFeedback">
          {{ submitting ? '提交中...' : '提交反馈' }}
        </button>
      </section>

      <!-- 我的反馈 -->
      <section class="card">
        <h2 class="card-title">我的反馈（{{ list.length }}）</h2>
        <div v-if="loading" class="empty">加载中...</div>
        <div v-else-if="!list.length" class="empty">暂无反馈</div>
        <div v-for="f in list" :key="f.feedback_id" class="fb-item">
          <div class="fb-head">
            <span class="fb-cat">{{ f.category }}</span>
            <span :class="['fb-status', 'st-' + f.status]">{{ statusLabel(f.status) }}</span>
          </div>
          <div class="fb-content">{{ f.content }}</div>
          <div v-if="f.reply" class="fb-reply">
            <strong>回复：</strong>{{ f.reply }}
            <span class="fb-time">{{ (f.replied_at || '').slice(0, 10) }}</span>
          </div>
          <div class="fb-time">{{ (f.created_at || '').slice(0, 10) }}</div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

const router = useRouter();
const auth: any = (window as any).__VTJ_AUTH__;
const form = reactive<any>({ category: '功能异常', content: '', contact: '' });
const list = ref<any[]>([]);
const loading = ref(false);
const submitting = ref(false);

const statusLabel = (s: string) =>
  ({ pending: '待处理', processing: '处理中', replied: '已回复', closed: '已关闭' } as any)[s] || s;

// 统一返回机制：有历史则回退，无历史则回「我的」，避免退到空白页
const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/profile');
};

const loadMy = async () => {
  loading.value = true;
  try {
    const res = await auth.apiFetch('/api/feedback/my');
    const data = await res.json();
    list.value = data.items || [];
  } catch (e) {
    console.error('加载反馈列表失败', e);
  } finally {
    loading.value = false;
  }
};

const submitFeedback = async () => {
  if (!form.content.trim()) {
    ElMessage.warning('请填写反馈内容');
    return;
  }
  submitting.value = true;
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
    } else {
      ElMessage.error(data.detail || '提交失败，请重试');
    }
  } catch (e) {
    ElMessage.error('提交失败，请重试');
  } finally {
    submitting.value = false;
  }
};

onMounted(loadMy);
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 48px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e8ecf1;
  position: sticky;
  top: 0;
  z-index: 10;
}
.back-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #1a2b5f;
  cursor: pointer;
  min-width: 44px;
  min-height: 44px;
  padding: 4px 8px;
}
.title { font-size: 16px; font-weight: 600; color: #1a2b5f; margin: 0; }
.spacer { width: 32px; }

.list { flex: 1; padding: 12px 12px 24px; }
.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}
.card-title { font-size: 15px; font-weight: 700; color: #1a2b5f; margin: 0 0 14px; }

.field { display: block; margin-bottom: 12px; }
.field-label { display: block; font-size: 13px; color: #5a6488; margin-bottom: 6px; }
.field-input {
  width: 100%;
  min-height: 44px;
  padding: 10px 12px;
  border: 1px solid #e8ecf1;
  border-radius: 8px;
  font-size: 14px;
  color: #1a2a3a;
  background: #fff;
  font-family: inherit;
  box-sizing: border-box;
}
.field-input:focus { outline: none; border-color: #1a2b5f; }
textarea.field-input { min-height: 96px; resize: vertical; }

.btn-submit {
  width: 100%;
  min-height: 44px;
  background: #c41e3a;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.btn-submit:disabled { opacity: 0.6; cursor: not-allowed; }

.empty { text-align: center; color: #8899aa; padding: 30px 0; }
.fb-item { border-bottom: 1px solid #f0f2f5; padding: 12px 0; }
.fb-item:last-child { border-bottom: none; }
.fb-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.fb-cat { font-size: 12px; color: #1A365D; background: #f0f3f7; padding: 2px 8px; border-radius: 10px; }
.fb-status { font-size: 12px; }
.st-pending { color: #f59e0b; }
.st-processing { color: #1890ff; }
.st-replied { color: #10b981; }
.st-closed { color: #8899aa; }
.fb-content { font-size: 14px; color: #333; margin: 6px 0; line-height: 1.6; }
.fb-reply {
  font-size: 13px;
  color: #1a2b5f;
  background: #f8f9fc;
  border-radius: 8px;
  padding: 10px 12px;
  margin: 8px 0;
}
.fb-time { font-size: 11px; color: #8899aa; }
</style>
