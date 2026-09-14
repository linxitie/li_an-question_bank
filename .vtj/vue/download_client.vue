<!-- 扫码登录页面 -->
<template>
  <div class="dl-page">
    <NavBar></NavBar>
    <main class="dl-main">
      <!-- Hero区域 -->
      <section class="dl-hero">
        <div class="hero-bg"></div>
        <div class="hero-content">
          <h1 class="hero-title">扫码登录</h1>
          <p class="hero-subtitle">使用砺安题库APP扫描二维码，安全快捷登录</p>
          <p class="hero-desc">无需记忆密码，一扫即达，多端数据实时同步</p>
        </div>
      </section>

      <!-- 扫码核心区域 -->
      <div class="dl-scan-area">
        <!-- 二维码面板 -->
        <div class="qr-panel">
          <div class="qr-container">
            <!-- 二维码图片 -->
            <img 
              v-if="qrImage" 
              :src="qrImage" 
              alt="登录二维码" 
              class="qr-image" />
            
            <!-- 加载状态 -->
            <div v-else class="qr-loading">
              <div class="spinner"></div>
              <span>正在生成二维码...</span>
            </div>
            
            <!-- 过期遮罩 -->
            <div v-if="status === 'expired'" class="qr-overlay">
              <div class="expired-icon">⏰</div>
              <p class="expired-text">二维码已过期</p>
              <p class="expired-sub">请点击下方按钮重新生成</p>
              <button class="refresh-btn" @click="refresh">🔄 刷新二维码</button>
            </div>
          </div>
          
          <!-- 状态显示 -->
          <div class="qr-status">
            <span v-if="status === 'pending'" class="status-pending">
              ⏱️ <span class="countdown">{{ countdown }}</span>秒后过期
            </span>
            <span v-if="status === 'confirmed'" class="status-confirmed">
              ✅ 扫码成功，正在跳转...
            </span>
            <span v-if="status === 'expired'" class="status-expired">
              ⏰ 二维码已过期，请刷新
            </span>
            <span v-if="status === 'initial'" class="status-initial">
              正在准备...
            </span>
          </div>
          
          <!-- 切换登录方式 -->
          <div class="switch-login">
            <a @click="goToLogin">使用账号密码登录 →</a>
          </div>
        </div>
        
        <!-- 操作说明面板 -->
        <div class="info-panel">
          <h3>操作步骤</h3>
          <ul class="step-list">
            <li>
              <div class="step-num">1</div>
              <div class="step-text">
                <strong>打开砺安题库APP</strong>
                <span>在手机或平板上打开砺安题库应用</span>
              </div>
            </li>
            <li>
              <div class="step-num">2</div>
              <div class="step-text">
                <strong>点击"扫一扫"</strong>
                <span>在APP首页或登录页找到扫码入口</span>
              </div>
            </li>
            <li>
              <div class="step-num">3</div>
              <div class="step-text">
                <strong>扫描左侧二维码</strong>
                <span>对准屏幕上的二维码进行扫描</span>
              </div>
            </li>
            <li>
              <div class="step-num">4</div>
              <div class="step-text">
                <strong>在手机上确认登录</strong>
                <span>核对设备信息后点击确认，即可登录成功</span>
              </div>
            </li>
          </ul>
          
          <!-- 安全提示 -->
          <div class="security-tips">
            <h4>🔒 安全提示</h4>
            <ul>
              <li>二维码60秒自动过期，防止被他人误扫</li>
              <li>每次登录生成唯一二维码，安全可靠</li>
              <li>仅支持已登录用户扫码，保障账号安全</li>
              <li>可在"设备管理"中随时移除已登录设备</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- 为什么选择扫码登录 -->
      <section class="dl-features">
        <h2>为什么选择扫码登录？</h2>
        <div class="feat-items">
          <div class="feat-item">
            <div class="feat-icon" style="background: #eff6ff">🔒</div>
            <h4>更安全</h4>
            <p>无需记忆密码，避免密码泄露风险，设备二次确认保障安全</p>
          </div>
          <div class="feat-item">
            <div class="feat-icon" style="background: #fef2f2">⚡</div>
            <h4>更快捷</h4>
            <p>一扫即达，3秒完成登录，告别繁琐的密码输入</p>
          </div>
          <div class="feat-item">
            <div class="feat-icon" style="background: #fffbeb">📱</div>
            <h4>多端同步</h4>
            <p>手机、平板、电脑数据实时同步，学习进度无缝衔接</p>
          </div>
          <div class="feat-item">
            <div class="feat-icon" style="background: #f0fdf4">🔄</div>
            <h4>无缝切换</h4>
            <p>随时在不同设备间切换，学习不中断</p>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive, ref, onMounted, onUnmounted } from 'vue';
import NavBar from './navbar.vue';
import { useProvider } from '@vtj/renderer';
import { useRouter } from 'vue-router';

export default defineComponent({
  name: 'DownloadClient',
  components: { NavBar },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'download_client', version: '1788919369987' });
    
    // 状态
    const uuid = ref('');
    const status = ref('initial'); // initial, pending, confirmed, expired
    const countdown = ref(60);
    const qrImage = ref('');
    
    // 定时器
    let countdownTimer: number | null = null;
    let pollingTimer: number | null = null;
    
    // 生成二维码
    const generateQRCode = async () => {
      try {
        // 清理之前的定时器
        clearTimers();
        
        // 重置状态
        status.value = 'initial';
        qrImage.value = '';
        countdown.value = 60;
        
        // 调用后端API生成二维码（公开接口，无需鉴权；透传 origin 生成 URL 二维码）
        const res = await fetch('/api/auth/qrcode/generate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ origin: window.location.origin })
        });
        
        const data = await res.json();
        if (data.uuid) {
          uuid.value = data.uuid;
          qrImage.value = data.qr_image_base64 || `https://api.qrserver.com/v1/create-qr-code/?size=256x256&data=${encodeURIComponent(window.location.origin + '/#/mobile/scan?uuid=' + data.uuid)}`;
          status.value = 'pending';
          startCountdown();
          startPolling();
        }
      } catch (error) {
        console.error('生成二维码失败:', error);
        // 兜底：后端不可用时用第三方服务生成演示二维码（URL 格式）
        qrImage.value = `https://api.qrserver.com/v1/create-qr-code/?size=256x256&data=${encodeURIComponent('/#/mobile/scan?uuid=demo_' + Date.now())}`;
        status.value = 'pending';
        startCountdown();
        startPolling();
      }
    };
    
    // 开始倒计时
    const startCountdown = () => {
      countdown.value = 60;
      countdownTimer = window.setInterval(() => {
        countdown.value--;
        if (countdown.value <= 0) {
          clearInterval(countdownTimer!);
          status.value = 'expired';
        }
      }, 1000);
    };
    
    // 开始轮询状态
    const startPolling = async () => {
      const poll = async () => {
        try {
          const res = await fetch(`/api/auth/qrcode/${uuid.value}/status`);
          const data = await res.json();
          
          if (data.status === 'confirmed') {
            // 登录成功：走统一认证模块写入本地登录态（token 键必须与 auth.ts 一致）
            if (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.loginWithToken) {
              window.__VTJ_AUTH__.loginWithToken(data.token, '', '');
            }
            status.value = 'confirmed';
            clearTimers();
            // 按角色跳转对应仪表盘/首页
            setTimeout(() => {
              const role = window.__VTJ_AUTH__ ? window.__VTJ_AUTH__.getUserRole() : null;
              const dash = role === 'admin' ? '/admin/dashboard' : (role === 'teacher' ? '/teacher/dashboard' : '/');
              router.push(dash);
            }, 1500);
          } else if (data.status === 'expired') {
            status.value = 'expired';
            clearTimers();
          } else {
            // 继续轮询
            pollingTimer = window.setTimeout(poll, 1500);
          }
        } catch (error) {
          console.error('轮询状态失败:', error);
          // 模拟轮询（演示用）
          pollingTimer = window.setTimeout(poll, 1500);
        }
      };
      poll();
    };
    
    // 清理定时器
    const clearTimers = () => {
      if (countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
      }
      if (pollingTimer) {
        clearTimeout(pollingTimer);
        pollingTimer = null;
      }
    };
    
    // 刷新二维码
    const refresh = () => {
      generateQRCode();
    };
    
    // 跳转到登录页
    const goToLogin = () => {
      router.push('/login');
    };
    
    // 组件挂载时生成二维码
    onMounted(() => {
      generateQRCode();
    });
    
    // 组件卸载时清理定时器
    onUnmounted(() => {
      clearTimers();
    });
    
    return {
      uuid,
      status,
      countdown,
      qrImage,
      generateQRCode,
      refresh,
      goToLogin
    };
  }
});
</script>

<style lang="css" scoped>
.dl-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.dl-main {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 32px 40px;
}

.dl-hero {
  text-align: center;
  padding: 60px 20px 40px;
  position: relative;
  margin-bottom: 40px;
}

.hero-bg {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(196, 30, 58, 0.08) 0%, transparent 70%);
  border-radius: 50%;
}

.hero-content {
  position: relative;
  z-index: 1;
}

.hero-title {
  font-size: 42px;
  font-weight: 900;
  color: #1a2b5f;
  margin: 0;
  letter-spacing: 3px;
}

.hero-subtitle {
  font-size: 18px;
  color: #5a6488;
  margin: 12px 0 8px;
}

.hero-desc {
  font-size: 14px;
  color: #8a8faa;
}

.dl-scan-area {
  display: flex;
  gap: 40px;
  justify-content: center;
  align-items: flex-start;
  margin-bottom: 48px;
  flex-wrap: wrap;
}

.qr-panel {
  background: #fff;
  border-radius: 24px;
  padding: 32px;
  box-shadow: 0 4px 24px rgba(26, 43, 95, 0.08);
  text-align: center;
  width: 320px;
  flex-shrink: 0;
}

.qr-container {
  width: 256px;
  height: 256px;
  margin: 0 auto 20px;
  border-radius: 16px;
  border: 2px solid #e8eaf0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8f9fc;
  overflow: hidden;
  position: relative;
}

.qr-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.qr-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #8a8faa;
  font-size: 14px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e8eaf0;
  border-top-color: #c41e3a;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.qr-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border-radius: 14px;
}

.expired-icon {
  font-size: 48px;
  opacity: 0.4;
}

.expired-text {
  font-size: 14px;
  color: #8a8faa;
  margin: 0;
}

.expired-sub {
  font-size: 12px;
  color: #c0c4cc;
  margin: 0;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #1a365f, #2a5298);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.2);
}

.refresh-btn:hover {
  transform: scale(1.03);
  box-shadow: 0 4px 12px rgba(26, 54, 95, 0.3);
}

.qr-status {
  margin-top: 16px;
  font-size: 13px;
  color: #5a6488;
}

.status-pending .countdown {
  color: #c41e3a;
  font-weight: 700;
}

.status-confirmed {
  color: #52c41a;
  font-weight: 600;
}

.status-expired {
  color: #c41e3a;
}

.switch-login {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f2f5;
}

.switch-login a {
  font-size: 14px;
  color: #1a365f;
  text-decoration: none;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.2s;
}

.switch-login a:hover {
  color: #c41e3a;
}

.info-panel {
  flex: 1;
  max-width: 420px;
  padding-top: 8px;
}

.info-panel h3 {
  font-size: 20px;
  font-weight: 800;
  color: #1a2b5f;
  margin: 0 0 24px;
}

.step-list {
  list-style: none;
  padding: 0;
  margin: 0 0 32px;
}

.step-list li {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid #f0f2f5;
}

.step-list li:last-child {
  border-bottom: none;
}

.step-num {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #c41e3a, #e8384f);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 800;
  flex-shrink: 0;
}

.step-text {
  flex: 1;
}

.step-text strong {
  display: block;
  font-size: 15px;
  color: #1a2b5f;
  margin-bottom: 2px;
}

.step-text span {
  font-size: 13px;
  color: #5a6488;
  line-height: 1.5;
}

.security-tips {
  background: #f0f7ff;
  border-radius: 14px;
  padding: 16px 20px;
}

.security-tips h4 {
  font-size: 14px;
  font-weight: 700;
  color: #1a365f;
  margin: 0 0 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.security-tips ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.security-tips li {
  font-size: 12px;
  color: #5a6488;
  padding: 3px 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.security-tips li::before {
  content: '✓';
  color: #52c41a;
  font-weight: 700;
  font-size: 11px;
}

.dl-features {
  margin-top: 20px;
}

.dl-features h2 {
  text-align: center;
  font-size: 20px;
  font-weight: 800;
  color: #1a2b5f;
  margin: 0 0 24px;
}

.feat-items {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.feat-item {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 10px rgba(26, 43, 95, 0.04);
  text-align: center;
  transition: all 0.3s;
}

.feat-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(26, 43, 95, 0.08);
}

.feat-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  margin: 0 auto 14px;
}

.feat-item h4 {
  font-size: 15px;
  font-weight: 700;
  color: #1a2b5f;
  margin: 0 0 6px;
}

.feat-item p {
  font-size: 12px;
  color: #5a6488;
  margin: 0;
  line-height: 1.5;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 响应式适配 */
@media (max-width: 768px) {
  .dl-main {
    padding: 16px;
  }
  
  .dl-hero {
    padding: 40px 16px 24px;
  }
  
  .hero-title {
    font-size: 28px;
  }
  
  .dl-scan-area {
    flex-direction: column;
    align-items: center;
  }
  
  .qr-panel {
    width: 100%;
    max-width: 320px;
  }
  
  .info-panel {
    width: 100%;
  }
  
  .feat-items {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
