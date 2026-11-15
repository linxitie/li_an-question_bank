/**
 * 批量改信息（D7，2026-11-15）的纯函数。
 *
 * 为什么抽出来：三个字段"留空=不改"的语义 + "一项都没改就别发请求"这条拦截，
 * 写在组件里既测不到也容易写错（发一个空 body 会被后端 400）。
 */

export interface BatchMetaForm {
  /** '' = 不改；xingce / shenlun / gongzhuan */
  subject: string;
  /** '' = 不改；非空 = 写入该分类 */
  category: string;
  /** '' = 不改；exam / library / both（仅试卷类生效） */
  placement: string;
}

export interface BatchMetaPayload {
  ids: number[];
  subject?: string;
  category?: string;
  placement?: string;
}

export const BATCH_META_EMPTY: BatchMetaForm = { subject: '', category: '', placement: '' };

/** 表单里有没有"改过"的字段（用于禁用提交按钮 / 提示）。 */
export function hasBatchMetaChange(form: BatchMetaForm): boolean {
  return Boolean((form.subject || '').trim() || (form.category || '').trim() || (form.placement || '').trim());
}

/**
 * 组装请求体：只带改过的字段；一项都没改返回 null（调用方提示"至少选一项"）。
 * ids 原样透传（去重与上限由后端兜底）。
 */
export function buildBatchMetaPayload(
  ids: number[],
  form: BatchMetaForm
): BatchMetaPayload | null {
  if (!ids || ids.length === 0) return null;
  const payload: BatchMetaPayload = { ids: [...ids] };
  const subject = (form.subject || '').trim();
  const category = (form.category || '').trim();
  const placement = (form.placement || '').trim();
  if (subject) payload.subject = subject;
  if (category) payload.category = category;
  if (placement) payload.placement = placement;
  const changed = Boolean(payload.subject || payload.category || payload.placement);
  return changed ? payload : null;
}
