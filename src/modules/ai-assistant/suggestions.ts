/**
 * 联考小智（ai-assistant）—— 推荐问题池（A2「动态问题」前端实现）
 *
 * 方案：纯前端固定池轮换（航少 2026-11-13 选定方案 a）。
 * 不新增后端端点、不改 /api/llm/* 契约，343 端点基线不动。
 *
 * 用法（供后续接入 ai_chat.vue 的 <script> 或 store 使用）：
 *   import { nextSuggestions } from './suggestions';
 *   const list = nextSuggestions({ sessionId: 1, exclude: [] });
 *
 * 红线：本文件不涉及 .vtj 页面的 <template>，仅纯 TS 逻辑，可安全由 AI 维护。
 */

/** 推荐问题分组 —— 对应域卡定义的三类能力：心理调整 / 疑难解答 / 提升建议 */
export const SUGGESTION_POOL = {
  /** 心理调整：备考焦虑、时间压力、状态管理 */
  mental: [
    '最近总觉得自己复习不完，一坐下来就心慌，怎么办？',
    '联考还有几个月，我每天学不进去，是不是没救了？',
    '模考成绩忽高忽低，我该怎么稳住心态？',
    '看到同学进度比我快就焦虑，怎么调整？',
    '一到大考前一晚就睡不着，有什么办法？',
  ],
  /** 疑难解答：题型、知识点、方法困惑 */
  question: [
    '逻辑判断里的削弱加强题总是选错，有什么判断顺序？',
    '资料分析我算得慢，有没有提速的办法？',
    '申论大作文的开头怎么写才不套路？',
    '数量关系要不要放弃？怎么取舍？',
    '常识判断该怎么积累比较有效？',
  ],
  /** 提升建议：复习计划、复盘、方法优化 */
  advice: [
    '帮我看看现阶段该主攻哪个模块？',
    '我每天只有三小时，复习顺序应该怎么排？',
    '错题本要怎么用才真的有用？',
    '怎么判断一个模块该继续练还是该放弃？',
    '每周复盘应该复盘哪些东西？',
  ],
} as const;

export type SuggestionCategory = keyof typeof SUGGESTION_POOL;

/** 一次推荐展示的条数 */
export const SUGGESTION_BATCH_SIZE = 3;

interface NextSuggestionsOptions {
  /** 会话标识 —— 同一会话内轮换位置稳定，不同会话起点错开 */
  sessionId?: number | null;
  /** 已展示或已点击过的文本，避免重复推送 */
  exclude?: string[];
  /** 每批条数，默认 SUGGESTION_BATCH_SIZE */
  size?: number;
  /** 指定分类；不传则三类混排 */
  category?: SuggestionCategory;
}

/**
 * 计算一个可复现的起始偏移。
 * 用 sessionId 做种子，保证同一会话刷新后推荐不跳变；无会话时按时间轮换。
 */
function startOffset(sessionId: number | null | undefined, total: number): number {
  if (total <= 0) return 0;
  if (typeof sessionId === 'number' && Number.isFinite(sessionId)) {
    return Math.abs(Math.trunc(sessionId)) % total;
  }
  return Math.floor(Date.now() / 1000) % total;
}

/**
 * 取下一批推荐问题。
 * - 过滤 exclude 中已出现的文本
 * - 环形轮换，保证同会话每次调用尽量不同
 * - 候选不足时原样返回剩余，不补假数据
 */
export function nextSuggestions(options: NextSuggestionsOptions = {}): string[] {
  const { sessionId = null, exclude = [], size = SUGGESTION_BATCH_SIZE, category } = options;

  const source: readonly string[] = category
    ? SUGGESTION_POOL[category]
    : [...SUGGESTION_POOL.mental, ...SUGGESTION_POOL.question, ...SUGGESTION_POOL.advice];

  const excluded = new Set(exclude.filter(Boolean));
  const candidates = source.filter((item) => !excluded.has(item));
  if (candidates.length === 0) return [];

  const offset = startOffset(sessionId, candidates.length);
  const picked: string[] = [];
  const limit = Math.min(Math.max(size, 0), candidates.length);

  for (let i = 0; i < limit; i += 1) {
    picked.push(candidates[(offset + i) % candidates.length]);
  }
  return picked;
}

/** 首次进入会话时的开场问候，与推荐问题一起展示 */
export const OPENING_HINT = '我是联考小智。复习卡住了、心里发慌了，都可以直接问我。';
