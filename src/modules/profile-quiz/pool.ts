/**
 * 备考画像 · 动态问题池
 *
 * 设计约束：
 * 1) 只使用后端 UserProfile 已存在的字段键，零后端改动（R11 安全）
 * 2) 同一字段准备多条问法，按 sessionId 轮换 —— 用户每次进来看到的问题不一样
 * 3) 步骤顺序在维度内轮换，避免答案顺序被记忆
 */

export type QuizFieldType = 'single' | 'multi' | 'text' | 'date' | 'slider' | 'textarea'
export type DimensionId = 'basic' | 'target' | 'level' | 'weakness' | 'habit' | 'self'

export interface QuizField {
  key: string
  label: string
  type: QuizFieldType
  options?: string[]
  min?: number
  max?: number
  placeholder?: string
}

export interface QuizStep {
  title: string
  dimension: DimensionId
  fields: QuizField[]
}

const GRADE_OPTS = ['大一', '大二', '大三', '大四', '已毕业', '研究生在读']
const LEVEL_OPTS = ['零基础', '了解一点', '有基础', '比较稳', '冲刺提分']
const SUBJECTS = ['行测·言语', '行测·判断', '行测·数量', '行测·资料', '申论', '公安专业科目']
const STYLE_OPTS = ['刷题为主', '看课为主', '背书为主', '错题复盘为主']
const SLOT_OPTS = ['清晨', '上午', '午休', '下午', '晚上', '深夜']
const REVIEW_OPTS = ['当天就复习', '隔一两天', '考前一天', '基本不复习']

/** 每个字段的多条问法（轮换用） */
const VARIANTS: Record<string, QuizField[]> = {
  grade: [
    { key: 'grade', label: '你现在是什么阶段？', type: 'single', options: GRADE_OPTS },
    { key: 'grade', label: '先确认一下年级，方便排节奏', type: 'single', options: GRADE_OPTS },
    { key: 'grade', label: '你目前读几年级？', type: 'single', options: GRADE_OPTS },
  ],
  exam_date: [
    { key: 'exam_date', label: '预计什么时候考试？', type: 'date' },
    { key: 'exam_date', label: '目标考试日期是哪天？', type: 'date' },
    { key: 'exam_date', label: '留给你还有多少时间？选个日期', type: 'date' },
  ],
  target_score: [
    { key: 'target_score', label: '目标分数大概多少？', type: 'text', placeholder: '如：行测 65 / 申论 60' },
    { key: 'target_score', label: '你心里的目标分是多少？', type: 'text', placeholder: '写个数字就行' },
    { key: 'target_score', label: '想考到什么水平？', type: 'text', placeholder: '如：总分 210' },
  ],
  daily_hours: [
    { key: 'daily_hours', label: '每天能挤出多少小时学习？', type: 'slider', min: 1, max: 12 },
    { key: 'daily_hours', label: '平均每天投入几小时？', type: 'slider', min: 1, max: 12 },
    { key: 'daily_hours', label: '你实际能保证的每日时长', type: 'slider', min: 1, max: 12 },
  ],
  self_level: [
    { key: 'self_level', label: '目前整体水平自评', type: 'single', options: LEVEL_OPTS },
    { key: 'self_level', label: '你觉得自己现在在哪个档？', type: 'single', options: LEVEL_OPTS },
    { key: 'self_level', label: '客观评价一下当前状态', type: 'single', options: LEVEL_OPTS },
  ],
  subject_weaknesses: [
    { key: 'subject_weaknesses', label: '哪些科目最让你头疼？（可多选）', type: 'multi', options: SUBJECTS },
    { key: 'subject_weaknesses', label: '薄弱项选一下，越准越好（可多选）', type: 'multi', options: SUBJECTS },
    { key: 'subject_weaknesses', label: '拖后腿的是哪几块？（可多选）', type: 'multi', options: SUBJECTS },
  ],
  subject_strengths: [
    { key: 'subject_strengths', label: '哪些科目你比较有底？（可多选）', type: 'multi', options: SUBJECTS },
    { key: 'subject_strengths', label: '强项盘点一下（可多选）', type: 'multi', options: SUBJECTS },
    { key: 'subject_strengths', label: '你有把握的是哪几门？（可多选）', type: 'multi', options: SUBJECTS },
  ],
  target_region: [
    { key: 'target_region', label: '意向报考地区（选填）', type: 'text', placeholder: '如：江苏南京' },
    { key: 'target_region', label: '想去哪个省市？（选填）', type: 'text', placeholder: '可留空' },
  ],
  target_post: [
    { key: 'target_post', label: '意向岗位方向（选填）', type: 'text', placeholder: '如：特警 / 交警 / 网安' },
    { key: 'target_post', label: '有想去的岗位吗？（选填）', type: 'text', placeholder: '可留空' },
  ],
  /** 习惯维度：复用 daily_hours 之外的既有字段语义由前端聚合，不新增列 */
  self_intro: [
    {
      key: 'self_intro',
      label: '用你自己的话说说学习情况（这一步最有用）',
      type: 'textarea',
      placeholder: '例如：白天上课，晚上 8-11 点能学；数量关系完全不会，资料分析还行；这周刚开始复习。',
    },
  ],
}

/** 维度 → 字段池（每维抽 1–2 题，轮换问法） */
const DIMENSIONS: { id: DimensionId; title: string; keys: string[] }[] = [
  { id: 'basic', title: '先认识一下你', keys: ['grade', 'target_region'] },
  { id: 'target', title: '定个靶子', keys: ['exam_date', 'target_score', 'target_post'] },
  { id: 'level', title: '自评一下当前水平', keys: ['self_level'] },
  { id: 'weakness', title: '强弱项盘点', keys: ['subject_weaknesses', 'subject_strengths'] },
  { id: 'habit', title: '你的学习节奏', keys: ['daily_hours'] },
  { id: 'self', title: '最后，说两句', keys: ['self_intro'] },
]

function hashSeed(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return Math.abs(h)
}

function rotate<T>(arr: T[], offset: number): T[] {
  if (!arr.length) return arr
  const n = ((offset % arr.length) + arr.length) % arr.length
  return arr.slice(n).concat(arr.slice(0, n))
}

export interface BuildStepsOptions {
  /** 每次进页面生成一个，靠它让问法轮换 */
  seed?: string
  /** 每维抽几题（默认维度全量） */
  perDimension?: number
}

/**
 * 构建本轮问卷步骤：问法轮换 + 维度内顺序轮换。
 * 不改变提交字段的含义，后端 upsert 无需改动。
 */
export function buildSteps(options: BuildStepsOptions = {}): QuizStep[] {
  const seed = options.seed || String(Date.now()) + Math.random()
  const base = hashSeed(seed)
  const perDim = options.perDimension ?? 2

  return DIMENSIONS.map((dim, di) => {
    const order = rotate(dim.keys, base + di * 7)
    const picked = order.slice(0, Math.max(1, Math.min(perDim, order.length)))
    const fields: QuizField[] = []
    for (const key of picked) {
      const list = VARIANTS[key] || []
      if (!list.length) continue
      fields.push(list[(base + di + key.length) % list.length])
    }
    return { title: dim.title, dimension: dim.id, fields }
  }).filter((s) => s.fields.length > 0)
}

/** 给步骤字段填初值 */
export function initialAnswers(steps: QuizStep[]): Record<string, any> {
  const out: Record<string, any> = {}
  for (const s of steps) {
    for (const f of s.fields) {
      if (f.type === 'multi') out[f.key] = []
      else if (f.type === 'slider') out[f.key] = f.min ?? 1
      else out[f.key] = ''
    }
  }
  return out
}

export const DEFAULT_OPTION_POOLS = { STYLE_OPTS, SLOT_OPTS, REVIEW_OPTS }
