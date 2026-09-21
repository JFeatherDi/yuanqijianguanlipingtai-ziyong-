<script setup>
/**
 * 登录页背景：PCB 走线 + 焊盘 + 漂移的芯片小块 + 数据脉冲。
 *
 * 选 GSAP 而不是 CSS 动画的原因：入场时要按顺序把走线「画」出来
 * （stroke-dashoffset 从全长收到 0），再接上焊盘缩放和漂浮小块的错峰，
 * 这种一次性编排用时间线写起来最短，也最好调顺序。
 *
 * 所有元素都是纯装饰，动完就不再碰主线程：
 *   - 入场：走线画出来 -> 焊盘弹出 -> 漂浮小块入场
 *   - 常驻：漂浮小块缓慢位移、脉冲沿水平走线跑
 * prefers-reduced-motion 时只做一次性呈现，不起任何循环。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import gsap from 'gsap'

const props = defineProps({
  reducedMotion: { type: Boolean, default: false },
})

const root = ref(null)
let ctx = null

/** 走线：横平竖直 + 45° 拐角，和真实 PCB 布线同一种语言 */
const WIRES = [
  'M -40 168 H 330 l 70 70 H 700',
  'M -40 306 H 208 l 74 74 H 520',
  'M -40 704 H 298 l 68 -68 H 690',
  'M 1480 206 H 1152 l -62 62 H 826',
  'M 1480 350 H 1242 l -70 70 H 942',
  'M 1480 744 H 1184 l -64 -64 H 836',
  'M 382 -30 V 96 l 46 46 V 214',
  'M 1082 -30 V 118 l -46 46 V 218',
  'M 302 930 V 812 l 54 -54 H 616',
  'M 1164 930 V 806 l -54 -54 H 906',
]

/**
 * 穿过登录卡片的那几段。
 * 卡片是半透明的，这些走线从框外一直连到框内，视线能顺着一条线走到卡片里面，
 * 而不是「外面有张电路图、卡片是贴在它上面的一块板」。
 */
const INNER_WIRES = [
  'M 240 338 H 560 l 62 62 H 1036',
  'M 240 626 H 520 l 66 -66 H 1074',
  'M 300 470 H 528 l 54 54 H 972 l 62 -62 H 1180',
  'M 524 168 V 300 l 56 56 V 566',
  'M 916 754 V 592 l -58 -58 V 296',
  'M 470 96 V 236 l 50 50 H 690',
]

/** 焊盘：走线终点 + 几个孤立焊点，[cx, cy, r] */
const PADS = [
  [700, 238, 5],
  [520, 380, 5],
  [690, 636, 5],
  [826, 268, 5],
  [942, 420, 5],
  [836, 680, 5],
  [428, 214, 5],
  [1036, 218, 5],
  [616, 758, 4],
  [906, 752, 4],
  [176, 486, 4],
  [1268, 560, 4],
  // 内圈：卡片后面那几段走线的落点
  [1036, 400, 4],
  [1074, 560, 4],
  [580, 566, 4],
  [858, 296, 4],
  [1180, 462, 4],
  [690, 286, 4],
]

/** 脉冲：沿几条水平走线跑的光点 */
const PULSES = [
  { y: 168, from: -40, to: 330, delay: 0.3 },
  { y: 704, from: -40, to: 298, delay: 1.4 },
  { y: 206, from: 1480, to: 1152, delay: 0.8 },
  // 卡片后面那几条也让光跑起来，半透明之后能看到它在玻璃里面走
  { y: 400, from: 622, to: 1036, delay: 0.6 },
  { y: 524, from: 582, to: 972, delay: 1.9 },
  { y: 462, from: 1034, to: 1180, delay: 1.1 },
]

/** 漂浮的芯片小块：[x%, y%, 边长, 漂浮周期, 延迟] */
const FLOATS = [
  [9, 20, 17, 7.4, 0],
  [17, 74, 12, 6.2, 0.7],
  [87, 25, 15, 8.1, 1.2],
  [79, 79, 11, 5.6, 0.4],
  [49, 7, 10, 6.8, 1.0],
  [31, 91, 13, 7.8, 1.5],
]

function play() {
  ctx?.revert()
  ctx = gsap.context((self) => {
    const wires = self.selector('.bg__wire')
    const pads = self.selector('.bg__pad')
    const floats = self.selector('.bg__float')
    const pulses = self.selector('.bg__pulse')

    const tl = gsap.timeline()

    if (props.reducedMotion) {
      // 只呈现终态：不做描线、不做循环
      gsap.set(wires, { strokeDashoffset: 0 })
      gsap.set(floats, { opacity: 0.55 })
      return
    }

    // 描线前先量出每条走线的长度，dashoffset 从全长收到 0 就是「画出来」
    wires.forEach((el) => {
      const len = el.getTotalLength()
      gsap.set(el, { strokeDasharray: len, strokeDashoffset: len })
    })

    tl.to(wires, { strokeDashoffset: 0, duration: 1.15, ease: 'power2.inOut', stagger: 0.075 }, 0)
    tl.from(pads, { attr: { r: 0 }, duration: 0.42, ease: 'back.out(3)', stagger: 0.045 }, 0.55)
    tl.from(floats, { opacity: 0, scale: 0.35, duration: 0.7, ease: 'back.out(1.8)', stagger: 0.09 }, 0.4)

    floats.forEach((el, i) => {
      const [, , , period, delay] = FLOATS[i]
      gsap.to(el, {
        y: -16,
        x: 9,
        duration: period,
        yoyo: true,
        repeat: -1,
        ease: 'sine.inOut',
        delay,
      })
    })

    pulses.forEach((el, i) => {
      const lane = PULSES[i]
      const loop = gsap.timeline({ repeat: -1, repeatDelay: 1.6, delay: lane.delay })
      loop.fromTo(
        el,
        { attr: { cx: lane.from }, opacity: 0 },
        { attr: { cx: lane.to }, opacity: 0.7, duration: 2.4, ease: 'none' },
        0,
      )
      loop.to(el, { opacity: 0, duration: 0.35, ease: 'none', immediateRender: false }, 2.4)
    })
  }, root.value)
}

onMounted(play)
onBeforeUnmount(() => ctx?.revert())

defineExpose({ play })
</script>

<template>
  <div ref="root" class="bg" aria-hidden="true">
    <svg class="bg__wires" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
      <path v-for="(d, i) in WIRES" :key="`w${i}`" class="bg__wire" :d="d" />
      <path v-for="(d, i) in INNER_WIRES" :key="`iw${i}`" class="bg__wire" :d="d" />
      <circle
        v-for="(p, i) in PADS"
        :key="`p${i}`"
        class="bg__pad"
        :cx="p[0]"
        :cy="p[1]"
        :r="p[2]"
      />
      <circle
        v-for="(p, i) in PULSES"
        :key="`u${i}`"
        class="bg__pulse"
        :cy="p.y"
        :cx="p.from"
        r="3.2"
      />
    </svg>

    <span
      v-for="(f, i) in FLOATS"
      :key="`f${i}`"
      class="bg__float"
      :style="{ left: `${f[0]}%`, top: `${f[1]}%`, '--s': `${f[2]}px` }"
    >
      <i />
      <i />
    </span>
  </div>
</template>

<style scoped>
.bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
  /* 装饰层永远不参与命中测试 */
  pointer-events: none;
  z-index: 0;
}

/*
 * 底色是一块平的冷灰底，只有走线这一层图形。
 * 这里刻意没有径向渐变光晕：卡片的半透明要能透出「同一张电路图」，
 * 背后压一层渐变会让透过去的东西变成一片模糊的色块，读不出是走线。
 */
.bg__wires {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

/* 描线要能透过卡片看清，所以比纯装饰时稍微实一点 */
.bg__wire {
  fill: none;
  stroke: rgba(47, 127, 209, 0.3);
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.bg__pad {
  fill: rgba(47, 127, 209, 0.36);
}

.bg__pulse {
  fill: var(--c-primary-band);
  opacity: 0;
}

.bg__float {
  position: absolute;
  width: var(--s);
  height: var(--s);
  border-radius: calc(var(--s) * 0.28);
  background: rgba(74, 150, 222, 0.42);
  box-shadow: inset 0 0 0 1px rgba(47, 127, 209, 0.25);
}

/* 漂浮小块两边的引脚 */
.bg__float i {
  position: absolute;
  top: 30%;
  width: calc(var(--s) * 0.3);
  height: calc(var(--s) * 0.16);
  border-radius: 1px;
  background: rgba(47, 127, 209, 0.32);
}

.bg__float i:first-child {
  left: calc(var(--s) * -0.28);
}

.bg__float i:last-child {
  right: calc(var(--s) * -0.28);
}
</style>
