/**
 * D1（2026-11-14）：判断「资料上架」与「关联卷发布」是否一致。
 *
 * 背景：有 4 处旧入口会直接写 `paper.paper_type = "PUBLISHED"`（papers / paper_generation /
 * admin_approval / teacher），绕过 P5 的单向同步，会把库带成两种错态：
 *   ① 卷已发布、资料未上架 → 学生能考，但资料库里看不到原卷；
 *   ② 资料已上架、卷未发布 → 资料看得到，考试页却没有这张卷。
 * 本轮不改那 4 处（要单独收敛），先在列表上把不一致**标出来**，避免"静默错"。
 *
 * 纯函数：不碰 DOM / 请求，便于单测。
 */

export type DriftKind = '' | 'paper_public' | 'material_public';

export interface DriftInput {
  type?: string | null;
  status?: number | null;
  exam?: {
    known?: boolean;
    published?: boolean | null;
    paper_type?: string | null;
  } | null;
}

export interface DriftResult {
  kind: DriftKind;
  label: string;
  hint: string;
}

const EMPTY: DriftResult = { kind: '', label: '', hint: '' };

/**
 * @returns `kind='paper_public'` 卷已发布但资料未上架；
 *          `kind='material_public'` 资料已上架但卷未发布；否则空。
 */
export function paperDrift(row: DriftInput): DriftResult {
  const exam = row.exam;
  // 只有「试卷 + 已建卷」才谈得上漂移；卡片/文章/讲义、未建卷（known=false）一律不管
  if (row.type !== 'paper' || !exam || !exam.known) return EMPTY;
  const paperType = String(exam.paper_type || '').toUpperCase();
  // ENDED = 历史卷：学生本就看不到，原卷仍可挂资料库，不算不一致
  if (paperType === 'ENDED') return EMPTY;

  const paperPublic = paperType === 'PUBLISHED' || exam.published === true;
  const materialPublic = Number(row.status) === 1;
  if (paperPublic === materialPublic) return EMPTY;

  if (paperPublic) {
    return {
      kind: 'paper_public',
      label: '上架不一致',
      hint: '学生已能考这张卷，但资料库里看不到它的原卷。'
        + '处置：把这个资料「上架」（=审批通过），或把卷撤回草稿。'
    };
  }
  return {
    kind: 'material_public',
    label: '上架不一致',
    hint: '资料能看到，但考试页不出现这张卷。'
      + '若本意是「只放资料页」，把投放位改成「仅资料页」；否则把卷发布。'
  };
}
