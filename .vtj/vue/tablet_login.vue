<!-- 平板端登录页 - VTJ规范版 -->
<template>
  <div class="tablet-login-page">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
    </div>

    <!-- 主内容区 -->
    <div class="login-container">
      <!-- 左侧品牌面板 -->
      <div class="brand-panel">
        <div class="brand-content">
          <div class="brand-logo">
            <XIcon :icon="Medal" :size="64" color="#ffffff"></XIcon>
          </div>
          <h1 class="brand-title">砺安题库</h1>
          <p class="brand-subtitle">公安联考智能备考平台</p>
          <div class="brand-features">
            <div class="feature-item">
              <XIcon :icon="CircleCheck" :size="20" color="#10b981"></XIcon>
              <span>海量题库，精准练习</span>
            </div>
            <div class="feature-item">
              <XIcon :icon="CircleCheck" :size="20" color="#10b981"></XIcon>
              <span>智能组卷，高效备考</span>
            </div>
            <div class="feature-item">
              <XIcon :icon="CircleCheck" :size="20" color="#10b981"></XIcon>
              <span>多端同步，随时随地</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧表单面板 -->
      <div class="form-panel">
        <div class="form-card">
          <!-- Tab切换 -->
          <div class="tab-switcher">
            <button :class="['tab-btn', { active: activeTab === 'login' }]" @click="switchTab('login')">
              <XIcon :icon="User" :size="16" color="currentColor"></XIcon>
              登录
            </button>
            <button :class="['tab-btn', { active: activeTab === 'qr' }]" @click="switchTab('qr')">
              <XIcon :icon="Iphone" :size="16" color="currentColor"></XIcon>
              扫码登录
            </button>
            <div class="tab-indicator" :class="{ right: activeTab === 'qr' }"></div>
          </div>

          <!-- 错误提示 -->
          <div v-if="message" :class="['form-message', msgType]">
            <XIcon v-if="msgType === 'error'" :icon="CircleCloseFilled" :size="16" color="#c41e3a"></XIcon>
            <XIcon v-else-if="msgType === 'success'" :icon="SuccessFilled" :size="16" color="#10b981"></XIcon>
            <XIcon v-else :icon="InfoFilled" :size="16" color="#1890ff"></XIcon>
            <span>{{ message }}</span>
          </div>

          <!-- 密码登录表单 -->
          <div v-if="activeTab === 'login'" class="login-form">
            <!-- 用户名输入 -->
            <div class="form-group">
              <label class="form-label">账号</label>
              <div class="input-wrapper">
                <XIcon :icon="User" :size="18" color="#8899aa" class="input-icon"></XIcon>
                <input
                  v-model="loginForm.username"
                  type="text"
                  class="form-input"
                  placeholder="请输入用户名或手机号"
                  autocomplete="username"
                />
              </div>
            </div>

            <!-- 密码输入 -->
            <div class="form-group">
              <label class="form-label">密码</label>
              <div class="input-wrapper">
                <XIcon :icon="Lock" :size="18" color="#8899aa" class="input-icon"></XIcon>
                <input
                  v-model="loginForm.password"
                  :type="loginForm.showPassword ? 'text' : 'password'"
                  class="form-input"
                  placeholder="请输入密码"
                  autocomplete="current-password"
                />
                <button
                  type="button"
                  class="toggle-password"
                  @click="togglePasswordVisibility"
                >
                  <XIcon :icon="loginForm.showPassword ? View : Hide" :size="18" color="#8899aa"></XIcon>
                </button>
              </div>
            </div>

            <!-- 记住我 & 忘记密码 -->
            <div class="form-options">
              <label class="remember-me">
                <input v-model="rememberMe" type="checkbox" />
                <span>记住我</span>
              </label>
              <a href="#" class="forgot-password" @click.prevent="handleForgotPassword">
                忘记密码？
              </a>
            </div>

            <!-- 登录按钮 -->
            <button
              class="login-btn"
              :disabled="loading"
              @click="handleLogin"
            >
              <span v-if="loading" class="loading-spinner"></span>
              <span v-else>登 录</span>
            </button>
          </div>

          <!-- 扫码登录表单 -->
          <div v-if="activeTab === 'qr'" class="qr-form">
            <div class="qr-container">
              <div class="qr-image">
                <XIcon :icon="Iphone" :size="80" color="#1A365D"></XIcon>
              </div>
              <p class="qr-tip">使用砺安题库APP扫描二维码</p>
              <p class="qr-subtip">无需输入密码，安全便捷</p>
            </div>
            <button class="refresh-btn" @click="refreshQR">
              <XIcon :icon="Refresh" :size="16" color="#1890ff"></XIcon>
              刷新二维码
            </button>
          </div>

          <!-- 底部提示 -->
          <div class="footer-tip">
            <p>还没有账号？请联系管理员分配</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import {
  Medal,
  User,
  Lock,
  View,
  Hide,
  Iphone,
  CircleCheck,
  CircleCloseFilled,
  SuccessFilled,
  InfoFilled,
  Refresh
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'TabletLogin',
  components: {
    XIcon
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'tablet_login', version: '1788919369989' });
    
    // 当前Tab
    const activeTab = ref('login');
    
    // 表单数据
    const loginForm = reactive({
      username: '',
      password: '',
      showPassword: false
    });
    const rememberMe = ref(false);
    const loading = ref(false);
    const message = ref('');
    const msgType = ref('error');

    // 显示消息
    const showMessage = (msg: string, type: string) => {
      message.value = msg;
      msgType.value = type;
      setTimeout(() => {
        message.value = '';
      }, 3000);
    };

    // 切换Tab
    const switchTab = (tab: string) => {
      activeTab.value = tab;
      message.value = '';
    };

    // 切换密码可见性
    const togglePasswordVisibility = () => {
      loginForm.showPassword = !loginForm.showPassword;
    };

    // 登录处理
    // 复用 window.__VTJ_AUTH__.login(username, password)：
    //   后端 /api/auth/login 是 OAuth2PasswordRequestForm，必须用
    //   application/x-www-form-urlencoded 提交，自己写 JSON 会 422。
    //   auth 模块内部已封装正确格式 + token 存储 + 设备会话注册，三端行为一致。
    const handleLogin = async () => {
      const username = loginForm.username.trim();
      const password = loginForm.password.trim();
      if (!username) {
        showMessage('请输入用户名', 'error');
        return;
      }
      if (!password) {
        showMessage('请输入密码', 'error');
        return;
      }

      loading.value = true;
      message.value = '';

      try {
        const auth = window.__VTJ_AUTH__;
        if (!auth || !auth.login) {
          showMessage('认证模块未就绪，请刷新页面重试', 'error');
          return;
        }
        const result = await auth.login(username, password);
        if (result && result.success) {
          showMessage('登录成功', 'success');
          setTimeout(() => {
            router.push('/tablet/home');
          }, 1000);
        } else {
          showMessage((result && result.message) || '登录失败，请检查用户名和密码', 'error');
        }
      } catch (error) {
        console.error('登录失败:', error);
        showMessage('网络错误，请稍后重试', 'error');
      } finally {
        loading.value = false;
      }
    };

    // 忘记密码
    const handleForgotPassword = () => {
      showMessage('请联系管理员重置密码', 'info');
    };

    // 刷新二维码
    const refreshQR = () => {
      showMessage('二维码已刷新', 'success');
    };

    return {
      activeTab,
      loginForm,
      rememberMe,
      loading,
      message,
      msgType,
      switchTab,
      handleLogin,
      togglePasswordVisibility,
      handleForgotPassword,
      refreshQR,
      Medal,
      User,
      Lock,
      View,
      Hide,
      Iphone,
      CircleCheck,
      CircleCloseFilled,
      SuccessFilled,
      InfoFilled,
      Refresh
    };
  }
});
</script>

<style lang="css" scoped>
.tablet-login-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 背景装饰 */
.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.04;
}

.circle-1 {
  width: 600px;
  height: 600px;
  background: #1A365D;
  top: -200px;
  right: -150px;
}

.circle-2 {
  width: 400px;
  height: 400px;
  background: #C91F37;
  bottom: -150px;
  left: -100px;
}

.circle-3 {
  width: 250px;
  height: 250px;
  background: #1A365D;
  top: 50%;
  left: 60%;
  transform: translate(-50%, -50%);
}

/* 主容器 */
.login-container {
  position: relative;
  z-index: 1;
  display: flex;
  width: 960px;
  max-width: 96vw;
  min-height: 600px;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(15, 52, 96, 0.15), 0 4px 16px rgba(0, 0, 0, 0.06);
}

/* 品牌面板 */
.brand-panel {
  flex: 0 0 420px;
  background: linear-gradient(160deg, #0F3460 0%, #0a2340 40%, #0d2848 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.brand-content {
  text-align: center;
  padding: 40px;
}

.brand-logo {
  margin-bottom: 24px;
}

.brand-title {
  font-size: 36px;
  font-weight: 800;
  color: #ffffff;
  margin: 0 0 8px;
  letter-spacing: 4px;
}

.brand-subtitle {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.7);
  margin: 0 0 40px;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 16px;
  text-align: left;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 15px;
}

/* 表单面板 */
.form-panel {
  flex: 1;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.form-card {
  width: 100%;
  max-width: 380px;
}

/* Tab切换 */
.tab-switcher {
  display: flex;
  position: relative;
  background: #F5F7FA;
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 24px;
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  border: none;
  background: transparent;
  font-size: 15px;
  font-weight: 600;
  color: #8899aa;
  cursor: pointer;
  border-radius: 10px;
  transition: all 0.3s ease;
  position: relative;
  z-index: 1;
}

.tab-btn.active {
  color: #C91F37;
}

.tab-indicator {
  position: absolute;
  top: 4px;
  left: 4px;
  width: calc(50% - 4px);
  height: calc(100% - 8px);
  background: #ffffff;
  border-radius: 10px;
  transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  z-index: 0;
}

.tab-indicator.right {
  transform: translateX(100%);
}

/* 表单消息 */
.form-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 16px;
}

.form-message.error {
  background: #fff2f0;
  border: 1px solid #ffccc7;
  color: #c41e3a;
}

.form-message.success {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  color: #10b981;
}

.form-message.info {
  background: #e6f7ff;
  border: 1px solid #91d5ff;
  color: #1890ff;
}

/* 表单组 */
.form-group {
  margin-bottom: 18px;
}

.form-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 8px;
}

.input-wrapper {
  display: flex;
  align-items: center;
  background: #f8f9fc;
  border: 1px solid #e8ecf1;
  border-radius: 10px;
  padding: 0 14px;
  transition: all 0.3s ease;
}

.input-wrapper:focus-within {
  border-color: #1A365D;
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(26, 54, 95, 0.1);
}

.input-icon {
  margin-right: 10px;
  flex-shrink: 0;
}

.form-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 12px 0;
  font-size: 15px;
  color: #1a2b5f;
  outline: none;
}

.form-input::placeholder {
  color: #a0a4b8;
}

.toggle-password {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 表单选项 */
.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.remember-me {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #5a6488;
  cursor: pointer;
}

.remember-me input {
  width: 16px;
  height: 16px;
  accent-color: #1A365D;
}

.forgot-password {
  font-size: 13px;
  color: #1890ff;
  text-decoration: none;
}

.forgot-password:hover {
  color: #096dd9;
}

/* 登录按钮 */
.login-btn {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  color: #ffffff;
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(26, 54, 95, 0.3);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 扫码登录表单 */
.qr-form {
  text-align: center;
}

.qr-container {
  margin-bottom: 24px;
}

.qr-image {
  width: 200px;
  height: 200px;
  background: #f8f9fc;
  border: 2px dashed #e8ecf1;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}

.qr-tip {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0 0 8px;
}

.qr-subtip {
  font-size: 13px;
  color: #8899aa;
  margin: 0;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  background: #ffffff;
  border: 1px solid #e8ecf1;
  border-radius: 8px;
  font-size: 14px;
  color: #1890ff;
  cursor: pointer;
  transition: all 0.3s ease;
}

.refresh-btn:hover {
  border-color: #1890ff;
  background: #e6f7ff;
}

/* 底部提示 */
.footer-tip {
  text-align: center;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #f0f2f5;
}

.footer-tip p {
  font-size: 13px;
  color: #8899aa;
  margin: 0;
}

/* 响应式 */
@media (max-width: 768px) {
  .login-container {
    flex-direction: column;
    min-height: auto;
  }
  
  .brand-panel {
    flex: none;
    padding: 40px 20px;
  }
  
  .brand-features {
    display: none;
  }
  
  .form-panel {
    padding: 24px;
  }
}
</style>
