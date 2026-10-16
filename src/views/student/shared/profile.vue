<!-- 学生端「我的」个人中心（桌面端） -->
<template>
  <div class="profile-page">
    <NavBar />
    <main class="profile-main">
      <!-- 左栏：个人资料 + 金币 -->
      <aside class="left-col">
        <section class="card profile-card">
          <div class="avatar" @click="openEditProfile">
            <img v-if="user.avatar" :src="user.avatar" class="avatar-img" alt="头像" />
            <XIcon v-else :icon="UserFilled" :size="40" color="#fff" />
          </div>
          <h2 class="name">{{ user.username || '同学' }}</h2>
          <p class="meta">{{ user.user_no || '' }}</p>
          <p class="meta">{{ user.class_name || '公安联考备考学员' }}</p>
          <button class="btn-edit" @click="openEditProfile">编辑资料</button>
        </section>

        <section class="card coin-card">
          <h3 class="card-title"><XIcon :icon="GoldMedal" :size="18" color="#f59e0b" /> 我的金币</h3>
          <div class="coin-balance">{{ coin.balance }} <span>金币</span></div>
          <div class="coin-month">
            <span>本月收入 +{{ coin.month_income }}</span>
            <span>本月支出 -{{ coin.month_expense }}</span>
          </div>
          <div class="coin-actions">
            <button class="btn-mini" @click="go('/page/gold_purchase')">金币购</button>
            <button class="btn-mini" @click="openCoinDetail">明细</button>
          </div>
        </section>
      </aside>

      <!-- 中栏：学习数据 + 学习内容 -->
      <section class="center-col">
        <div class="card">
          <h3 class="card-title"><XIcon :icon="DataLine" :size="18" color="#1A365D" /> 学习数据</h3>
          <div class="stats-grid">
            <div class="stat"><span class="stat-val">{{ stats.totalQuestions }}</span><span class="stat-label">总做题</span></div>
            <div class="stat"><span class="stat-val">{{ stats.accuracyRate }}%</span><span class="stat-label">正确率</span></div>
            <div class="stat"><span class="stat-val">{{ stats.totalStudyHours }}h</span><span class="stat-label">学习时长</span></div>
            <div class="stat"><span class="stat-val">{{ stats.streak }}</span><span class="stat-label">连续天数</span></div>
          </div>

          <!-- 题型掌握度：进度条宽度绑定接口返回的真实正确率，不含任何硬编码百分比。
               数据源 /api/stats/type-mastery（用户维度），与题库库存量统计无关。 -->
          <div class="mastery">
            <div class="mastery-head">
              <span class="mastery-title">题型掌握度</span>
              <span class="mastery-hint" v-if="typeMastery.length">
                共 {{ typeMastery.length }} 个题型
              </span>
            </div>
            <div v-if="!typeMastery.length" class="mastery-empty">
              还没有练习记录，去练几道题后这里会显示各题型的掌握情况
            </div>
            <div v-else class="mastery-list">
              <div v-for="(t, i) in typeMastery" :key="t.typeId ?? i" class="mastery-row">
                <div class="mastery-row-head">
                  <span class="mastery-name">{{ t.typeName }}</span>
                  <span class="mastery-meta">{{ t.count }} 题 · {{ t.accuracy }}%</span>
                </div>
                <div class="mastery-track">
                  <div
                    class="mastery-fill"
                    :style="{
                      width: (Number(t.accuracy) || 0) + '%',
                      background: masteryColor(t.accuracy),
                    }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <h3 class="card-title"><XIcon :icon="Collection" :size="18" color="#1A365D" /> 学习内容管理</h3>
          <div class="content-grid">
            <div class="content-item" @click="go('/page/wrong_questions')"><XIcon :icon="Warning" :size="22" color="#f59e0b" /><span>错题集</span></div>
            <div class="content-item" @click="go('/page/favorites')"><XIcon :icon="Star" :size="22" color="#f59e0b" /><span>收藏</span></div>
            <div class="content-item" @click="go('/page/notes')"><XIcon :icon="Notebook" :size="22" color="#10b981" /><span>笔记</span></div>
            <div class="content-item" @click="go('/achievements')"><XIcon :icon="Trophy" :size="22" color="#8b5cf6" /><span>我的成就</span></div>
          </div>
        </div>

        <!-- 最近做题记录：三端共用同一组件 src/components/RecentPracticeRecords.vue，
             排序与条数完全一致（后端已按 recency 倒序，前端不二次排序）。 -->
        <RecentPracticeRecords :limit="5" />
      </section>

      <!-- 右栏：成就 + 等级 + 设置 -->
      <aside class="right-col">
        <div class="card">
          <h3 class="card-title"><XIcon :icon="Trophy" :size="18" color="#f59e0b" /> 成就与激励</h3>
          <div class="ach-badges" v-if="earnedBadges.length">
            <span
              v-for="b in earnedBadges"
              :key="b.achievement_id"
              class="ach-badge"
              :style="{ borderColor: tierColor(b.tier), color: tierColor(b.tier) }"
              :title="b.name"
            >{{ b.icon }}</span>
          </div>
          <p class="ach-count">已获得 <strong>{{ earnedCount }}</strong> 枚勋章</p>
          <button class="btn-mini full" @click="go('/achievements')">查看全部 →</button>
        </div>

        <div class="card">
          <h3 class="card-title"><XIcon :icon="TrendCharts" :size="18" color="#1A365D" /> 学习等级</h3>
          <p class="level-text">Lv.{{ level.level }} {{ level.title }}</p>
          <div class="progress-bar"><div class="progress-fill" :style="{ width: level.progress + '%' }"></div></div>
          <p class="level-sub">{{ level.growth_points }} 成长值 · 进度 {{ level.progress }}%</p>
        </div>

        <div class="card">
          <h3 class="card-title"><XIcon :icon="Setting" :size="18" color="#1A365D" /> 设置</h3>
          <div class="menu-list">
            <div class="menu-row" @click="openEditProfile">个人设置</div>
            <div class="menu-row" @click="openDevices">设备管理</div>
            <div class="menu-row" @click="go('/feedback')">意见反馈</div>
            <div class="menu-row" @click="go('/help')">帮助中心</div>
            <div class="menu-row" @click="go('/page/about')">关于砺安题库</div>
            <div class="menu-row danger" @click="handleLogout">退出登录</div>
          </div>
        </div>
      </aside>
    </main>

    <!-- 编辑资料弹窗 -->
    <div class="modal-overlay" v-if="showEdit" @click.self="showEdit = false">
      <div class="modal">
        <h3>编辑资料</h3>
        <div class="avatar-edit">
          <div class="avatar-edit-img" @click="triggerAvatarUpload">
            <img v-if="user.avatar" :src="user.avatar" alt="头像" />
            <XIcon v-else :icon="UserFilled" :size="40" color="#fff" />
          </div>
          <span class="avatar-edit-hint">点击更换头像</span>
          <input
            ref="avatarInput"
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            style="display:none"
            @change="handleAvatarChange"
          />
        </div>
        <div class="form-row"><label>手机号</label><input v-model="editForm.phone" /></div>
        <div class="form-row"><label>邮箱</label><input v-model="editForm.email" /></div>
        <div class="form-row"><label>性别</label>
          <select v-model="editForm.gender"><option>男</option><option>女</option><option>未知</option></select>
        </div>
        <div class="form-row"><label>学院/部门</label><input v-model="editForm.department" /></div>
        <div class="form-row"><label>班级</label><input v-model="editForm.class_name" /></div>
        <div class="modal-actions">
          <button class="btn-mini" @click="saveProfile">保存</button>
          <button class="btn-mini ghost" @click="showEdit = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 设备管理弹窗 -->
    <div class="modal-overlay" v-if="showDevices" @click.self="showDevices = false">
      <div class="modal">
        <h3>设备管理</h3>
        <div v-if="devices.length === 0" class="empty">暂无设备记录</div>
        <div v-for="d in devices" :key="d.device_id" class="device-row">
          <span class="device-name">{{ d.os || '未知设备' }} · {{ d.browser || '' }}</span>
          <span v-if="d.is_current" class="tag">当前设备</span>
          <button v-else class="btn-mini ghost" @click="removeDevice(d.device_id)">移除</button>
        </div>
        <button class="btn-mini danger-outline" @click="logoutAll">退出所有设备</button>
      </div>
    </div>

    <!-- 金币明细弹窗 -->
    <div class="modal-overlay" v-if="showCoinDetail" @click.self="showCoinDetail = false">
      <div class="modal wide">
        <h3>金币明细</h3>
        <div v-if="coinRecords.length === 0" class="empty">暂无记录</div>
        <div v-for="r in coinRecords" :key="r.record_id" class="record-row">
          <span class="record-desc">{{ r.description }}</span>
          <span :class="['record-amt', r.transaction_type === 'GAIN' ? 'plus' : 'minus']">{{ r.transaction_type === 'GAIN' ? '+' : '' }}{{ r.coin_change }}</span>
          <span class="record-date">{{ (r.transaction_time || '').slice(0, 10) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import { ElMessage } from 'element-plus';
import {
  UserFilled, DataLine, GoldMedal, Collection, Warning, Star, Notebook,
  Trophy, TrendCharts, Setting,
} from '@vtj/icons';
import NavBar from '$vtj/vue/navbar.vue';
// 最近做题记录：三端共用的单一真源组件，保证排序/条数/空态完全一致
import RecentPracticeRecords from '@/components/domain/RecentPracticeRecords.vue';

const router = useRouter();
const auth: any = (window as any).__VTJ_AUTH__;

const user = ref<any>({});
const stats = ref<any>({});
const coin = ref<any>({ balance: 0, month_income: 0, month_expense: 0 });
const level = ref<any>({ level: 1, title: '新手学员', progress: 0, growth_points: 0 });
const earnedCount = ref(0);
const earnedBadges = ref<any[]>([]);
const devices = ref<any[]>([]);
const coinRecords = ref<any[]>([]);
// 题型掌握度：来自 /api/stats/type-mastery（用户维度按 type_id 聚合），
// 与题库库存量统计是完全不同的东西，不可混用。
const typeMastery = ref<any[]>([]);

/** 掌握度进度条配色：低正确率偏红，高正确率偏绿，参照移动端金色主题 */
function masteryColor(accuracy: number) {
  const a = Number(accuracy) || 0;
  if (a >= 80) return 'linear-gradient(90deg, #10b981, #34d399)';
  if (a >= 60) return 'linear-gradient(90deg, #2a5298, #3b82f6)';
  if (a >= 40) return 'linear-gradient(90deg, #f59e0b, #fbbf24)';
  return 'linear-gradient(90deg, #C91F37, #e8384f)';
}
const avatarInput = ref<HTMLInputElement | null>(null);

const showEdit = ref(false);
const showDevices = ref(false);
const showCoinDetail = ref(false);
const editForm = reactive<any>({});

async function apiGet(url: string) {
  const res = await auth.apiFetch(url);
  return res.json();
}

// 练习/目标统计的加载逻辑抽成独立函数：既供首次挂载用，也供
// __VTJ_SYNC__ 事件触发时重拉，避免两处重复实现。
async function loadStudyData() {
  const [s, c, l, m] = await Promise.all([
    apiGet('/api/stats/'),
    apiGet('/api/coins/overview'),
    apiGet('/api/stats/level'),
    apiGet('/api/stats/type-mastery'),
  ]);
  stats.value = s;
  coin.value = c;
  level.value = l;
  typeMastery.value = Array.isArray(m) ? m : [];
}

onMounted(async () => {
  try {
    const [p, s, c, l, a, m] = await Promise.all([
      apiGet('/api/auth/profile'),
      apiGet('/api/stats/'),
      apiGet('/api/coins/overview'),
      apiGet('/api/stats/level'),
      apiGet('/api/achievements/earned'),
      apiGet('/api/stats/type-mastery'),
    ]);
    user.value = p;
    stats.value = s;
    coin.value = c;
    level.value = l;
    earnedCount.value = a.earned_count || 0;
    earnedBadges.value = (a.items || []).slice(0, 12);
    typeMastery.value = Array.isArray(m) ? m : [];
  } catch (e) {
    console.error('加载个人中心数据失败', e);
  }

  // ===== 三端实时同步 =====
  // 练习落库后后端会定向广播 sync 事件，auth.ts 转发为 __VTJ_SYNC__。
  // 只关心练习范围，避免题目导入等事件触发无谓重拉。
  // 防抖 800ms：连续答题会连发多个事件，合并为一次刷新。
  let syncTimer: any = null;
  const onVTJSync = (e: any) => {
    const d = e && e.detail && e.detail.data;
    if (d && d.scope && d.scope !== 'practice') return;
    if (syncTimer) clearTimeout(syncTimer);
    syncTimer = setTimeout(() => {
      syncTimer = null;
      loadStudyData().catch(() => { /* 静默：同步刷新失败不影响页面 */ });
    }, 800);
  };
  window.addEventListener('__VTJ_SYNC__', onVTJSync);
  onBeforeUnmount(() => {
    window.removeEventListener('__VTJ_SYNC__', onVTJSync);
    if (syncTimer) clearTimeout(syncTimer);
  });
});

const TIER_COLORS: Record<number, string> = {
  1: '#b87333', 2: '#c0c0c0', 3: '#ffd700', 4: '#e5e4e2', 5: '#b9f2ff',
};
function tierColor(tier: number) {
  return TIER_COLORS[tier] || '#b87333';
}

function triggerAvatarUpload() {
  avatarInput.value?.click();
}

async function handleAvatarChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files && input.files[0];
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.warning('头像不能超过 2MB');
    return;
  }
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await auth.apiFetch('/api/auth/avatar', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      ElMessage.error(err.detail || '上传失败');
      return;
    }
    const data = await res.json();
    if (data.success) {
      user.value.avatar = data.avatar_url;
      ElMessage.success('头像上传成功');
    } else {
      ElMessage.error(data.message || '上传失败');
    }
  } catch (err) {
    ElMessage.error('上传失败，请重试');
  } finally {
    input.value = '';
  }
}

function go(path: string) {
  router.push(path);
}

function openEditProfile() {
  editForm.phone = user.value.phone || '';
  editForm.email = user.value.email || '';
  editForm.gender = user.value.gender || '未知';
  editForm.department = user.value.department || '';
  editForm.class_name = user.value.class_name || '';
  showEdit.value = true;
}

async function saveProfile() {
  try {
    const res = await auth.apiFetch('/api/auth/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm),
    });
    const data = await res.json();
    if (data.success) {
      ElMessage.success('保存成功');
      showEdit.value = false;
      Object.assign(user.value, editForm);
    }
  } catch (e) {
    ElMessage.error('保存失败，请重试');
  }
}

async function loadDevices() {
  const data = await apiGet('/api/auth/devices/');
  devices.value = (data.devices || []).map((d: any) => ({
    ...d,
    is_current: !!d.is_current,
  }));
}

function openDevices() {
  showDevices.value = true;
  loadDevices();
}

function openCoinDetail() {
  showCoinDetail.value = true;
  loadCoinRecords();
}

async function removeDevice(deviceId: string) {
  await auth.apiFetch(`/api/auth/devices/${deviceId}`, { method: 'DELETE' });
  ElMessage.success('设备已移除');
  loadDevices();
}

async function logoutAll() {
  await auth.apiFetch('/api/auth/devices/revoke-all', { method: 'POST' });
  ElMessage.success('已退出所有设备');
  showDevices.value = false;
}

async function loadCoinRecords() {
  const data = await apiGet('/api/coins/transactions?page=1&page_size=50');
  coinRecords.value = data.items || [];
}

function handleLogout() {
  auth.logout();
  router.push('/login');
}
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.profile-main {
  max-width: 1300px;
  margin: 0 auto;
  padding: 24px 32px 40px;
  display: grid;
  grid-template-columns: 280px 1fr 320px;
  gap: 20px;
  align-items: start;
}
.left-col, .right-col { display: flex; flex-direction: column; gap: 16px; }
.center-col { display: flex; flex-direction: column; gap: 16px; }

.card {
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 14px rgba(26, 43, 95, 0.05);
}
.card-title { display: flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 700; color: #1a2b5f; margin: 0 0 16px; }

.profile-card { text-align: center; }
.avatar { width: 72px; height: 72px; border-radius: 50%; background: linear-gradient(135deg, #1a2b5f, #2a5298); display: flex; align-items: center; justify-content: center; margin: 0 auto 12px; overflow: hidden; cursor: pointer; }
.avatar-img { width: 100%; height: 100%; object-fit: cover; }
.name { font-size: 20px; font-weight: 800; color: #1a2b5f; margin: 0 0 4px; }
.meta { font-size: 13px; color: #8a8faa; margin: 2px 0; }
.btn-edit { margin-top: 16px; padding: 8px 20px; background: linear-gradient(135deg, #1a2b5f, #1e3470); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; }

.coin-balance { font-size: 30px; font-weight: 900; color: #b45309; font-family: 'DIN Alternate', sans-serif; }
.coin-balance span { font-size: 13px; color: #92400e; }
.coin-month { display: flex; gap: 16px; font-size: 12px; color: #8a8faa; margin: 8px 0 16px; }
.coin-actions { display: flex; gap: 8px; }

.btn-mini { padding: 7px 16px; background: linear-gradient(135deg, #1a2b5f, #1e3470); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 12px; font-weight: 600; }
.btn-mini.full { width: 100%; }
.btn-mini.ghost { background: #f0f2f5; color: #555; }
.btn-mini.danger-outline { background: transparent; color: #c41e3a; border: 1px solid #c41e3a; margin-top: 16px; width: 100%; }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
  .stat { text-align: center; }
  .stat-val { display: block; font-size: 26px; font-weight: 800; color: #1a2b5f; }
  .stat-label { font-size: 12px; color: #8a8faa; }
  /* ===== 题型掌握度 ===== */
  .mastery { margin-top: 18px; padding-top: 16px; border-top: 1px solid #eef1f6; }
  .mastery-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 12px; }
  .mastery-title { font-size: 14px; font-weight: 600; color: #1a2b5f; }
  .mastery-hint { font-size: 12px; color: #8a8faa; }
  .mastery-empty { font-size: 13px; color: #8a8faa; padding: 12px 0; line-height: 1.6; }
  .mastery-list { display: flex; flex-direction: column; gap: 12px; }
  .mastery-row-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 5px; }
  .mastery-name { font-size: 13px; color: #3a4260; }
  .mastery-meta { font-size: 12px; color: #8a8faa; }
  .mastery-track { height: 8px; background: #f0f2f5; border-radius: 4px; overflow: hidden; }
  .mastery-fill { height: 100%; border-radius: 4px; transition: width 0.3s; min-width: 0; }

.content-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.content-item { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 16px 8px; background: #f8f9fc; border-radius: 12px; cursor: pointer; font-size: 13px; color: #1a2b5f; transition: all 0.2s; }
.content-item:hover { background: #f0f2f5; transform: translateY(-2px); }

.ach-count { font-size: 14px; color: #5a6488; }
.ach-count strong { font-size: 22px; color: #f59e0b; }
.ach-badges { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.ach-badge { width: 40px; height: 40px; border-radius: 50%; border: 2px solid #b87333; display: flex; align-items: center; justify-content: center; font-size: 20px; background: #fafafa; }

.level-text { font-size: 18px; font-weight: 800; color: #1a2b5f; margin: 0 0 10px; }
.progress-bar { height: 8px; background: #f0f2f5; border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #1a2b5f, #2a5298); border-radius: 4px; transition: width 0.3s; }
.level-sub { font-size: 12px; color: #8a8faa; margin: 8px 0 0; }

.menu-list { display: flex; flex-direction: column; }
.menu-row { padding: 10px 4px; font-size: 14px; color: #1a2b5f; border-bottom: 1px solid #f0f2f5; cursor: pointer; }
.menu-row:hover { color: #c41e3a; }
.menu-row.danger { color: #c41e3a; border-bottom: none; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 2000; }
.modal { background: #fff; border-radius: 14px; padding: 28px; width: 440px; max-width: 90vw; max-height: 80vh; overflow-y: auto; }
.modal.wide { width: 560px; }
.modal h3 { color: #1a2b5f; margin: 0 0 20px; font-size: 18px; }
.avatar-edit { display: flex; flex-direction: column; align-items: center; margin-bottom: 20px; }
.avatar-edit-img { width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, #1a2b5f, #2a5298); display: flex; align-items: center; justify-content: center; overflow: hidden; cursor: pointer; }
.avatar-edit-img img { width: 100%; height: 100%; object-fit: cover; }
.avatar-edit-hint { font-size: 12px; color: #8a8faa; margin-top: 8px; }
.form-row { display: flex; align-items: center; margin-bottom: 14px; }
.form-row label { width: 90px; font-weight: 600; color: #555; font-size: 14px; }
.form-row input, .form-row select { flex: 1; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 14px; }
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
.empty { text-align: center; color: #8a8faa; padding: 20px; }
.device-row { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid #f0f2f5; }
.device-name { flex: 1; font-size: 14px; color: #1a2b5f; }
.tag { font-size: 11px; color: #10b981; background: #10b98118; padding: 2px 8px; border-radius: 10px; }
.record-row { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #f0f2f5; font-size: 13px; }
.record-desc { flex: 1; color: #333; }
.record-amt { font-weight: 700; }
.record-amt.plus { color: #10b981; }
.record-amt.minus { color: #ef4444; }
.record-date { color: #8a8faa; font-size: 11px; }
</style>
