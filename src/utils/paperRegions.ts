/**
 * 地区词表（C2b，2026-11-08）——**与后端保持同一套代码**。
 *
 * 后端权威：`backend/app/services/paper_meta_parser.py` 的 `REGIONS`。
 * 这里只做下拉选项，不在前端做校验（提交后端，未知地区会 400 并把原因带回来）。
 * 加省份时**两边一起改**；`paperRegions.spec.ts` 有一条快照用例防止漏改。
 */
export interface RegionOption {
  code: string;
  name: string;
}

export const PAPER_REGIONS: RegionOption[] = [
  { code: 'BJ', name: '北京' },
  { code: 'JS', name: '江苏' },
  { code: 'ZJ', name: '浙江' },
  { code: 'GD', name: '广东' },
  { code: 'SD', name: '山东' },
  { code: 'SH', name: '上海' },
  { code: 'TJ', name: '天津' },
  { code: 'CQ', name: '重庆' },
  { code: 'HE', name: '河北' },
  { code: 'HA', name: '河南' },
  { code: 'HB', name: '湖北' },
  { code: 'HN', name: '湖南' },
  { code: 'SC', name: '四川' },
  { code: 'FJ', name: '福建' },
  { code: 'AH', name: '安徽' },
  { code: 'JX', name: '江西' },
  { code: 'SX', name: '山西' },
  { code: 'SN', name: '陕西' },
  { code: 'LN', name: '辽宁' },
  { code: 'JL', name: '吉林' },
  { code: 'HLJ', name: '黑龙江' },
  { code: 'GX', name: '广西' },
  { code: 'YN', name: '云南' },
  { code: 'GZ', name: '贵州' },
  { code: 'NM', name: '内蒙古' },
  { code: 'GS', name: '甘肃' },
  { code: 'XJ', name: '新疆' },
  { code: 'NX', name: '宁夏' },
  { code: 'QH', name: '青海' },
  { code: 'HI', name: '海南' },
  { code: 'XZ', name: '西藏' },
  { code: 'GK', name: '国考' },
  { code: 'LK', name: '联考' },
];

/** 卷别：T 题本 / A 答案 / J 解析（与后端 BOOK_KINDS 同构） */
export const BOOK_KINDS: RegionOption[] = [
  { code: 'T', name: '题本' },
  { code: 'A', name: '答案' },
  { code: 'J', name: '解析' },
];

export function regionNameOf(code: string | null | undefined): string {
  return PAPER_REGIONS.find((r) => r.code === (code || ''))?.name || '';
}

export function regionCodeOf(name: string | null | undefined): string {
  return PAPER_REGIONS.find((r) => r.name === (name || ''))?.code || '';
}
