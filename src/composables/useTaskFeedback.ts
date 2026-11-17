/**
 * 任务反馈（模块4 · 4-5）：勾选任务时给一声轻响 + 卡片弹一下。
 *
 * 设计取舍：
 * - 不用音频文件，用 Web Audio 现场合成，省静态资源；
 * - 不加模板结构，靠捕获阶段点击 + closest('.task-item') 定位卡片，
 *   避免改 .vtj 模板（R3）；
 * - 尊重 prefers-reduced-motion 与静音偏好。
 */

let ctx: AudioContext | null = null
let muted = false
let listenerBound = false
let styleInjected = false

const STYLE_ID = 'li-an-task-feedback-style'

function ensureStyle(): void {
  if (styleInjected || typeof document === 'undefined') return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
    @keyframes liAnTaskPulse {
      0% { transform: scale(1); }
      35% { transform: scale(1.018); }
      100% { transform: scale(1); }
    }
    .li-an-task-pulse { animation: liAnTaskPulse 320ms cubic-bezier(0.22, 1, 0.36, 1); }
    @media (prefers-reduced-motion: reduce) {
      .li-an-task-pulse { animation: none; }
    }
  `
  document.head.appendChild(style)
  styleInjected = true
}

function audio(): AudioContext | null {
  if (muted || typeof window === 'undefined') return null
  try {
    if (!ctx) {
      const Ctor = window.AudioContext || (window as any).webkitAudioContext
      if (!Ctor) return null
      ctx = new Ctor()
    }
    if (ctx.state === 'suspended') ctx.resume().catch(() => {})
    return ctx
  } catch (e) {
    return null
  }
}

/** done=true 用上行两音（完成），false 用下行一音（取消） */
export function playTaskTick(done: boolean): void {
  const ac = audio()
  if (!ac) return
  const now = ac.currentTime
  const freqs = done ? [880, 1174.66] : [523.25]
  freqs.forEach((f, i) => {
    const osc = ac.createOscillator()
    const gain = ac.createGain()
    osc.type = 'sine'
    osc.frequency.value = f
    const t0 = now + i * 0.07
    gain.gain.setValueAtTime(0, t0)
    gain.gain.linearRampToValueAtTime(0.12, t0 + 0.01)
    gain.gain.exponentialRampToValueAtTime(0.001, t0 + 0.18)
    osc.connect(gain).connect(ac.destination)
    osc.start(t0)
    osc.stop(t0 + 0.2)
  })
}

function pulse(el: Element | null): void {
  if (!el) return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  el.classList.remove('li-an-task-pulse')
  // 强制重排，保证连续点击也能重新触发动画
  void (el as HTMLElement).offsetWidth
  el.classList.add('li-an-task-pulse')
  setTimeout(() => el.classList.remove('li-an-task-pulse'), 360)
}

/**
 * 绑定一次全局点击监听：命中任务卡的勾选区域时给反馈。
 * 只认 .task-item 内的点击，其它地方不打扰。
 */
export function bindTaskFeedback(): void {
  if (listenerBound || typeof document === 'undefined') return
  listenerBound = true
  ensureStyle()
  document.addEventListener(
    'click',
    (e) => {
      const target = e.target as Element | null
      if (!target || !target.closest) return
      const card = target.closest('.task-item')
      if (!card) return
      // 只在勾选区域或勾选按钮上触发，避免点标题也响
      const isCheck = target.closest('.task-check') || target.closest('.task-checkbox')
      if (!isCheck) return
      const done = !(card.classList.contains('done') || card.classList.contains('is-done'))
      playTaskTick(done)
      pulse(card)
    },
    true,
  )
}

/** 静音开关（可在设置里接） */
export function setTaskFeedbackMuted(value: boolean): void {
  muted = !!value
}
