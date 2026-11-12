/**
 * 「新建 / 改正文」弹窗的纯函数（S2，2026-11-12）。
 *
 * 为什么单独抽出来：这层最容易出"类型串味"的错 —— 卡片把富文本正文也提交、
 * 文章把卡片的背面塞进 content、编辑时把 subject/type 一起改了。规则要能单测。
 *
 * 后端契约（`POST /api/materials/admin`、`PUT /api/materials/admin/{id}`）：
 * 字段白名单 `subject/type/category/point_id/title/summary/content/card_front/
 * card_back/cover_image/video_id/duration/read_time/difficulty/badge/sort_order`；
 * 新建默认 `status=0`（未上架）；`content` 会被 `sanitize_html` 清洗。
 */

export type EditorMode = 'create' | 'edit';
export type EditorType = 'article' | 'lecture' | 'card';
export type EditorSubject = 'xingce' | 'shenlun' | 'gongzhuan';

export interface EditorForm {
  type: EditorType;
  subject: EditorSubject;
  title: string;
  summary: string;
  category: string;
  /** 富文本 HTML（文章/讲义） */
  content: string;
  /** 卡片正面 / 背面 / 封面（卡片） */
  cardFront: string;
  cardBack: string;
  cover: string;
  badge: string;
}

/** 卡片文本上限（与后端 `CARD_FRONT_MAX` / `CARD_BACK_MAX` 对齐） */
export const CARD_FRONT_MAX = 120;
export const CARD_BACK_MAX = 600;

export function emptyForm(subject: EditorSubject = 'gongzhuan'): EditorForm {
  return {
    type: 'article',
    subject,
    title: '',
    summary: '',
    category: '',
    content: '',
    cardFront: '',
    cardBack: '',
    cover: '',
    badge: ''
  };
}

/** 类型 → 需要哪些输入块（决定弹窗显示什么、提交什么） */
export function editorBlocks(type: EditorType): { richText: boolean; card: boolean } {
  return { richText: type !== 'card', card: type === 'card' };
}

/** 提交前校验：返回人类可读的错误列表（空数组 = 通过） */
export function validateEditor(form: EditorForm, mode: EditorMode = 'create'): string[] {
  const errs: string[] = [];
  if (!(form.title || '').trim()) errs.push('标题必填');
  if (mode === 'create' && !form.subject) errs.push('科目必选');
  if (form.type === 'card') {
    const front = (form.cardFront || '').trim();
    if (!front) errs.push('卡片正面必填');
    if (front.length > CARD_FRONT_MAX) errs.push(`卡片正面不能超过 ${CARD_FRONT_MAX} 字`);
    if ((form.cardBack || '').trim().length > CARD_BACK_MAX) errs.push(`卡片背面不能超过 ${CARD_BACK_MAX} 字`);
  } else if (!(form.content || '').replace(/<[^>]*>/g, '').trim()) {
    // 富文本空壳（`<p><br></p>`）不算有正文
    errs.push('正文不能为空（富文本里至少要有一段文字）');
  }
  return errs;
}

/**
 * 拼提交体。
 *
 * - **卡片**：只带 `card_front / card_back / cover_image`，不带 content/summary
 *   （卡片的价值在正反面，混进正文会让详情页渲染两套）；
 * - **文章/讲义**：带 `content / summary`，卡片三列一律不传；
 * - **编辑**：不带 `subject / type`（避免顺手把类型改掉，后端 partial 会照单全收）；
 * - 空字符串的摘要/分类/封面一律省略（后端 `v is not None` 会把空串当真值写进去）。
 */
export function buildMaterialPayload(
  form: EditorForm,
  mode: EditorMode = 'create'
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    title: (form.title || '').trim()
  };
  if (mode === 'create') {
    payload.subject = form.subject;
    payload.type = form.type;
  }
  const category = (form.category || '').trim();
  if (category) payload.category = category;
  const badge = (form.badge || '').trim();
  if (badge) payload.badge = badge;

  if (form.type === 'card') {
    payload.card_front = (form.cardFront || '').trim();
    const back = (form.cardBack || '').trim();
    if (back) payload.card_back = back;
    const cover = (form.cover || '').trim();
    if (cover) payload.cover_image = cover;
  } else {
    payload.content = form.content || '';
    const summary = (form.summary || '').trim();
    if (summary) payload.summary = summary;
  }
  return payload;
}
