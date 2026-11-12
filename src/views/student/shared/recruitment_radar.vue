<template>
  <div class="radar-page ds-page">
    <header class="radar-head">
      <div>
        <span class="ds-eyebrow">招考决策 · 资格预筛</span>
        <h1>警考雷达</h1>
        <p>按你的资格卡筛选职位，先看匹配原因，再看公告原文。</p>
      </div>
      <button class="profile-btn" type="button" @click="profileOpen = true">
        资格卡 {{ eligibility.completed ? '已完善' : '待完善' }}
      </button>
    </header>

    <section class="filters ds-card">
      <select v-model="filters.province" @change="load">
        <option value="">全部地区</option>
        <option v-for="p in provinces" :key="p" :value="p">{{ p }}</option>
      </select>
      <select v-model="filters.education" @change="load">
        <option value="">全部学历</option>
        <option value="大专">大专</option>
        <option value="本科">本科</option>
        <option value="硕士">硕士</option>
        <option value="博士">博士</option>
      </select>
      <input
        v-model="filters.major"
        placeholder="专业关键词"
        @keyup.enter="load" />
      <select v-model="filters.political" @change="load">
        <option value="">政治面貌不限</option>
        <option value="党员">党员</option>
        <option value="团员">团员</option>
      </select>
      <select v-model="filters.match_level" @change="load">
        <option value="">全部匹配</option>
        <option value="green">完美匹配</option>
        <option value="yellow">风险提示</option>
        <option value="red">不可报考</option>
      </select>
      <button type="button" class="search-btn" @click="load">筛选</button>
    </section>

    <div class="result-head">
      <span>共 {{ total }} 个职位</span>
      <span v-if="!eligibility.completed" class="profile-warning">
        资格卡未完善，当前结果仅作参考
      </span>
    </div>

    <div v-if="error" class="state error">{{ error }}</div>
    <div v-else-if="loading" class="state">雷达扫描中...</div>
    <div v-else-if="!items.length" class="state">暂无匹配职位</div>

    <div v-else class="job-grid">
      <article
        v-for="item in items"
        :key="item.post_id"
        class="job-card ds-card">
        <div class="job-card__head">
          <span :class="['match-badge', item.match.level]">
            {{ matchLabel(item.match.level) }}
          </span>
          <button type="button" class="compare-btn" @click="addCompare(item)">
            + 对比
          </button>
        </div>
        <p class="job-employer">{{ item.employer }}</p>
        <h2>{{ item.job_name }}</h2>
        <p class="job-org">
          {{ item.province }}{{ item.city }} · 招录
          {{ item.plan_count || '未写明' }} 人
        </p>
        <div class="job-tags">
          <span>学历：{{ item.education_req || '未写明' }}</span>
          <span>专业：{{ item.major_req || '未写明' }}</span>
          <span>政治面貌：{{ item.political_req || '未写明' }}</span>
          <span>应届：{{ item.fresh_grad_req || '未写明' }}</span>
        </div>
        <p v-if="item.registration_end" class="deadline">
          报名截止：{{ item.registration_end }}
        </p>
        <div class="job-card__actions">
          <button type="button" @click="openDetail(item)">查看详情</button>
          <button
            type="button"
            class="match-action"
            @click="openProfileForMatch">
            一键匹配我的资格
          </button>
          <a
            v-if="item.official_url"
            :href="item.official_url"
            target="_blank"
            rel="noopener">
            公告原文
          </a>
        </div>
      </article>
    </div>

    <div v-if="total > pageSize" class="pager">
      <button type="button" :disabled="page <= 1" @click="changePage(-1)">
        上一页
      </button>
      <span>{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button
        type="button"
        :disabled="page >= Math.ceil(total / pageSize)"
        @click="changePage(1)">
        下一页
      </button>
    </div>

    <div v-if="compared.length" class="compare-bar">
      <span>对比篮 {{ compared.length }}/3</span>
      <span v-for="item in compared" :key="item.post_id" class="compare-item">
        {{ item.job_name }}
        <button type="button" @click="removeCompare(item.post_id)">×</button>
      </span>
      <button type="button" @click="compareOpen = true">查看对比</button>
    </div>

    <div
      v-if="profileOpen"
      class="drawer-mask"
      @click.self="profileOpen = false">
      <aside class="drawer">
        <h2>我的资格卡</h2>
        <label
          >学历
          <select v-model="form.degree">
            <option value="">请选择</option>
            <option>大专</option>
            <option>本科</option>
            <option>硕士</option>
            <option>博士</option>
          </select>
        </label>
        <label>专业名称 <input v-model="form.major_name" /></label>
        <label>专业大类 <input v-model="form.major_category" /></label>
        <label
          >是否应届
          <select v-model.number="form.fresh_grad">
            <option :value="null">请选择</option>
            <option :value="1">是</option>
            <option :value="0">否</option>
          </select>
        </label>
        <label
          >年龄
          <input v-model.number="form.age" type="number" min="16" max="60"
        /></label>
        <label
          >政治面貌
          <select v-model="form.political_status">
            <option value="">请选择</option>
            <option>群众</option>
            <option>团员</option>
            <option>党员</option>
            <option>预备党员</option>
          </select>
        </label>
        <label
          >性别
          <select v-model="form.gender">
            <option value="">请选择</option>
            <option>男</option>
            <option>女</option>
          </select>
        </label>
        <label
          >基层年限
          <input v-model.number="form.grassroots_years" type="number" min="0"
        /></label>
        <label
          >体能自评
          <select v-model.number="form.physical_ok">
            <option :value="null">未自评</option>
            <option :value="1">通过</option>
            <option :value="0">未通过</option>
          </select>
        </label>
        <div class="drawer-actions">
          <button type="button" @click="profileOpen = false">取消</button>
          <button type="button" class="primary" @click="saveProfile">
            保存并刷新
          </button>
        </div>
      </aside>
    </div>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <section class="detail-modal">
        <button class="modal-close" type="button" @click="detail = null">
          ×
        </button>
        <h2>{{ detail.job_name }}</h2>
        <p class="job-org">
          {{ detail.employer }} · {{ detail.province }}{{ detail.city }}
        </p>
        <span :class="['match-badge', detail.match.level]">
          {{ matchLabel(detail.match.level) }}
        </span>
        <ul class="reason-list">
          <li
            v-for="reason in detail.match.reasons"
            :key="reason.field"
            :class="reason.result">
            {{ reason.message }}
          </li>
        </ul>
        <p class="disclaimer">{{ detail.match.disclaimer }}</p>

        <h3>关键时间轴</h3>
        <div class="timeline">
          <div
            v-for="node in timeline"
            :key="node.node_type + node.title"
            class="timeline-node">
            <span>{{ node.title }}</span>
            <strong>{{ node.start_at || node.end_at || node.date }}</strong>
          </div>
          <p v-if="!timeline.length" class="muted">
            暂无结构化时间节点，请查看公告原文。
          </p>
        </div>

        <h3>报名材料待办</h3>
        <label v-for="task in tasks" :key="task.task_id" class="task-row">
          <input
            type="checkbox"
            :checked="task.status === 1"
            @change="toggleTask(task)" />
          <span>{{ task.title }}</span>
        </label>

        <h3>历年考情</h3>
        <div v-if="history.length" class="history-list">
          <span v-for="h in history" :key="h.year">
            {{ h.year }}：最低 {{ h.min_score ?? '暂无' }} / 报录比
            {{ h.ratio || '暂无' }}
          </span>
        </div>
        <p v-else class="muted">暂无历年数据，以官方公布为准。</p>

        <div class="modal-actions">
          <button type="button" @click="remind(detail)">截止提醒</button>
          <a
            v-if="detail.official_url"
            :href="detail.official_url"
            target="_blank"
            rel="noopener">
            查看公告原文
          </a>
        </div>
      </section>
    </div>

    <div
      v-if="compareOpen"
      class="modal-mask"
      @click.self="compareOpen = false">
      <section class="compare-modal">
        <button class="modal-close" type="button" @click="compareOpen = false">
          ×
        </button>
        <h2>岗位对比</h2>
        <table>
          <thead>
            <tr>
              <th>项目</th>
              <th v-for="item in compared" :key="item.post_id">
                {{ item.job_name }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>招录人数</td>
              <td v-for="item in compared" :key="item.post_id">
                {{ item.plan_count }}
              </td>
            </tr>
            <tr>
              <td>学历</td>
              <td v-for="item in compared" :key="item.post_id">
                {{ item.education_req || '不限' }}
              </td>
            </tr>
            <tr>
              <td>专业</td>
              <td v-for="item in compared" :key="item.post_id">
                {{ item.major_req || '不限' }}
              </td>
            </tr>
            <tr>
              <td>政治面貌</td>
              <td v-for="item in compared" :key="item.post_id">
                {{ item.political_req || '不限' }}
              </td>
            </tr>
            <tr>
              <td>报名截止</td>
              <td v-for="item in compared" :key="item.post_id">
                {{ item.registration_end || '暂无' }}
              </td>
            </tr>
            <tr>
              <td>匹配</td>
              <td v-for="item in compared" :key="item.post_id">
                {{ matchLabel(item.match.level) }}
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { apiClient } from '@/services/api/client';

interface MatchReason {
  field: string;
  result: string;
  message: string;
}
interface JobItem {
  post_id: number;
  job_name: string;
  employer: string;
  province: string;
  city: string;
  education_req: string;
  major_req: string;
  political_req: string;
  fresh_grad_req: string;
  registration_end: string;
  official_url: string;
  plan_count: number;
  match: {
    level: string;
    score: number;
    reasons: MatchReason[];
    disclaimer: string;
  };
}

const items = ref<JobItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);
const error = ref('');
const profileOpen = ref(false);
const detail = ref<JobItem | null>(null);
const timeline = ref<any[]>([]);
const tasks = ref<any[]>([]);
const history = ref<any[]>([]);
const compared = ref<JobItem[]>([]);
const compareOpen = ref(false);
const provinces = [
  '北京',
  '天津',
  '河北',
  '山西',
  '内蒙古',
  '辽宁',
  '吉林',
  '黑龙江',
  '上海',
  '江苏',
  '浙江',
  '安徽',
  '福建',
  '江西',
  '山东',
  '河南',
  '湖北',
  '湖南',
  '广东',
  '广西',
  '海南',
  '重庆',
  '四川',
  '贵州',
  '云南',
  '西藏',
  '陕西',
  '甘肃',
  '青海',
  '宁夏',
  '新疆'
];
const filters = reactive({
  province: '',
  education: '',
  major: '',
  political: '',
  match_level: ''
});
const eligibility = reactive({ completed: false, missing: [] as string[] });
const form = reactive<any>({
  degree: '',
  major_name: '',
  major_category: '',
  graduation_year: null,
  fresh_grad: null,
  age: null,
  political_status: '',
  gender: '',
  grassroots_years: 0,
  physical_ok: null
});

async function request<T>(url: string, config: any = {}) {
  const response = await apiClient.request<T>({ url, baseURL: '', ...config });
  return response.data;
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const data = await request<any>('/api/recruitment/radar', {
      method: 'GET',
      params: { ...filters, page: page.value, page_size: pageSize }
    });
    items.value = data.items || [];
    total.value = data.total || 0;
    Object.assign(eligibility, data.profile || {});
  } catch (e) {
    error.value = e instanceof Error ? e.message : '雷达加载失败';
  } finally {
    loading.value = false;
  }
}

async function loadProfile(): Promise<void> {
  try {
    const data = await request<any>('/api/recruitment/eligibility');
    Object.assign(eligibility, data);
    Object.assign(form, data);
  } catch {
    // 未登录时保持空资格卡
  }
}

async function saveProfile(): Promise<void> {
  try {
    const data = await request<any>('/api/recruitment/eligibility', {
      method: 'PUT',
      data: form
    });
    Object.assign(eligibility, data);
    profileOpen.value = false;
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : '资格卡保存失败';
  }
}

function openProfileForMatch(): void {
  profileOpen.value = true;
}

async function openDetail(item: JobItem): Promise<void> {
  detail.value = item;
  const [t, taskData, h] = await Promise.all([
    request<any>(`/api/recruitment/jobs/${item.post_id}/timeline`),
    request<any>(`/api/recruitment/jobs/${item.post_id}/tasks`).catch(() => ({
      items: []
    })),
    request<any>(`/api/recruitment/jobs/${item.post_id}/history`).catch(() => ({
      items: []
    }))
  ]);
  timeline.value = t.nodes || [];
  tasks.value = taskData.items || [];
  history.value = h.items || [];
}

async function toggleTask(task: any): Promise<void> {
  await request(`/api/recruitment/tasks/${task.task_id}`, { method: 'PATCH' });
  task.status = task.status ? 0 : 1;
}

async function remind(item: JobItem): Promise<void> {
  try {
    await request(`/api/recruitment/jobs/${item.post_id}/remind`, {
      method: 'POST'
    });
    error.value = '';
  } catch (e) {
    error.value = e instanceof Error ? e.message : '提醒设置失败';
  }
}

async function loadCompare(): Promise<void> {
  try {
    const data = await request<any>('/api/recruitment/compare');
    compared.value = data.items || [];
  } catch {
    compared.value = [];
  }
}

async function addCompare(item: JobItem): Promise<void> {
  try {
    await request(`/api/recruitment/compare/${item.post_id}`, {
      method: 'POST'
    });
    await loadCompare();
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加入对比失败';
  }
}

async function removeCompare(postId: number): Promise<void> {
  await request(`/api/recruitment/compare/${postId}`, { method: 'DELETE' });
  await loadCompare();
}

function changePage(delta: number): void {
  page.value = Math.max(1, page.value + delta);
  void load();
}

function matchLabel(level: string): string {
  return level === 'green'
    ? '完美匹配'
    : level === 'red'
      ? '不可报考'
      : '风险提示';
}

onMounted(() => {
  void loadProfile();
  void load();
  void loadCompare();
});
</script>

<style scoped>
.radar-page {
  max-width: 1180px;
}
.radar-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.radar-head h1 {
  margin: 4px 0;
  color: var(--ds-navy-deep);
  font-size: 30px;
}
.radar-head p {
  margin: 0;
  color: var(--ds-muted);
  font-size: 13px;
}
.profile-btn {
  padding: 8px 13px;
  border: 1px solid var(--ds-border);
  border-radius: 9px;
  background: #fff;
  color: var(--ds-ink);
  cursor: pointer;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  margin-bottom: 14px;
}
.filters select,
.filters input {
  flex: 1 1 130px;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--ds-border);
  border-radius: 8px;
  background: #fff;
}
.filters .search-btn {
  flex: 0 0 auto;
  padding: 0 16px;
  border: 0;
  border-radius: 8px;
  background: var(--ds-ink);
  color: #fff;
  cursor: pointer;
}
.result-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  color: var(--ds-muted);
  font-size: 12px;
}
.profile-warning {
  color: #a36a28;
}
.job-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.job-card {
  padding: 18px;
}
.job-card__head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.match-badge {
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11px;
}
.match-badge.green {
  background: #e8f4ec;
  color: #2f6b4b;
}
.match-badge.yellow {
  background: #fff4df;
  color: #946b22;
}
.match-badge.red {
  background: #fff0ee;
  color: #a33b2d;
}
.compare-btn {
  border: 0;
  background: transparent;
  color: var(--ds-ink);
  font-size: 12px;
  cursor: pointer;
}
.job-card h2 {
  margin: 10px 0 5px;
  color: var(--ds-navy-deep);
  font-size: 17px;
  line-height: 1.45;
}
.job-employer {
  margin: 9px 0 0;
  color: #7b8794;
  font-size: 12px;
}
.job-org {
  margin: 0;
  color: var(--ds-muted);
  font-size: 12px;
}
.job-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 10px;
}
.job-tags span {
  padding: 3px 7px;
  border-radius: 999px;
  background: #f0f4f8;
  color: #53657a;
  font-size: 11px;
}
.deadline {
  margin: 9px 0 0;
  color: #a36a28;
  font-size: 12px;
}
.job-card__actions {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-top: 13px;
}
.job-card__actions button,
.job-card__actions a {
  border: 0;
  background: transparent;
  color: var(--ds-ink);
  font-size: 12px;
  cursor: pointer;
  text-decoration: none;
}
.job-card__actions .match-action {
  padding: 5px 9px;
  border-radius: 7px;
  background: var(--ds-ink);
  color: #fff;
}
.pager {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 18px;
  color: var(--ds-muted);
  font-size: 12px;
}
.pager button {
  border: 1px solid var(--ds-border);
  border-radius: 7px;
  background: #fff;
  padding: 5px 9px;
  cursor: pointer;
}
.compare-bar {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  align-items: center;
  max-width: 760px;
  padding: 10px 14px;
  border-radius: 12px;
  background: #163a5f;
  color: #fff;
  box-shadow: 0 8px 26px rgba(16, 42, 71, 0.25);
  font-size: 12px;
}
.compare-item {
  padding: 3px 7px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.14);
}
.compare-item button {
  border: 0;
  background: transparent;
  color: #fff;
  cursor: pointer;
}
.compare-bar > button {
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 6px;
  background: transparent;
  color: #fff;
  padding: 4px 8px;
  cursor: pointer;
}
.drawer-mask,
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  justify-content: flex-end;
  background: rgba(16, 42, 71, 0.28);
}
.drawer {
  width: min(390px, 92vw);
  height: 100%;
  padding: 24px;
  overflow: auto;
  background: #fff;
}
.drawer h2 {
  margin-top: 0;
  color: var(--ds-navy-deep);
}
.drawer label {
  display: block;
  margin: 11px 0;
  color: #59635c;
  font-size: 12px;
}
.drawer label input,
.drawer label select {
  display: block;
  box-sizing: border-box;
  width: 100%;
  margin-top: 5px;
  padding: 8px;
  border: 1px solid var(--ds-border);
  border-radius: 7px;
}
.drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
}
.drawer-actions button,
.modal-actions button {
  padding: 7px 12px;
  border: 1px solid var(--ds-border);
  border-radius: 7px;
  background: #fff;
  cursor: pointer;
}
.drawer-actions .primary {
  border-color: var(--ds-ink);
  background: var(--ds-ink);
  color: #fff;
}
.modal-mask {
  justify-content: center;
  align-items: center;
  padding: 20px;
}
.detail-modal,
.compare-modal {
  position: relative;
  width: min(720px, 100%);
  max-height: 90vh;
  overflow: auto;
  padding: 24px;
  border-radius: 16px;
  background: #fff;
}
.modal-close {
  position: absolute;
  top: 10px;
  right: 14px;
  border: 0;
  background: transparent;
  color: #8492a6;
  font-size: 24px;
  cursor: pointer;
}
.detail-modal h2 {
  margin: 0 0 5px;
  color: var(--ds-navy-deep);
}
.detail-modal h3 {
  margin: 20px 0 8px;
  color: #34413a;
  font-size: 14px;
}
.reason-list {
  padding-left: 18px;
  color: #59635c;
  font-size: 13px;
  line-height: 1.8;
}
.reason-list .fail {
  color: #a33b2d;
}
.reason-list .risk {
  color: #946b22;
}
.disclaimer {
  color: #9aa3ad;
  font-size: 11px;
}
.timeline {
  display: grid;
  gap: 7px;
}
.timeline-node {
  display: flex;
  justify-content: space-between;
  padding: 7px 9px;
  border-left: 3px solid var(--ds-ink);
  background: #f7faf8;
  font-size: 12px;
}
.task-row {
  display: flex;
  gap: 7px;
  align-items: center;
  padding: 5px 0;
  color: #59635c;
  font-size: 13px;
}
.history-list {
  display: grid;
  gap: 5px;
  color: #59635c;
  font-size: 12px;
}
.muted {
  color: #9aa3ad;
  font-size: 12px;
}
.modal-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}
.compare-modal table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.compare-modal th,
.compare-modal td {
  padding: 8px;
  border-bottom: 1px solid var(--ds-border);
  text-align: left;
}
.state {
  padding: 50px;
  text-align: center;
  color: var(--ds-muted);
}
.state.error {
  color: #a33b2d;
}
@media (max-width: 760px) {
  .radar-head {
    display: block;
  }
  .profile-btn {
    margin-top: 12px;
  }
  .job-grid {
    grid-template-columns: 1fr;
  }
  .compare-bar {
    bottom: 8px;
    width: calc(100% - 24px);
  }
}
</style>
