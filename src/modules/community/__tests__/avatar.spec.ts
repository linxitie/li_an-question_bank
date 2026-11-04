import { describe, expect, it } from 'vitest';
import { avatarInitial } from '../avatar';

describe('avatarInitial', () => {
  it('纯数字学号不显示数字，回退为友', () => {
    expect(avatarInitial('202516001')).toBe('友');
  });

  it('中文昵称取第一个汉字', () => {
    expect(avatarInitial('张三')).toBe('张');
  });

  it('数字开头的混合昵称取第一个汉字', () => {
    expect(avatarInitial('2025张三')).toBe('张');
  });

  it('英文昵称取首字母并大写', () => {
    expect(avatarInitial('alice')).toBe('A');
  });

  it('空值回退为友', () => {
    expect(avatarInitial('')).toBe('友');
    expect(avatarInitial(null)).toBe('友');
    expect(avatarInitial('   ')).toBe('友');
  });
});
