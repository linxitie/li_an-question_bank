/**
 * 认证与个人中心（identity）域 API 封装（P2-76）。
 *
 * 后端端点（api_surface.json 冻结口径，路径一律不改）：
 *   - 认证：`/api/auth/*`（auth.py / auth_qrcode.py）
 *   - 设备：`/api/auth/devices/*`（devices.py）
 *   - 通知：`/api/stats/messages`（exam/stats.py，只读系统消息）
 *   - 帮助：`/api/feedback/faq`（platform/feedback.py，公开只读）
 *   - 反馈：`/api/feedback`、`/api/feedback/my`（platform/feedback.py）
 *
 * 约束：
 *   1. 全域只允许使用 @/services/api/client 暴露的唯一 axios 实例，禁止自行 axios.create；
 *   2. 这些端点不挂在 `/api/v1` 前缀下，故统一显式 `baseURL: ''` + 完整 `/api/...` 路径；
 *   3. 登录凭据的落地（token 存储 / 刷新 / 设备会话）只属于 `window.__VTJ_AUTH__`，
 *      本文件的 `loginWithPassword` 仅暴露后端契约，页面与 store 不得用它替代 auth 模块。
 */
import { apiClient } from '@/services/api/client';

/** 本域统一客户端引用：所有请求都经由此实例发起 */
export const identityClient = apiClient;

/** 用户档案（与 backend UserResponse 对齐，仅列前端消费字段） */
export interface IdentityUser {
  user_id: number;
  user_no: string;
  username: string;
  email?: string | null;
  phone?: string;
  avatar?: string | null;
  gender?: string;
  user_type: string;
  department?: string | null;
  class_name?: string | null;
  school?: string;
  title?: string | null;
  specialty?: string | null;
  role_level: number;
  status: number;
  total_coins: number;
  register_time?: string | null;
}

/** 登录响应（后端 LoginResponse） */
export interface IdentityLoginResult {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: IdentityUser;
}

/** 个人信息可编辑字段（后端 ProfileUpdateForm） */
export interface IdentityProfileUpdate {
  email?: string;
  phone?: string;
  avatar?: string;
  gender?: string;
  department?: string;
  class_name?: string;
  school?: string;
}

/** 登录设备会话 */
export interface IdentityDevice {
  device_id: string;
  platform?: string;
  browser?: string;
  os?: string;
  ip?: string;
  last_active?: string;
  is_current?: boolean;
}

export interface IdentityDeviceList {
  devices: IdentityDevice[];
  max_devices: number;
}

/** 系统通知（GET /api/stats/messages） */
export interface IdentityNotification {
  id: number | string;
  title: string;
  content: string;
  type?: string;
  createdAt?: string;
}

export interface IdentityFaqItem {
  q: string;
  a: string;
}

export interface IdentityFaqCategory {
  category: string;
  items: IdentityFaqItem[];
}

export interface IdentityFeedback {
  feedback_id: number;
  category: string;
  content: string;
  contact?: string | null;
  status: string;
  reply?: string | null;
  replied_at?: string | null;
  created_at?: string | null;
}

export interface IdentityFeedbackList {
  total: number;
  page: number;
  page_size: number;
  items: IdentityFeedback[];
}

export interface IdentityFeedbackInput {
  category: string;
  content: string;
  contact?: string;
}

export interface IdentityFeedbackSubmitResult {
  feedback_id: number;
  message: string;
}

/** 二维码登录契约（auth_qrcode.py） */
export interface IdentityQrCode {
  uuid: string;
  qr_url: string;
  qr_image_base64: string;
  expires_in: number;
}

export interface IdentityQrStatus {
  status: 'pending' | 'confirmed' | 'expired';
  token?: string | null;
}

interface IdentityRequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  params?: Record<string, unknown>;
  data?: unknown;
  headers?: Record<string, string>;
}

async function request<T>(config: IdentityRequestConfig): Promise<T> {
  const response = await identityClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

/**
 * 密码登录（后端契约）。
 * 页面与 store 必须优先走 `window.__VTJ_AUTH__.login()`，由认证模块统一落地 token。
 */
export function loginWithPassword(
  username: string,
  password: string,
  clientType: 'web' | 'mobile' | 'tablet' = 'web'
): Promise<IdentityLoginResult> {
  const body = new URLSearchParams();
  body.set('username', username);
  body.set('password', password);
  body.set('client_type', clientType);
  return request<IdentityLoginResult>({
    url: '/api/auth/login',
    method: 'POST',
    data: body.toString(),
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
}

/** 刷新令牌（后端契约；正常路径由 __VTJ_AUTH__.ensureAuth 调用） */
export function refreshAccessToken(refreshToken: string): Promise<{ access_token: string; token_type: string }> {
  return request({ url: '/api/auth/refresh', method: 'POST', data: { refresh_token: refreshToken } });
}

/** 读取当前用户完整档案（只读） */
export function fetchProfile(): Promise<IdentityUser> {
  return request({ url: '/api/auth/profile', method: 'GET' });
}

/** 编辑个人信息（仅非敏感字段） */
export function updateProfile(payload: IdentityProfileUpdate): Promise<{ success: boolean; message: string; user: IdentityUser }> {
  return request({ url: '/api/auth/profile', method: 'PUT', data: payload });
}

/** 修改密码 */
export function changePassword(
  newPassword: string,
  oldPassword?: string
): Promise<{ success: boolean; message: string }> {
  return request({
    url: '/api/auth/change-password',
    method: 'POST',
    data: { new_password: newPassword, old_password: oldPassword }
  });
}

/** 上传头像（2MB 上限，后端白名单校验） */
export function uploadAvatar(file: File): Promise<{ success: boolean; message: string; avatar_url: string }> {
  const formData = new FormData();
  formData.append('file', file);
  return request({ url: '/api/auth/avatar', method: 'POST', data: formData });
}

/** 设备列表（最多 3 台） */
export function fetchDevices(): Promise<IdentityDeviceList> {
  return request({ url: '/api/auth/devices/', method: 'GET' });
}

/** 移除指定设备 */
export function removeDevice(deviceId: string): Promise<{ message: string }> {
  return request({
    url: `/api/auth/devices/${encodeURIComponent(deviceId)}`,
    method: 'DELETE'
  });
}

/** 强制下线所有设备 */
export function revokeAllDevices(): Promise<{ message: string }> {
  return request({ url: '/api/auth/devices/revoke-all', method: 'POST' });
}

/** 系统通知（只读） */
export function fetchNotifications(page = 1, pageSize = 20): Promise<IdentityNotification[]> {
  return request({
    url: '/api/stats/messages',
    method: 'GET',
    params: { page, page_size: pageSize }
  });
}

/** 帮助中心 FAQ（公开只读） */
export async function fetchFaq(): Promise<IdentityFaqCategory[]> {
  const data = await request<{ items: IdentityFaqCategory[] }>({
    url: '/api/feedback/faq',
    method: 'GET'
  });
  return data.items ?? [];
}

/** 我的反馈列表 */
export function fetchMyFeedback(page = 1, pageSize = 20): Promise<IdentityFeedbackList> {
  return request({
    url: '/api/feedback/my',
    method: 'GET',
    params: { page, page_size: pageSize }
  });
}

/** 提交反馈 */
export function submitFeedback(payload: IdentityFeedbackInput): Promise<IdentityFeedbackSubmitResult> {
  return request({ url: '/api/feedback', method: 'POST', data: payload });
}

/** 生成扫码登录二维码（公开接口） */
export function generateLoginQrCode(origin?: string): Promise<IdentityQrCode> {
  return request({
    url: '/api/auth/qrcode/generate',
    method: 'POST',
    data: origin ? { origin } : {}
  });
}

/** 移动端扫码后读取 PC 设备信息 */
export function fetchLoginQrInfo(uuid: string): Promise<{ device: Record<string, unknown>; login_time: string }> {
  return request({ url: `/api/auth/qrcode/${encodeURIComponent(uuid)}/info`, method: 'GET' });
}

/** 移动端确认扫码登录 */
export function confirmLoginQr(uuid: string): Promise<{ success: boolean; message: string }> {
  return request({ url: `/api/auth/qrcode/${encodeURIComponent(uuid)}/confirm`, method: 'POST', data: {} });
}

/** PC 端轮询二维码状态 */
export function fetchLoginQrStatus(uuid: string): Promise<IdentityQrStatus> {
  return request({ url: `/api/auth/qrcode/${encodeURIComponent(uuid)}/status`, method: 'GET' });
}

/** 刷新本域只读数据（等同重新加载 profile，由 store.load 编排） */
export function refreshIdentity(): Promise<IdentityUser> {
  return fetchProfile();
}
