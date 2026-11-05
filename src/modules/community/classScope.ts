/**
 * 当前账号可选的班级范围（论坛发帖「仅指定班级」用）。
 *
 * 为什么要单独一个模块：
 * - JWT 里**没有**班级字段（`auth.parseUserInfo()` 只返回 role/roleLevel/permissions/userId），
 *   之前前端直接读 `info.className` 恒为空，导致「当前账号没有可选班级」；
 * - 班级的事实来源是 `/api/auth/profile`（实测返回 `class_name: "测试班"`）；
 * - 三端（学生 PC / 平板 / 手机）都要用，集中一份避免各写一份、口径漂移。
 *
 * 缓存策略：同一会话只请求一次；失败不缓存（下次重试），且不抛异常打断发帖流程。
 */
import { apiClient } from '@/services/api/client';

export interface MyClassScope {
  /** 本人班级名，未分班时为空串 */
  className: string;
  /** 可作为「仅指定班级」选项的班级列表：有班级时就是 [className] */
  classes: string[];
  /** 账号是否已分班 */
  hasClass: boolean;
}

const EMPTY: MyClassScope = { className: '', classes: [], hasClass: false };

let cache: MyClassScope | null = null;
let inflight: Promise<MyClassScope> | null = null;

function normalizeClass(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

/**
 * 读取本人班级范围（带缓存）。
 * 出错时返回空范围而不是抛出：发帖页仍应能用「全站可见」继续。
 */
export async function loadMyClasses(): Promise<MyClassScope> {
  if (cache) return cache;
  if (inflight) return inflight;

  inflight = (async () => {
    try {
      const res = await apiClient.request<{ class_name?: string | null }>({
        url: '/api/auth/profile',
        method: 'GET',
        baseURL: ''
      });
      const className = normalizeClass(res.data?.class_name);
      const scope: MyClassScope = {
        className,
        classes: className ? [className] : [],
        hasClass: Boolean(className)
      };
      cache = scope;
      return scope;
    } catch {
      return EMPTY;
    } finally {
      inflight = null;
    }
  })();

  return inflight;
}

/** 登出或切换账号时必须清空，否则会用到上一个用户的班级 */
export function clearMyClassCache(): void {
  cache = null;
  inflight = null;
}
