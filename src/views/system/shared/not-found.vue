<template>
  <div class="nf-page">
    <!-- 背景装饰 -->
    <div class="nf-bg-decor">
      <div class="decor-circle decor-1"></div>
      <div class="decor-circle decor-2"></div>
      <div class="decor-circle decor-3"></div>
      <div class="decor-line decor-l1"></div>
      <div class="decor-line decor-l2"></div>
    </div>

    <div class="nf-container">
      <!-- 404 大数字动画区 -->
      <div class="nf-hero">
        <div class="nf-shield">
          <div class="shield-inner">
            <span class="shield-star">★</span>
          </div>
        </div>
        <div class="nf-code">
          <span class="digit digit-4">4</span>
          <span class="digit digit-0">0</span>
          <span class="digit digit-4-2">4</span>
        </div>
      </div>

      <!-- 信息区 -->
      <div class="nf-content">
        <h1 class="nf-title">页面未找到</h1>
        <p class="nf-subtitle">您访问的页面不存在或已被移除</p>
        <div class="nf-divider">
          <span class="divider-dot"></span>
        </div>
        <p class="nf-hint">请检查链接是否正确，或使用下方导航返回</p>

        <!-- 主要操作 -->
        <div class="nf-actions">
          <button class="btn-home" @click="goHome">
            <span class="btn-icon">🏠</span>
            <span>返回首页</span>
          </button>
          <button class="btn-back" @click="goBack">
            <span class="btn-icon">↩</span>
            <span>返回上页</span>
          </button>
        </div>
      </div>

      <!-- 快速导航 -->
      <div class="nf-links">
        <h3 class="links-title">快捷导航</h3>
        <div class="links-grid">
          <a class="link-card" @click="navTo('/')">
            <span class="link-card-icon">📚</span>
            <span class="link-card-text">题库中心</span>
          </a>
          <a class="link-card" @click="navTo('/login')">
            <span class="link-card-icon">🔐</span>
            <span class="link-card-text">用户登录</span>
          </a>
          <a class="link-card" @click="navTo('/question-import')">
            <span class="link-card-icon">📥</span>
            <span class="link-card-text">导入试题</span>
          </a>
        </div>
      </div>

      <!-- 底部提示 -->
      <p class="nf-footer">
        如有疑问，请联系 <span class="footer-contact">系统管理员</span>
      </p>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
  name: 'NotFound',
  methods: {
    goHome() {
      this.$router.push('/');
    },
    goBack() {
      if (window.history.length > 1) {
        this.$router.back();
      } else {
        this.$router.push('/');
      }
    },
    navTo(path: string) {
      this.$router.push(path);
    }
  }
});
</script>

<style scoped>
/* ===== 基础容器 ===== */
.nf-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #F5F7FA 0%, #e8ecf2 60%, #dce1e8 100%);
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  overflow: hidden;
}

/* ===== 背景装饰 ===== */
.nf-bg-decor {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
.decor-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.06;
}
.decor-1 {
  width: 600px;
  height: 600px;
  background: #0F3460;
  top: -200px;
  right: -150px;
  animation: float-slow 20s ease-in-out infinite;
}
.decor-2 {
  width: 400px;
  height: 400px;
  background: #C91F37;
  bottom: -100px;
  left: -100px;
  animation: float-slow 25s ease-in-out infinite reverse;
}
.decor-3 {
  width: 200px;
  height: 200px;
  background: #0F3460;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation: pulse-soft 4s ease-in-out infinite;
}
.decor-line {
  position: absolute;
  height: 1px;
  background: linear-gradient(90deg, transparent, #C91F37, transparent);
  opacity: 0.08;
}
.decor-l1 {
  width: 80%;
  top: 25%;
  left: 10%;
}
.decor-l2 {
  width: 60%;
  bottom: 30%;
  right: 5%;
}

/* ===== 主容器 ===== */
.nf-container {
  position: relative;
  z-index: 1;
  max-width: 620px;
  width: 92vw;
  text-align: center;
  animation: fadeInUp 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ===== 404 数字区域 ===== */
.nf-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 8px;
}

.nf-shield {
  width: 80px;
  height: 96px;
  margin-bottom: -12px;
  animation: shield-glow 3s ease-in-out infinite;
  filter: drop-shadow(0 4px 16px rgba(201, 31, 55, 0.3));
}
.shield-inner {
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, #C91F37 0%, #a0182c 100%);
  clip-path: polygon(50% 0%, 100% 15%, 100% 50%, 50% 100%, 0% 50%, 0% 15%);
  display: flex;
  align-items: center;
  justify-content: center;
}
.shield-star {
  font-size: 32px;
  color: #FFD700;
  text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
  animation: star-pulse 2s ease-in-out infinite;
}

.nf-code {
  display: flex;
  gap: 16px;
  margin-top: 8px;
}
.digit {
  font-size: 120px;
  font-weight: 900;
  line-height: 1;
  background: linear-gradient(180deg, #0F3460 0%, #162D50 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-shadow: none;
  filter: drop-shadow(0 6px 24px rgba(15, 52, 96, 0.18));
  animation: digit-float 3s ease-in-out infinite;
}
.digit-0 {
  animation-delay: 0.15s;
  color: #C91F37;
  background: linear-gradient(180deg, #C91F37 0%, #a0182c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.digit-4-2 {
  animation-delay: 0.3s;
}

/* ===== 信息区 ===== */
.nf-content {
  margin-top: 4px;
}
.nf-title {
  font-size: 28px;
  font-weight: 800;
  color: #0F3460;
  margin: 0;
  letter-spacing: 3px;
}
.nf-subtitle {
  font-size: 15px;
  color: #5a6488;
  margin: 10px 0 0;
  font-weight: 400;
}
.nf-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 24px 0;
}
.nf-divider::before,
.nf-divider::after {
  content: '';
  width: 60px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #C91F37, transparent);
  opacity: 0.3;
}
.divider-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #C91F37;
  margin: 0 12px;
  opacity: 0.6;
}
.nf-hint {
  font-size: 13px;
  color: #8899aa;
  margin: 0 0 28px;
}

/* ===== 操作按钮 ===== */
.nf-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
  flex-wrap: wrap;
}
.btn-home,
.btn-back {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 32px;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  letter-spacing: 1px;
  user-select: none;
}
.btn-home {
  background: linear-gradient(135deg, #0F3460, #1a4a8a);
  color: #ffffff;
  box-shadow: 0 4px 16px rgba(15, 52, 96, 0.3);
}
.btn-home:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(15, 52, 96, 0.4);
}
.btn-back {
  background: #ffffff;
  color: #0F3460;
  border: 1.5px solid rgba(15, 52, 96, 0.15);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.btn-back:hover {
  background: #F5F7FA;
  border-color: #0F3460;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.btn-home:active,
.btn-back:active {
  transform: scale(0.96);
}
.btn-icon {
  font-size: 18px;
}

/* ===== 快捷导航 ===== */
.nf-links {
  margin-top: 40px;
  padding: 28px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 16px;
  border: 1px solid rgba(15, 52, 96, 0.06);
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.03);
  backdrop-filter: blur(8px);
}
.links-title {
  font-size: 14px;
  font-weight: 600;
  color: #0F3460;
  margin: 0 0 16px;
  letter-spacing: 2px;
  text-transform: uppercase;
  opacity: 0.7;
}
.links-grid {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}
.link-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: #ffffff;
  border: 1px solid rgba(15, 52, 96, 0.08);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  text-decoration: none;
  user-select: none;
}
.link-card:hover {
  border-color: #C91F37;
  background: #fef5f6;
  transform: translateY(-2px);
  box-shadow: 0 4px 14px rgba(201, 31, 55, 0.1);
}
.link-card-icon {
  font-size: 18px;
}
.link-card-text {
  font-size: 14px;
  font-weight: 500;
  color: #2d3a5c;
}

/* ===== 底部 ===== */
.nf-footer {
  margin-top: 32px;
  font-size: 12px;
  color: #aab2c8;
}
.footer-contact {
  color: #C91F37;
  font-weight: 500;
  cursor: default;
}

/* ===== 动画 ===== */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(40px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@keyframes float-slow {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(20px, -30px) scale(1.02); }
  66% { transform: translate(-15px, 20px) scale(0.98); }
}
@keyframes pulse-soft {
  0%, 100% { opacity: 0.04; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 0.1; transform: translate(-50%, -50%) scale(1.15); }
}
@keyframes shield-glow {
  0%, 100% { filter: drop-shadow(0 4px 16px rgba(201, 31, 55, 0.3)); }
  50% { filter: drop-shadow(0 6px 28px rgba(201, 31, 55, 0.5)); }
}
@keyframes star-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.15); opacity: 0.8; }
}
@keyframes digit-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

/* ===== 响应式 ===== */
@media (max-width: 600px) {
  .digit {
    font-size: 80px;
  }
  .nf-code {
    gap: 10px;
  }
  .nf-shield {
    width: 60px;
    height: 72px;
  }
  .shield-star {
    font-size: 24px;
  }
  .nf-title {
    font-size: 22px;
  }
  .nf-subtitle {
    font-size: 13px;
  }
  .btn-home,
  .btn-back {
    padding: 10px 24px;
    font-size: 13px;
  }
  .links-grid {
    flex-direction: column;
  }
  .link-card {
    justify-content: center;
  }
  .decor-1 {
    width: 300px;
    height: 300px;
  }
  .decor-2 {
    width: 200px;
    height: 200px;
  }
}
</style>
