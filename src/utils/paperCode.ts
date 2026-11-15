/**
 * 试卷编号与「建卷」入口的纯函数（D10，2026-11-15）。
 *
 * 为什么抽出来：这几个判定散在 `materials.vue` 里时没人能单测，而它们正好是
 * 今天那条死路的根：编号只读 `badge`、"没编号就不显示建卷按钮"、无编号时静默 return。
 */

export interface PaperCodeSource {
  paper_code?: string | null;
  badge?: string | null;
}

export interface BuildPaperSource extends PaperCodeSource {
  id: number;
  type?: string | null;
  exam?: { known?: boolean } | null;
  paper_code_suggest?: string | null;
}

/** 试卷编号：`paper_code` 优先（C2b 之后写这一列），回落 `badge`（老数据）。 */
export function paperCodeOf(row: PaperCodeSource): string {
  return (row.paper_code || row.badge || '').trim();
}

/**
 * 要不要显示「建卷」：试卷类 + 还没有可作答卷。
 *
 * **不再要求"有编号"** —— 没编号时点开是"先补编号"的引导；
 * 以前这里要求编号，于是没编号的资料连入口都没有（material 139）。
 */
export function canBuildPaper(row: BuildPaperSource): boolean {
  return row.type === 'paper' && !row.exam?.known;
}

/** 建议编号：后端给了就用后端的（标题解析优先），否则本地兜底 `MAT-{YYYYMMDD}-{id}`。 */
export function suggestPaperCode(row: BuildPaperSource, now: Date = new Date()): string {
  const given = (row.paper_code_suggest || '').trim();
  if (given) return given;
  const ymd = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(
    now.getDate()
  ).padStart(2, '0')}`;
  return `MAT-${ymd}-${row.id}`;
}

/** 编号合法性：字母/数字/`-`/`_`，3–40 位（与后端 `paper_code[:40]` 对齐）。 */
export function isValidPaperCode(value: string): boolean {
  return /^[A-Za-z0-9_-]{3,40}$/.test((value || '').trim());
}
