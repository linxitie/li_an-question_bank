/**
 * 每日签到（checkin）域 API（P2-48）。
 *
 * 端点为本域新增的 `/api/v1/growth/checkin`：
 *   - POST /growth/checkin          签到（一天一次，后端幂等）
 *   - GET  /growth/checkin/status   今日状态（每次实时查询，不做本地缓存）
 *
 * `apiClient` 的 baseURL 已是 `/api/v1`，故此处使用相对路径；
 * 全域仅经此唯一 axios 实例发请求。
 */
import { apiClient } from '@/services/api/client';

export const checkinClient = apiClient;

export interface CheckinReward {
  coins: number;
  growth: number;
}

/** 今日签到状态（后端权威快照） */
export interface CheckinStatus {
  date: string;
  checked_in: boolean;
  continuous_days: number;
  /** 今日已获得的金币（未签到为 0） */
  today_reward: number;
  /** 下次签到可获得的奖励 */
  next_reward: CheckinReward;
}

/** 签到结果；is_today_first=false 表示今日已签、本次未发奖 */
export interface CheckinResult {
  date: string;
  checked_in: boolean;
  is_today_first: boolean;
  continuous_days: number;
  today_reward: number;
  reward_growth: number;
  message: string;
}

/** 查询今日签到状态（只读，不发布行为事件） */
export function fetchTodayStatus(): Promise<CheckinStatus> {
  return checkinClient
    .get<CheckinStatus>('/growth/checkin/status')
    .then((response) => response.data);
}

/** 执行签到；幂等由后端唯一约束保证 */
export function submitCheckin(): Promise<CheckinResult> {
  return checkinClient
    .post<CheckinResult>('/growth/checkin')
    .then((response) => response.data);
}

/** 刷新今日状态（等同重新查询） */
export function refreshCheckin(): Promise<CheckinStatus> {
  return fetchTodayStatus();
}
