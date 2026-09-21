<script setup>
/** 应用外壳：侧边导航 + 顶栏 + 内容区。共享数据在这里统一加载。 */
import { onMounted, ref } from 'vue'
import SideNav from './SideNav.vue'
import TopBar from './TopBar.vue'
import { provideRefreshSignal } from '@/composables/useRefresh'
import { useInventoryStore } from '@/stores/inventory'
import { useToastStore } from '@/stores/toast'

const inventory = useInventoryStore()
const toast = useToastStore()

const collapsed = ref(false)
const mobileOpen = ref(false)
const refreshSignal = provideRefreshSignal()

onMounted(async () => {
  try {
    await inventory.load()
  } catch (error) {
    // 首屏加载失败要明确告知，而不是留一个空表格
    toast.error(error.message)
  }
})

function refresh() {
  refreshSignal.value += 1
  inventory.load({ silent: true }).catch((error) => toast.error(error.message))
}
</script>

<template>
  <div class="shell">
    <SideNav v-model:collapsed="collapsed" v-model:mobileOpen="mobileOpen" />

    <div class="shell__main">
      <TopBar @toggle-menu="mobileOpen = !mobileOpen" @refresh="refresh" />

      <main class="shell__content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.shell__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.shell__content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--sp-3);
}

@media (max-width: 900px) {
  .shell__content {
    padding: var(--sp-2);
  }
}
</style>