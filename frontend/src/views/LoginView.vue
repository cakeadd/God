<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock, Operation, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const formRef = ref()
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login(form)
    const redirect = typeof route.query.redirect === 'string'
      ? route.query.redirect
      : '/projects'
    await router.replace(redirect)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '用户名或密码错误')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-brand">
        <span class="brand-mark brand-mark--large"><el-icon><Operation /></el-icon></span>
        <div>
          <p class="login-product">接口自动化测试平台</p>
          <p class="login-context">项目协作与回归测试工作台</p>
        </div>
      </div>

      <div class="login-heading">
        <h1>登录</h1>
        <p>使用你的项目账号进入工作台</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="submit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :prefix-icon="User" autocomplete="username" size="large" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            :prefix-icon="Lock"
            autocomplete="current-password"
            show-password
            type="password"
            size="large"
          />
        </el-form-item>
        <el-button class="login-submit" type="primary" size="large" :loading="loading" @click="submit">
          登录
        </el-button>
      </el-form>
    </section>
  </main>
</template>
