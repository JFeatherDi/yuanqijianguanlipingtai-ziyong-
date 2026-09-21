<script setup>
/**
 * 登录页。
 *
 * 动效选型（结论来自 alignify 前端动画库清单）：
 *   - GSAP 管一次性编排：背景 PCB 走线描出、卡片/字段错峰入场、报错抖动。
 *     这些是「有先后顺序的整段演出」，命令式时间线最直接，也最容易调顺序。
 *   - Motion（motion-v）管状态驱动的进出场：错误条的出现/消失、密码可见性图标
 *     的交叉淡入。这类动效的价值在于组件挂载/卸载时自动收尾，声明式更省心。
 *   - 登录按钮的跑马灯是纯 CSS 循环：4 条渐变光条沿四条边追着跑（参考
 *     css+js 登陆按钮跑马灯效果），走合成层不占主线程，没必要动用 JS。
 *
 * 吉祥物 ChipMascot 自己管自己的姿势，这里只负责把「哪个输入框有焦点」翻译成姿势，
 * 并在入场时间线走到位时叫它挥一次手。
 *
 * 页面的层次是「一张电路板 + 一块压在它上面的玻璃」：
 *   - LoginBackdrop 画走线、焊盘、脉冲，其中内圈那几段刻意穿过卡片的位置；
 *   - 卡片自己不带底色渐变，也不做 backdrop-filter，只压一层 60% 的白，背后的电路板
 *     因此从框外一直透到框里，视线能顺着一条线走进卡片。不用模糊是被实测逼出来的：
 *     2px 的走线一旦被 blur 摊开、再被 60% 的白一压，框内就只剩 1/255 不到的差，
 *     等于走线断在边框上。
 *
 * 卡片还是一块会回应的板子，分两层装饰（都在 CardCircuitry 里）：
 *   - 表面一层极浅的偏光跟着指针走、卡片极轻微地朝指针倾一点、投影往反方向让开
 *     （usePointerLight）；标题条是一层静止的纯色蓝，不再有跟着指针扫的高光。
 *   - 边框是一圈沿周长跑的信号光 + 四角焊盘，颜色直接反映登录状态，
 *     焊盘在指针靠近那个角时点亮。
 * 两者都只在有精确指针、且未开启减弱动态效果的设备上装，触屏上整块退回静态外观。
 *
 * 验证码是服务端签发的（backend/captcha.py）：图片由 <img> 直接引接口，答案只留在
 * 服务端内存里。后端每次校验都会作废那一张，所以提交失败后必须换一张，
 * 否则下一次提交填什么都是「验证码错误」。
 *
 * 所有时长/缓动都从 styles/tokens.css 换算，不另起一套节奏：
 *   --dur-fast 120ms · --dur 180ms · --ease-out cubic-bezier(0.16, 1, 0.3, 1)
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AnimatePresence, MotionConfig, motion, useReducedMotion } from 'motion-v'
import gsap from 'gsap'
import AppButton from '@/components/ui/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import CardCircuitry from '@/components/ui/CardCircuitry.vue'
import ChipMascot from '@/components/ui/ChipMascot.vue'
import LoginBackdrop from '@/components/ui/LoginBackdrop.vue'
import { authApi } from '@/api/endpoints'
import { usePointerLight } from '@/composables/usePointerLight'
import { useAuthStore } from '@/stores/auth'

/* ---------------------------------------------------------------- 动效常量 */

const EASE_OUT = [0.16, 1, 0.3, 1] // 与 --ease-out 一致
const DUR_FAST = 0.12 // --dur-fast
const DUR = 0.18 // --dur

/** 验证码位数，和后端 backend/captcha.py 的 LENGTH 对齐 */
const CAPTCHA_LENGTH = 4

const ERROR_MOTION = {
  initial: { opacity: 0, y: -6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
  transition: { duration: DUR, ease: EASE_OUT },
}

/** 密码可见性图标：两个图标层叠做交叉淡入 + 轻微旋转 */
const REVEAL_ICON = {
  on: {
    initial: { opacity: 0, rotate: -35 },
    animate: { opacity: 1, rotate: 0 },
    exit: { opacity: 0, rotate: 35 },
    transition: { duration: DUR_FAST, ease: EASE_OUT },
  },
  off: {
    initial: { opacity: 0, rotate: 35 },
    animate: { opacity: 1, rotate: 0 },
    exit: { opacity: 0, rotate: -35 },
    transition: { duration: DUR_FAST, ease: EASE_OUT },
  },
}

/** 报错抖动：方向交替，避免连续失败像复读机 */
const SHAKE_STEPS = [11, -9, 7, -4]
const SHAKE_SPANS = [0.07, 0.09, 0.09, 0.09]

/* ---------------------------------------------------------------- 状态 */

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const prefersReducedMotion = useReducedMotion()

const username = ref('')
const password = ref('')
const captcha = ref('')
const revealed = ref(false)
const errorText = ref('')
const focused = ref('')

/**
 * 验证码图片：src 里带一个时间戳，否则浏览器会复用上一张图。
 * loading 只用来在换图时给个过渡，避免旧图硬邦邦地卡在那。
 */
const captchaStamp = ref(Date.now())
const captchaState = ref('loading')
const captchaSrc = computed(() => `${authApi.captchaPath}?t=${captchaStamp.value}`)

const backdrop = ref(null)
const mascot = ref(null)
const mascotHost = ref(null)
const card = ref(null)
const codeInput = ref(null)
/** 登录按钮所在的盒子：磁吸位移加在这一层，免得内联 transform 盖掉按钮自己的 :active 缩放 */
const magnet = ref(null)
let introTl = null

const submitting = ref(false)
const granted = ref(false)

const canSubmit = computed(
  () =>
    username.value.trim() !== '' &&
    password.value !== '' &&
    captcha.value.trim().length === CAPTCHA_LENGTH,
)
/** 跑马灯只在「能提交了」的时候亮起来，禁用态保持安静 */
const marqueeOn = computed(() => canSubmit.value && !submitting.value)

/**
 * 卡片状态：一处判定，两处消费 —— 标题条上的状态灯、边框信号光的颜色。
 * 顺序即优先级：已经通过了就别再显示「校验失败」。
 */
const cardState = computed(() => {
  if (granted.value) return 'granted'
  if (submitting.value) return 'pending'
  if (errorText.value) return 'error'
  return canSubmit.value ? 'ready' : 'idle'
})

/** 状态文案：只交给读屏，界面上靠指示灯的颜色和边框信号光表达，不占可见文字 */
const STATUS_LABEL = {
  idle: '待机',
  ready: '就绪',
  pending: '校验中',
  error: '校验失败',
  granted: '已通过',
}

/** 聚焦密码框就让它遮眼；选择「显示密码」时改成从指缝里偷看 */
const mascotState = computed(() => {
  if (focused.value !== 'pass') return 'idle'
  return revealed.value ? 'peek' : 'cover'
})

const shakeCount = ref(0)

function onFocus(field) {
  focused.value = field
}

function onBlur() {
  focused.value = ''
}

/** 显示密码按钮：prevent 掉 mousedown，输入框才不会失焦，吉祥物也就不会放下手 */
function toggleReveal() {
  revealed.value = !revealed.value
}

/**
 * 换一张验证码。
 * 后端每次校验都会把那一张作废，所以失败之后必须重新取 —— 不然下一次提交
 * 无论填什么都是「验证码错误」。
 */
function refreshCaptcha({ focus = false } = {}) {
  captcha.value = ''
  captchaState.value = 'loading'
  captchaStamp.value = Date.now()
  if (focus) codeInput.value?.focus()
}

/** 通过之后停留一下再跳走：让「已通过」真的被看见，成功不该没有回应 */
const GRANTED_HOLD = 420

async function submit() {
  if (!canSubmit.value || submitting.value) return
  errorText.value = ''
  submitting.value = true
  try {
    await auth.login(username.value.trim(), password.value, captcha.value.trim())
    granted.value = true
    await new Promise((resolve) => setTimeout(resolve, GRANTED_HOLD))
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (error) {
    errorText.value = error.message
    password.value = ''
    refreshCaptcha({ focus: true })
    shakeCount.value += 1
  } finally {
    submitting.value = false
  }
}

watch(shakeCount, (count) => {
  if (!card.value || !count) return
  const dir = count % 2 === 1 ? 1 : -1
  const tl = gsap.timeline()
  SHAKE_STEPS.forEach((step, index) => {
    tl.to(card.value, { x: step * dir, duration: SHAKE_SPANS[index], ease: 'power2.out' })
  })
  tl.to(card.value, { x: 0, duration: 0.12, ease: 'power2.out' })
})

/* ---------------------------------------------------------------- 卡片交互 */

/**
 * 指针光效：表面光斑跟随指针、卡片朝指针轻微倾斜、登录按钮被指针吸住。
 * 触屏或开启「减弱动态效果」时这里什么都不装，卡片退回静态外观，输入与按钮不受影响。
 */
const { active: pointerLive } = usePointerLight({
  card,
  mascot: mascotHost,
  magnetTarget: magnet,
  reducedMotion: prefersReducedMotion,
})

/* ---------------------------------------------------------------- 入场 */

onMounted(() => {
  backdrop.value?.play()

  if (prefersReducedMotion.value) {
    // 减弱动态效果下只淡入，不做位移与缩放
    gsap.from([mascotHost.value, card.value], {
      opacity: 0,
      duration: 0.3,
      stagger: 0.06,
      ease: 'power1.out',
    })
    mascot.value?.wave()
    return
  }

  const fields = card.value.querySelectorAll('.login__field, .login__submit')

  introTl = gsap.timeline({ defaults: { ease: 'power3.out' } })
  introTl
    // 吉祥物先落到卡片上沿，再挥手
    .from(
      mascotHost.value,
      { y: 30, scale: 0.8, opacity: 0, duration: 0.74, ease: 'back.out(1.5)' },
      0.32,
    )
    .from(card.value, { y: 38, opacity: 0, duration: 0.7 }, 0.44)
    .from(fields, { y: 16, opacity: 0, duration: 0.52, stagger: 0.075 }, 0.6)
    .call(() => mascot.value?.wave(), undefined, 0.92)
})

onBeforeUnmount(() => {
  introTl?.kill()
  gsap.killTweensOf(card.value)
})
</script>

<template>
  <!-- reducedMotion="user"：跟随系统「减弱动态效果」，此时 Motion 保留淡入淡出、去掉位移 -->
  <MotionConfig reduced-motion="user">
    <div class="login">
      <LoginBackdrop ref="backdrop" :reduced-motion="prefersReducedMotion" />

      <div class="login__stage">
        <!-- 吉祥物：下缘压进卡片里，只探出上半身 -->
        <div ref="mascotHost" class="login__mascot">
          <ChipMascot
            ref="mascot"
            :state="mascotState"
            :reduced-motion="prefersReducedMotion"
            :size="148"
          />
        </div>

        <main
          ref="card"
          class="login__card"
          :class="[`login__card--${cardState}`, { 'is-pointer-live': pointerLive }]"
        >
          <CardCircuitry :state="cardState" :reduced-motion="prefersReducedMotion" />

          <header class="login__head">
            <span class="login__logo" aria-hidden="true">
              <AppIcon name="chip" :size="22" :stroke-width="2" />
            </span>
            <div class="login__titles">
              <h1 class="login__title">IOTAT 元器件管理平台</h1>
            </div>
            <!-- 状态灯：和边框信号光同源，说明这台「仪器」现在在干什么。
                 只留指示灯本身，状态文字收进 sr-only，读屏仍能听到 -->
            <span class="login__status" :class="`login__status--${cardState}`" role="status">
              <i class="login__status-dot" aria-hidden="true" />
              <span class="sr-only">{{ STATUS_LABEL[cardState] }}</span>
            </span>
          </header>

          <form class="login__body" novalidate @submit.prevent="submit">
            <AnimatePresence>
              <motion.p
                v-if="errorText"
                key="error"
                class="login__error"
                role="alert"
                v-bind="ERROR_MOTION"
              >
                <AppIcon name="alert-circle" :size="16" />
                <span>{{ errorText }}</span>
              </motion.p>
            </AnimatePresence>

            <div class="field login__field">
              <label class="field__label" for="login-user">账号</label>
              <div class="login__control" :class="{ 'is-focused': focused === 'user' }">
                <AppIcon name="user" :size="16" class="login__control-icon" />
                <input
                  id="login-user"
                  v-model="username"
                  class="login__input"
                  type="text"
                  name="username"
                  autocomplete="username"
                  required
                  @focus="onFocus('user')"
                  @blur="onBlur"
                />
              </div>
            </div>

            <div class="field login__field">
              <label class="field__label" for="login-pass">密码</label>
              <div class="login__control" :class="{ 'is-focused': focused === 'pass' }">
                <AppIcon name="lock" :size="16" class="login__control-icon" />
                <input
                  id="login-pass"
                  v-model="password"
                  class="login__input"
                  :type="revealed ? 'text' : 'password'"
                  name="password"
                  autocomplete="current-password"
                  required
                  @focus="onFocus('pass')"
                  @blur="onBlur"
                />
                <button
                  type="button"
                  class="login__reveal"
                  :aria-label="revealed ? '隐藏密码' : '显示密码'"
                  :title="revealed ? '隐藏密码' : '显示密码'"
                  @mousedown.prevent
                  @click="toggleReveal"
                >
                  <!-- 图标切换用交叉淡入，避免眼睛图标毫无过渡地瞬间换形 -->
                  <AnimatePresence :initial="false">
                    <motion.span
                      v-if="revealed"
                      key="on"
                      class="login__reveal-icon"
                      v-bind="REVEAL_ICON.on"
                    >
                      <AppIcon name="eye-off" :size="16" />
                    </motion.span>
                    <motion.span v-else key="off" class="login__reveal-icon" v-bind="REVEAL_ICON.off">
                      <AppIcon name="eye" :size="16" />
                    </motion.span>
                  </AnimatePresence>
                </button>
              </div>
            </div>

            <div class="field login__field">
              <label class="field__label" for="login-code">验证码</label>
              <div class="login__control" :class="{ 'is-focused': focused === 'code' }">
                <AppIcon name="shield" :size="16" class="login__control-icon" />
                <input
                  id="login-code"
                  ref="codeInput"
                  v-model="captcha"
                  class="login__input login__input--code"
                  type="text"
                  name="captcha"
                  :maxlength="CAPTCHA_LENGTH"
                  autocomplete="off"
                  autocapitalize="characters"
                  spellcheck="false"
                  required
                  @focus="onFocus('code')"
                  @blur="onBlur"
                />
                <!-- 验证码图就摆在输入框里：要照抄的东西和填的地方在同一行。
                     点一下换一张，mousedown.prevent 让输入框不失焦 -->
                <button
                  type="button"
                  class="login__captcha"
                  :class="`login__captcha--${captchaState}`"
                  aria-label="看不清？点击更换验证码"
                  title="看不清？点击更换验证码"
                  @mousedown.prevent
                  @click="refreshCaptcha()"
                >
                  <img
                    class="login__captcha-img"
                    :src="captchaSrc"
                    alt=""
                    width="112"
                    height="36"
                    @load="captchaState = 'ready'"
                    @error="captchaState = 'error'"
                  />
                  <span class="login__captcha-again" aria-hidden="true">
                    <AppIcon name="refresh" :size="14" :stroke-width="2" />
                  </span>
                </button>
              </div>
            </div>

            <div ref="magnet" class="login__submit">
              <AppButton
                class="login__submit-btn"
                variant="primary"
                type="submit"
                block
                :loading="submitting"
                :disabled="!canSubmit || submitting"
              >
                {{ submitting ? '登录中' : '登录' }}
              </AppButton>
              <!-- 跑马灯：四条边各一条渐变光条追着跑，能提交时才亮 -->
              <span class="login__marquee" :class="{ 'is-on': marqueeOn }" aria-hidden="true">
                <i /><i /><i /><i />
              </span>
            </div>
          </form>
        </main>
      </div>
    </div>
  </MotionConfig>
</template>

<style scoped>
.login {
  position: relative;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px var(--sp-4);
  background: var(--c-bg);
}

.login__stage {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 460px;
  display: flex;
  flex-direction: column;
  align-items: center;
  /* 卡片会在指针下轻微转动，透视放在这一层：吉祥物和卡片共享同一套近大远小 */
  perspective: 1000px;
}

.login__mascot {
  flex: none;
  display: flex;
  justify-content: center;
  /* 负外边距让芯片人下缘落进卡片后面，形成「从卡片后探出头」的位置关系 */
  margin-bottom: -20px;
}

.login__card {
  position: relative;
  width: 100%;
  /*
   * 一块半透明玻璃，不再自带底色渐变。
   * 这里刻意不用 backdrop-filter：模糊会把 2px 宽的走线摊到十几像素，
   * 再被这层 0.6 的白一压，框内那几段走线实测直接归零（不到 1/255 的差），
   * 「线从框外穿进框里」就断在边框上了。磨砂感改由这层半透明白自己承担 ——
   * 底色够干净，透过去的走线不影响读字，却真能一路连进卡片。
   */
  background: rgba(255, 255, 255, 0.6);
  /* 描边偏蓝而不是中性灰：边上那圈信号光才有「电路板镀边」的底子 */
  border: 1px solid rgba(47, 127, 209, 0.22);
  border-radius: var(--radius-lg);
  /*
   * 三层阴影：常规海拔、顶部一道内高光（玻璃的厚度感来自这道线）、
   * 以及跟着指针反向让开的第二层投影（--sh-x / --sh-y 由 usePointerLight 写在卡片上），
   * 光在指针处、影子往反方向偏，卡片才有被灯照着的厚度。
   */
  box-shadow:
    var(--shadow-3),
    inset 0 1px 0 rgba(255, 255, 255, 0.75),
    var(--sh-x, 0px) var(--sh-y, 0px) 18px rgba(27, 92, 155, 0.1);
  overflow: hidden;
}

/* 只有真的装了指针光效（精确指针 + 未减弱动态效果）才提升图层，触屏上不占合成层 */
.login__card.is-pointer-live {
  will-change: transform;
}

/* 边框也跟着状态走色：被拒偏红、通过偏绿 */
.login__card--error {
  border-color: rgba(214, 69, 69, 0.4);
}

.login__card--granted {
  border-color: rgba(46, 158, 107, 0.45);
}

/* ---------- 蓝色标题条 ---------- */
.login__head {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  padding: 26px 28px;
  color: var(--c-text-on-primary);
  /*
   * 一层纯色蓝，不叠渐变，也不用 backdrop-filter。
   * 透明度定在 0.76：再透白字就压不住（这个深度盖在浅底上约 4.1:1），
   * 再实就和「半透明卡片」不是一块料了。
   * 这个深度下穿过标题条的走线还留得住 —— 走线比标题条更暗，
   * 透上来是压暗而不是提亮，所以白字的对比度只会更好，不会更差。
   */
  background: rgba(27, 92, 155, 0.76);
}

.login__logo {
  width: 46px;
  height: 46px;
  flex: none;
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.18);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.login__titles {
  min-width: 0;
}

.login__title {
  font-size: var(--fs-xl);
  font-weight: 600;
  letter-spacing: 0.2px;
}

/* ---------- 状态灯：和边框信号光同源，说明这台「仪器」此刻在干什么 ---------- */
.login__status {
  margin-left: auto;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.15);
  transition:
    background var(--dur) var(--ease-out),
    border-color var(--dur) var(--ease-out);
}

.login__status-dot {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.6);
  transition:
    background var(--dur) var(--ease-out),
    box-shadow var(--dur) var(--ease-out);
}

/* 就绪：可以提交了，灯先亮起来 */
.login__status--ready .login__status-dot {
  background: #cfe9ff;
  box-shadow: 0 0 8px rgba(207, 233, 255, 0.9);
}

/* 校验中：缓慢呼吸，表示正在等后端 */
.login__status--pending .login__status-dot {
  background: #ffe1a8;
  box-shadow: 0 0 9px rgba(255, 225, 168, 0.95);
  animation: status-pulse 0.9s ease-in-out infinite;
}

.login__status--error {
  border-color: rgba(255, 255, 255, 0.46);
  background: rgba(214, 69, 69, 0.32);
}

.login__status--error .login__status-dot {
  background: #ffc4c4;
  box-shadow: 0 0 9px rgba(255, 196, 196, 0.95);
}

.login__status--granted {
  border-color: rgba(255, 255, 255, 0.46);
  background: rgba(46, 158, 107, 0.36);
}

.login__status--granted .login__status-dot {
  background: #a9e3c6;
  box-shadow: 0 0 10px rgba(169, 227, 198, 0.95);
}

@keyframes status-pulse {
  50% {
    opacity: 0.35;
  }
}

/* ---------- 表单主体 ---------- */
.login__body {
  position: relative;
  /* 抬到表面光斑之上：光斑是「板面」的一部分，内容永远压在它上面 */
  z-index: 1;
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}

.login__field {
  gap: 8px;
}

.field__label {
  font-size: var(--fs-md);
}

.login__error {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 11px 13px;
  border-radius: var(--radius-md);
  /* 同样留一点透明度，和玻璃卡片一个体系 */
  background: rgba(251, 234, 234, 0.88);
  border: 1px solid #f2cccc;
  color: #a83232;
  font-size: var(--fs-md);
  line-height: 1.45;
}

.login__control {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  height: 46px;
  padding: 0 14px;
  /* 输入框也留一点透明度：整块卡片是玻璃，只有输入框不透明会像贴上去的补丁 */
  border: 1px solid rgba(47, 127, 209, 0.18);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.72);
  transition: border-color var(--dur) var(--ease-out), box-shadow var(--dur) var(--ease-out),
    background var(--dur) var(--ease-out);
}

/*
 * 聚焦时沿下缘扫过一道光：像走线在这一刻接通。
 * 只在聚焦的瞬间跑一次，之后靠上面的描边和光晕维持「这里是焦点」。
 */
.login__control::after {
  content: '';
  position: absolute;
  left: 6px;
  right: 6px;
  bottom: -1px;
  height: 1px;
  pointer-events: none;
  background: linear-gradient(
    90deg,
    rgba(47, 127, 209, 0),
    rgba(47, 127, 209, 0.85),
    rgba(47, 127, 209, 0)
  );
  opacity: 0;
}

.login__control.is-focused::after {
  animation: field-trace 0.62s var(--ease-out) 1;
}

@keyframes field-trace {
  0% {
    opacity: 0;
    transform: scaleX(0.12);
    transform-origin: 0 50%;
  }
  35% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: scaleX(1);
    transform-origin: 0 50%;
  }
}

.login__control:hover {
  border-color: #c0cddc;
}

.login__control.is-focused {
  border-color: var(--c-primary);
  box-shadow: 0 0 0 3px rgba(47, 127, 209, 0.14);
}

.login__control-icon {
  color: var(--c-text-mute);
  flex: none;
}

.login__input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: var(--c-text);
}

.login__reveal {
  position: relative;
  width: 28px;
  height: 28px;
  flex: none;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--c-text-mute);
  cursor: pointer;
}

.login__reveal:hover {
  background: var(--c-surface-alt);
  color: var(--c-primary);
}

/* 两个图标叠在同一格里做交叉淡入，按钮尺寸不会因为换图标而跳动 */
.login__reveal-icon {
  position: absolute;
  inset: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* ---------- 验证码 ---------- */

/* 验证码不区分大小写，统一显示成大写，和图片上的字形对得上 */
.login__input--code {
  text-transform: uppercase;
  letter-spacing: 3px;
  font-family: var(--font-num);
}

/*
 * 验证码图就嵌在输入框右端：要照抄的东西和填的地方在同一行，视线不用来回跳。
 * 图片是 2 倍图（224x72），这里按一半显示，缩小时的插值顺便当了抗锯齿。
 */
.login__captcha {
  position: relative;
  flex: none;
  width: 112px;
  height: 36px;
  padding: 0;
  overflow: hidden;
  border: 1px solid rgba(47, 127, 209, 0.2);
  border-radius: var(--radius-sm);
  background: #f7fafe;
  cursor: pointer;
  transition: border-color var(--dur) var(--ease-out), box-shadow var(--dur) var(--ease-out);
}

.login__captcha:hover {
  border-color: var(--c-primary);
  box-shadow: 0 0 0 2px rgba(47, 127, 209, 0.14);
}

.login__captcha-img {
  display: block;
  width: 100%;
  height: 100%;
  /* 换图后旧图要淡出，不然会出现一帧「上一张还挂着」 */
  opacity: 1;
  transition: opacity var(--dur) var(--ease-out);
}

.login__captcha--loading .login__captcha-img {
  opacity: 0;
}

/* 图片取不到时（后端没起来）留一块空白格，不给浏览器画裂图图标 */
.login__captcha--error {
  background: var(--c-surface-alt);
}

.login__captcha--error .login__captcha-img {
  opacity: 0;
}

/* 「换一张」的提示：平时不露，悬停时在图上浮出来一个刷新图标 */
.login__captcha-again {
  position: absolute;
  inset: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--c-primary-deep);
  background: rgba(255, 255, 255, 0.72);
  opacity: 0;
  transition: opacity var(--dur) var(--ease-out);
}

.login__captcha:hover .login__captcha-again,
.login__captcha:focus-visible .login__captcha-again {
  opacity: 1;
}

/* 加载中也可以点（再点一次就重新请求），所以提示图标照常给 */
.login__captcha--loading .login__captcha-again,
.login__captcha--error .login__captcha-again {
  opacity: 1;
}

/* ---------- 提交按钮 + 跑马灯 ---------- */
.login__submit {
  position: relative;
}

.login__submit-btn {
  height: 46px;
  font-size: var(--fs-lg);
  font-weight: 600;
  letter-spacing: 6px;
  border-radius: var(--radius-md);
  transition: background var(--dur) var(--ease-out), border-color var(--dur) var(--ease-out),
    box-shadow var(--dur) var(--ease-out), transform var(--dur-fast) var(--ease-out);
}

/* 按压反馈留在 CSS：内联 transform 会盖掉 :active，而且这条本来就在指针路径上 */
.login__submit-btn:active:not(:disabled) {
  transform: scale(0.978);
}

/*
 * 跑马灯层单独一套盒子：自己 overflow:hidden 裁掉跑到边外的光条，
 * 不裁按钮本身，键盘聚焦时 :focus-visible 的外描边才不会丢。
 */
.login__marquee {
  position: absolute;
  inset: 0;
  border-radius: var(--radius-md);
  overflow: hidden;
  pointer-events: none;
  opacity: 0;
  transition: opacity var(--dur-slow) var(--ease-out), box-shadow var(--dur-slow) var(--ease-out);
}

.login__marquee.is-on {
  opacity: 1;
}

.login__submit:hover .login__marquee.is-on {
  box-shadow: 0 0 14px rgba(47, 127, 209, 0.5);
}

.login__marquee i {
  position: absolute;
  display: block;
}

/* 四条边各一条：前 50% 的时间里穿过去，剩下 50% 停在边外，靠 0.25 的时差接力 */
.login__marquee i:nth-child(1) {
  top: 0;
  left: -100%;
  width: 100%;
  height: 2px;
  background: linear-gradient(to right, transparent, rgba(255, 255, 255, 0.95));
  animation: marquee-x 1.7s linear infinite;
}

.login__marquee i:nth-child(2) {
  right: 0;
  top: -100%;
  width: 2px;
  height: 100%;
  background: linear-gradient(transparent, rgba(255, 255, 255, 0.95));
  animation: marquee-y 1.7s linear 0.425s infinite;
}

.login__marquee i:nth-child(3) {
  right: -100%;
  bottom: 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(to left, transparent, rgba(255, 255, 255, 0.95));
  animation: marquee-x-rev 1.7s linear 0.85s infinite;
}

.login__marquee i:nth-child(4) {
  left: 0;
  bottom: -100%;
  width: 2px;
  height: 100%;
  background: linear-gradient(rgba(255, 255, 255, 0.95), transparent);
  animation: marquee-y-rev 1.7s linear 1.275s infinite;
}

/* 悬停时加速，光跑得更急 */
.login__submit:hover .login__marquee i {
  animation-duration: 1.05s;
}

@keyframes marquee-x {
  0% {
    left: -100%;
  }
  50%,
  100% {
    left: 100%;
  }
}

@keyframes marquee-y {
  0% {
    top: -100%;
  }
  50%,
  100% {
    top: 100%;
  }
}

@keyframes marquee-x-rev {
  0% {
    right: -100%;
  }
  50%,
  100% {
    right: 100%;
  }
}

@keyframes marquee-y-rev {
  0% {
    bottom: -100%;
  }
  50%,
  100% {
    bottom: 100%;
  }
}

/* ---------- 响应式：矮屏按比例收一档，保证整页不用滚动 ---------- */
@media (max-height: 840px) {
  .login {
    padding: 32px var(--sp-4);
  }

  .login__head {
    padding: 20px 24px;
  }

  .login__logo {
    width: 40px;
    height: 40px;
  }

  .login__body {
    padding: 22px 24px;
    gap: var(--sp-4);
  }

  .login__control,
  .login__submit-btn {
    height: 42px;
  }
}

@media (max-width: 520px) {
  .login {
    padding: 28px 16px;
  }

  .login__head {
    padding: 20px;
  }

  .login__body {
    padding: 20px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login__marquee {
    display: none;
  }

  /* 减弱动态效果下，聚焦只留描边与光晕，不再扫光 */
  .login__control.is-focused::after,
  .login__status-dot {
    animation: none;
  }
}
</style>
