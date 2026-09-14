<template>
  <div class="mobile-scan-page">
    <header class="scan-topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="scan-title">扫码登录</h1>
      <span class="topbar-spacer"></span>
    </header>

    <!-- 有 uuid：展示确认登录 -->
    <main v-if="hasUuid" class="scan-body">
      <div class="confirm-panel">
        <div class="confirm-icon">📱</div>
        <p class="confirm-title">检测到 PC 端登录请求</p>
        <p class="confirm-sub">请核对以下设备信息后确认登录</p>

        <div class="device-card" v-if="deviceInfo">
          <div class="device-row">
            <span class="label">设备</span>
            <span class="value">{{ deviceInfo.browser }} / {{ deviceInfo.os }}</span>
          </div>
          <div class="device-row" v-if="loginTime">
            <span class="label">时间</span>
            <span class="value">{{ loginTime }}</span>
          </div>
        </div>
        <div class="device-card error" v-else-if="loadError">
          <span>{{ loadError }}</span>
        </div>

        <div class="message" v-if="message" :class="messageType">{{ message }}</div>

        <div class="btn-group">
          <button class="btn btn-cancel" @click="goBack" :disabled="confirming">取消</button>
          <button class="btn btn-confirm" @click="confirmLogin" :disabled="confirming || !deviceInfo">
            {{ confirming ? '确认中...' : '确认登录' }}
          </button>
        </div>
      </div>
    </main>

    <!-- 无 uuid：展示说明 + 手动输入 -->
    <main v-else class="scan-body">
      <div class="confirm-panel">
        <div class="confirm-icon">🔍</div>
        <p class="confirm-title">扫码登录</p>
        <p class="confirm-sub">请在电脑端打开「扫码登录」页，用手机相机扫描屏幕上的二维码；或手动输入二维码编号。</p>

        <div class="manual-input">
          <input v-model="manualUuid" type="text" placeholder="请输入二维码编号" class="uuid-input" />
          <button class="btn btn-confirm full" @click="submitManual" :disabled="!manualUuid.trim()">确认</button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();

const uuid = ref('');
const manualUuid = ref('');
const deviceInfo = ref<any>(null);
const loginTime = ref('');
const loadError = ref('');
const confirming = ref(false);
const message = ref('');
const messageType = ref('');

const hasUuid = computed(() => !!uuid.value);

const goBack = () => {
  if (window.history.length > 1) {
    router.back();
  } else {
    router.push('/mobile/home');
  }
};

const fetchDeviceInfo = async (id: string) => {
  loadError.value = '';
  deviceInfo.value = null;
  try {
    const auth = (window as any).__VTJ_AUTH__;
    const headers = auth ? auth.getJsonHeaders() : { 'Content-Type': 'application/json' };
    const res = await fetch(`/api/auth/qrcode/${id}/info`, { headers });
    if (res.status === 404) {
      loadError.value = '二维码不存在或已过期';
      return;
    }
    const data = await res.json();
    if (data.device) {
      deviceInfo.value = data.device;
      if (data.login_time) {
        loginTime.value = new Date(data.login_time).toLocaleString();
      }
    } else {
      loadError.value = data.detail || '无法获取设备信息';
    }
  } catch (e: any) {
    loadError.value = '网络异常，请重试';
  }
};

const confirmLogin = async () => {
  if (!uuid.value) return;
  confirming.value = true;
  message.value = '';
  try {
    const auth = (window as any).__VTJ_AUTH__;
    const headers = auth ? auth.getJsonHeaders() : { 'Content-Type': 'application/json' };
    const res = await fetch(`/api/auth/qrcode/${uuid.value}/confirm`, {
      method: 'POST',
      headers,
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data.success) {
      message.value = '登录确认成功，请在电脑端查看登录结果';
      messageType.value = 'success';
      setTimeout(goBack, 1500);
    } else {
      message.value = data.detail || '确认失败，请重试';
      messageType.value = 'error';
    }
  } catch (e: any) {
    message.value = '网络异常，请重试';
    messageType.value = 'error';
  } finally {
    confirming.value = false;
  }
};

const submitManual = () => {
  const id = manualUuid.value.trim();
  if (!id) return;
  uuid.value = id;
  fetchDeviceInfo(id);
};

onMounted(() => {
  const q = route.query.uuid;
  if (q) {
    uuid.value = String(q);
    fetchDeviceInfo(String(q));
  }
});
</script>

<style scoped>
.mobile-scan-page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}

.scan-topbar {
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

.scan-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}

.topbar-spacer {
  width: 32px;
}

.scan-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 20px;
}

.confirm-panel {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 16px;
  padding: 32px 24px;
  box-shadow: 0 4px 20px rgba(26, 54, 95, 0.08);
  text-align: center;
}

.confirm-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.confirm-title {
  font-size: 18px;
  font-weight: 700;
  color: #1a2b5f;
  margin: 0 0 8px;
}

.confirm-sub {
  font-size: 13px;
  color: #8899aa;
  margin: 0 0 24px;
}

.device-card {
  background: #f8f9fc;
  border: 1px solid #e8ecf1;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  text-align: left;
}

.device-card.error {
  color: #c41e3a;
  text-align: center;
}

.device-row {
  display: flex;
  gap: 12px;
  padding: 6px 0;
  font-size: 14px;
}

.device-row .label {
  color: #8899aa;
  flex-shrink: 0;
  width: 44px;
}

.device-row .value {
  color: #1a2b5f;
}

.message {
  font-size: 13px;
  margin-bottom: 12px;
  padding: 10px 14px;
  border-radius: 8px;
}

.message.success {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  color: #10b981;
}

.message.error {
  background: #fff2f0;
  border: 1px solid #ffccc7;
  color: #c41e3a;
}

.btn-group {
  display: flex;
  gap: 12px;
}

.btn {
  flex: 1;
  min-height: 48px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all 0.3s ease;
}

.btn.full {
  width: 100%;
  margin-top: 12px;
}

.btn-cancel {
  background: #f5f7fa;
  color: #5a6488;
  border: 1px solid #e8ecf1;
}

.btn-confirm {
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  color: #fff;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.manual-input {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.uuid-input {
  min-height: 48px;
  padding: 0 16px;
  border: 1px solid #e8ecf1;
  border-radius: 10px;
  font-size: 15px;
  color: #1a2b5f;
  outline: none;
}

.uuid-input:focus {
  border-color: #1A365D;
  box-shadow: 0 0 0 3px rgba(26, 54, 95, 0.1);
}
</style>
