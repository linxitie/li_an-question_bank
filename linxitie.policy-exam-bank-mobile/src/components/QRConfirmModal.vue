<template>
  <div class="qr-confirm-modal" v-if="visible">
    <div class="modal-overlay" @click="handleCancel"></div>
    <div class="modal-content">
      <div class="modal-header">
        <h3>确认登录</h3>
        <button class="close-btn" @click="handleCancel">×</button>
      </div>
      
      <div class="modal-body">
        <div class="device-info">
          <div class="info-item">
            <span class="label">设备：</span>
            <span class="value">{{ deviceInfo.browser }} / {{ deviceInfo.os }}</span>
          </div>
          <div class="info-item">
            <span class="label">位置：</span>
            <span class="value">{{ deviceInfo.location || '获取中...' }}</span>
          </div>
          <div class="info-item">
            <span class="label">时间：</span>
            <span class="value">{{ loginTime }}</span>
          </div>
        </div>
      </div>
      
      <div class="modal-footer">
        <button class="btn btn-secondary" @click="handleCancel">取消</button>
        <button class="btn btn-primary" @click="handleConfirm" :disabled="confirming">
          {{ confirming ? '确认中...' : '确认登录' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  visible: Boolean,
  qrUuid: String
})

const emit = defineEmits(['confirm', 'cancel'])

const deviceInfo = ref({})
const loginTime = ref('')
const confirming = ref(false)

onMounted(async () => {
  if (props.qrUuid) {
    try {
      const token = localStorage.getItem('token')
      const res = await fetch(`/api/auth/qrcode/${props.qrUuid}/info`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      const data = await res.json()
      deviceInfo.value = data.device
      loginTime.value = new Date(data.login_time).toLocaleString()
    } catch (error) {
      console.error('获取PC端信息失败:', error)
    }
  }
})

const handleConfirm = async () => {
  confirming.value = true
  try {
    const token = localStorage.getItem('token')
    const res = await fetch(`/api/auth/qrcode/${props.qrUuid}/confirm`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({})
    })
    const data = await res.json()
    if (data.success) {
      emit('confirm')
    }
  } catch (error) {
    console.error('确认登录失败:', error)
  } finally {
    confirming.value = false
  }
}

const handleCancel = () => {
  emit('cancel')
}
</script>

<style scoped>
.qr-confirm-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
}

.modal-content {
  position: relative;
  width: 90%;
  max-width: 400px;
  background: white;
  border-radius: 16px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #E5E7EB;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  color: #1F2937;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #9CA3AF;
  cursor: pointer;
}

.modal-body {
  padding: 24px;
}

.info-item {
  display: flex;
  margin-bottom: 16px;
}

.info-item .label {
  color: #6B7280;
  width: 60px;
}

.info-item .value {
  color: #1F2937;
}

.modal-footer {
  display: flex;
  gap: 16px;
  padding: 20px;
  border-top: 1px solid #E5E7EB;
}

.btn {
  flex: 1;
  padding: 16px;
  border-radius: 10px;
  font-size: 16px;
  cursor: pointer;
  border: none;
}

.btn-secondary {
  background: #F5F7FA;
  color: #6B7280;
}

.btn-primary {
  background: #1A365D;
  color: white;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
