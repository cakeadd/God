<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, Operation } from '@element-plus/icons-vue'

import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const avatarText = computed(() => authStore.displayName.slice(0, 1).toUpperCase())

function handleCommand(command) {
  if (command === 'logout') {
    authStore.logout()
    router.replace({ name: 'login' })
  }
}
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand-lockup" aria-label="接口自动化测试平台">
        <span class="brand-mark"><el-icon><Operation /></el-icon></span>
        <span class="brand-name">接口自动化测试平台</span>
      </div>

      <el-dropdown trigger="click" @command="handleCommand">
        <button class="user-menu" type="button">
          <span class="user-avatar">{{ avatarText }}</span>
          <span class="user-copy">
            <strong>{{ authStore.displayName }}</strong>
            <small>{{ authStore.user?.username }}</small>
          </span>
          <el-icon><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
