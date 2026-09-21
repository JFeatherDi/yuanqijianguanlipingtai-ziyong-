<script setup>
/**
 * 登录页吉祥物「小芯片人」。
 *
 * 遮眼机制参考 css+jquery 可爱熊猫遮眼登录页：输入密码时把爪子抬起来挡在眼睛上。
 * 与那份实现不同的是，这里没有让登录卡上移把眼睛压住 —— 熊猫的脸本来就只有眼睛，
 * 芯片人的五官却需要一直看得见。改成爪子自己从卡片上沿后面抬出来盖住眼睛，
 * 动作一样一眼能读懂，脸却不用被挡掉。
 *
 * 动效分工：
 *   - 姿势（idle / cover / peek）与挥手：GSAP 时间线，新姿势会打断旧姿势
 *   - 呼吸、眨眼、天线明暗、瞳孔跟手：常驻循环，只在没被遮住时运行
 *   - prefers-reduced-motion：姿势瞬时切换，不起循环，也不跟手
 *
 * 几何约定：CSS 用百分比排版，JS 用同一份比例常量算位移，改比例只改 G 这一处。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import gsap from 'gsap'

/* ------------------------------------------------------------------ 几何 */

/**
 * eyeX / eyeY   眼睛中心（占身体宽高的比例）
 * pawRestX / Y  爪子静止时的中心；静止位在身体下缘两侧，底边搭在卡片上沿附近
 * peekInset     偷看时两只爪子往外让开的距离
 */
const G = {
  eyeX: [0.32, 0.68],
  eyeY: 0.39,
  pawRestX: [0.05, 0.95],
  pawRestY: 0.74,
  peekInset: 0.055,
}

const props = defineProps({
  /** idle | cover | peek */
  state: { type: String, default: 'idle' },
  /** 由父组件传入 useReducedMotion() 的结果 */
  reducedMotion: { type: Boolean, default: false },
  /** 身体边长（px）；天线另占 28px，由样式表补齐 */
  size: { type: Number, default: 148 },
})

const root = ref(null)
const body = ref(null)
const pawLeft = ref(null)
const pawRight = ref(null)
const eyeLeft = ref(null)
const eyeRight = ref(null)
const mouth = ref(null)
const pupilLeft = ref(null)
const pupilRight = ref(null)
const antennaDot = ref(null)

const eyes = computed(() => [eyeLeft.value, eyeRight.value])
const paws = computed(() => [pawLeft.value, pawRight.value])

/**
 * 姿势 -> GSAP 补间目标。
 * 位移都是从「CSS 里写死的静止位」出发的偏移量，静止姿势就是 0，
 * 所以 CSS 改位置时这里不用跟着改。
 */
function resolve(name) {
  const w = props.size
  const coverX = [(G.eyeX[0] - G.pawRestX[0]) * w, (G.eyeX[1] - G.pawRestX[1]) * w]
  const coverY = (G.eyeY - G.pawRestY) * w
  const gap = G.peekInset * w

  if (name === 'cover') {
    return {
      left: { x: coverX[0], y: coverY, rotation: 11 },
      right: { x: coverX[1], y: coverY, rotation: -11 },
      eye: 0.1,
      mouth: 0.55,
    }
  }
  if (name === 'peek') {
    return {
      left: { x: coverX[0] - gap, y: coverY + gap * 0.5, rotation: 3 },
      right: { x: coverX[1] + gap, y: coverY + gap * 0.5, rotation: -3 },
      eye: 0.55,
      mouth: 0.85,
    }
  }
  return {
    left: { x: 0, y: 0, rotation: 6 },
    right: { x: 0, y: 0, rotation: -6 },
    eye: 1,
    mouth: 1,
  }
}

/* ------------------------------------------------------------------ 状态 */

let poseTl = null
let waveTl = null
let blinkCall = null
let ambientTl = null
let pupilTos = []

/** 眼睛当前睁开程度，眨眼会回到这个值 */
let eyeOpen = 1
/** 被遮住时不眨眼，否则两个补间会打架 */
let covered = false
/** 父组件在入场时间线里调 wave()，在此之前先别响应 state 变化 */
let ready = false

const rootStyle = computed(() => ({ '--chip-w': `${props.size}px` }))

/* ------------------------------------------------------------------ 姿势 */

function playPose(name, immediate = false) {
  if (!pawLeft.value) return
  const target = resolve(name)
  const instant = immediate || props.reducedMotion
  const dur = instant ? 0 : 0.44
  const cover = name === 'cover'

  poseTl?.kill()
  /*
   * 遮眼时要先停掉正在跑的眨眼补间。顺序不能挪到建完时间线之后：
   * 那时这条时间线里的闭眼补间已经存在，killTweensOf 会把它一起杀掉，
   * 爪子底下会留着一双睁开的眼睛。
   */
  if (cover) gsap.killTweensOf(eyes.value)

  const tl = gsap.timeline()
  tl.to(pawLeft.value, { ...target.left, duration: dur, ease: 'power3.out' }, 0)
  tl.to(pawRight.value, { ...target.right, duration: dur, ease: 'power3.out' }, 0)
  tl.to(
    eyes.value,
    { scaleY: target.eye, duration: instant ? 0 : 0.26, ease: 'power3.out' },
    instant ? 0 : 0.08,
  )
  tl.to(
    mouth.value,
    {
      scaleY: target.mouth,
      scaleX: instant ? 1 : 1 - (1 - target.mouth) * 0.5,
      duration: instant ? 0 : 0.3,
      ease: 'power3.out',
    },
    0,
  )
  poseTl = tl

  covered = cover
  eyeOpen = target.eye
  if (covered) {
    // 眼睛已经闭上，眨眼补间必须停掉，否则会把闭眼重新拉开
    blinkCall?.kill()
    blinkCall = null
  } else {
    scheduleBlink()
  }
}

/** 挂载后挥一次手，然后交还给 state。父组件在入场时间线里调用。 */
function wave() {
  if (props.reducedMotion || !pawRight.value) {
    ready = true
    return
  }
  const tl = gsap.timeline()
  tl.to(pawRight.value, { x: -14, y: -34, rotation: -16, duration: 0.32, ease: 'back.out(2)' }, 0)
  tl.to(pawRight.value, { rotation: 2, duration: 0.16, ease: 'sine.inOut' }, 0.32)
  tl.to(pawRight.value, { rotation: -16, duration: 0.22, ease: 'sine.inOut' })
  tl.to(pawRight.value, { rotation: 2, duration: 0.22, ease: 'sine.inOut' })
  tl.to(pawRight.value, { rotation: -16, duration: 0.22, ease: 'sine.inOut' })
  tl.to(pawRight.value, { x: 0, y: 0, rotation: -6, duration: 0.4, ease: 'power3.inOut' })
  tl.call(() => {
    ready = true
    playPose(props.state)
  })
  waveTl = tl
}

watch(
  () => props.state,
  (name) => {
    if (!ready) return
    waveTl?.kill()
    waveTl = null
    playPose(name)
  },
)

/* ------------------------------------------------------------------ 常驻循环 */

function scheduleBlink() {
  blinkCall?.kill()
  blinkCall = gsap.delayedCall(gsap.utils.random(2.8, 5.6), () => {
    blinkCall = null
    if (props.reducedMotion || covered) return scheduleBlink()
    const tl = gsap.timeline({ onComplete: scheduleBlink })
    tl.to(eyes.value, { scaleY: 0.12, duration: 0.08, ease: 'power2.in' })
    tl.to(eyes.value, { scaleY: eyeOpen, duration: 0.14, ease: 'power2.out' })
  })
}

function startAmbient() {
  ambientTl = gsap.timeline()
  ambientTl.to(body.value, { y: -4, duration: 2.4, yoyo: true, repeat: -1, ease: 'sine.inOut' }, 0)
  ambientTl.to(
    antennaDot.value,
    { opacity: 0.45, scale: 0.82, duration: 1.3, yoyo: true, repeat: -1, ease: 'sine.inOut' },
    0,
  )
}

/* ------------------------------------------------------------------ 瞳孔跟手 */

function onPointerMove(event) {
  if (event.pointerType !== 'mouse' || props.reducedMotion || covered) return
  const box = root.value?.getBoundingClientRect()
  if (!box) return
  const cx = box.left + box.width / 2
  const cy = box.top + box.height * 0.45
  const max = props.size * 0.028
  const nx = gsap.utils.clamp(-1, 1, (event.clientX - cx) / (window.innerWidth * 0.5))
  const ny = gsap.utils.clamp(-1, 1, (event.clientY - cy) / (window.innerHeight * 0.5))
  for (const to of pupilTos) {
    to.x(nx * max)
    to.y(ny * max)
  }
}

/* ------------------------------------------------------------------ 生命周期 */

onMounted(() => {
  playPose(props.state, true)
  ready = true
  if (!props.reducedMotion) {
    startAmbient()
    scheduleBlink()
  }
  pupilTos = [pupilLeft.value, pupilRight.value].map((el) => ({
    x: gsap.quickTo(el, 'x', { duration: 0.5, ease: 'power3' }),
    y: gsap.quickTo(el, 'y', { duration: 0.5, ease: 'power3' }),
  }))
  window.addEventListener('pointermove', onPointerMove, { passive: true })
})

onBeforeUnmount(() => {
  poseTl?.kill()
  waveTl?.kill()
  ambientTl?.kill()
  blinkCall?.kill()
  window.removeEventListener('pointermove', onPointerMove)
  gsap.killTweensOf([body.value, ...paws.value, ...eyes.value, mouth.value, antennaDot.value])
})

defineExpose({ wave })
</script>

<template>
  <div ref="root" class="chip" :style="rootStyle" aria-hidden="true">
    <div ref="body" class="chip__body">
      <!-- 引脚：左三根、右三根，下缘留给爪子 -->
      <span
        v-for="n in 3"
        :key="`l${n}`"
        class="chip__pin chip__pin--left"
        :style="{ top: `${8 + n * 16}%` }"
      />
      <span
        v-for="n in 3"
        :key="`r${n}`"
        class="chip__pin chip__pin--right"
        :style="{ top: `${8 + n * 16}%` }"
      />

      <span class="chip__gloss" />

      <span ref="eyeLeft" class="chip__eye chip__eye--left">
        <i ref="pupilLeft" class="chip__pupil" />
      </span>
      <span ref="eyeRight" class="chip__eye chip__eye--right">
        <i ref="pupilRight" class="chip__pupil" />
      </span>
      <span ref="mouth" class="chip__mouth" />

      <!-- 爪子放在最后：盖眼时要压在眼睛上面 -->
      <span ref="pawLeft" class="chip__paw chip__paw--left"><i /><i /><i /></span>
      <span ref="pawRight" class="chip__paw chip__paw--right"><i /><i /><i /></span>
    </div>

    <span class="chip__antenna" />
    <span ref="antennaDot" class="chip__antenna-dot" />
  </div>
</template>

<style scoped>
.chip {
  position: relative;
  width: var(--chip-w);
  /* 天线立在身体上方 28px，一起算进盒子里，父级排版才对得上 */
  height: calc(var(--chip-w) + 28px);
  flex: none;
  pointer-events: none;
  user-select: none;
}

.chip__body {
  position: absolute;
  left: 0;
  bottom: 0;
  width: 100%;
  height: var(--chip-w);
  border-radius: 32px;
  background: linear-gradient(158deg, #5ba2e6 0%, var(--c-primary) 56%, #2a6fb8 100%);
  box-shadow:
    inset 0 2px 0 rgba(255, 255, 255, 0.3),
    inset 0 -12px 20px rgba(27, 92, 155, 0.28),
    0 12px 24px rgba(27, 92, 155, 0.24);
}

/* 左上角一块柔光，让封装看起来是有厚度的塑料 */
.chip__gloss {
  position: absolute;
  inset: 5px 7px 44% 7px;
  border-radius: 27px 27px 36px 36px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.32), rgba(255, 255, 255, 0));
}

.chip__pin {
  position: absolute;
  width: 6px;
  height: 20px;
  margin-top: -10px;
  border-radius: 3px;
  background: var(--c-primary-deep);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.14);
}

.chip__pin--left {
  left: -5px;
}

.chip__pin--right {
  right: -5px;
}

.chip__eye {
  position: absolute;
  top: 39%;
  width: 26px;
  height: 30px;
  margin: -15px 0 0 -13px;
  border-radius: 13px;
  background: #fff;
  box-shadow: inset 0 -3px 6px rgba(47, 127, 209, 0.2);
}

.chip__eye--left {
  left: 32%;
}

.chip__eye--right {
  left: 68%;
}

.chip__pupil {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 12px;
  height: 12px;
  margin: -6px 0 0 -6px;
  border-radius: 50%;
  background: var(--c-primary-deep);
}

.chip__mouth {
  position: absolute;
  left: 50%;
  top: 68%;
  width: 24px;
  height: 11px;
  margin: -5px 0 0 -12px;
  border-bottom: 3px solid rgba(255, 255, 255, 0.92);
  border-radius: 50%;
}

.chip__paw {
  position: absolute;
  top: 74%;
  width: 34px;
  height: 30px;
  margin: -15px 0 0 -17px;
  padding: 0 6px 3px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 2px;
  border-radius: 13px 13px 11px 11px;
  background: linear-gradient(180deg, #6aadea, var(--c-primary-band));
  box-shadow:
    0 3px 7px rgba(27, 92, 155, 0.34),
    inset 0 1px 0 rgba(255, 255, 255, 0.4);
}

.chip__paw--left {
  left: 5%;
}

.chip__paw--right {
  left: 95%;
}

/* 三根手指之间的缝：靠三条深色小竖条表现，不额外加元素 */
.chip__paw i {
  width: 6px;
  height: 12px;
  border-radius: 3px;
  background: rgba(27, 92, 155, 0.42);
}

.chip__antenna {
  position: absolute;
  left: 50%;
  top: 14px;
  width: 5px;
  height: 16px;
  margin-left: -2.5px;
  border-radius: 3px;
  background: var(--c-primary-deep);
}

.chip__antenna-dot {
  position: absolute;
  left: 50%;
  top: 0;
  width: 14px;
  height: 14px;
  margin-left: -7px;
  border-radius: 50%;
  background: #8fc0ef;
  box-shadow: 0 0 10px rgba(143, 192, 239, 0.95);
}
</style>
