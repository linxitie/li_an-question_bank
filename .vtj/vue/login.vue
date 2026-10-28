<template>
  <div class="auth-page">
    <div class="auth-bg-decor">
      <div class="decor-circle decor-1"></div>
      <div class="decor-circle decor-2"></div>
      <div class="decor-circle decor-3"></div>
    </div>
    <div class="auth-container">
      <!-- 左侧品牌区 -->
      <div class="auth-brand-panel">
        <div class="brand-inner">
          <div class="brand-badge">
            <XIcon :icon="StarFilled" :size="32" color="#C91F37"></XIcon>
          </div>
          <h1 class="brand-title">砺安题库</h1>
          <p class="brand-subtitle">公安联考智能学习平台</p>
          <div class="brand-quote">
            <div class="quote-line"></div>
            <p class="quote-text">忠诚·担当·卓越<br/>以奋斗书写藏蓝青春</p>
            <div class="quote-line"></div>
          </div>
          <div class="brand-features">
            <div class="feature-tag">
              <XIcon :icon="Check" :size="14" color="#4ade80"></XIcon>
              <span>AI 智能组卷</span>
            </div>
            <div class="feature-tag">
              <XIcon :icon="Check" :size="14" color="#4ade80"></XIcon>
              <span>公安联考真题库</span>
            </div>
            <div class="feature-tag">
              <XIcon :icon="Check" :size="14" color="#4ade80"></XIcon>
              <span>智能错题分析</span>
            </div>
            <div class="feature-tag">
              <XIcon :icon="Check" :size="14" color="#4ade80"></XIcon>
              <span>个性化学习规划</span>
            </div>
          </div>
        </div>
      </div>
      <!-- 右侧表单区 -->
      <div class="auth-form-panel">
        <div class="form-card">
          <!-- 登录/注册切换 -->
          <div class="tab-switcher">
            <button
              :class="['tab-btn', { active: state.activeTab === 'login' }]"
              @click="switchTab('login')">
              <XIcon :icon="UserFilled" :size="16" :color="state.activeTab === 'login' ? '#C91F37' : '#8899aa'"></XIcon>
              <span>登 录</span>
            </button>
            <button
              :class="['tab-btn', { active: state.activeTab === 'register' }]"
              @click="switchTab('register')">
              <XIcon :icon="EditPen" :size="16" :color="state.activeTab === 'register' ? '#C91F37' : '#8899aa'"></XIcon>
              <span>注 册</span>
            </button>
            <div class="tab-indicator" :class="{ right: state.activeTab === 'register' }"></div>
          </div>
          <!-- 消息提示 -->
          <transition name="msg-fade">
            <div class="form-message" v-if="state.message" :class="state.msgType">
              <XIcon
                :icon="state.msgType === 'error' ? CloseBold : Check"
                :size="16"
                :color="state.msgType === 'error' ? '#e8384f' : '#4ade80'"></XIcon>
              <span>{{ state.message }}</span>
            </div>
          </transition>
          <!-- ========== 登录表单 ========== -->
          <div class="form-body" v-if="state.activeTab === 'login'">
            <!-- 登录子模式切换 -->
            <div class="login-mode-tabs">
              <span
                :class="['mode-tab', { active: state.loginMode === 'password' }]"
                @click="state.loginMode = 'password'">密码登录</span>
              <span class="mode-divider">|</span>
              <span
                :class="['mode-tab', { active: state.loginMode === 'sms' }]"
                @click="state.loginMode = 'sms'">验证码登录</span>
              <span class="mode-divider">|</span>
              <span class="mode-tab" @click="goToScanLogin">扫码登录</span>
            </div>
            <!-- 密码登录 -->
            <template v-if="state.loginMode === 'password'">
              <div class="input-group">
                <div class="input-icon-wrapper">
                  <XIcon :icon="UserFilled" :size="20" color="#8899aa"></XIcon>
                </div>
                <input
                  v-model="state.loginForm.username"
                  type="text"
                  class="form-input"
                  placeholder="请输入学号 / 教师编号"
                  @keyup.enter="handleLogin" />
              </div>
              <div class="input-group">
                <div class="input-icon-wrapper">
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8899aa" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                    <circle cx="12" cy="16" r="1.5"></circle>
                    <line x1="12" y1="17.5" x2="12" y2="19.5"></line>
                  </svg>
                </div>
                <input
                  v-model="state.loginForm.password"
                  :type="state.loginForm.showPassword ? 'text' : 'password'"
                  class="form-input"
                  placeholder="请输入密码"
                  @keyup.enter="handleLogin" />
                <div class="input-suffix" @click="toggleLoginPwdVisibility">
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" :stroke="state.loginForm.showPassword ? '#C91F37' : '#8899aa'" stroke-width="1.5" stroke-linecap="round">
                    <template v-if="state.loginForm.showPassword">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"></path>
                      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"></path>
                      <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"></path>
                      <line x1="1" y1="1" x2="23" y2="23"></line>
                    </template>
                    <template v-else>
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </template>
                  </svg>
                </div>
              </div>
            </template>
            <!-- 验证码登录 -->
            <template v-if="state.loginMode === 'sms'">
              <div class="input-group">
                <div class="input-icon-wrapper">
                  <XIcon :icon="UserFilled" :size="20" color="#8899aa"></XIcon>
                </div>
                <input
                  v-model="state.smsLoginForm.username"
                  type="text"
                  class="form-input"
                  placeholder="请输入学号 / 教师编号" />
              </div>
              <div class="input-group">
                <div class="input-icon-wrapper">
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8899aa" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="5" y="2" width="14" height="20" rx="2" ry="2"></rect>
                    <line x1="12" y1="18" x2="12.01" y2="18"></line>
                  </svg>
                </div>
                <input
                  v-model="state.smsLoginForm.phone"
                  type="text"
                  class="form-input"
                  placeholder="请输入手机号" />
              </div>
              <div class="input-group">
                <div class="input-icon-wrapper">
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8899aa" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="4" width="20" height="16" rx="2"></rect>
                    <polyline points="2,8 12,14 22,8"></polyline>
                  </svg>
                </div>
                <input
                  v-model="state.smsLoginForm.code"
                  type="text"
                  class="form-input code-input"
                  placeholder="请输入验证码"
                  maxlength="6" />
                <button
                  class="sms-btn"
                  :disabled="state.smsLoginForm.countdown > 0"
                  @click="sendSmsCode('login')">
                  <span v-if="state.smsLoginForm.countdown > 0">{{ state.smsLoginForm.countdown }}s 后重发</span>
                  <span v-else>获取验证码</span>
                </button>
              </div>
            </template>
            <button class="submit-btn" @click="handleLogin" :disabled="state.loading">
              <XIcon :icon="ArrowRight" :size="20" color="#ffffff" v-if="!state.loading"></XIcon>
              <span v-if="state.loading">登录中...</span>
              <span v-else>登 录 砺安题库</span>
            </button>
          </div>
          <!-- ========== 注册表单 ========== -->
          <div class="form-body" v-if="state.activeTab === 'register'">
            <div class="input-group">
              <div class="input-icon-wrapper">
                <XIcon :icon="UserFilled" :size="20" color="#8899aa"></XIcon>
              </div>
              <input
                v-model="state.registerForm.username"
                type="text"
                class="form-input"
                placeholder="请输入学号 / 教师编号"
                maxlength="20" />
            </div>
            <div class="input-group">
              <div class="input-icon-wrapper">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8899aa" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                </svg>
              </div>
              <input
                v-model="state.registerForm.password"
                :type="state.registerForm.showPassword ? 'text' : 'password'"
                class="form-input"
                placeholder="请设置密码（6-20位）"
                maxlength="20" />
              <div class="input-suffix" @click="state.registerForm.showPassword = !state.registerForm.showPassword">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" :stroke="state.registerForm.showPassword ? '#C91F37' : '#8899aa'" stroke-width="1.5" stroke-linecap="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" v-if="!state.registerForm.showPassword"></path>
                  <circle cx="12" cy="12" r="3" v-if="!state.registerForm.showPassword"></circle>
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" v-if="state.registerForm.showPassword"></path>
                  <line x1="1" y1="1" x2="23" y2="23" v-if="state.registerForm.showPassword"></line>
                </svg>
              </div>
            </div>
            <div class="input-group">
              <div class="input-icon-wrapper">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8899aa" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="5" y="2" width="14" height="20" rx="2" ry="2"></rect>
                  <line x1="12" y1="18" x2="12.01" y2="18"></line>
                </svg>
              </div>
              <input
                v-model="state.registerForm.phone"
                type="text"
                class="form-input"
                placeholder="请输入手机号"
                maxlength="11" />
            </div>
            <div class="input-group">
              <div class="input-icon-wrapper">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8899aa" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="2" y="4" width="20" height="16" rx="2"></rect>
                  <polyline points="2,8 12,14 22,8"></polyline>
                </svg>
              </div>
              <input
                v-model="state.registerForm.code"
                type="text"
                class="form-input code-input"
                placeholder="请输入验证码"
                maxlength="6" />
              <button
                class="sms-btn"
                :disabled="state.registerForm.countdown > 0"
                @click="sendSmsCode('register')">
                <span v-if="state.registerForm.countdown > 0">{{ state.registerForm.countdown }}s 后重发</span>
                <span v-else>获取验证码</span>
              </button>
            </div>
            <!-- 身份选择 -->
            <div class="role-selector">
              <label class="role-label">
                <XIcon :icon="StarFilled" :size="14" color="#8899aa"></XIcon>
                <span>选择身份</span>
              </label>
              <div class="role-options">
                <label
                  :class="['role-option', { active: state.registerForm.role === 'student' }]"
                  @click="selectRole('student')">
                  <div class="role-icon-box" :class="{ active: state.registerForm.role === 'student' }">
                    <svg viewBox="0 0 24 24" width="28" height="28" fill="none" :stroke="state.registerForm.role === 'student' ? '#C91F37' : '#8899aa'" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M22 10v6M2 10l10-5 10 5-10 5z"></path>
                      <path d="M6 12v5c0 2 3 4 6 4s6-2 6-4v-5"></path>
                    </svg>
                  </div>
                  <span class="role-name">预备警官</span>
                  <span class="role-sub">学生</span>
                </label>
                <div class="role-note">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#8899aa" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  <span>教师/管理员账号请联系管理员创建</span>
              </div>
            </div>
          </div>
            <button class="submit-btn" @click="handleRegister" :disabled="state.loading">
              <XIcon :icon="EditPen" :size="20" color="#ffffff" v-if="!state.loading"></XIcon>
              <span v-if="state.loading">注册中...</span>
              <span v-else>注 册 加入砺安题库</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive } from 'vue';
import { XIcon } from '@vtj/ui';
import {
  UserFilled,
  EditPen,
  Check,
  StarFilled,
  Timer,
  CloseBold,
  ArrowRight
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'AuthPage',
  components: { XIcon },
  setup(props) {
    const provider = useProvider({ id: 'login', version: '1781164000000' });
    const state = reactive({
      activeTab: 'login',
      loginMode: 'password',
      message: '',
      msgType: 'error',
      loading: false,
      loginForm: {
        username: '',
        password: '',
        showPassword: false
      },
      smsLoginForm: {
        username: '',
        phone: '',
        code: '',
        countdown: 0
      },
      registerForm: {
        username: '',
        password: '',
        phone: '',
        code: '',
        role: 'student',
        showPassword: false,
        countdown: 0
      }
    });
    return {
      state, props, provider,
      UserFilled, EditPen, Check, StarFilled, Timer, CloseBold, ArrowRight
    };
  },
  mounted() {
    if (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.isLoggedIn()) {
      // 支持 /login?logout=1 强制退出登录，打破"已登录但仪表盘白屏"的死循环
      // 解析 hash 路由中的查询参数（Vue Router hash 模式下 URL 形如 /#/login?logout=1）
      var hashSearch = '';
      var hashIdx = window.location.hash.indexOf('?');
      if (hashIdx >= 0) hashSearch = window.location.hash.substring(hashIdx + 1);
      var urlParams = new URLSearchParams(hashSearch);
      if (urlParams.get('logout') === '1') {
        window.__VTJ_AUTH__.logout();
        this.showMessage('已退出登录，请重新登录', 'success');
        return;  // 留在登录页，不跳转
      }
      const username = window.__VTJ_AUTH__.getUsername();
      this.showMessage('已登录为 ' + username + '，即将跳转...', 'success');
      setTimeout(function() {
        const dash = this.getDashboardPath();
        if (this.$router) this.$router.push(dash);
        else window.location.href = dash;
      }.bind(this), 1000);
    }
  },
  methods: {
    showMessage(msg, type) {
      this.state.message = msg;
      this.state.msgType = type || 'error';
      if (type === 'success') {
        setTimeout(function() { this.state.message = ''; }.bind(this), 4000);
      }
    },
    switchTab(tab) {
      this.state.activeTab = tab;
      this.state.message = '';
    },
    /**
     * 跳转到扫码登录页（PC端）
     */
    goToScanLogin() {
      if (this.$router) this.$router.push('/scan');
      else window.location.href = '/#/scan';
    },
    selectRole(role) {
      this.state.registerForm.role = role;
    },
    toggleLoginPwdVisibility() {
      this.state.loginForm.showPassword = !this.state.loginForm.showPassword;
    },
    /**
     * 根据角色获取登录后跳转路径
     */
    getDashboardPath() {
      const auth = window.__VTJ_AUTH__;
      if (auth) {
        const role = auth.getUserRole();
        if (role === 'admin') return '/admin/dashboard';
        if (role === 'teacher') return '/teacher/dashboard';
      }
      return '/';
    },
    /**
     * 发送验证码（模拟）
     */
    sendSmsCode(formType) {
      const form = formType === 'login' ? this.state.smsLoginForm : this.state.registerForm;
      const phone = form.phone || '';
      if (!/^1[3-9]\d{9}$/.test(phone)) {
        this.showMessage('请输入正确的手机号');
        return;
      }
      form.countdown = 60;
      const timer = setInterval(function() {
        form.countdown--;
        if (form.countdown <= 0) clearInterval(timer);
      }.bind(this), 1000);
      this.showMessage('验证码已发送（模拟：123456）', 'success');
    },
    /**
     * 登录处理
     */
    async handleLogin() {
      const mode = this.state.loginMode;
      let username = '';
      let password = '';
      if (mode === 'password') {
        username = (this.state.loginForm.username || '').trim();
        password = this.state.loginForm.password;
        if (!username) { this.showMessage('请输入学号或教师编号'); return; }
        if (!password) { this.showMessage('请输入密码'); return; }
      } else {
        username = (this.state.smsLoginForm.username || '').trim();
        const phone = (this.state.smsLoginForm.phone || '').trim();
        const code = (this.state.smsLoginForm.code || '').trim();
        if (!username) { this.showMessage('请输入学号或教师编号'); return; }
        if (!phone) { this.showMessage('请输入手机号'); return; }
        if (!/^1[3-9]\d{9}$/.test(phone)) { this.showMessage('请输入正确的手机号'); return; }
        if (code !== '123456') { this.showMessage('验证码错误（模拟验证码：123456）'); return; }
        // 调用 SMS 登录 API
        this.state.loading = true;
        this.state.message = '';
        try {
          const res = await fetch('/api/auth/sms-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: username, phone: phone, code: code })
          });
          const data = await res.json();
          if (res.ok && data.access_token) {
            window.__VTJ_AUTH__.login(username, 'sms-bypass');
            localStorage.setItem('__VTJ_AUTH_STATE__', JSON.stringify({
              token: data.access_token,
              refreshToken: data.refresh_token || '',
              username: username,
              loginTime: Date.now()
            }));
            this.showMessage('登录成功，即将跳转...', 'success');
            setTimeout(function() {
              if (this.$router) this.$router.push(this.getDashboardPath());
              else window.location.href = this.getDashboardPath();
            }.bind(this), 800);
          } else {
            this.showMessage(data.detail || '验证码登录失败');
          }
        } catch (e) {
          this.showMessage('登录失败：' + (e.message || '网络异常'));
        }
        this.state.loading = false;
        return;
      }
      this.state.loading = true;
      this.state.message = '';
      try {
        const result = await window.__VTJ_AUTH__.login(username, password);
        if (result.success) {
          this.showMessage('登录成功，即将跳转...', 'success');
          setTimeout(function() {
            if (this.$router) this.$router.push(this.getDashboardPath());
            else window.location.href = this.getDashboardPath();
          }.bind(this), 800);
        } else {
          this.showMessage(result.message);
        }
      } catch (e) {
        this.showMessage('登录失败：' + (e.message || '网络异常'));
      }
      this.state.loading = false;
    },
    /**
     * 注册处理
     */
    async handleRegister() {
      const f = this.state.registerForm;
      const username = (f.username || '').trim();
      const password = f.password || '';
      const phone = (f.phone || '').trim();
      const code = (f.code || '').trim();
      const role = f.role;
      // 校验
      if (!username) { this.showMessage('请输入学号或教师编号'); return; }
      if (!/^[a-zA-Z0-9]{4,20}$/.test(username)) { this.showMessage('账号应为4-20位字母或数字'); return; }
      if (!password || password.length < 6 || password.length > 20) { this.showMessage('密码应为6-20位字符'); return; }
      if (!phone) { this.showMessage('请输入手机号'); return; }
      if (!/^1[3-9]\d{9}$/.test(phone)) { this.showMessage('请输入正确的11位手机号'); return; }
      if (code !== '123456') { this.showMessage('验证码错误（模拟验证码：123456）'); return; }
      const roleMap = { student: 'student', teacher: 'teacher', admin: 'admin' };
      if (!roleMap[role]) { this.showMessage('请选择身份类型'); return; }
      this.state.loading = true;
      this.state.message = '';
      try {
        const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: username,
            password: password,
            phone: phone,
            user_no: username,
            user_type: roleMap[role]
          })
        });
        const data = await res.json();
        if (res.ok && data.user_id) {
          this.showMessage('注册成功！正在自动登录...', 'success');
          const result = await window.__VTJ_AUTH__.login(username, password);
          if (result.success) {
            setTimeout(function() {
              // v2 画像引导：新注册用户先完成备考画像，再做学习计划
              if (this.state.activeTab === 'register') {
                if (this.$router) this.$router.push('/profile-quiz');
                else window.location.hash = '#/profile-quiz';
              } else {
                if (this.$router) this.$router.push(this.getDashboardPath());
                else window.location.href = this.getDashboardPath();
              }
            }.bind(this), 1000);
          }
        } else {
          this.showMessage(data.detail || '注册失败，请稍后重试');
        }
      } catch (e) {
        this.showMessage('注册失败：' + (e.message || '网络异常'));
      }
      this.state.loading = false;
    }
  }
})
</script>
<style lang="css" scoped>
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }
  /* ===== 页面布局 ===== */
  .auth-page {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: #F5F7FA;
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', 'Segoe UI', sans-serif;
    position: relative;
    overflow: hidden;
  }
  /* 背景装饰 */
  .auth-bg-decor {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 0;
  }
  .decor-circle {
    position: absolute;
    border-radius: 50%;
    opacity: 0.04;
  }
  .decor-1 {
    width: 600px;
    height: 600px;
    background: #0F3460;
    top: -200px;
    right: -150px;
  }
  .decor-2 {
    width: 400px;
    height: 400px;
    background: #C91F37;
    bottom: -150px;
    left: -100px;
  }
  .decor-3 {
    width: 250px;
    height: 250px;
    background: #0F3460;
    top: 50%;
    left: 60%;
    transform: translate(-50%, -50%);
  }
  .auth-container {
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
  /* ===== 左侧品牌区 ===== */
  .auth-brand-panel {
    flex: 0 0 420px;
    background: linear-gradient(160deg, #0F3460 0%, #0a2340 40%, #0d2848 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }
  .auth-brand-panel::before {
    content: '';
    position: absolute;
    top: -80px;
    right: -80px;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(201, 31, 55, 0.12) 0%, transparent 70%);
    border-radius: 50%;
  }
  .auth-brand-panel::after {
    content: '';
    position: absolute;
    bottom: -60px;
    left: 40px;
    width: 200px;
    height: 200px;
    background: radial-gradient(circle, rgba(201, 31, 55, 0.08) 0%, transparent 70%);
    border-radius: 50%;
  }
  .brand-inner {
    text-align: center;
    position: relative;
    z-index: 1;
    padding: 40px;
  }
  .brand-badge {
    width: 72px;
    height: 72px;
    background: rgba(201, 31, 55, 0.12);
    border: 2px solid rgba(201, 31, 55, 0.3);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 20px;
    animation: badge-glow 3s ease-in-out infinite;
  }
  @keyframes badge-glow {
    0%, 100% { box-shadow: 0 0 12px rgba(201, 31, 55, 0.3); }
    50% { box-shadow: 0 0 28px rgba(201, 31, 55, 0.6); }
  }
  .brand-title {
    font-size: 34px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 4px;
    margin-bottom: 8px;
  }
  .brand-subtitle {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.55);
    letter-spacing: 2px;
    font-weight: 400;
  }
  .brand-quote {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 28px 0 24px;
  }
  .quote-line {
    flex: 1;
    height: 1px;
    background: rgba(255, 255, 255, 0.12);
  }
  .quote-text {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.45);
    line-height: 1.8;
    font-weight: 400;
    letter-spacing: 2px;
    white-space: nowrap;
  }
  .brand-features {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
  }
  .feature-tag {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.65);
    transition: all 0.3s;
  }
  .feature-tag:hover {
    background: rgba(201, 31, 55, 0.12);
    border-color: rgba(201, 31, 55, 0.25);
    color: #ffffff;
  }
  /* ===== 右侧表单区 ===== */
  .auth-form-panel {
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
  /* Tab 切换 */
  .tab-switcher {
    display: flex;
    position: relative;
    background: #F0F3F7;
    border-radius: 12px;
    padding: 4px;
    margin-bottom: 24px;
  }
  .tab-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 0;
    border: none;
    background: transparent;
    font-size: 15px;
    font-weight: 600;
    color: #8899aa;
    cursor: pointer;
    border-radius: 10px;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
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
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .tab-indicator.right {
    transform: translateX(100%);
  }
  /* 消息提示 */
  .form-message {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-radius: 10px;
    margin-bottom: 16px;
    font-size: 13px;
    font-weight: 500;
  }
  .form-message.error {
    background: rgba(232, 56, 79, 0.06);
    border: 1px solid rgba(232, 56, 79, 0.15);
    color: #e8384f;
  }
  .form-message.success {
    background: rgba(74, 222, 128, 0.06);
    border: 1px solid rgba(74, 222, 128, 0.15);
    color: #22c55e;
  }
  .msg-fade-enter-active, .msg-fade-leave-active {
    transition: all 0.3s ease;
  }
  .msg-fade-enter-from, .msg-fade-leave-to {
    opacity: 0;
    transform: translateY(-8px);
  }
  /* 登录子模式 */
  .login-mode-tabs {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-bottom: 20px;
    font-size: 14px;
  }
  .mode-tab {
    color: #8899aa;
    cursor: pointer;
    transition: color 0.3s;
    font-weight: 500;
    padding: 4px 0;
    border-bottom: 2px solid transparent;
  }
  .mode-tab.active {
    color: #C91F37;
    border-bottom-color: #C91F37;
  }
  .mode-divider {
    color: #d0d5de;
  }
  /* 输入框组 */
  .form-body {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .input-group {
    display: flex;
    align-items: center;
    background: #F8FAFC;
    border: 1.5px solid #e8ecf1;
    border-radius: 12px;
    transition: all 0.3s;
    overflow: hidden;
  }
  .input-group:focus-within {
    border-color: #C91F37;
    box-shadow: 0 0 0 3px rgba(201, 31, 55, 0.08);
    background: #ffffff;
  }
  .input-icon-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 46px;
    flex-shrink: 0;
  }
  .form-input {
    flex: 1;
    border: none;
    outline: none;
    background: transparent;
    padding: 14px 0;
    font-size: 14px;
    color: #1a2a3a;
    font-family: inherit;
  }
  .form-input::placeholder {
    color: #bcc4d0;
  }
  .form-input.code-input {
    max-width: 110px;
  }
  .input-suffix {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 42px;
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.2s;
  }
  .input-suffix:hover {
    opacity: 0.7;
  }
  .sms-btn {
    flex-shrink: 0;
    padding: 8px 16px;
    margin: 4px 6px 4px 0;
    background: rgba(201, 31, 55, 0.06);
    border: 1px solid rgba(201, 31, 55, 0.15);
    border-radius: 8px;
    color: #C91F37;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.3s;
    font-family: inherit;
  }
  .sms-btn:hover:not(:disabled) {
    background: rgba(201, 31, 55, 0.12);
    border-color: rgba(201, 31, 55, 0.3);
  }
  .sms-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  /* 身份选择 */
  .role-selector {
    margin-top: 4px;
  }
  .role-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #8899aa;
    font-weight: 500;
    margin-bottom: 10px;
  }
  .role-options {
    display: flex;
    gap: 10px;
  }
  .role-option {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 14px 8px;
    background: #F8FAFC;
    border: 1.5px solid #e8ecf1;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .role-option:hover {
    border-color: rgba(201, 31, 55, 0.25);
    background: rgba(201, 31, 55, 0.02);
  }
  .role-option.active {
    border-color: #C91F37;
    background: rgba(201, 31, 55, 0.04);
    box-shadow: 0 0 0 3px rgba(201, 31, 55, 0.06);
  }
  .role-note { display:flex; align-items:center; gap:8px; padding:10px 14px; color:#8899aa; font-size:13px; background:#f8f9fc; border-radius:8px; margin-top:12px; }
  .role-icon-box {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(15, 52, 96, 0.04);
    transition: all 0.3s;
  }
  .role-icon-box.active {
    background: rgba(201, 31, 55, 0.08);
  }
  .role-name {
    font-size: 13px;
    font-weight: 600;
    color: #1a2a3a;
  }
  .role-sub {
    font-size: 11px;
    color: #8899aa;
  }
  /* 提交按钮 */
  .submit-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    padding: 15px 0;
    margin-top: 6px;
    background: linear-gradient(135deg, #C91F37 0%, #e8384f 100%);
    border: none;
    border-radius: 12px;
    color: #ffffff;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 2px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    font-family: inherit;
    position: relative;
    overflow: hidden;
  }
  .submit-btn::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 50%);
    opacity: 0;
    transition: opacity 0.3s;
  }
  .submit-btn:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(201, 31, 55, 0.35);
  }
  .submit-btn:hover:not(:disabled)::after {
    opacity: 1;
  }
  .submit-btn:active:not(:disabled) {
    transform: translateY(0);
  }
  .submit-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  /* ===== 响应式 ===== */
  @media (max-width: 860px) {
    .auth-container {
      flex-direction: column;
      max-height: none;
      margin: 20px;
    }
    .auth-brand-panel {
      flex: 0 0 auto;
      padding: 30px 20px;
    }
    .brand-title {
      font-size: 26px;
    }
    .brand-quote {
      margin: 16px 0;
    }
    .brand-features {
      display: none;
    }
    .brand-badge {
      width: 52px;
      height: 52px;
    }
  }
  @media (max-width: 480px) {
    .auth-container {
      margin: 0;
      border-radius: 0;
      min-height: 100vh;
    }
    .auth-brand-panel {
      padding: 24px 20px;
    }
    .auth-form-panel {
      padding: 24px 20px;
    }
    .form-card {
      max-width: 100%;
    }
    .role-options {
      flex-wrap: wrap;
    }
    .role-option {
      min-width: 90px;
    }
  }
</style>
