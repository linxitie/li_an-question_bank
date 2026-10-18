/**
 * 成就成长（growth）域 API（P2-54）。
 *
 * 端点均挂在根路径 `/api/*`（非 `/api/v1`），因此沿用 community / library 的
 * `baseURL: ''` 覆盖方式复用唯一 axios 实例；不自行 axios.create。
 *
 *   - GET /api/achievements      成就墙（分类 + 已获得 + 实时进度）
 *   - GET /api/goals/            学习目标列表
 *   - GET /api/tasks/overview    任务中心总览（每日 / 随机 / 周常）
 */
import { apiClient } from '@/services/api/client';

export const growthClient = apiClient;

export interface AchievementItem {
  achievement_id: number;
  category: string;
  name: string;
  icon: string;
  condition_desc: string;
  reward_coins: number;
  condition_code: string;
  threshold: number;
  extra?: string | null;
  earned: boolean;
  tier: number;
  is_hidden: number;
  tier_times?: number[] | null;
  style_params?: Record<string, unknown> | null;
  current: number;
}

export interface AchievementWall {
  total: number;
  earned_count: number;
  progress: Record<string, number | Record<number, number>>;
  categories: Record<string, AchievementItem[]>;
}

export type GoalType = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'CUSTOM';

export interface GoalListQuery {
  goalType?: GoalType;
  isCompleted?: boolean;
}

export interface GoalItem {
  goal_id: number;
  user_id: number;
  title: string;
  description?: string | null;
  goal_type: GoalType;
  target_count: number;
  current_count: number;
  subject_mode?: number | null;
  expected_minutes?: number | null;
  deadline?: string | null;
  priority: number;
  is_completed: boolean;
  completed_time?: string | null;
  create_time?: string | null;
  update_time?: string | null;
  progress_percent: number;
}

export interface GoalListResult {
  total: number;
  items: GoalItem[];
}

export interface TaskItem {
  task_id: number;
  task_code: string;
  title: string;
  description?: string | null;
  metric: string;
  threshold: number;
  reward_coins: number;
  current: number;
  completed: boolean;
  claimed: boolean;
}

export interface TaskCheckinState {
  checked_in: boolean;
  continuous_days: number;
  today_reward: number;
}

export interface TaskOverview {
  checkin: TaskCheckinState;
  daily: TaskItem[];
  random: TaskItem[];
  weekly: TaskItem[];
}

interface GrowthRequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  params?: Record<string, unknown>;
}

async function request<T>(config: GrowthRequestConfig): Promise<T> {
  const response = await growthClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

export function fetchAchievementWall(): Promise<AchievementWall> {
  return request<AchievementWall>({ url: '/api/achievements', method: 'GET' });
}

export function fetchGoals(query: GoalListQuery = {}): Promise<GoalListResult> {
  const params: Record<string, unknown> = {};
  if (query.goalType) params.goal_type = query.goalType;
  if (query.isCompleted !== undefined) params.is_completed = query.isCompleted;
  return request<GoalListResult>({ url: '/api/goals/', method: 'GET', params });
}

export function fetchTaskOverview(): Promise<TaskOverview> {
  return request<TaskOverview>({ url: '/api/tasks/overview', method: 'GET' });
}

export async function refreshGrowth(): Promise<{
  wall: AchievementWall;
  goals: GoalListResult;
  tasks: TaskOverview;
}> {
  const [wall, goals, tasks] = await Promise.all([
    fetchAchievementWall(),
    fetchGoals(),
    fetchTaskOverview()
  ]);
  return { wall, goals, tasks };
}
