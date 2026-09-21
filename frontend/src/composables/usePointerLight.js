/**
 * 卡片表面的指针光效。
 *
 * 把「指针在卡片上的位置」翻译成三样东西：一层跟着走的浅光、一点极克制的 3D 倾斜、
 * 以及登录按钮的磁吸。卡片因此是一块会被手推动的板子，而不是一张静态的图。
 *
 * 只在「有精确指针 + 未开启减弱动态效果」的设备上装。触屏和无障碍场景下整块退回静态外观，
 * 输入、按钮、键盘操作完全不受影响（装饰层都是 pointer-events: none）。
 *
 * 平滑策略分两套：
 *   - 光斑位置用自己的一条 rAF 循环做指数趋近，值收敛后循环自己停下，不常驻空转；
 *   - 变换类属性（倾斜、位移）交给 GSAP quickTo，它内部复用同一条补间，
 *     pointermove 高频触发也不会堆出成百上千条补间。
 */
import { onBeforeUnmount, onMounted, ref, toValue, watch } from 'vue'
import gsap from 'gsap'

/** 倾斜幅度（度）。刻意压小：先看见内容，再察觉到动 */
const TILT_Y = 3.4
const TILT_X = 2.2
/** 吉祥物跟着指针挪的横向距离（px） */
const MASCOT_X = 3.5
/** 按钮被指针吸过去的距离（px）与作用半径 */
const MAGNET = 4.5
const MAGNET_RANGE = 150
/** 光斑趋近系数：越大越跟手，越小越黏 */
const FOLLOW = 0.16

export function usePointerLight({ card, mascot, magnetTarget, reducedMotion }) {
  /** 是否装上了指针光效。触屏 / 减弱动态效果下为 false，卡片保持静态 */
  const active = ref(false)

  /**
   * reducedMotion 可以传 ref（跟随系统设置实时变化）也可以传普通布尔。
   * 用 toValue 统一取值，调用方不必关心是哪种。
   */
  function still() {
    return toValue(reducedMotion) === true
  }

  /** 装了才有东西可拆；触屏和减弱动态效果下从头到尾没装过 */
  function canInstall() {
    if (!card.value || still()) return false
    return window.matchMedia?.('(hover: hover) and (pointer: fine)').matches ?? false
  }

  const target = { x: 0.5, y: 0.5 }
  const current = { x: 0.5, y: 0.5 }
  let frame = 0
  let box = null
  let magnetBox = null
  let settle = null
  let magnetTo = null
  let observer = null

  /** 把当前光斑位置写成卡片上的 CSS 变量，样式层只读这些变量 */
  function paint() {
    const el = card.value
    if (!el) return
    el.style.setProperty('--mx', `${(current.x * 100).toFixed(2)}%`)
    el.style.setProperty('--my', `${(current.y * 100).toFixed(2)}%`)
    // 光斑落在指针处，投影就被推向反方向，卡片才有「被灯照着」的厚度
    el.style.setProperty('--sh-x', `${((0.5 - current.x) * 10).toFixed(2)}px`)
    el.style.setProperty('--sh-y', `${((0.5 - current.y) * 8).toFixed(2)}px`)
  }

  function follow() {
    frame = 0
    const dx = target.x - current.x
    const dy = target.y - current.y
    if (Math.abs(dx) < 0.0008 && Math.abs(dy) < 0.0008) {
      current.x = target.x
      current.y = target.y
      paint()
      return
    }
    current.x += dx * FOLLOW
    current.y += dy * FOLLOW
    paint()
    frame = requestAnimationFrame(follow)
  }

  function wake() {
    if (!frame) frame = requestAnimationFrame(follow)
  }

  /** 量一次卡片与按钮的位置。卡片尺寸只在报错条出现/消失时变，交给 ResizeObserver 触发 */
  function measure() {
    const el = card.value
    if (!el) return
    box = el.getBoundingClientRect()
    const magnetEl = magnetTarget?.value
    magnetBox = magnetEl?.getBoundingClientRect() ?? null
  }

  /** 指针离按钮越近，按钮越往指针那边偏一点 —— 偏几个像素，手感到就够了 */
  function pullTo(px, py) {
    if (!magnetTo || !magnetBox) return
    const cx = magnetBox.left + magnetBox.width / 2
    const cy = magnetBox.top + magnetBox.height / 2
    const dx = px - cx
    const dy = py - cy
    const distance = Math.hypot(dx, dy)
    if (distance > MAGNET_RANGE) {
      magnetTo.x(0)
      magnetTo.y(0)
      return
    }
    const force = (1 - distance / MAGNET_RANGE) ** 1.4
    const unit = distance < 1 ? 0 : 1 / distance
    magnetTo.x(dx * unit * force * MAGNET)
    magnetTo.y(dy * unit * force * MAGNET * 0.55)
  }

  function onMove(event) {
    if (!box) return
    const x = gsap.utils.clamp(0, 1, (event.clientX - box.left) / box.width)
    const y = gsap.utils.clamp(0, 1, (event.clientY - box.top) / box.height)
    target.x = x
    target.y = y
    wake()

    settle?.tiltY(-(x - 0.5) * 2 * TILT_Y)
    settle?.tiltX((y - 0.5) * 2 * TILT_X)
    settle?.mascot((x - 0.5) * 2 * MASCOT_X)
    pullTo(event.clientX, event.clientY)
  }

  function onEnter(event) {
    measure()
    card.value?.style.setProperty('--lit', '1')
    onMove(event)
  }

  /** 指针离开就全部回中：光斑淡出、卡片回到水平、按钮归位 */
  function onLeave() {
    card.value?.style.setProperty('--lit', '0')
    target.x = 0.5
    target.y = 0.5
    wake()
    settle?.tiltX(0)
    settle?.tiltY(0)
    settle?.mascot(0)
    magnetTo?.x(0)
    magnetTo?.y(0)
  }

  function install() {
    if (active.value || !canInstall()) return
    const el = card.value
    settle = {
      tiltX: gsap.quickTo(el, 'rotationX', { duration: 0.7, ease: 'power3' }),
      tiltY: gsap.quickTo(el, 'rotationY', { duration: 0.7, ease: 'power3' }),
      mascot: mascot?.value
        ? gsap.quickTo(mascot.value, 'x', { duration: 0.7, ease: 'power3' })
        : null,
    }
    const magnetEl = magnetTarget?.value
    magnetTo = magnetEl
      ? {
          x: gsap.quickTo(magnetEl, 'x', { duration: 0.5, ease: 'power3' }),
          y: gsap.quickTo(magnetEl, 'y', { duration: 0.5, ease: 'power3' }),
        }
      : null

    paint()
    el.addEventListener('pointerenter', onEnter)
    el.addEventListener('pointermove', onMove)
    el.addEventListener('pointerleave', onLeave)
    observer = new ResizeObserver(measure)
    observer.observe(el)
    active.value = true
  }

  /**
   * 拆干净：监听、rAF、补间全部收掉，并把倾斜、位移、光斑复位成静态外观，
   * 否则打开「减弱动态效果」的瞬间卡片会停在最后一次倾斜的角度上。
   */
  function teardown() {
    if (!active.value) return
    active.value = false

    if (frame) cancelAnimationFrame(frame)
    frame = 0
    observer?.disconnect()
    observer = null

    const el = card.value
    el?.removeEventListener('pointerenter', onEnter)
    el?.removeEventListener('pointermove', onMove)
    el?.removeEventListener('pointerleave', onLeave)

    const targets = [el, mascot?.value, magnetTarget?.value].filter(Boolean)
    gsap.killTweensOf(targets)
    gsap.set(targets, { clearProps: 'transform' })
    if (el) {
      for (const name of ['--mx', '--my', '--sh-x', '--sh-y', '--lit']) el.style.removeProperty(name)
    }

    settle = null
    magnetTo = null
  }

  onMounted(install)

  // 系统设置中途切换也要跟上：打开减弱动态效果就立刻停掉并复位，关掉再装回来
  watch(
    () => toValue(reducedMotion),
    () => (still() ? teardown() : install()),
  )

  onBeforeUnmount(teardown)

  return { active }
}
