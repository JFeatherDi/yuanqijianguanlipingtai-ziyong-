<script setup>
/** 登录页：沿用参考图的「蓝色标题条 + 浅色主体」卡片语言。 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const revealed = ref(false)
const errorText = ref('')
const focused = ref('')

const canSubmit = computed(() => username.value.trim() !== '' && password.value !== '')

async function submit() {
  if (!canSubmit.value || auth.pending) return
  errorText.value = ''
  try {
    await auth.login(username.value.trim(), password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (error) {
    errorText.value = error.message
    password.value = ''
  }
}
</script>

<template>
  <div class="login">
    <main class="login__card">
      <header class="login__head">
        <span class="login__logo" aria-hidden="true">
          <AppIcon name="chip" :size="20" :stroke-width="2" />
        </span>
        <div class="login__titles">
          <h1 class="login__title">IOTAT 元器件管理平台</h1>
          <p class="login__subtitle">实验室库存 · 出入库 · 批量导入</p>
        </div>
      </header>

      <form class="login__body" novalidate @submit.prevent="submit">
        <p v-if="errorText" class="login__error" role="alert">
          <AppIcon name="alert-circle" :size="15" />
          <span>{{ errorText }}</span>
        </p>

        <div class="field">
          <label class="field__label" for="login-user">账号</label>
          <div class="login__control" :class="{ 'is-focused': focused === 'user' }">
            <AppIcon name="user" :size="15" class="login__control-icon" />
            <input
              id="login-user"
              v-model="username"
              class="login__input"
              type="text"
              name="username"
              autocomplete="username"
              placeholder="请输入账号"
              required
              @focus="focused = 'user'"
              @blur="focused = ''"
            />
          </div>
        </div>

        <div class="field">
          <label class="field__label" for="login-pass">密码</label>
          <div class="login__control" :class="{ 'is-focused': focused === 'pass' }">
            <AppIcon name="lock" :size="15" class="login__control-icon" />
            <input
              id="login-pass"
              v-model="password"
              class="login__input"
              :type="revealed ? 'text' : 'password'"
              name="password"
              autocomplete="current-password"
              placeholder="请输入密码"
              required
              @focus="focused = 'pass'"
              @blur="focused = ''"
            />
            <button
              type="button"
              class="login__reveal"
              :aria-label="revealed ? '隐藏密码' : '显示密码'"
              :title="revealed ? '隐藏密码' : '显示密码'"
              @click="revealed = !revealed"
            >
              <AppIcon :name="revealed ? 'eye-off' : 'eye'" :size="15" />
            </button>
          </div>
        </div>

        <AppButton
          variant="primary"
          type="submit"
          block
          :loading="auth.pending"
          :disabled="!canSubmit"
        >
          {{ auth.pending ? '登录中' : '登 录' }}
        </AppButton>
      </form>

      <footer class="login__foot">
        <AppIcon name="shield" :size="13" />
        连续 5 次登录失败将锁定 5 分钟；会话 12 小时无操作自动失效
      </footer>
    </main>

    <p class="login__copyright">IOTAT Laboratory · 元器件管理平台</p>
  </div>
</template>

<style scoped>
.login {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-5);
  padding: var(--sp-6) var(--sp-4);
  /* 极浅的蓝色晕染，与内容区底色同族，不使用蓝紫渐变 */
  background:
    radial-gradient(1100px 460px at 50% -180px, #dceafa 0%, rgba(220, 234, 250, 0) 70%),
    var(--c-bg);
}

.login__card {
  width: 100%;
  max-width: 392px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-2);
  overflow: hidden;
}

/* ---------- 蓝色标题条 ---------- */
.login__head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-5) var(--sp-5);
  background: var(--c-primary-band);
  color: var(--c-text-on-primary);
}

.login__logo {
  width: 38px;
  height: 38px;
  flex: none;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.18);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.login__titles {
  min-width: 0;
}

.login__title {
  font-size: var(--fs-lg);
  font-weight: 600;
  letter-spacing: 0.2px;
}

.login__subtitle {
  font-size: var(--fs-xs);
  color: rgba(255, 255, 255, 0.85);
  margin-top: 2px;
}

/* ---------- 表单主体 ---------- */
.login__body {
  padding: var(--sp-5);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.login__error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 9px 11px;
  border-radius: var(--radius);
  background: var(--c-danger-soft);
  border: 1px solid #f2cccc;
  color: #a83232;
  font-size: var(--fs-sm);
  line-height: 1.45;
}

.login__control {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  height: 36px;
  padding: 0 11px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius);
  background: var(--c-surface);
  transition: border-color var(--dur) var(--ease-out), box-shadow var(--dur) var(--ease-out);
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
  font-size: var(--fs-md);
  color: var(--c-text);
}

.login__input::placeholder {
  color: #a8b3c0;
}

.login__reveal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
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

.login__foot {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: var(--sp-3) var(--sp-5);
  border-top: 1px solid var(--c-border-soft);
  background: var(--c-surface-alt);
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
  line-height: 1.5;
}

.login__copyright {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}
</style>