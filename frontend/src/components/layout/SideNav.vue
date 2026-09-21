<script setup>
/**
 * 侧边导航：复刻参考图的分组式菜单。
 * 结构 = 品牌区 + 可滚动菜单区 + 折叠控件；移动端切换为抽屉。
 */
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '@/components/ui/AppIcon.vue'
import { NAV_ITEMS } from '@/domain/navigation'
import { useInventoryStore } from '@/stores/inventory'

const props = defineProps({
  collapsed: { type: Boolean, default: false },
  mobileOpen: { type: Boolean, default: false },
})

const emit = defineEmits(['update:collapsed', 'update:mobileOpen'])

const route = useRoute()
const inventory = useInventoryStore()

const openGroups = ref(new Set())

/** 进入某个子页时自动展开它的父分组，进入首页则全部收起。 */
watch(
  () => route.name,
  (name) => {
    const next = new Set(openGroups.value)
    for (const item of NAV_ITEMS) {
      if (!item.children) continue
      if (item.children.some((child) => child.to.name === name)) next.add(item.id)
    }
    openGroups.value = next
  },
  { immediate: true },
)

const badges = computed(() => ({ lowCount: inventory.lowCount }))

function isGroupOpen(id) {
  return openGroups.value.has(id)
}

function toggleGroup(id) {
  const next = new Set(openGroups.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  openGroups.value = next
}

const isActive = (to) => route.name === to.name

function closeMobile() {
  emit('update:mobileOpen', false)
}
</script>

<template>
  <aside
    class="nav"
    :class="{ 'is-collapsed': props.collapsed, 'is-open': props.mobileOpen }"
    aria-label="主导航"
  >
    <div class="nav__brand">
      <span class="nav__logo" aria-hidden="true">
        <AppIcon name="chip" :size="18" :stroke-width="2" />
      </span>
      <span v-if="!props.collapsed" class="nav__brand-text">
        IOTAT<b>元器件</b>
      </span>
    </div>

    <nav class="nav__list">
      <ul>
        <li v-for="item in NAV_ITEMS" :key="item.id">
          <!-- 叶子项 -->
          <RouterLink
            v-if="item.to"
            :to="item.to"
            class="nav__link"
            :class="{ 'is-active': isActive(item.to) }"
            :title="props.collapsed ? item.label : undefined"
            @click="closeMobile"
          >
            <AppIcon :name="item.icon" :size="16" />
            <span v-if="!props.collapsed" class="nav__label">{{ item.label }}</span>
            <span
              v-if="!props.collapsed && item.badgeKey && badges[item.badgeKey]"
              class="nav__badge"
            >{{ badges[item.badgeKey] }}</span>
          </RouterLink>

          <!-- 分组项 -->
          <template v-else>
            <button
              type="button"
              class="nav__link nav__link--group"
              :class="{ 'is-open': isGroupOpen(item.id) }"
              :aria-expanded="isGroupOpen(item.id)"
              :title="props.collapsed ? item.label : undefined"
              @click="toggleGroup(item.id)"
            >
              <AppIcon :name="item.icon" :size="16" />
              <span v-if="!props.collapsed" class="nav__label">{{ item.label }}</span>
              <AppIcon
                v-if="!props.collapsed"
                name="chevronDown"
                :size="13"
                class="nav__caret"
              />
            </button>

            <ul v-show="!props.collapsed && isGroupOpen(item.id)" class="nav__sub">
              <li v-for="child in item.children" :key="child.id">
                <RouterLink
                  :to="child.to"
                  class="nav__link nav__link--sub"
                  :class="{ 'is-active': isActive(child.to) }"
                  @click="closeMobile"
                >
                  <span class="nav__label">{{ child.label }}</span>
                  <span
                    v-if="child.badgeKey && badges[child.badgeKey]"
                    class="nav__badge"
                  >{{ badges[child.badgeKey] }}</span>
                </RouterLink>
              </li>
            </ul>
          </template>
        </li>
      </ul>
    </nav>

    <button
      type="button"
      class="nav__collapse"
      :aria-label="props.collapsed ? '展开侧边栏' : '收起侧边栏'"
      @click="emit('update:collapsed', !props.collapsed)"
    >
      <AppIcon name="panel" :size="16" />
      <span v-if="!props.collapsed" class="nav__label">收起菜单</span>
    </button>
  </aside>

  <!-- 移动端遮罩 -->
  <transition name="fade">
    <div v-if="props.mobileOpen" class="nav__scrim" @click="closeMobile" />
  </transition>
</template>

<style scoped>
.nav {
  width: var(--sidebar-w);
  flex: none;
  background: var(--c-surface);
  border-right: 1px solid var(--c-border);
  display: flex;
  flex-direction: column;
  transition: width var(--dur) var(--ease-out);
}

.nav.is-collapsed {
  width: var(--sidebar-w-collapsed);
}

/* ---------- 品牌区 ---------- */
.nav__brand {
  height: var(--topbar-h);
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: 0 var(--sp-3);
  border-bottom: 1px solid var(--c-border);
  overflow: hidden;
}

.nav__logo {
  width: 26px;
  height: 26px;
  flex: none;
  border-radius: var(--radius-md);
  background: var(--c-primary);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.nav__brand-text {
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--c-text);
  white-space: nowrap;
}

.nav__brand-text b {
  color: var(--c-primary);
  font-weight: 700;
}

/* ---------- 菜单 ---------- */
.nav__list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--sp-2) 0;
}

.nav__link {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: 36px;
  padding: 0 var(--sp-3);
  color: var(--c-text-sub);
  font-size: var(--fs-sm);
  cursor: pointer;
  border: none;
  background: transparent;
  width: 100%;
  text-align: left;
  text-decoration: none;
  border-left: 3px solid transparent;
  transition: background var(--dur) var(--ease-out), color var(--dur) var(--ease-out);
}

.nav__link:hover {
  background: var(--c-surface-alt);
  color: var(--c-text);
  text-decoration: none;
}

.nav__link.is-active {
  background: var(--c-primary-soft);
  color: var(--c-primary-deep);
  border-left-color: var(--c-primary);
  font-weight: 600;
}

.nav__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav__caret {
  flex: none;
  color: var(--c-text-mute);
  transition: transform var(--dur) var(--ease-out);
}

.nav__link--group.is-open .nav__caret {
  transform: rotate(180deg);
}

.nav__sub {
  padding: 2px 0;
}

.nav__link--sub {
  padding-left: 38px;
  min-height: 32px;
  font-size: var(--fs-xs);
  border-left-width: 3px;
}

.nav__badge {
  flex: none;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: var(--c-danger);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-num);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* ---------- 折叠控件 ---------- */
.nav__collapse {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  height: 38px;
  padding: 0 var(--sp-3);
  border: none;
  border-top: 1px solid var(--c-border);
  background: var(--c-surface);
  color: var(--c-text-mute);
  font-size: var(--fs-xs);
  cursor: pointer;
  transition: background var(--dur) var(--ease-out), color var(--dur) var(--ease-out);
}

.nav__collapse:hover {
  background: var(--c-surface-alt);
  color: var(--c-primary);
}

.nav__scrim {
  display: none;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--dur) var(--ease-out);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ---------- 移动端：抽屉 ---------- */
@media (max-width: 900px) {
  .nav {
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    z-index: var(--z-modal);
    width: var(--sidebar-w);
    transform: translateX(-100%);
    box-shadow: var(--shadow-3);
  }

  .nav.is-open {
    transform: translateX(0);
  }

  .nav.is-collapsed {
    width: var(--sidebar-w);
  }

  .nav__scrim {
    display: block;
    position: fixed;
    inset: 0;
    z-index: calc(var(--z-modal) - 1);
    background: rgba(20, 30, 42, 0.4);
  }
}
</style>