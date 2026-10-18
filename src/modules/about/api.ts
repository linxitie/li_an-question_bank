/**
 * 关于砺安题库（about）域 API 封装（P2-69）。
 *
 * 本域没有专属后端端点：页面内容为静态展示，只读消费通用配置——
 *   - 版本号 / 服务名：`GET /health`（main.py，无需登录，只读）
 *   - 联系方式：前端静态常量（与 `.vtj/vue/about.vue` 页脚口径一致）
 *
 * 约束：
 *   1. 复用 @/services/api/client 的唯一 axios 实例，禁止自行 axios.create；
 *   2. 无写接口、无事件进出、不写 localStorage。
 */
import { apiClient } from '@/services/api/client';

/** 本域统一客户端引用 */
export const aboutClient = apiClient;

/** 通用配置：后端健康检查返回的服务信息 */
export interface AboutAppInfo {
  status: string;
  service: string;
  version: string;
}

/** 通用配置：联系方式（静态，无对应端点） */
export interface AboutContact {
  email: string;
  hotline: string;
  copyright: string;
}

/** 关于页只读消费的完整配置 */
export interface AboutProfile {
  info: AboutAppInfo;
  contact: AboutContact;
}

/** 联系方式与版权（与 about.vue 页脚一致；无专属端点） */
export const ABOUT_CONTACT: Readonly<AboutContact> = Object.freeze({
  email: 'service@lianzhi.com',
  hotline: '400-000-0000',
  copyright: '© 2025 砺安题库'
});

/** 读取通用配置（只读） */
export async function fetchAboutInfo(): Promise<AboutAppInfo> {
  const response = await aboutClient.request<AboutAppInfo>({
    url: '/health',
    method: 'GET',
    baseURL: ''
  });
  return {
    status: response.data?.status ?? 'unknown',
    service: response.data?.service ?? '砺安题库',
    version: response.data?.version ?? ''
  };
}

/** 读取联系方式（静态只读） */
export function fetchAboutContact(): AboutContact {
  return { ...ABOUT_CONTACT };
}

/** 读取关于页完整配置（版本号 + 联系方式） */
export async function fetchAboutProfile(): Promise<AboutProfile> {
  const info = await fetchAboutInfo();
  return { info, contact: fetchAboutContact() };
}

/** 刷新关于页配置（等同重新拉取） */
export function refreshAbout(): Promise<AboutProfile> {
  return fetchAboutProfile();
}
