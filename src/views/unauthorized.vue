<template>
  <div class="page-container">
    <div class="card">
      <div class="lock-icon">🔒</div>
      <h1>401 - 未授权</h1>
      <p class="desc">您没有权限访问该页面，请先登录或联系管理员。</p>
      <div class="actions">
        <button class="btn-primary" @click="goHome">返回首页</button>
        <button class="btn-outline" @click="goLogin">去登录</button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue'
export default defineComponent({
  name: 'Unauthorized',
  methods: {
    goHome() {
      this.$router.push('/')
    },
    goLogin() {
      this.$router.push('/login')
    }
  }
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
}
.card {
  text-align: center;
  background: #fff;
  border-radius: 20px;
  padding: 60px 80px;
  box-shadow: 0 8px 40px rgba(26, 43, 95, 0.08);
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
}
.actions {
  display: flex;
  gap: 12px;
  justify-content: center;
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
</style>
