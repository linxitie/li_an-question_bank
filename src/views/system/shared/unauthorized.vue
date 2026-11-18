<template>
  <div class="page-container">
    <div class="card">
      <div class="lock-icon">{{ lockIcon }}</div>
      <h1>{{ title }}</h1>
      <p class="desc">{{ description }}</p>
      <div class="actions">
        <button class="btn-primary" @click="primaryAction">{{ primaryText }}</button>
        <button class="btn-outline" @click="goHome">返回首页</button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
/**
 * 未授权页（三端登录方案 P2 扩展，2026-11-16）
 *
 * 三种 reason：
 *   · admin_pc_only      —— 管理员在平板/手机端（需求：管理员必须电脑）→ 主按钮「去电脑端登录」
 *   · mobile_student_only —— 历史 reason（旧守卫用），保留兼容，避免旧书签/旧代码链接失配
 *   · 无                  —— 通用 401
 *
 * 为什么"去电脑端登录"用整页跳转：设备端访问 /login 会被守卫映射回 /tablet/login，
 * 只有整页跳到 `/#/login` 才真正落到电脑端登录页（电脑上打开即正常）。
 */
import { defineComponent } from 'vue'

const PC_LOGIN_PATH = '/#/login'

export default defineComponent({
  name: 'Unauthorized',
  computed: {
    reason(): string {
      const q = this.$route.query.reason
      return Array.isArray(q) ? String(q[0] || '') : String(q || '')
    },
    isAdminPcOnly(): boolean {
      return this.reason === 'admin_pc_only'
    },
    isMobileRestrict(): boolean {
      return this.reason === 'mobile_student_only'
    },
    lockIcon(): string {
      return this.isAdminPcOnly ? '💻' : '🔒'
    },
    title(): string {
      if (this.isAdminPcOnly) return '管理员仅支持电脑端'
      if (this.isMobileRestrict) return '仅限学生使用'
      return '401 - 未授权'
    },
    description(): string {
      if (this.isAdminPcOnly) {
        return `当前是平板/手机端。管理员请在电脑上访问 ${PC_LOGIN_PATH} 登录；本页不会保留登录状态。`
      }
      if (this.isMobileRestrict) {
        return '移动端/平板端仅支持学生登录，教师/管理员请使用电脑端访问。'
      }
      return '您没有权限访问该页面，请先登录或联系管理员。'
    },
    primaryText(): string {
      return this.isAdminPcOnly ? '去电脑端登录' : '去登录'
    },
  },
  methods: {
    primaryAction() {
      if (this.isAdminPcOnly) {
        window.location.href = `${window.location.origin}${PC_LOGIN_PATH}`
        return
      }
      this.goLogin()
    },
    goHome() {
      this.$router.push('/')
    },
    goLogin() {
      this.$router.push('/login')
    },
  },
})
</script>

<style scoped>
.page-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  padding: 20px;
}
.card {
  text-align: center;
  background: #fff;
  border-radius: 20px;
  padding: 60px 80px;
  box-shadow: 0 8px 40px rgba(26, 43, 95, 0.08);
  max-width: 560px;
}
.lock-icon {
  font-size: 64px;
  margin-bottom: 16px;
}
h1 {
  font-size: 32px;
  color: #1a2b5f;
  margin: 0 0 12px;
}
.desc {
  color: #5a6488;
  font-size: 15px;
  margin: 0 0 32px;
  line-height: 1.8;
  word-break: break-all;
}
.actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}
.btn-primary {
  padding: 10px 28px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #1a2b5f, #1e3470);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}
.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 18px rgba(26, 43, 95, 0.3);
}
.btn-outline {
  padding: 10px 28px;
  border: 1px solid #e8eaf0;
  border-radius: 10px;
  background: #fff;
  color: #1a2b5f;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}
.btn-outline:hover {
  border-color: #c41e3a;
}
@media (max-width: 640px) {
  .card {
    padding: 36px 22px;
  }
  h1 {
    font-size: 24px;
  }
}
</style>
