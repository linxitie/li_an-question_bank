/**
 * 17 个域外壳冒烟测试（P1-33）
 *
 * 覆盖范围（对齐实施计划 P1-33 验收标准）：
 *   1. 17 个域目录四件套齐备（store.ts / api.ts / events.ts / README.md）；
 *   2. 17 个 store.ts 均可在全新 createPinia + setActivePinia 下实例化，且状态契约可用；
 *   3. 17 个 api.ts 均引用 @/services/api/client 的唯一 apiClient，禁止自建 axios 实例；
 *   4. events.ts 的 PUBLISHED_EVENTS / SUBSCRIBED_EVENTS 与 EVENT_NAMES 常量表一致；
 *   5. README.md 具备 7 个域卡章节。
 *
 * 注意：本文件刻意不 import 认证 store（src/stores/auth.ts 在 setup 时访问
 * window.__VTJ_AUTH__），此处只测域外壳；环境为 node，无需 DOM。
 */
import { beforeEach, describe, expect, it } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { apiClient } from '@/services/api/client';
import { EVENT_NAMES } from '@/stores/event-bus';

/** 17 个业务域（顺序与实施计划一致） */
const DOMAINS = [
  'identity',
  'catalog',
  'practice',
  'records',
  'papers',
  'wrongbook',
  'notes',
  'analytics',
  'community',
  'news',
  'calendar',
  'recruitment',
  'about',
  'library',
  'growth',
  'reward',
  'checkin'
] as const;

/** 每个域必须具备的四件套 */
const REQUIRED_FILES = ['store.ts', 'api.ts', 'events.ts', 'README.md'] as const;

/** 全部合法事件名（常量表值集合） */
const REGISTERED_EVENT_VALUES = new Set<string>(Object.values(EVENT_NAMES));

/** 域名 -> store 工厂导出名（scaffolder 的 PascalCase 约定） */
function storeExportName(domain: string): string {
  return `use${domain.charAt(0).toUpperCase()}${domain.slice(1)}Store`;
}

/**
 * 预加载全部域模块。使用 import.meta.glob 保证 Vite 可静态分析；
 * eager 加载后直接按路径取值，避免用例内动态拼接 import。
 */
const storeModules = import.meta.glob('../*/store.ts', { eager: true }) as Record<
  string,
  Record<string, unknown>
>;
const apiModules = import.meta.glob('../*/api.ts', { eager: true }) as Record<
  string,
  Record<string, unknown>
>;
const eventModules = import.meta.glob('../*/events.ts', { eager: true }) as Record<
  string,
  Record<string, unknown>
>;
/** 原始文本加载（as: 'raw'），键形如 ../<domain>/README.md、../<domain>/api.ts */
const rawModules = import.meta.glob(['../*/README.md', '../*/api.ts'], {
  as: 'raw',
  eager: true
}) as Record<string, string>;

/** 读取模块的文本内容（Vite 原生 raw glob，无 node:fs 依赖） */
function readModuleFile(domain: string, file: string): string {
  return rawModules[`../${domain}/${file}`] ?? '';
}

/** 取模块导出：优先约定名，缺失时回退到唯一 use*Store 导出 */
function resolveStoreFactory(
  domain: string,
  module: Record<string, unknown>
): ((...args: unknown[]) => unknown) | undefined {
  const preferred = module[storeExportName(domain)];
  if (typeof preferred === 'function') {
    return preferred as (...args: unknown[]) => unknown;
  }
  const candidates = Object.entries(module).filter(
    ([name, value]) => name.startsWith('use') && name.endsWith('Store') && typeof value === 'function'
  );
  return candidates.length === 1 ? (candidates[0][1] as (...args: unknown[]) => unknown) : undefined;
}

beforeEach(() => {
  // 每个用例一个全新 Pinia 实例，避免 store 状态跨用例泄漏
  setActivePinia(createPinia());
});

describe('17 个域外壳：目录四件套', () => {
  it.each(DOMAINS)('%s 域四件套齐备（store/api/events/README）', (domain) => {
    for (const file of REQUIRED_FILES) {
      const exists = file === 'README.md' ? rawModules[`../${domain}/${file}`] !== undefined
        : (file === 'store.ts' ? storeModules : file === 'api.ts' ? apiModules : eventModules)[`../${domain}/${file}`] !== undefined;
      expect(exists, `${domain}/${file} 缺失`).toBe(true);
    }
  });
});

describe('17 个域外壳：store.ts 可实例化', () => {
  it.each(DOMAINS)('%s 的 setup store 可实例化且状态契约可用', (domain) => {
    const module = storeModules[`../${domain}/store.ts`];
    expect(module, `${domain}/store.ts 未被加载`).toBeTruthy();

    const factory = resolveStoreFactory(domain, module);
    expect(factory, `${domain}/store.ts 未导出 use*Store`).toBeTypeOf('function');

    // 全新 pinia 已由 beforeEach 设为 active，直接实例化
    const store = factory!() as {
      loading: boolean;
      error: string | null;
      initialized: boolean;
      ready: boolean;
      reset: () => void;
      load: () => Promise<void>;
    };

    // 外壳状态契约
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.ready).toBe(false);
    expect(store.reset).toBeTypeOf('function');
    expect(store.load).toBeTypeOf('function');

    // ready 是派生值：initialized 且无错误
    store.initialized = true;
    expect(store.ready).toBe(true);
    store.error = 'boom';
    expect(store.ready).toBe(false);

    // reset() 可以回到初始状态
    store.reset();
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.ready).toBe(false);
  });

  it.each(DOMAINS)('%s 的 store id 与域名一致', (domain) => {
    const module = storeModules[`../${domain}/store.ts`];
    const factory = resolveStoreFactory(domain, module);
    const store = factory!() as { $id: string };
    expect(store.$id).toBe(domain);
  });
});

describe('17 个域外壳：api.ts 引用统一客户端', () => {
  it.each(DOMAINS)('%s 的 api.ts 导出同一个 apiClient 实例', (domain) => {
    const module = apiModules[`../${domain}/api.ts`];
    expect(module, `${domain}/api.ts 未被加载`).toBeTruthy();

    const exported = Object.entries(module).find(([name]) => name.endsWith('Client'));
    expect(exported, `${domain}/api.ts 未导出 *Client`).toBeTruthy();
    expect(exported![1], `${domain}/api.ts 的客户端不是统一实例`).toBe(apiClient);
  });

  it.each(DOMAINS)('%s 的 api.ts 不自建 axios 实例', (domain) => {
    const source = readModuleFile(domain, 'api.ts');
    expect(source).toContain("@/services/api/client");

    // 去掉注释后再断言，避免文件头“禁止自行 axios.create”的说明误报
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/(^|[^:])\/\/.*$/gm, '$1');

    expect(code).not.toMatch(/axios\s*\.\s*create/);
    expect(code).not.toMatch(/from\s+['"]axios['"]/);
    expect(code).not.toMatch(/require\(\s*['"]axios['"]\s*\)/);
  });
});

describe('17 个域外壳：events.ts 与常量表一致', () => {
  it('EVENT_NAMES 的事件名无重复', () => {
    const values = Object.values(EVENT_NAMES);
    expect(new Set(values).size).toBe(values.length);
  });

  it.each(DOMAINS)('%s 的事件导出均取自 EVENT_NAMES', (domain) => {
    const module = eventModules[`../${domain}/events.ts`];
    expect(module, `${domain}/events.ts 未被加载`).toBeTruthy();

    const published = module.PUBLISHED_EVENTS;
    const subscribed = module.SUBSCRIBED_EVENTS;
    expect(published, `${domain} 缺少 PUBLISHED_EVENTS`).toBeTypeOf('object');
    expect(subscribed, `${domain} 缺少 SUBSCRIBED_EVENTS`).toBeTypeOf('object');

    for (const [key, value] of [
      ...Object.entries(published as Record<string, unknown>),
      ...Object.entries(subscribed as Record<string, unknown>)
    ]) {
      // 键必须是常量表的键（不手写第二份命名）
      expect(EVENT_NAMES, `${domain}.${key} 未在 EVENT_NAMES 登记`).toHaveProperty(key);
      // 值必须与常量表完全相等，且属于合法事件名
      expect(value, `${domain}.${key} 与 EVENT_NAMES 不一致`).toBe(
        EVENT_NAMES[key as keyof typeof EVENT_NAMES]
      );
      expect(REGISTERED_EVENT_VALUES.has(value as string)).toBe(true);
    }
  });
});

describe('17 个域外壳：README.md 域卡章节', () => {
  it.each(DOMAINS)('%s 的 README.md 具备 7 个章节', (domain) => {
    const source = readModuleFile(domain, 'README.md');
    const sections = Array.from(source.matchAll(/^##\s+([1-7])\.\s+/gm)).map((m) => Number(m[1]));
    expect(sections).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it.each(DOMAINS)('%s 的 README.md 标注「功能还未开发」', (domain) => {
    const source = readModuleFile(domain, 'README.md');
    expect(source).toContain('功能还未开发');
  });
});
