<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Iphone, Lock, Message, Operation, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const formRef = ref()
const form = reactive({
  username: '',
  nickname: '',
  email: '',
  phone: '',
  password: '',
  password_confirm: '',
})
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { max: 150, message: '用户名不能超过 150 个字符', trigger: 'blur' },
  ],
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    { max: 50, message: '昵称不能超过 50 个字符', trigger: 'blur' },
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' },
  ],
  phone: [
    { max: 20, message: '手机号不能超过 20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少需要 8 个字符', trigger: 'blur' },
  ],
  password_confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value && value !== form.password) {
          callback(new Error('两次输入的密码不一致'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

function registerErrorMessage(error) {
  const data = error.response?.data
  if (!data) return '注册失败，请稍后重试'
  if (typeof data.detail === 'string') return data.detail

  const [field, messages] = Object.entries(data)[0] || []
  const message = Array.isArray(messages) ? messages[0] : messages
  const fieldLabels = {
    username: '用户名',
    nickname: '昵称',
    email: '邮箱',
    phone: '手机号',
    password: '密码',
    password_confirm: '确认密码',
  }
  return typeof message === 'string'
    ? `${fieldLabels[field] || field}：${message}`
    : '注册失败，请稍后重试'
}

async function submit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.register({
      username: form.username.trim(),
      nickname: form.nickname.trim(),
      email: form.email.trim(),
      phone: form.phone.trim(),
      password: form.password,
      password_confirm: form.password_confirm,
    })
    const redirect = typeof route.query.redirect === 'string'
      ? route.query.redirect
      : '/projects'
    await router.replace(redirect)
  } catch (error) {
    ElMessage.error(registerErrorMessage(error))
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
        <h1>注册</h1>
        <p>创建账号后即可进入项目工作台</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="submit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :prefix-icon="User" autocomplete="username" size="large" />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="form.nickname" :prefix-icon="User" autocomplete="nickname" size="large" />
        </el-form-item>
        <el-form-item label="邮箱（选填）" prop="email">
          <el-input v-model="form.email" :prefix-icon="Message" autocomplete="email" size="large" />
        </el-form-item>
        <el-form-item label="手机号（选填）" prop="phone">
          <el-input v-model="form.phone" :prefix-icon="Iphone" autocomplete="tel" size="large" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            :prefix-icon="Lock"
            autocomplete="new-password"
            show-password
            type="password"
            size="large"
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="password_confirm">
          <el-input
            v-model="form.password_confirm"
            :prefix-icon="Lock"
            autocomplete="new-password"
            show-password
            type="password"
            size="large"
          />
        </el-form-item>
        <el-button class="login-submit" type="primary" size="large" :loading="loading" @click="submit">
          注册并登录
        </el-button>
      </el-form>
      <p class="auth-switch">
        已有账号？
        <RouterLink :to="{ name: 'login', query: { redirect: route.query.redirect } }">返回登录</RouterLink>
      </p>
    </section>
  </main>
</template>
