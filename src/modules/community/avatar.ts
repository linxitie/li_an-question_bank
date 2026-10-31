/**
 * 论坛头像文字回退。
 *
 * 昵称可能是纯数字（例如学号 202516001），直接 charAt(0) 会得到“2”，
 * 不能作为可读头像。优先取第一个汉字，其次取第一个英文字母，最后回退“友”。
 */
export function avatarInitial(name?: string | null): string {
  const text = (name || '').trim();
  if (!text) return '友';

  const han = text.match(/[\u4e00-\u9fa5]/);
  if (han) return han[0];

  const letter = text.match(/[A-Za-z]/);
  if (letter) return letter[0].toUpperCase();

  return '友';
}
