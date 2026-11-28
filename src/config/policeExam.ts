/**
 * 公安联考考试日期（手机端倒计时用）。
 *
 * 每年官方公告发布后，在这里追加下一年日期即可；不要写死单个 2027 日期。
 * 日期格式：YYYY-MM-DD（本地日历日，不含时区）。
 * 如果列表里没有未来日期，getNextPoliceExamDate 会回退到下一年 1 月 16 日并打印警告。
 */
export const POLICE_EXAM_DATES = [
  '2027-01-16',
  '2028-01-15',
  '2029-01-13',
  '2030-01-12'
];

export interface PoliceExamInfo {
  date: Date;
  iso: string;
  daysLeft: number;
  fallback: boolean;
}

function atMidnight(y: number, m: number, d: number): Date {
  return new Date(y, m - 1, d, 0, 0, 0, 0);
}

export function getNextPoliceExamDate(now: Date = new Date()): PoliceExamInfo {
  const today = atMidnight(now.getFullYear(), now.getMonth() + 1, now.getDate());
  for (const iso of POLICE_EXAM_DATES) {
    const parts = iso.split('-').map(Number);
    if (parts.length !== 3) continue;
    const date = atMidnight(parts[0], parts[1], parts[2]);
    if (date.getTime() >= today.getTime()) {
      return {
        date,
        iso,
        daysLeft: Math.ceil((date.getTime() - today.getTime()) / 86400000),
        fallback: false
      };
    }
  }
  // 日期表未维护到下一年时给出可预计的回退值，避免页面空白；请及时补充配置。
  const year = now.getFullYear() + 1;
  const date = atMidnight(year, 1, 16);
  console.warn('[police-exam] 未找到未来考试日期，回退到 ' + year + '-01-16，请更新 POLICE_EXAM_DATES');
  return {
    date,
    iso: year + '-01-16',
    daysLeft: Math.ceil((date.getTime() - today.getTime()) / 86400000),
    fallback: true
  };
}

export function formatPoliceExamDate(info: PoliceExamInfo): string {
  return info.date.getFullYear() + '年' + (info.date.getMonth() + 1) + '月' + info.date.getDate() + '日';
}
