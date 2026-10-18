/**
 * 成绩分析（analytics）域 API（P2-59）。
 *
 * 数据来源均为根路径 `/api/*`（非 `/api/v1`），因此显式置空 baseURL，
 * 复用唯一 axios 实例，不自行 axios.create：
 *
 *   - GET /api/exam-records/trend   得分趋势（按 exam_type）
 *   - GET /api/stats/type-mastery   知识点/题型掌握度
 *   - GET /api/stats/dashboard      薄弱点（weakPoints 字段，E13 供给）
 */
import { apiClient } from '@/services/api/client';

export const analyticsClient = apiClient;

export type ExamType = 'SELF_TEST' | 'MOCK_EXAM';

export interface ScoreTrendPoint {
  index: number;
  recordId: number;
  paperName: string;
  submitTime: string | null;
  totalScore: number;
  maxScore: number;
  accuracy: number;
  durationUsed: number;
}

export interface ScoreTrend {
  examType: ExamType;
  trend: ScoreTrendPoint[];
  avgScore: number;
}

export interface KnowledgeMasteryItem {
  typeId: number;
  typeName: string;
  count: number;
  correct: number;
  wrong: number;
  accuracy: number;
  minutes: number;
  lastPracticeDate: string | null;
}

export interface WeakPoint {
  knowledge_point: string;
  accuracy: number;
  total: number;
  correct: number;
}

export interface ScoreTrendQuery {
  examType?: ExamType;
  limit?: number;
}

interface AnalyticsRequestConfig {
  url: string;
  method: 'GET';
  params?: Record<string, unknown>;
}

async function request<T>(config: AnalyticsRequestConfig): Promise<T> {
  const response = await analyticsClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

function normalizeTrend(raw: {
  exam_type?: string;
  trend?: Array<Record<string, unknown>>;
  avg_score?: number;
}): ScoreTrend {
  const trend = (raw.trend ?? []).map((item) => ({
    index: Number(item.index) || 0,
    recordId: Number(item.record_id) || 0,
    paperName: String(item.paper_name ?? '未知'),
    submitTime: item.submit_time ? String(item.submit_time) : null,
    totalScore: Number(item.total_score) || 0,
    maxScore: Number(item.max_score) || 100,
    accuracy: Number(item.accuracy) || 0,
    durationUsed: Number(item.duration_used) || 0
  }));
  return {
    examType: (raw.exam_type as ExamType) || 'SELF_TEST',
    trend,
    avgScore: Number(raw.avg_score) || 0
  };
}

export async function fetchScoreTrend(
  query: ScoreTrendQuery = {}
): Promise<ScoreTrend> {
  const data = await request<{
    exam_type?: string;
    trend?: Array<Record<string, unknown>>;
    avg_score?: number;
  }>({
    url: '/api/exam-records/trend',
    method: 'GET',
    params: {
      exam_type: query.examType ?? 'SELF_TEST',
      limit: Math.min(Math.max(query.limit ?? 10, 5), 30)
    }
  });
  return normalizeTrend(data);
}

export async function fetchKnowledgeMastery(): Promise<KnowledgeMasteryItem[]> {
  const data = await request<Array<Record<string, unknown>>>(
    { url: '/api/stats/type-mastery', method: 'GET' }
  );
  return (data ?? []).map((item) => ({
    typeId: Number(item.typeId) || 0,
    typeName: String(item.typeName ?? '未知题型'),
    count: Number(item.count) || 0,
    correct: Number(item.correct) || 0,
    wrong: Number(item.wrong) || 0,
    accuracy: Number(item.accuracy) || 0,
    minutes: Number(item.minutes) || 0,
    lastPracticeDate: item.lastPracticeDate ? String(item.lastPracticeDate) : null
  }));
}

export async function fetchWeakPoints(): Promise<WeakPoint[]> {
  const data = await request<{ weakPoints?: Array<Record<string, unknown>> }>(
    { url: '/api/stats/dashboard', method: 'GET' }
  );
  return (data?.weakPoints ?? []).map((item) => ({
    knowledge_point: String(item.knowledge_point ?? '未分类考点'),
    accuracy: Number(item.accuracy) || 0,
    total: Number(item.total) || 0,
    correct: Number(item.correct) || 0
  }));
}

export async function refreshAnalytics(
  query: ScoreTrendQuery = {}
): Promise<{
  trend: ScoreTrend;
  mastery: KnowledgeMasteryItem[];
  weakPoints: WeakPoint[];
}> {
  const [trend, mastery, weakPoints] = await Promise.all([
    fetchScoreTrend(query),
    fetchKnowledgeMastery(),
    fetchWeakPoints()
  ]);
  return { trend, mastery, weakPoints };
}
