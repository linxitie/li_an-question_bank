/**
 * 考试结果口径（唯一真源）—— 弹窗 / 结果页 / 成绩分析共用，避免"同一份成绩三种算法"。
 *
 * 背景（2026-11-11 用户真机验收发现）：
 *   · PC 交卷弹窗「正确/错误 97 / 0」把 `scored_count`（参与评分题数）当成了答对数；
 *   · 「正确率 2%」其实是**得分率** 2/97 取整，真实值是 2.06%；
 *   · 结果页按 `correct/details.length` 算，成绩分析按 `score/max` 算，三处精度还不一样。
 *
 * 口径（用户 2026-11-11 拍板）：
 *   得分     = 得分 / 满分                  → "2 / 97"
 *   得分率   = 得分 ÷ 满分，**保留两位小数**  → "2.06%"（旁注 "2 ÷ 97"）
 *   已答     = 有作答的题数 / 总题数          → "2 / 97"
 *   未答     = 总题数 - 已答（按错计）        → 95
 *   答对率   = 答对 ÷ 已答（明确"按已答"）     → "100%"
 */

export interface ExamSummaryInput {
  /** 得分 */
  score: number;
  /** 满分 */
  maxScore: number;
  /** 答对题数（is_correct=1） */
  correct: number;
  /** 答错题数（含空白，is_correct=0） */
  wrong: number;
  /** 未作答题数 */
  unanswered: number;
  /** 卷面总题数 */
  total: number;
  /** 已作答题数 */
  answered: number;
  /** 待人工评分题数（主观题） */
  manualPending?: number;
  /** 用时（秒，优先用服务端 time_used） */
  seconds?: number;
}

export interface ExamSummary {
  scoreText: string;
  rateText: string;
  rateRatioText: string;
  correctText: string;
  wrongText: string;
  answeredText: string;
  unansweredText: string;
  accuracyAnsweredText: string;
  timeText: string;
  pendingText: string;
}

/** 百分比，保留两位小数（2/97 → 2.06）；满分 0 时返回 0 */
export function percent2(part: number, whole: number): number {
  if (!whole || whole <= 0) return 0;
  return Math.round((part / whole) * 10000) / 100;
}

/** 秒 → "hh:mm:ss" 或 "mm:ss" */
export function formatDuration(seconds?: number | null): string {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

function num(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

/**
 * 组装展示口径。所有页面都应只调这个函数，不要再各自 `Math.round(...)`。
 */
export function buildExamSummary(input: ExamSummaryInput): ExamSummary {
  const score = num(input.score);
  const maxScore = num(input.maxScore);
  const total = num(input.total) || (num(input.correct) + num(input.wrong) + num(input.unanswered));
  const answered = num(input.answered) || Math.max(total - num(input.unanswered), 0);
  const correct = num(input.correct);
  const wrong = num(input.wrong);
  const unanswered = num(input.unanswered) || Math.max(total - answered, 0);
  const pending = num(input.manualPending);

  const rate = percent2(score, maxScore);
  const answeredAccuracy = answered > 0 ? percent2(correct, answered) : 0;
  // 「正确 / 错误」里的"错误"= **除答对之外的全部**（含未答）。
  // 为什么不用后端 wrong_count：只提交部分题时 wrong_count=0（空题没建明细），
  // 弹窗就会变成 "2 / 0"，比 97/0 更迷惑。用 total-correct 才是学生心里的"错"。
  const wrongIncludingBlank = Math.max(total - correct, 0);

  const fmtNum = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2));

  return {
    scoreText: `${fmtNum(score)} / ${fmtNum(maxScore)}`,
    rateText: `${rate}%`,
    rateRatioText: `${fmtNum(score)} ÷ ${fmtNum(maxScore)}`,
    correctText: String(correct),
    wrongText: String(wrongIncludingBlank),
    answeredText: `${answered} / ${total}`,
    unansweredText: String(unanswered),
    accuracyAnsweredText: answered > 0 ? `${answeredAccuracy}%` : '—',
    timeText: formatDuration(input.seconds),
    pendingText: pending > 0 ? `有 ${pending} 题待人工评分，当前分数不含它们` : ''
  };
}
