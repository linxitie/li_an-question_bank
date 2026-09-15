<!-- 手机端登录页 - VTJ规范版 -->
<template>
  <div class="mobile-login-page">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
    </div>

    <!-- 主内容区 -->
    <div class="login-container">
      <!-- Logo区域 -->
      <div class="logo-section">
        <div class="logo-icon">
          <XIcon :icon="Medal" :size="48" color="#1A365D"></XIcon>
        </div>
        <h1 class="logo-title">砺安题库</h1>
        <p class="logo-subtitle">公安联考智能备考</p>
      </div>

      <!-- 登录表单 -->
      <div class="login-form">
        <!-- 错误提示 -->
        <div v-if="message" :class="['form-message', msgType]">
          <XIcon v-if="msgType === 'error'" :icon="CircleCloseFilled" :size="16" color="#c41e3a"></XIcon>
          <XIcon v-else-if="msgType === 'success'" :icon="SuccessFilled" :size="16" color="#10b981"></XIcon>
          <XIcon v-else :icon="InfoFilled" :size="16" color="#1890ff"></XIcon>
          <span>{{ message }}</span>
        </div>

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

      <!-- 分割线 -->
      <div class="divider">
        <span class="divider-text">或</span>
      </div>

      <!-- 扫码登录入口 -->
      <div class="qr-login-section">
        <button class="qr-login-btn" @click="goToQRLogin">
          <XIcon :icon="Iphone" :size="20" color="#1A365D"></XIcon>
          <span class="qr-text">扫码登录（推荐）</span>
        </button>
        <p class="qr-tip">
          使用砺安题库APP扫描二维码，无需输入密码
        </p>
      </div>

      <!-- 底部提示 -->
      <div class="footer-tip">
        <p>还没有账号？请联系管理员分配</p>
      </div>
    </div>

    <!-- 底部安全区域 -->
    <div class="safe-area-bottom"></div>
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
  CircleCloseFilled,
  SuccessFilled,
  InfoFilled
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'MobileLogin',
  components: {
    XIcon
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'mobile_login', version: '1788919369989' });
    
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
        // client_type='mobile' 触发后端三端分离校验：移动端仅学生可登录
        const result = await auth.login(username, password, 'mobile');
        if (result && result.success) {
          showMessage('登录成功', 'success');
          setTimeout(() => {
            router.push('/mobile/home');
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

    // 跳转到扫码登录
    const goToQRLogin = () => {
      router.push('/mobile/scan');
    };

    return {
      loginForm,
      rememberMe,
      loading,
      message,
      msgType,
      handleLogin,
      togglePasswordVisibility,
      handleForgotPassword,
      goToQRLogin,
      Medal,
      User,
      Lock,
      View,
      Hide,
      Iphone,
      CircleCloseFilled,
      SuccessFilled,
      InfoFilled
    };
  }
});
</script>

<style lang="css" scoped>
.mobile-login-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f5f7fa 0%, #e8ecf1 100%);
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
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
  width: 300px;
  height: 300px;
  background: #1A365D;
  top: -100px;
  right: -80px;
}

.circle-2 {
  width: 200px;
  height: 200px;
  background: #C91F37;
  bottom: -80px;
  left: -60px;
}

/* 主容器 */
.login-container {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 40px 24px 20px;
}

/* Logo区域 */
.logo-section {
  text-align: center;
  margin-bottom: 40px;
}

.logo-icon {
  margin-bottom: 12px;
}

.logo-title {
  font-size: 28px;
  font-weight: 800;
  color: #1A365D;
  margin: 0 0 6px;
  letter-spacing: 2px;
}

.logo-subtitle {
  font-size: 14px;
  color: #5a6488;
  margin: 0;
}

/* 登录表单 */
.login-form {
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(26, 54, 95, 0.08);
  margin-bottom: 20px;
}

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

/* 分割线 */
.divider {
  display: flex;
  align-items: center;
  margin: 20px 0;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #e8ecf1;
}

.divider-text {
  padding: 0 16px;
  font-size: 13px;
  color: #a0a4b8;
}

/* 扫码登录 */
.qr-login-section {
  text-align: center;
  margin-bottom: 24px;
}

.qr-login-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: #ffffff;
  border: 1px solid #e8ecf1;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #1A365D;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.qr-login-btn:hover {
  border-color: #1A365D;
  box-shadow: 0 4px 12px rgba(26, 54, 95, 0.1);
}

.qr-tip {
  font-size: 12px;
  color: #8899aa;
  margin-top: 10px;
}

/* 底部提示 */
.footer-tip {
  text-align: center;
  margin-top: auto;
  padding-top: 20px;
}

.footer-tip p {
  font-size: 13px;
  color: #8899aa;
  margin: 0;
}

/* 安全区域适配 */
.safe-area-bottom {
  height: env(safe-area-inset-bottom, 0);
}

@media (max-width: 375px) {
  .login-container {
    padding: 30px 20px 16px;
  }
  
  .login-form {
    padding: 20px;
  }
  
  .logo-title {
    font-size: 24px;
  }
}
</style>
