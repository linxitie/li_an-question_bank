/**
 * 批量导入的文件编排（B2，2026-11-07）—— 纯函数，便于单测。
 *
 * 需求：一次最多 50 个文件、总量 ≤2GB、**同名 docx + pdf 合并成一条资料**
 * （docx 当主文件、pdf 当附件）。
 *
 * 为什么把"编排"抽成纯函数：
 *   · 组队规则是业务规则（哪种组合算一条、谁当主文件），不该埋在组件模板里；
 *   · 队列里每个文件的成败要能单独重试，编排结果必须是**稳定可测**的数据结构；
 *   · 后续 C 批加"文件名解析元数据"时，只改这里，不动上传队列。
 */

/** 单批最多文件数（用户 2026-11-07 口径） */
export const MAX_BATCH_FILES = 50;
/** 单批总量上限：2 GB */
export const MAX_BATCH_BYTES = 2 * 1024 * 1024 * 1024;
/** 允许上传的原件扩展名（与后端 `material_files.ALLOWED_EXT_MIME` 对齐） */
export const ALLOWED_EXTS = ['docx', 'pdf', 'xlsx', 'doc', 'xls'] as const;
/** 参与双格式配对的两类 */
const PAIR_PRIMARY_EXT = 'docx';
const PAIR_ATTACH_EXT = 'pdf';

export type FileExt = (typeof ALLOWED_EXTS)[number];

export interface PickedFile {
  name: string;
  size: number;
}

export type IssueCode = 'empty' | 'too_many' | 'too_large' | 'unsupported' | 'repeated';
export interface SelectionIssue {
  code: IssueCode;
  message: string;
  file?: string;
}

export interface UploadGroup {
  /** 分组键：小写 base 名（同名 docx/pdf 会落到同一个 key） */
  key: string;
  /** 展示用 base 名（保留原始大小写） */
  label: string;
  primary: PickedFile;
  primaryExt: FileExt;
  attachment?: PickedFile & { ext: FileExt };
  kind: 'pair' | 'single';
}

/** `2019 北京公专.docx` → `{ base: '2019 北京公专', ext: 'docx' }` */
export function splitFileName(name: string): { base: string; ext: string } {
  const clean = (name || '').replace(/\\/g, '/').split('/').pop() || '';
  const dot = clean.lastIndexOf('.');
  if (dot <= 0) return { base: clean, ext: '' };
  return { base: clean.slice(0, dot), ext: clean.slice(dot + 1).toLowerCase() };
}

export function isAllowedExt(ext: string): ext is FileExt {
  return (ALLOWED_EXTS as readonly string[]).includes(ext);
}

/** 人读大小（与后端 `human_size` 口径一致，便于界面对照） */
export function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/** 数量 / 总量 / 扩展名校验（选择文件后立刻反馈，不等点上传） */
export function validateSelection(files: PickedFile[]): SelectionIssue[] {
  const issues: SelectionIssue[] = [];
  if (!files.length) issues.push({ code: 'empty', message: '还没有选择文件' });

  if (files.length > MAX_BATCH_FILES) {
    issues.push({
      code: 'too_many',
      message: `一次最多 ${MAX_BATCH_FILES} 个文件，当前选了 ${files.length} 个`
    });
  }
  const total = files.reduce((s, f) => s + (f.size || 0), 0);
  if (total > MAX_BATCH_BYTES) {
    issues.push({
      code: 'too_large',
      message: `总大小 ${humanBytes(total)} 超过 ${humanBytes(MAX_BATCH_BYTES)} 上限`
    });
  }
  for (const f of files) {
    const { ext } = splitFileName(f.name);
    if (!isAllowedExt(ext)) {
      issues.push({
        code: 'unsupported',
        message: `「${f.name}」格式不支持（只收 ${ALLOWED_EXTS.join(' / ')}）`,
        file: f.name
      });
    }
  }
  return issues;
}

/**
 * 把选中的文件编排成上传组。
 *
 * 规则（确定性，顺序稳定）：
 *   1. 同 base 名（忽略大小写）的 **docx + pdf** → 一个 `pair` 组，docx 当主文件、pdf 当附件；
 *   2. 只有 docx 或只有 pdf → `single` 组；
 *   3. xlsx/doc/xls → `single` 组（不参与配对）；
 *   4. 同 base 同扩展名重复选中 → 只取第一个，其余记为 `repeated`（不静默丢）；
 *   5. 扩展名不支持 → 不进组，记 `unsupported`。
 */
export function planUploadGroups(files: PickedFile[]): {
  groups: UploadGroup[];
  issues: SelectionIssue[];
} {
  const issues: SelectionIssue[] = [];
  const buckets = new Map<string, PickedFile[]>();
  const order: string[] = [];
  const labels = new Map<string, string>();

  for (const f of files) {
    const { base, ext } = splitFileName(f.name);
    if (!isAllowedExt(ext)) {
      issues.push({
        code: 'unsupported',
        message: `「${f.name}」格式不支持（只收 ${ALLOWED_EXTS.join(' / ')}）`,
        file: f.name
      });
      continue;
    }
    const key = base.trim().toLowerCase();
    if (!buckets.has(key)) {
      buckets.set(key, []);
      order.push(key);
      labels.set(key, base.trim());
    }
    buckets.get(key)!.push({ ...f, name: f.name });
  }

  const groups: UploadGroup[] = [];
  for (const key of order) {
    const list = buckets.get(key)!;
    const byExt = new Map<string, PickedFile>();
    for (const f of list) {
      const ext = splitFileName(f.name).ext;
      if (byExt.has(ext)) {
        issues.push({
          code: 'repeated',
          message: `「${f.name}」与同名同类型文件重复，只上传第一个`,
          file: f.name
        });
        continue;
      }
      byExt.set(ext, f);
    }

    const docx = byExt.get(PAIR_PRIMARY_EXT);
    const pdf = byExt.get(PAIR_ATTACH_EXT);
    if (docx && pdf) {
      groups.push({
        key,
        label: labels.get(key)!,
        primary: docx,
        primaryExt: PAIR_PRIMARY_EXT,
        attachment: { ...pdf, ext: PAIR_ATTACH_EXT },
        kind: 'pair'
      });
      byExt.delete(PAIR_PRIMARY_EXT);
      byExt.delete(PAIR_ATTACH_EXT);
    }

    // 剩下的（未配对上的单文件、以及 xlsx/doc/xls）各自成组。
    // 配对成功后 docx/pdf 已从 byExt 移除，这里不会重复出组。
    for (const [ext, f] of byExt) {
      groups.push({
        key: `${key}::${ext}`,
        label: labels.get(key)!,
        primary: f,
        primaryExt: ext as FileExt,
        kind: 'single'
      });
    }
  }

  return { groups, issues };
}

/** 汇总一次编排的规模，用于界面提示「将创建 N 条资料」 */
export function summarize(groups: UploadGroup[]): {
  materials: number;
  files: number;
  bytes: number;
  pairs: number;
} {
  let files = 0;
  let bytes = 0;
  let pairs = 0;
  for (const g of groups) {
    files += g.attachment ? 2 : 1;
    bytes += g.primary.size + (g.attachment?.size || 0);
    if (g.kind === 'pair') pairs += 1;
  }
  return { materials: groups.length, files, bytes, pairs };
}
