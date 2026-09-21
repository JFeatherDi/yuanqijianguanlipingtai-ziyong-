<script setup>
/** 顶栏：面包屑 + 仓库标识 + 用户菜单。 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '@/components/ui/AppIcon.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { BREADCRUMBS } from '@/domain/navigation'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const emit = defineEmits(['toggle-menu', 'refresh'])

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const menuOpen = ref(false)
const menuRoot = ref(null)

const crumbs = computed(() => BREADCRUMBS.get(route.name) ?? [route.meta.title ?? ''])

function onDocumentClick(event) {
  if (menuOpen.value && menuRoot.value && !menuRoot.value.contains(event.target)) {
    menuOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))

async function logout() {
  menuOpen.value = false
  await auth.logout()
  toast.info('已退出登录')
  router.replace({ name: 'login' })
}
</script>

<template>
  <header class="topbar">
    <button class="topbar__menu" type="button" aria-label="打开导航菜单" @click="emit('toggle-menu')">
      <AppIcon name="menu" :size="18" />
    </button>

    <nav class="topbar__crumbs" aria-label="面包屑">
      <template v-for="(crumb, index) in crumbs" :key="crumb">
        <AppIcon v-if="index" name="chevronRight" :size="12" class="topbar__sep" />
        <span class="topbar__crumb" :class="{ 'is-current': index === crumbs.length - 1 }">
          {{ crumb }}
        </span>
      </template>
    </nav>

    <div class="topbar__right">
      <AppButton
        variant="ghost"
        icon-only
        icon="refresh"
        size="sm"
        aria-label="刷新数据"
        @click="emit('refresh')"
      />

      <span class="topbar__chip">
        <AppIcon name="building" :size="14" />
        元器件仓库
      </span>

      <div ref="menuRoot" class="topbar__user">
        <button
          type="button"
          class="topbar__user-btn"
          :aria-expanded="menuOpen"
          aria-haspopup="menu"
          @click="menuOpen = !menuOpen"
        >
          <span class="topbar__avatar" aria-hidden="true">{{ auth.initial }}</span>
          <span class="topbar__name">{{ auth.user || '未登录' }}</span>
          <AppIcon name="chevronDown" :size="13" />
        </button>

        <div v-if="menuOpen" class="topbar__menu-panel" role="menu">
          <p class="topbar__menu-head">
            <span class="topbar__menu-title">当前账号</span>
            <span class="topbar__menu-user">{{ auth.user }}</span>
          </p>
          <button type="button" class="topbar__menu-item" role="menuitem" @click="logout">
            <AppIcon name="logout" :size="14" />
            退出登录
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: var(--topbar-h);
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: 0 var(--sp-4);
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
}

.topbar__menu {
  display: none;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: var(--radius);
  background: transparent;
  color: var(--c-text-sub);
  cursor: pointer;
}

.topbar__menu:hover {
  background: var(--c-surface-alt);
}

.topbar__crumbs {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}

.topbar__crumb {
  font-size: var(--fs-sm);
  color: var(--c-text-mute);
  white-space: nowrap;
}

.topbar__crumb.is-current {
  color: var(--c-primary-deep);
  font-weight: 600;
}

.topbar__sep {
  color: #b9c4d1;
}

.topbar__right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.topbar__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  padding: 0 10px;
  border-radius: var(--radius);
  background: var(--c-primary-softer);
  border: 1px solid var(--c-border-soft);
  color: var(--c-primary-deep);
  font-size: var(--fs-xs);
  white-space: nowrap;
}

.topbar__user {
  position: relative;
  margin-left: var(--sp-2);
  padding-left: var(--sp-3);
  border-left: 1px solid var(--c-border);
}

.topbar__user-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  height: 30px;
  padding: 0 6px;
  border: none;
  border-radius: var(--radius);
  background: transparent;
  color: var(--c-text-sub);
  font-size: var(--fs-sm);
  cursor: pointer;
  transition: background var(--dur) var(--ease-out);
}

.topbar__user-btn:hover {
  background: var(--c-surface-alt);
}

.topbar__avatar {
  width: 24px;
  height: 24px;
  flex: none;
  border-radius: 50%;
  background: var(--c-primary);
  color: #fff;
  font-size: var(--fs-xs);
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.topbar__name {
  font-weight: 500;
  color: var(--c-text);
}

.topbar__menu-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 180px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-2);
  z-index: var(--z-dropdown);
  overflow: hidden;
}

.topbar__menu-head {
  padding: 10px var(--sp-3);
  border-bottom: 1px solid var(--c-border-soft);
  background: var(--c-surface-alt);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.topbar__menu-title {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}

.topbar__menu-user {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--c-text);
}

.topbar__menu-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  width: 100%;
  height: 36px;
  padding: 0 var(--sp-3);
  border: none;
  background: transparent;
  color: var(--c-text-sub);
  font-size: var(--fs-sm);
  text-align: left;
  cursor: pointer;
  transition: background var(--dur) var(--ease-out), color var(--dur) var(--ease-out);
}

.topbar__menu-item:hover {
  background: var(--c-danger-soft);
  color: var(--c-danger);
}

@media (max-width: 900px) {
  .topbar__menu {
    display: inline-flex;
  }
}

@media (max-width: 640px) {
  .topbar__chip,
  .topbar__name {
    display: none;
  }
}
</style>