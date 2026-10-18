#!/usr/bin/env node
/**
 * 学生端模块外壳生成器（P1-13）
 *
 * 用法：
 *   node scripts/scaffold-module.mjs <domain-name> [中文模块名]
 *   node scripts/scaffold-module.mjs --help
 *
 * 输出 src/modules/<domain>/ 下四件套：
 *   store.ts  —— Pinia setup store 外壳（可实例化，无业务逻辑）
 *   api.ts    —— 统一 API 客户端封装外壳（空方法体，P2 阶段实现）
 *   events.ts —— 事件契约外壳（仅登记常量，不建立订阅）
 *   README.md —— 域卡（7 个必填字段骨架）
 *
 * 约定：
 *   - 无外部依赖，纯 Node ESM；
 *   - domain-name 必须为 kebab-case ASCII（小写字母 / 数字 / 连字符，
 *     下划线仅用于 __scaffold_test 这类临时测试域）；
 *   - 目标目录已存在时拒绝覆盖，退出码 1。
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const MODULES_DIR = path.join(ROOT, 'src', 'modules');

/** 规划中的 17 个业务域及其中文名 */
const DOMAIN_NAMES = {
  identity: '认证与个人中心',
  catalog: '题库浏览',
  practice: '答题练习',
  records: '练习记录',
  papers: '智能组卷与历年试卷',
  wrongbook: '错题集',
  notes: '笔记与收藏',
  analytics: '成绩分析',
  community: '论坛社区',
  news: '每日新闻',
  calendar: '考试日历',
  recruitment: '招考信息',
  about: '关于砺安题库',
  library: '备考资料',
  growth: '成就成长',
  reward: '金币商城',
  checkin: '每日签到'
};

/**
 * 各域的事件契约计划（仅用于生成注释与常量登记）。
 * published / subscribed 为前端事件常量名（必须在 EVENT_NAMES 中已登记）；
 * reportBackend / consumeBackend 为后端 record_user_action 的 trigger_type。
 */
const DOMAIN_EVENTS = {
  identity: {
    subscribed: [
      {
        key: 'GROWTH_ACHIEVEMENT_UNLOCKED',
        note: '成就解锁后刷新「我的」通知（P2 阶段接入，当前不建立订阅）'
      }
    ]
  },
  catalog: {
    note: '本域无成就入边，不发布也不订阅前端事件。'
  },
  practice: {
    published: [
      {
        key: 'WRONG_QUESTIONS_CHANGED',
        note: '作答提交成功后发布，通知错题域与成就域'
      }
    ],
    reportBackend: [
      { name: 'practice.submit', note: '答题提交成功后上报（成就 E1）' }
    ]
  },
  records: {
    reportBackend: [
      { name: 'practice.record.created', note: '练习记录生成后上报（成就 E2）' }
    ]
  },
  papers: {
    reportBackend: [
      { name: 'paper.completed', note: '整卷完成后上报（成就 E3）' }
    ]
  },
  wrongbook: {
    published: [
      {
        key: 'WRONG_QUESTIONS_CHANGED',
        note: '错题复习或掌握度流转后发布'
      }
    ],
    subscribed: [
      {
        key: 'WRONG_QUESTIONS_CHANGED',
        note: '订阅其他域产生的错题集合变更（P2 阶段接入）'
      }
    ],
    reportBackend: [
      { name: 'wrong.reviewed', note: '错题消灭 / 掌握状态流转后上报（成就 E4）' }
    ]
  },
  notes: {
    reportBackend: [
      { name: 'note.created', note: '笔记创建后上报（成就 E5）' },
      { name: 'favorite.added', note: '收藏新增后上报（成就 E5）' }
    ]
  },
  analytics: {
    note: '本域只读，无成就入边，不发布也不订阅前端事件。'
  },
  community: {
    reportBackend: [
      { name: 'forum.posted', note: '发帖 / 回帖后上报（成就 E6）' }
    ]
  },
  news: {
    reportBackend: [
      { name: 'news.read', note: '阅读新闻后上报（成就 E7，同一篇去重）' }
    ]
  },
  calendar: {
    note: '本域无事件进出：不发布、不订阅、不上报。'
  },
  recruitment: {
    note: '本域无事件进出：不发布、不订阅、不上报。'
  },
  about: {
    note: '本域为纯静态展示，无事件进出。'
  },
  library: {
    reportBackend: [
      { name: 'material.opened', note: '打开资料后上报（成就 E8，按资料 id 去重）' }
    ]
  },
  growth: {
    note: '本域是成就枢纽：只消费后端行为事件，禁止 import 任何业务域。',
    published: [
      {
        key: 'GROWTH_ACHIEVEMENT_UNLOCKED',
        note: '成就解锁后发布，供「我的」通知与成就墙消费'
      }
    ],
    consumeBackend: [
      { name: 'practice.submit', note: 'E1 答题练习' },
      { name: 'practice.record.created', note: 'E2 练习记录' },
      { name: 'paper.completed', note: 'E3 整卷完成' },
      { name: 'wrong.reviewed', note: 'E4 错题复习' },
      { name: 'note.created', note: 'E5 笔记创建' },
      { name: 'favorite.added', note: 'E5 收藏新增' },
      { name: 'forum.posted', note: 'E6 论坛发帖' },
      { name: 'news.read', note: 'E7 新闻阅读' },
      { name: 'material.opened', note: 'E8 资料学习' },
      { name: 'shop.purchased', note: 'E9 商城消费' },
      { name: 'checkin.done', note: 'E10 每日签到' }
    ]
  },
  reward: {
    published: [
      {
        key: 'REWARD_COINS_CHANGED',
        note: '兑换成功或金币余额变化后发布'
      }
    ],
    reportBackend: [
      { name: 'shop.purchased', note: '商城兑换成功后上报（成就 E9）' }
    ]
  },
  checkin: {
    published: [
      {
        key: 'REWARD_COINS_CHANGED',
        note: '签到发放金币后发布，刷新「我的」与商城余额'
      }
    ],
    reportBackend: [
      { name: 'checkin.done', note: '签到成功后上报（成就 E10）' }
    ]
  }
};

function printUsage(stream = process.stdout) {
  stream.write(
    [
      '用法：',
      '  node scripts/scaffold-module.mjs <domain-name> [中文模块名]',
      '  node scripts/scaffold-module.mjs --help',
      '',
      '示例：',
      '  node scripts/scaffold-module.mjs identity 认证与个人中心',
      '  node scripts/scaffold-module.mjs __scaffold_test 测试域',
      '',
      '说明：',
      '  - domain-name 必须为 kebab-case ASCII（小写字母、数字、连字符；',
      '    下划线仅用于临时测试域，如 __scaffold_test）；',
      '  - 目标目录 src/modules/<domain>/ 已存在时拒绝覆盖；',
      '  - 生成 store.ts / api.ts / events.ts / README.md 四件套。',
      '',
      `支持的计划域：${Object.keys(DOMAIN_NAMES).join(', ')}`,
      ''
    ].join('\n')
  );
}

function fail(message) {
  process.stderr.write(`[scaffold-module] ${message}\n`);
  process.exit(1);
}

function toPascal(name) {
  return name
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('');
}

function toCamel(name) {
  const pascal = toPascal(name);
  return pascal.charAt(0).toLowerCase() + pascal.slice(1) || 'module';
}

function renderEventEntries(entries) {
  return entries
    .map((entry) => `  ${entry.key}: EVENT_NAMES.${entry.key}`)
    .join(',\n');
}

function renderEventDocLines(entries) {
  return entries.map((entry) => ` * - ${entry.key}：${entry.note}`);
}

function renderBackendList(title, entries) {
  if (!entries.length) {
    return [`/** ${title}：无。 */`, ''];
  }
  return [
    '/**',
    ` * ${title}：`,
    ...entries.map((entry) => ` * - ${entry.name}：${entry.note}`),
    ' */',
    ''
  ];
}

function renderEvents(domain, label) {
  const plan = DOMAIN_EVENTS[domain] || {};
  const published = plan.published || [];
  const subscribed = plan.subscribed || [];
  const reportBackend = plan.reportBackend || [];
  const consumeBackend = plan.consumeBackend || [];
  const hasFrontend = published.length > 0 || subscribed.length > 0;

  const lines = [
    '/**',
    ` * ${label}（${domain}）域事件契约外壳 —— scripts/scaffold-module.mjs 生成（P1-13）`,
    ' *',
    ' * 当前状态：仅登记计划，不建立任何订阅，也不触发任何事件（P2 阶段实现）。',
    ' *'
  ];
  if (plan.note) {
    lines.push(` * 说明：${plan.note}`, ' *');
  }
  lines.push(
    ' * 约束：',
    hasFrontend
      ? ' *   1. 前端事件常量一律在 @/stores/event-bus 的 EVENT_NAMES 登记，禁止手写事件名字面量；'
      : ' *   1. 本域不接入前端事件总线，不引用任何事件常量；',
    ' *   2. 本文件不建立订阅，P2 阶段在域入口调用 onEvent 并保留取消订阅函数；',
    ' *   3. 跨域只走事件总线，同域内部直接调用函数，不绕事件。',
    ' */'
  );

  if (hasFrontend) {
    lines.push("import { EVENT_NAMES } from '@/stores/event-bus';", '');
  }

  if (published.length) {
    lines.push(
      '/**',
      ' * 本域计划发布的前端事件（仅登记常量，不触发）：',
      ...renderEventDocLines(published),
      ' */',
      'export const PUBLISHED_EVENTS = {',
      renderEventEntries(published),
      '} as const;',
      ''
    );
  } else {
    lines.push(
      '/** 本域不发布前端事件。 */',
      'export const PUBLISHED_EVENTS = {} as const;',
      ''
    );
  }

  if (subscribed.length) {
    lines.push(
      '/**',
      ' * 本域计划订阅的前端事件（仅登记常量，不建立订阅）：',
      ...renderEventDocLines(subscribed),
      ' */',
      'export const SUBSCRIBED_EVENTS = {',
      renderEventEntries(subscribed),
      '} as const;',
      ''
    );
  } else {
    lines.push(
      '/** 本域不订阅前端事件。 */',
      'export const SUBSCRIBED_EVENTS = {} as const;',
      ''
    );
  }

  lines.push(
    ...renderBackendList('本域向后端 record_user_action() 上报的 trigger_type（P2 阶段补齐调用点）', reportBackend),
    ...renderBackendList('本域消费的后端行为 trigger_type', consumeBackend)
  );

  return lines.join('\n').replace(/\n+$/, '\n');
}

function renderStore(domain, label, pascal) {
  return `/**
 * ${label}（${domain}）域 Store 外壳 —— scripts/scaffold-module.mjs 生成（P1-13）
 *
 * 状态契约为最小公共骨架，字段与 README.md「store 状态契约」保持一致；
 * 本文件只提供可实例化的空签名，业务逻辑与真实数据加载在 P2 阶段实现。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

/** 本域状态契约（外壳字段） */
export interface ${pascal}State {
  /** 是否正在加载数据 */
  loading: boolean;
  /** 最近一次错误信息（无错误为 null） */
  error: string | null;
  /** 是否已完成首次初始化 */
  initialized: boolean;
}

/** 生成初始状态，保证 reset() 与首次加载口径一致 */
export function create${pascal}InitialState(): ${pascal}State {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

export const use${pascal}Store = defineStore('${domain}', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  /** 只读派生：本域是否可用（已完成初始化且无错误） */
  const ready = computed(() => initialized.value && error.value === null);

  /** 重置为初始状态（外壳实现，P2 阶段按需扩展） */
  function reset(): void {
    const initial = create${pascal}InitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
  }

  /**
   * 加载本域数据。
   * P2 阶段实现：调用 api.ts 中的封装方法，成功后置 initialized 为 true。
   */
  async function load(): Promise<void> {
    throw new Error('${domain} 域 load() 尚未实现（P2 阶段实现）');
  }

  return {
    loading,
    error,
    initialized,
    ready,
    reset,
    load
  };
});
`;
}

function renderApi(domain, label, pascal, camel) {
  return `/**
 * ${label}（${domain}）域 API 封装外壳 —— scripts/scaffold-module.mjs 生成（P1-13）
 *
 * 约束：
 *   1. 全域只允许使用 @/services/api/client 暴露的唯一 axios 实例，禁止自行 axios.create；
 *   2. 方法签名先按「列表 / 详情 / 刷新」三类占位，具体端点登记在 README「后端端点清单」；
 *   3. 方法体在 P2 阶段实现，当前调用会抛出明确的未实现错误。
 */
import { apiClient } from '@/services/api/client';

/** 本域统一客户端引用：P2 阶段所有请求都经由此实例发起 */
export const ${camel}Client = apiClient;

/** 分页查询参数（外壳占位，P2 阶段按真实端点收窄） */
export interface ${pascal}ListQuery {
  page?: number;
  pageSize?: number;
  [key: string]: unknown;
}

/** 分页查询结果（外壳占位，P2 阶段按后端响应结构收窄） */
export interface ${pascal}ListResult<T = unknown> {
  items: T[];
  total: number;
}

/**
 * 查询${label}列表。
 * P2 阶段实现：经由 ${camel}Client 发起请求，端点见 README「后端端点清单」。
 */
export async function fetch${pascal}List(
  query?: ${pascal}ListQuery
): Promise<${pascal}ListResult> {
  throw new Error('fetch${pascal}List 尚未实现（P2 阶段实现）');
}

/**
 * 查询${label}详情。
 * P2 阶段实现：按 id 调用对应只读端点，并复用 store 中的缓存。
 */
export async function fetch${pascal}Detail(
  id: string | number
): Promise<unknown> {
  throw new Error('fetch${pascal}Detail 尚未实现（P2 阶段实现）');
}

/**
 * 刷新${label}缓存。
 * P2 阶段实现：调用 store 的 load()，并处理强制刷新参数。
 */
export async function refresh${pascal}(): Promise<void> {
  throw new Error('refresh${pascal} 尚未实现（P2 阶段实现）');
}
`;
}

function renderReadme(domain, label) {
  const extraNote =
    domain === 'growth'
      ? '\n> 本域是成就枢纽：**禁止 import 任何业务域**，只允许经事件总线消费后端行为事件。\n'
      : '';

  return `# ${label}（${domain}）域卡

> 由 scripts/scaffold-module.mjs 生成（P1-13）。当前状态：**外壳，功能还未开发**。
> 功能上线前，三端入口统一提示「功能还未开发，敬请期待」；下表在 P2 / P3 阶段逐项填充。
${extraNote}
## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| （P2 阶段填写） | | | 未实现 |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| （P2 阶段按 api_surface.json 填写） | | | |

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载 | 否 |
| error | string \\| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| （P2 阶段填写） | | | 未接入 |

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| （P2 阶段填写） | | | 未接入 |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 单元测试 | src/modules/${domain}/__tests__/ | 未创建（P2 阶段） |
| 外壳冒烟测试 | src/modules/__tests__/shells.spec.ts | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 入口可进入，未开发提示正确 | 未验收 |
| 平板 | 布局与路由正常，未开发提示正确 | 未验收 |
| 手机 | 布局与路由正常，未开发提示正确 | 未验收 |

## 附：「功能还未开发」说明

本域尚未开发完成：三端入口沿用统一服务提醒「功能还未开发，敬请期待」，
该提示在本域通过验收后移除；域卡表格同步更新为真实验收记录。
`;
}

function main() {
  const args = process.argv.slice(2);

  if (args.includes('--help') || args.includes('-h')) {
    printUsage();
    return;
  }

  if (args.length < 1) {
    printUsage(process.stderr);
    process.exit(1);
  }

  if (args.length > 2) {
    fail('参数过多：只接受 <domain-name> 与可选的 [中文模块名]。使用 --help 查看用法。');
  }

  const domain = args[0];
  const domainPattern = /^[a-z_][a-z0-9_-]*$/;

  if (!domainPattern.test(domain) || domain.length > 40) {
    fail(
      `非法域名 "${domain}"：必须为 kebab-case ASCII（小写字母、数字、连字符；` +
        '下划线仅用于临时测试域），且不超过 40 个字符。'
    );
  }

  const label = args[1] || DOMAIN_NAMES[domain] || domain;
  const pascal = toPascal(domain);
  const camel = toCamel(domain);

  if (!pascal) {
    fail(`无法从域名 "${domain}" 推导出合法的标识符。`);
  }

  const moduleDir = path.join(MODULES_DIR, domain);

  if (fs.existsSync(moduleDir)) {
    fail(`目标目录已存在，拒绝覆盖：${path.relative(ROOT, moduleDir)}`);
  }

  if (!Object.prototype.hasOwnProperty.call(DOMAIN_NAMES, domain)) {
    process.stderr.write(
      `[scaffold-module] 提示：${domain} 不在 17 个规划域中，将按通用外壳生成。\n`
    );
  }

  fs.mkdirSync(MODULES_DIR, { recursive: true });
  fs.mkdirSync(moduleDir);

  const files = [
    ['store.ts', renderStore(domain, label, pascal)],
    ['api.ts', renderApi(domain, label, pascal, camel)],
    ['events.ts', renderEvents(domain, label)],
    ['README.md', renderReadme(domain, label)]
  ];

  const created = [];
  for (const [name, content] of files) {
    const fullPath = path.join(moduleDir, name);
    fs.writeFileSync(fullPath, content, 'utf8');
    created.push(fullPath);
  }

  process.stdout.write(`[scaffold-module] 已生成 ${label}（${domain}）模块外壳：\n`);
  for (const filePath of created) {
    process.stdout.write(`  ${path.relative(ROOT, filePath).split(path.sep).join('/')}\n`);
  }
}

main();
