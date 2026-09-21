<script setup>
/**
 * 卡片上的两层装饰。都是绝对定位，不参与布局，也不接受指针事件。
 *
 *   1. 表面偏光（下层）：指针在卡片上移动时，卡面有一层极浅的蓝往那边稍微偏一点。
 *      位置来自 usePointerLight 写在卡片元素上的 --mx / --my，--lit 控制淡入淡出。
 *      只在有精确指针的设备上会亮，触屏上这一层始终是暗的。
 *   2. 边缘电路（上层）：一圈沿周长跑的信号光 + 四角焊盘。
 *      信号光的颜色直接跟着卡片状态走（待机 / 就绪 / 校验中 / 被拒 / 通过），
 *      四个焊盘在指针靠近那个角时点亮 —— 边框因此承担状态反馈，而不是纯装饰。
 *
 * 这两层都刻意压得很轻。卡面上跟着指针跑的高亮只要做出可见的边界，就成了一块
 * 跳来跳去的亮斑，比完全没有光更难看；所以半径开大、峰值压到几乎看不见，
 * 边缘再用多段渐变抹开，目标是「余光扫到才察觉」。
 *
 * 原先还有一层压在内容之上的白光（mix-blend-mode: soft-light），已经去掉：
 * 它在白卡面上会显出一整片发白的雾，位置又跟着指针走，是刺眼的主要来源。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  /** idle | ready | pending | error | granted */
  state: { type: String, default: 'idle' },
  /** 由父组件传入 useReducedMotion() 的结果 */
  reducedMotion: { type: Boolean, default: false },
})

const CORNERS = ['tl', 'tr', 'bl', 'br']
/** 焊盘中心距两条边的距离。CSS 定位和命中判定共用这一个值，避免两边各写一份对不上 */
const VIA_INSET = 7
/** 指针离焊盘多近算「靠近」 */
const SENSE_RANGE = 130

const edge = ref(null)
const vias = ref([])

let frame = 0
let pointer = null
let box = null
let observer = null

function measure() {
  box = edge.value?.getBoundingClientRect() ?? null
}

/** 指针落在卡片外这么远，就把四个焊盘一起熄掉，省掉逐点计算 */
function farAway(x, y) {
  return (
    !box ||
    x < box.left - SENSE_RANGE ||
    x > box.right + SENSE_RANGE ||
    y < box.top - SENSE_RANGE ||
    y > box.bottom + SENSE_RANGE
  )
}

function apply() {
  frame = 0
  if (!box || !vias.value.length) return

  const lit = pointer && !farAway(pointer.clientX, pointer.clientY)
  const centers = lit
    ? [
        [box.left + VIA_INSET, box.top + VIA_INSET],
        [box.right - VIA_INSET, box.top + VIA_INSET],
        [box.left + VIA_INSET, box.bottom - VIA_INSET],
        [box.right - VIA_INSET, box.bottom - VIA_INSET],
      ]
    : null

  vias.value.forEach((via, index) => {
    if (!via) return
    let near = 0
    if (centers) {
      const distance = Math.hypot(
        pointer.clientX - centers[index][0],
        pointer.clientY - centers[index][1],
      )
      if (distance < SENSE_RANGE) near = (1 - distance / SENSE_RANGE) ** 1.5
    }
    via.style.setProperty('--near', near.toFixed(3))
  })
}

function onMove(event) {
  pointer = event
  if (!frame) frame = requestAnimationFrame(apply)
}

function onLeave() {
  pointer = null
  if (!frame) frame = requestAnimationFrame(apply)
}

function onResize() {
  measure()
  if (!frame) frame = requestAnimationFrame(apply)
}

onMounted(() => {
  measure()
  observer = new ResizeObserver(onResize)
  observer.observe(edge.value)

  // 减弱动态效果下不装指针感应：这一层保持安静的静态外观
  if (props.reducedMotion) return
  window.addEventListener('pointermove', onMove, { passive: true })
  window.addEventListener('pointerleave', onLeave)
  window.addEventListener('blur', onLeave)
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  if (frame) cancelAnimationFrame(frame)
  observer?.disconnect()
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerleave', onLeave)
  window.removeEventListener('blur', onLeave)
  window.removeEventListener('resize', onResize)
})
</script>

<template>
  <!-- 表面偏光：待在内容下面，所以自带负层级 -->
  <span class="card-glow" aria-hidden="true" />

  <!-- 边缘电路：压在内容上面，覆盖标题条四角 -->
  <div
    ref="edge"
    class="card-edge"
    :class="`card-edge--${state}`"
    :style="{ '--via-inset': `${VIA_INSET}px` }"
    aria-hidden="true"
  >
    <span class="card-edge__beam" />
    <span class="card-edge__burst" />
    <span class="card-edge__flash" />
    <span
      v-for="(corner, index) in CORNERS"
      :key="corner"
      :ref="(el) => (vias[index] = el)"
      class="card-edge__via"
      :class="`card-edge__via--${corner}`"
    >
      <i />
    </span>
  </div>
</template>

<style scoped>
/* 光斑跟随用的自定义属性必须注册过才能被动画/过渡，否则只是普通字符串 */
@property --beam-angle {
  syntax: '<angle>';
  initial-value: 0deg;
  inherits: false;
}

/*
 * 表面偏光。半径开到 460x380（比卡片本身还大），峰值只有 0.07，
 * 并且用四段渐变把边缘抹开 —— 单段渐变从 0.07 直接掉到 0 会在白卡面上
 * 显出一圈可辨的边界，跟着指针走的时候就是一块跳动的亮斑。
 */
.card-glow {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background: radial-gradient(
    460px 380px at var(--mx, 50%) var(--my, 30%),
    rgba(74, 150, 222, 0.07) 0%,
    rgba(74, 150, 222, 0.05) 32%,
    rgba(74, 150, 222, 0.024) 60%,
    rgba(74, 150, 222, 0) 84%
  );
  opacity: var(--lit, 0);
  transition: opacity var(--dur-slow) var(--ease-out);
}

.card-edge {
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  border-radius: inherit;

  /* 一圈信号光的配色由状态决定，一处改色就是一处改语义 */
  --beam: rgba(47, 127, 209, 0.5);
  --beam-hi: #b7d8f7;
  --flash: transparent;
  /* 信号光的基准亮度：状态越好，边框越亮 */
  --beam-base: 0.62;
}

.card-edge--ready {
  --beam-base: 0.78;
}

.card-edge--pending {
  --beam-base: 0.95;
}

.card-edge--error {
  --beam: rgba(214, 69, 69, 0.55);
  --beam-hi: #f0b3b3;
  --flash: rgba(214, 69, 69, 0.72);
  --beam-base: 0.9;
}

.card-edge--granted {
  --beam: rgba(46, 158, 107, 0.55);
  --beam-hi: #a9e3c6;
  --flash: rgba(46, 158, 107, 0.75);
  --beam-base: 0.9;
}

/*
 * 三圈都是同一套「只留 1px 边」的做法：元素铺满并留 1px 内边距，
 * 两层 mask 一减，就只剩贴边的那 1px 环，背景里的渐变只在环上显形。
 */
.card-edge__beam,
.card-edge__burst,
.card-edge__flash {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1px;
  -webkit-mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
}

/* 主信号：一段带尾迹的亮弧沿周长跑，扇形之外全透明 */
.card-edge__beam {
  background: conic-gradient(
    from var(--beam-angle),
    transparent 0 6%,
    rgba(74, 150, 222, 0.16) 28%,
    var(--beam) 62%,
    var(--beam-hi) 90%,
    #ffffff 100%
  );
  animation: edge-run 5.4s linear infinite;
  /*
   * 亮度 = 状态的基准值 + 指针在卡片上时的加成。
   * 指针一进来整圈就「通电」，离开又回到待机的暗度，边框本身因此是会回应的。
   */
  opacity: calc(var(--beam-base, 0.62) + var(--lit, 0) * 0.3);
  transition: opacity var(--dur-slow) var(--ease-out);
}

/* 数据突发：校验中才亮起来的第二条细光，反向且更快，读起来像「有流量进来了」 */
.card-edge__burst {
  background: conic-gradient(
    from var(--beam-angle),
    transparent 0 84%,
    rgba(255, 255, 255, 0.9) 92%,
    transparent 100%
  );
  animation: edge-run-rev 1.25s linear infinite;
  opacity: 0;
  transition: opacity var(--dur) var(--ease-out);
}

.card-edge--pending .card-edge__burst {
  opacity: 0.85;
}

/* 一次性闪环：被拒时闪两下，通过时闪一下 */
.card-edge__flash {
  background: var(--flash);
  opacity: 0;
}

.card-edge--error .card-edge__flash {
  animation: edge-flash 0.52s ease-out 2;
}

.card-edge--granted .card-edge__flash {
  animation: edge-flash 0.62s ease-out 1;
}

/*
 * 四角焊盘：白盘加一圈蓝环，压在蓝标题条上是「镀通孔」，
 * 落在白色区域上是「焊盘」，两种底色下都读得通。
 */
.card-edge__via {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fff;
  transform: translate(-50%, -50%) scale(calc(1 + var(--near, 0) * 0.55));
  box-shadow:
    0 0 0 1.5px rgba(47, 127, 209, 0.4),
    0 0 calc(var(--near, 0) * 14px) rgba(74, 150, 222, 0.75);
  transition: box-shadow var(--dur) var(--ease-out);
}

.card-edge__via--tl {
  top: var(--via-inset);
  left: var(--via-inset);
}

.card-edge__via--tr {
  top: var(--via-inset);
  right: var(--via-inset);
}

.card-edge__via--bl {
  bottom: var(--via-inset);
  left: var(--via-inset);
}

.card-edge__via--br {
  bottom: var(--via-inset);
  right: var(--via-inset);
}

/* 孔心：指针靠近时从浅蓝变成实心的品牌蓝 */
.card-edge__via i {
  position: absolute;
  inset: 2px;
  border-radius: 50%;
  background: var(--c-primary-deep);
  opacity: calc(0.32 + var(--near, 0) * 0.68);
  transition: opacity var(--dur) var(--ease-out);
}

/*
 * 每个焊盘上穿过一条走线：像电路真的从边框上走进去再出来，
 * 而不是往卡片的四个角随手点了四个点。深蓝在蓝条上是暗线，在白底上是浅线，
 * 两种底色都读得出来。
 */
.card-edge__via::before {
  content: '';
  position: absolute;
  left: -11px;
  top: 3px;
  width: 32px;
  height: 1px;
  border-radius: 1px;
  background: linear-gradient(
    90deg,
    rgba(27, 92, 155, 0),
    rgba(27, 92, 155, 0.42) 50%,
    rgba(27, 92, 155, 0)
  );
  opacity: calc(0.75 + var(--near, 0) * 0.25);
}

.card-edge__via::after {
  content: '';
  position: absolute;
  top: -11px;
  left: 3px;
  width: 1px;
  height: 32px;
  border-radius: 1px;
  background: linear-gradient(
    180deg,
    rgba(27, 92, 155, 0),
    rgba(27, 92, 155, 0.42) 50%,
    rgba(27, 92, 155, 0)
  );
  opacity: calc(0.75 + var(--near, 0) * 0.25);
}

@keyframes edge-run {
  to {
    --beam-angle: 360deg;
  }
}

@keyframes edge-run-rev {
  to {
    --beam-angle: -360deg;
  }
}

@keyframes edge-flash {
  0% {
    opacity: 0;
  }
  24% {
    opacity: 0.9;
  }
  100% {
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .card-edge__beam,
  .card-edge__burst,
  .card-edge__flash {
    animation: none;
  }

  /* 不动的情况下留一段静止的亮弧，边框仍有层次，只是不再跑 */
  .card-edge__beam {
    opacity: 0.7;
  }
}
</style>
