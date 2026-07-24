<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, Edit, Operation } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const profileDialogVisible = ref(false)
const profileSaving = ref(false)
const profileFormRef = ref()
const profileForm = reactive({
  username: '',
  nickname: '',
  email: '',
  phone: '',
})
const initialProfileForm = ref({
  nickname: '',
  email: '',
  phone: '',
})

const avatarText = computed(() => authStore.displayName.slice(0, 1).toUpperCase())
const hasProfileChanges = computed(() => (
  profileForm.nickname.trim() !== initialProfileForm.value.nickname
  || profileForm.email.trim() !== initialProfileForm.value.email
  || profileForm.phone.trim() !== initialProfileForm.value.phone
))

const profileRules = {
  nickname: [
    { max: 50, message: '昵称不能超过 50 个字符', trigger: 'blur' },
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' },
  ],
  phone: [
    { max: 20, message: '手机号不能超过 20 个字符', trigger: 'blur' },
  ],
}

function fillProfileForm(user) {
  const nickname = user?.nickname || ''
  const email = user?.email || ''
  const phone = user?.phone || ''

  profileForm.username = user?.username || ''
  profileForm.nickname = nickname
  profileForm.email = email
  profileForm.phone = phone
  initialProfileForm.value = { nickname, email, phone }
  profileFormRef.value?.clearValidate()
}

function openProfileDialog() {
  fillProfileForm(authStore.user)
  profileDialogVisible.value = true
}

function profileErrorMessage(error) {
  const data = error.response?.data
  if (!data) return '个人资料保存失败，请稍后重试'
  if (typeof data.detail === 'string') return data.detail

  const firstEntry = Object.entries(data)[0]
  if (!firstEntry) return '个人资料保存失败，请稍后重试'
  const [field, messages] = firstEntry
  const message = Array.isArray(messages) ? messages[0] : messages
  const fieldLabels = {
    nickname: '昵称',
    email: '邮箱',
    phone: '手机号',
  }
  return `${fieldLabels[field] || field}：${message}`
}

async function confirmDiscardProfile() {
  if (!hasProfileChanges.value) return true

  try {
    await ElMessageBox.confirm(
      '当前修改尚未保存，确认放弃吗？',
      '放弃修改',
      {
        confirmButtonText: '确认放弃',
        cancelButtonText: '继续编辑',
        type: 'warning',
      },
    )
    return true
  } catch {
    return false
  }
}

async function handleProfileDialogClose(done) {
  if (profileSaving.value) return
  if (await confirmDiscardProfile()) done()
}

async function cancelProfileEdit() {
  if (profileSaving.value) return
  if (await confirmDiscardProfile()) {
    profileDialogVisible.value = false
  }
}

function resetProfileDialog() {
  fillProfileForm(null)
}

async function submitProfile() {
  const valid = await profileFormRef.value.validate().catch(() => false)
  if (!valid || !hasProfileChanges.value) return

  profileSaving.value = true
  try {
    // 直接使用 PATCH 响应更新 Pinia，让顶部用户信息无需刷新即可同步。
    const updatedUser = await authStore.updateProfile({
      nickname: profileForm.nickname.trim(),
      email: profileForm.email.trim(),
      phone: profileForm.phone.trim(),
    })
    fillProfileForm(updatedUser)
    profileDialogVisible.value = false
    ElMessage.success('个人资料已更新')
  } catch (error) {
    ElMessage.error(profileErrorMessage(error))
  } finally {
    profileSaving.value = false
  }
}

function handleCommand(command) {
  if (command === 'profile') {
    openProfileDialog()
    return
  }

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
            <el-dropdown-item command="profile">
              <el-icon><Edit /></el-icon>
              编辑个人资料
            </el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>

    <main class="app-main">
      <RouterView />
    </main>

    <el-dialog
      v-model="profileDialogVisible"
      title="编辑个人资料"
      width="560px"
      align-center
      destroy-on-close
      :before-close="handleProfileDialogClose"
      @closed="resetProfileDialog"
    >
      <el-form
        ref="profileFormRef"
        :model="profileForm"
        :rules="profileRules"
        label-position="top"
      >
        <el-form-item label="用户名">
          <el-input v-model="profileForm.username" disabled />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input
            v-model="profileForm.nickname"
            maxlength="50"
            show-word-limit
            autocomplete="nickname"
          />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input
            v-model="profileForm.email"
            maxlength="254"
            autocomplete="email"
          />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input
            v-model="profileForm.phone"
            maxlength="20"
            autocomplete="tel"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            model-value=""
            type="password"
            disabled
            autocomplete="off"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-actions">
          <el-button :disabled="profileSaving" @click="cancelProfileEdit">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="profileSaving"
            :disabled="!hasProfileChanges"
            @click="submitProfile"
          >
            保存修改
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
