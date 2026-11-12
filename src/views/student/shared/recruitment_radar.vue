<template>
  <div class="radar-page ds-page">
    <header class="radar-head">
      <div>
        <span class="ds-eyebrow">招考信息 · 岗位表</span>
        <h1>警考雷达</h1>
        <p>岗位表与招考公告一一对应，查看学历、专业、人数和报名时间。</p>
      </div>
      <router-link class="home-link" to="/">← 返回首页</router-link>
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
      <button type="button" class="search-btn" @click="load">筛选</button>
    </section>

    <div class="result-head">
      <span>共 {{ total }} 个岗位 / {{ announcementCount }} 条公告</span>
      <span class="hint">岗位条件来自公告解析，最终以招录单位审核为准</span>
    </div>

    <div v-if="error" class="state error">{{ error }}</div>
    <div v-else-if="loading" class="state">正在加载岗位表...</div>
    <div v-else-if="!items.length" class="state">暂无可展示岗位</div>

    <div v-else class="table-wrap ds-card">
      <table class="job-table">
        <thead>
          <tr>
            <th>公告</th>
            <th>招录单位</th>
            <th>岗位</th>
            <th>地区</th>
            <th>学历</th>
            <th>专业</th>
            <th>政治面貌</th>
            <th>招录人数</th>
            <th>报名截止</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.post_id">
            <td class="announcement-cell">
              <strong>{{ item.announcement_title || '未关联公告' }}</strong>
              <small>
                {{ item.announcement_source || '来源未写明' }}
                <template v-if="item.announcement_publish_date">
                  · {{ item.announcement_publish_date }}
                </template>
              </small>
            </td>
            <td>{{ item.employer || '未写明' }}</td>
            <td class="job-name">{{ item.job_name }}</td>
            <td>{{ item.province }}{{ item.city }}</td>
            <td>{{ item.education_req || '未写明' }}</td>
            <td>{{ item.major_req || '未写明' }}</td>
            <td>{{ item.political_req || '未写明' }}</td>
            <td>{{ item.plan_count || '未写明' }}</td>
            <td>{{ item.registration_end || '未写明' }}</td>
            <td>
              <button
                type="button"
                class="detail-btn"
                @click="openDetail(item)">
                查看详情
              </button>
            </td>
          </tr>
        </tbody>
      </table>
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

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <section class="detail-modal">
        <button class="modal-close" type="button" @click="detail = null">
          ×
        </button>
        <span class="ds-eyebrow">岗位详情</span>
        <h2>{{ detail.job_name }}</h2>
        <p class="job-org">
          {{ detail.employer }} · {{ detail.province }}{{ detail.city }}
        </p>

        <div class="fact-grid">
          <div>
            <span>学历要求</span
            ><strong>{{ detail.education_req || '未写明' }}</strong>
          </div>
          <div>
            <span>专业要求</span
            ><strong>{{ detail.major_req || '未写明' }}</strong>
          </div>
          <div>
            <span>政治面貌</span
            ><strong>{{ detail.political_req || '未写明' }}</strong>
          </div>
          <div>
            <span>应届要求</span
            ><strong>{{ detail.fresh_grad_req || '未写明' }}</strong>
          </div>
          <div>
            <span>招录人数</span
            ><strong>{{ detail.plan_count || '未写明' }}</strong>
          </div>
          <div>
            <span>报名截止</span
            ><strong>{{ detail.registration_end || '未写明' }}</strong>
          </div>
        </div>

        <h3>对应招考公告</h3>
        <p class="announcement-text">
          {{ detail.announcement_title || '未关联公告' }}
        </p>
        <a
          v-if="detail.official_url"
          class="official-link"
          :href="detail.official_url"
          target="_blank"
          rel="noopener">
          查看公告原文
        </a>
        <span v-else class="source-unavailable">原文链接暂不可用</span>

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
        <p v-if="!tasks.length" class="muted">暂无待办，请按公告准备材料。</p>

        <h3>历年考情</h3>
        <div v-if="history.length" class="history-list">
          <span v-for="h in history" :key="h.year">
            {{ h.year }}：最低 {{ h.min_score ?? '暂无' }} / 报录比
            {{ h.ratio || '暂无' }}
          </span>
        </div>
        <p v-else class="muted">暂无历年数据，以官方公布为准。</p>

        <h3>报名提醒</h3>
        <div class="reminder-row">
          <input
            v-model="reminderAt"
            class="reminder-input"
            type="datetime-local"
            title="选择提醒时间" />
          <button type="button" @click="remind(detail)">设置提醒</button>
        </div>
        <p v-if="reminderMessage" class="reminder-message">
          {{ reminderMessage }}
        </p>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { apiClient } from '@/services/api/client';

interface JobItem {
  post_id: number;
  recruitment_id: number | null;
  announcement_title: string;
  announcement_url: string;
  announcement_source: string;
  announcement_publish_date: string;
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
}

const items = ref<JobItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);
const error = ref('');
const detail = ref<JobItem | null>(null);
const timeline = ref<any[]>([]);
const tasks = ref<any[]>([]);
const history = ref<any[]>([]);
const reminderAt = ref('');
const reminderMessage = ref('');
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
  political: ''
});

const announcementCount = computed(
  () =>
    new Set(items.value.map((item) => item.recruitment_id).filter(Boolean)).size
);

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
  } catch (e) {
    error.value = e instanceof Error ? e.message : '岗位表加载失败';
  } finally {
    loading.value = false;
  }
}

function toLocalInput(value: string): string {
  const match = String(value || '').match(
    /(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})/
  );
  if (!match) return '';
  return `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}T09:00`;
}

async function openDetail(item: JobItem): Promise<void> {
  detail.value = item;
  reminderMessage.value = '';
  reminderAt.value = toLocalInput(item.registration_end);
  const [t, taskData, h, reminder] = await Promise.all([
    request<any>(`/api/recruitment/jobs/${item.post_id}/timeline`),
    request<any>(`/api/recruitment/jobs/${item.post_id}/tasks`).catch(() => ({
      items: []
    })),
    request<any>(`/api/recruitment/jobs/${item.post_id}/history`).catch(() => ({
      items: []
    })),
    request<any>(
      `/api/recruitment/jobs/${item.post_id}/reminder-suggestion`
    ).catch(() => null)
  ]);
  timeline.value = t.nodes || [];
  tasks.value = taskData.items || [];
  history.value = h.items || [];
  if (reminder?.suggested_at) {
    reminderAt.value = toLocalInput(reminder.suggested_at);
    reminderMessage.value = reminder.message || '';
  } else {
    reminderAt.value = '';
    reminderMessage.value =
      reminder?.message || '公告未写明确报名截止时间，请手动选择提醒日期';
  }
}

async function toggleTask(task: any): Promise<void> {
  try {
    await request(`/api/recruitment/tasks/${task.task_id}`, {
      method: 'PATCH'
    });
    task.status = task.status ? 0 : 1;
  } catch (e) {
    reminderMessage.value = e instanceof Error ? e.message : '待办更新失败';
  }
}

async function remind(item: JobItem): Promise<void> {
  if (!reminderAt.value) {
    reminderMessage.value = '请选择提醒日期和时间';
    return;
  }
  try {
    const data = await request<any>(
      `/api/recruitment/jobs/${item.post_id}/remind`,
      {
        method: 'POST',
        data: { remind_at: reminderAt.value }
      }
    );
    reminderMessage.value = `提醒已设置：${data.remind_at || reminderAt.value}`;
  } catch (e) {
    reminderMessage.value = e instanceof Error ? e.message : '提醒设置失败';
  }
}

function changePage(delta: number): void {
  page.value = Math.max(1, page.value + delta);
  void load();
}

onMounted(() => {
  void load();
});
</script>

<style scoped>
.radar-page {
  max-width: 1280px;
  margin: 0 auto;
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
.home-link {
  padding: 8px 10px;
  color: var(--ds-ink);
  font-size: 12px;
  text-decoration: none;
  white-space: nowrap;
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
.hint {
  color: #9aa3ad;
}
.table-wrap {
  padding: 0;
  overflow-x: auto;
}
.job-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.job-table th {
  padding: 11px 10px;
  border-bottom: 1px solid var(--ds-border);
  background: #f7faf8;
  color: #59635c;
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
}
.job-table td {
  padding: 12px 10px;
  border-bottom: 1px solid #edf1ee;
  color: #3c4a42;
  vertical-align: top;
}
.job-table tr:last-child td {
  border-bottom: 0;
}
.announcement-cell strong {
  display: block;
  color: var(--ds-navy-deep);
  line-height: 1.5;
}
.announcement-cell small {
  display: block;
  margin-top: 4px;
  color: #9aa3ad;
  font-size: 11px;
}
.job-name {
  color: var(--ds-navy-deep);
  font-weight: 600;
}
.detail-btn {
  border: 1px solid var(--ds-border);
  border-radius: 6px;
  background: #fff;
  color: var(--ds-ink);
  padding: 5px 9px;
  cursor: pointer;
  white-space: nowrap;
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
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  background: rgba(16, 42, 71, 0.28);
}
.detail-modal {
  position: relative;
  width: min(760px, 100%);
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
  margin: 4px 0 5px;
  color: var(--ds-navy-deep);
}
.detail-modal h3 {
  margin: 20px 0 8px;
  color: #34413a;
  font-size: 14px;
}
.job-org {
  margin: 0;
  color: var(--ds-muted);
  font-size: 12px;
}
.fact-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 16px;
}
.fact-grid div {
  padding: 9px;
  border-radius: 8px;
  background: #f7faf8;
}
.fact-grid span {
  display: block;
  color: #9aa3ad;
  font-size: 11px;
}
.fact-grid strong {
  display: block;
  margin-top: 4px;
  color: #3c4a42;
  font-size: 12px;
  line-height: 1.5;
}
.announcement-text {
  margin: 0;
  color: #3c4a42;
  font-size: 12px;
  line-height: 1.6;
}
.official-link {
  display: inline-block;
  margin-top: 8px;
  color: var(--ds-ink);
  font-size: 12px;
}
.source-unavailable {
  display: inline-block;
  margin-top: 8px;
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
.reminder-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.reminder-input {
  padding: 7px 8px;
  border: 1px solid var(--ds-border);
  border-radius: 7px;
  color: var(--ds-ink);
  font-size: 12px;
}
.reminder-row button {
  padding: 7px 12px;
  border: 1px solid var(--ds-border);
  border-radius: 7px;
  background: #fff;
  cursor: pointer;
}
.reminder-message {
  margin: 9px 0 0;
  color: #2f6b4b;
  font-size: 12px;
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
  .home-link {
    display: inline-block;
    margin-top: 10px;
  }
  .job-table {
    min-width: 820px;
  }
  .fact-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
