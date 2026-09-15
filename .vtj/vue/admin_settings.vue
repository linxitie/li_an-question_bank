<template>
  <div class="admin-content">
    <div v-if="loading" class="skeleton-wrap"><div class="sk-bar"></div><div class="sk-table"></div></div>
    <div v-else>
      <div class="action-bar"><h2 class="page-title">⚙️ 系统设置</h2>
        <div class="action-buttons">
          <button class="btn-secondary" @click="resetSettings">🔄 重置默认</button>
          <button class="btn-primary" @click="save">💾 保存设置</button>
        </div>
      </div>
      
      <div class="settings-tabs">
        <button v-for="tab in tabs" :key="tab.key" :class="['tab-btn', {active: activeTab===tab.key}]" @click="activeTab=tab.key">{{ tab.icon }} {{ tab.label }}</button>
      </div>
      
      <div class="settings-panel" v-if="activeTab==='basic'">
        <div class="panel"><h3>基本设置</h3>
          <div class="fg"><label>站点名称</label><input class="fi" v-model="settings.site_name" placeholder="请输入站点名称"/></div>
          <div class="fg"><label>站点标识</label><div class="logo-upload"><div class="logo-preview" v-if="settings.site_logo">📝</div><button class="btn-secondary">上传标识</button></div></div>
          <div class="fg"><label>站点简介</label><textarea class="fi textarea" v-model="settings.site_desc" placeholder="请输入站点简介"></textarea></div>
          <div class="fg"><label>备案号</label><input class="fi" v-model="settings.icp_number" placeholder="请输入ICP备案号"/></div>
        </div>
      </div>
      
      <div class="settings-panel" v-if="activeTab==='security'">
        <div class="panel"><h3>安全设置</h3>
          <div class="fg"><label>最大登录尝试</label><input class="fi" type="number" v-model="settings.max_login_attempts"/></div>
          <div class="fg"><label>密码最小长度</label><input class="fi" type="number" v-model="settings.password_min_length"/></div>
          <div class="fg"><label>开放注册</label><select class="fi" v-model="settings.register_open"><option value="true">是</option><option value="false">否</option></select></div>
          <div class="fg"><label>验证码</label><select class="fi" v-model="settings.captcha_enabled"><option value="true">启用</option><option value="false">关闭</option></select></div>
        </div>
      </div>
      
      <div class="settings-panel" v-if="activeTab==='exam'">
        <div class="panel"><h3>考试设置</h3>
          <div class="fg"><label>自动提交时间(分钟)</label><input class="fi" type="number" v-model="settings.exam_auto_submit_minutes"/></div>
          <div class="fg"><label>考试时间限制(分钟)</label><input class="fi" type="number" v-model="settings.exam_time_limit"/></div>
        </div>
      </div>
      
      <div class="settings-panel" v-if="activeTab==='notify'">
        <div class="panel"><h3>通知设置</h3>
          <div class="fg"><label>邮件通知</label><select class="fi" v-model="settings.email_notify"><option value="true">开启</option><option value="false">关闭</option></select></div>
          <div class="fg"><label>公告弹窗</label><select class="fi" v-model="settings.announcement_popup"><option value="true">开启</option><option value="false">关闭</option></select></div>
        </div>
      </div>
      
      <div class="msg" v-if="msg">{{ msg }}</div>
    </div>
  </div>
</template>
<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, reactive, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'AdminSettings', setup() {
    const provider = useProvider({ id: 'admin_settings', version: '1' });
    const loading = ref(true);
    const activeTab = ref('basic');
    const tabs = [
      { key: 'basic', label: '基本设置', icon: '🏠' },
      { key: 'security', label: '安全设置', icon: '🔒' },
      { key: 'exam', label: '考试设置', icon: '📝' },
      { key: 'notify', label: '通知设置', icon: '🔔' },
    ];
    const settings = reactive({ site_name: '', max_login_attempts: '5', register_open: 'true', exam_auto_submit_minutes: '120', password_min_length: '6', site_logo: '', site_desc: '', icp_number: '', captcha_enabled: 'false', exam_time_limit: '120', email_notify: 'true', announcement_popup: 'true' });
    const msg = ref('');
    const auth = () => (window as any).__VTJ_AUTH__;
    onMounted(async () => {
      try {
        const r = await auth().apiFetch('/api/admin/settings');
        const d = await r.json();
        if (d.success && d.settings) { Object.keys(settings).forEach(k => { if (d.settings[k]) settings[k as keyof typeof settings] = d.settings[k].value; }); }
      } catch(e) { console.error('加载设置失败:', e); }
      loading.value = false;
    });
    async function save() {
      const s: any = {}; Object.keys(settings).forEach(k => { s[k] = (settings as any)[k]; });
      await auth().apiFetch('/api/admin/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ settings: s }) });
      msg.value = '✅ 设置已保存'; setTimeout(() => msg.value = '', 3000);
    }
    function resetSettings() { if (confirm('确定重置为默认设置？')) { msg.value = '设置已重置'; } }
    return { provider, loading, activeTab, tabs, settings, msg, save, resetSettings };
  }
});
</script>
<style scoped>
.admin-content{padding:20px;max-width:900px}.skeleton-wrap{display:flex;flex-direction:column;gap:20px}.sk-bar,.sk-table{background:linear-gradient(90deg,#f0f0f0 25%,#e0e0e0 50%,#f0f0f0 75%);background-size:200% 100%;animation:sk 1.5s infinite;border-radius:10px}.sk-bar{height:60px}.sk-table{height:400px}@keyframes sk{0%{background-position:200% 0}100%{background-position:-200% 0}}
.action-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.page-title{margin:0;color:#1A3C6D}.action-buttons{display:flex;gap:10px}
.settings-tabs{display:flex;gap:8px;margin-bottom:20px;border-bottom:2px solid #e8e8e8;padding-bottom:12px}.tab-btn{padding:8px 16px;border:1px solid #d9d9d9;border-radius:6px;background:#fff;cursor:pointer;font-size:14px}.tab-btn.active{background:#1A3C6D;color:#fff;border-color:#1A3C6D}
.panel{background:#fff;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,.06)}.panel h3{color:#1A3C6D;margin:0 0 16px}
.fg{margin-bottom:16px}.fg label{display:block;margin-bottom:6px;font-weight:500;color:#333}.fi{width:100%;padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px;font-size:14px;box-sizing:border-box}.fi.textarea{min-height:80px;resize:vertical}
.btn-primary{padding:8px 16px;background:#C41E3A;color:#fff;border:none;border-radius:6px;cursor:pointer}.btn-secondary{padding:8px 16px;background:#fff;color:#333;border:1px solid #d9d9d9;border-radius:6px;cursor:pointer}
.logo-upload{display:flex;align-items:center;gap:12px}.logo-preview{width:48px;height:48px;border:1px solid #d9d9d9;border-radius:8px;display:flex;align-items:center;justify-content:center}
.msg{margin-top:12px;padding:8px 16px;background:#f0f9eb;color:#67C23A;border-radius:6px}
</style>
