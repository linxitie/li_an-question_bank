/**
 * 登录被设备准入拒绝时的统一引导（P2，2026-11-16）
 *
 * 为什么要独立成模块：三个登录页（PC / 平板 / 手机）都是 `.vtj` 页面，
 * 按 R3 只能改 `<script>`，不能动 `<template>`；把"弹窗 + 跳电脑端"做成一个函数，
 * 三个页面各加一行调用即可，避免三份重复实现与三份文案漂移。
 *
 * 触发条件：后端 403（`error.code=DEVICE_FORBIDDEN`）或文案里出现"电脑端/仅支持学生"。
 * 交互：确认框「去电脑端登录」→ 整页跳 `/#/login`（用整页跳转而不是 router.push，
 * 因为平板/手机上被判定为设备端时，前端守卫会把 `/login` 再映射回 `/tablet/login`，
 * 整页跳 + 电脑端访问才是正确路径）。
 */
import { ElMessageBox } from 'element-plus'
import { PC_LOGIN_PATH, isDeviceDeniedMessage } from '@/router/loginPolicy'

export { isDeviceDeniedMessage }

/** 弹「管理员/该角色仅支持电脑端」并可选跳转；返回用户是否选择去电脑端 */
export async function guideToPcLogin(message?: string, options?: { autoJump?: boolean }): Promise<boolean> {
  const text = message && message.trim()
    ? message.trim()
    : '管理员仅支持电脑端登录，请改用电脑访问'
  try {
    await ElMessageBox.confirm(
      `${text}\n\n电脑端登录地址：${PC_LOGIN_PATH}`,
      '请使用电脑端登录',
      {
        confirmButtonText: '去电脑端登录',
        cancelButtonText: '知道了',
        type: 'warning',
        distinguishCancelAndClose: true,
      }
    )
  } catch (e) {
    return false
  }
  if (options?.autoJump !== false) {
    window.location.href = `${window.location.origin}${PC_LOGIN_PATH}`
  }
  return true
}
