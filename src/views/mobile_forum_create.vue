<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">发布帖子</h1>
      <button class="submit-btn" @click="submitPost" :disabled="submitting">发布</button>
    </header>

    <main class="form">
      <div class="msg" v-if="message" :class="msgType">{{ message }}</div>

      <div class="field">
        <label class="label">标题</label>
        <input v-model="title" type="text" class="input" placeholder="请输入标题（最多200字）" maxlength="200" />
      </div>

      <div class="field">
        <label class="label">分类</label>
        <div class="type-tabs">
          <div
            v-for="t in types"
            :key="t.key"
            :class="['type-tab', { active: shareType === t.key }]"
            @click="shareType = t.key"
          >
            {{ t.name }}
          </div>
        </div>
      </div>

      <div class="field">
        <label class="label">内容</label>
        <textarea v-model="content" class="textarea" placeholder="分享你的经验、资料或心得..." rows="10"></textarea>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const title = ref('');
const content = ref('');
const shareType = ref('EXPERIENCE');
const submitting = ref(false);
const message = ref('');
const msgType = ref('');

const types = [
  { key: 'EXPERIENCE', name: '经验分享' },
  { key: 'RESOURCE', name: '资料分享' },
  { key: 'DISCUSSION', name: '学习讨论' },
  { key: 'FEELING', name: '心情打卡' }
];

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/forum');
};

const submitPost = async () => {
  const t = title.value.trim();
  const c = content.value.trim();
  if (!t) { showMsg('请输入标题', 'error'); return; }
  if (!c) { showMsg('请输入内容', 'error'); return; }

  submitting.value = true;
  message.value = '';
  try {
    const auth = (window as any).__VTJ_AUTH__;
    // 后端用 Form 表单接收，需用 application/x-www-form-urlencoded
    const body = new URLSearchParams();
    body.append('title', t);
    body.append('content', c);
    body.append('share_type', shareType.value);
    const res = await auth.apiFetch('/api/forum/posts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString()
    });
    if (res.ok) {
      showMsg('发布成功', 'success');
      setTimeout(() => router.push('/mobile/forum'), 800);
    } else {
      const data = await res.json().catch(() => ({}));
      showMsg(data.detail || data.message || '发布失败', 'error');
    }
  } catch (e) {
    showMsg('网络异常，请重试', 'error');
  } finally {
    submitting.value = false;
  }
};

const showMsg = (m: string, type: string) => {
  message.value = m;
  msgType.value = type;
};
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
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
}
.back-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #1a2b5f;
  cursor: pointer;
  padding: 4px 8px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}
.submit-btn {
  min-height: 36px;
  padding: 0 16px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #C91F37, #e8384f);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}
.submit-btn:disabled {
  opacity: 0.6;
}
.form {
  flex: 1;
  padding: 16px;
}
.msg {
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 16px;
}
.msg.error {
  background: #fff2f0;
  color: #c41e3a;
  border: 1px solid #ffccc7;
}
.msg.success {
  background: #f6ffed;
  color: #10b981;
  border: 1px solid #b7eb8f;
}
.field {
  margin-bottom: 20px;
}
.label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 8px;
}
.input,
.textarea {
  width: 100%;
  border: 1px solid #e8ecf1;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 15px;
  color: #1a2a3a;
  font-family: inherit;
  outline: none;
  background: #fff;
}
.input:focus,
.textarea:focus {
  border-color: #C91F37;
  box-shadow: 0 0 0 3px rgba(201, 31, 55, 0.08);
}
.textarea {
  resize: vertical;
  line-height: 1.6;
}
.type-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.type-tab {
  padding: 8px 16px;
  border-radius: 18px;
  font-size: 13px;
  color: #5a6488;
  background: #f0f3f7;
  cursor: pointer;
}
.type-tab.active {
  background: #1a2b5f;
  color: #fff;
}
</style>
