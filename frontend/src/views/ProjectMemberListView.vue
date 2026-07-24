<script setup>
import { computed, onMounted, ref } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  getProjectMembers,
  updateProjectMemberRole,
} from '../api/projectMembers'
import { useProjectWorkspace } from '../composables/projectWorkspace'
import { useAuthStore } from '../stores/auth'

const workspace = useProjectWorkspace()
const authStore = useAuthStore()
const members = ref([])
const loading = ref(false)
const loadError = ref(false)
const updatingMemberIds = ref(new Set())

const isOwner = computed(() => workspace.project?.my_role === 'owner')
const roleLabels = {
  owner: '拥有者',
  member: '成员',
  viewer: '只读成员',
}
const editableRoleOptions = [
  { label: '成员', value: 'member' },
  { label: '只读成员', value: 'viewer' },
]

function roleTagType(role) {
  return {
    owner: 'success',
    member: 'primary',
    viewer: 'info',
  }[role] || 'info'
}

// 当前用户修改资料后优先读取全局用户状态，让成员列表无需刷新即可同步昵称。
function memberDisplayName(member) {
  const nickname = member.user === authStore.user?.id
    ? authStore.user.nickname
    : member.nickname

  return nickname || member.username
}

// owner 只能管理普通成员，拥有者所在行始终不提供删除入口。
function canRemoveMember(member) {
  return isOwner.value && member.role !== 'owner'
}

function canEditMemberRole(member) {
  return isOwner.value && member.role !== 'owner'
}

function isRoleUpdating(memberId) {
  return updatingMemberIds.value.has(memberId)
}

function setRoleUpdating(memberId, updating) {
  const nextIds = new Set(updatingMemberIds.value)
  if (updating) {
    nextIds.add(memberId)
  } else {
    nextIds.delete(memberId)
  }
  updatingMemberIds.value = nextIds
}

function roleUpdateErrorMessage(error) {
  const data = error.response?.data
  if (error.response?.status === 404) return '项目或成员不存在，或无权访问'
  if (error.response?.status === 403) return data?.detail || '只有拥有者可以修改成员身份'

  const roleMessage = Array.isArray(data?.role) ? data.role[0] : data?.role
  return roleMessage || data?.detail || '成员身份修改失败，请稍后重试'
}

async function changeMemberRole(member, nextRole) {
  if (nextRole === member.role || isRoleUpdating(member.id)) return

  const memberName = memberDisplayName(member)
  try {
    await ElMessageBox.confirm(
      `确认将“${memberName}”的身份从“${roleLabels[member.role]}”修改为“${roleLabels[nextRole]}”吗？`,
      '修改成员身份',
      {
        confirmButtonText: '确认修改',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  setRoleUpdating(member.id, true)
  try {
    const response = await updateProjectMemberRole(
      workspace.project.id,
      member.id,
      nextRole,
    )
    const memberIndex = members.value.findIndex((item) => item.id === member.id)
    if (memberIndex !== -1) {
      members.value.splice(memberIndex, 1, response.data)
    }
    ElMessage.success('成员身份已更新')
  } catch (error) {
    ElMessage.error(roleUpdateErrorMessage(error))
  } finally {
    setRoleUpdating(member.id, false)
  }
}

async function loadMembers() {
  loading.value = true
  loadError.value = false

  try {
    const response = await getProjectMembers(workspace.project.id)
    members.value = response.data
  } catch (error) {
    loadError.value = true
    const message = error.response?.status === 404
      ? '项目不存在或无权访问'
      : '项目成员加载失败'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

onMounted(loadMembers)
</script>

<template>
  <section class="member-section">
    <div class="page-heading member-heading">
      <div>
        <h2>项目成员</h2>
        <p>共 {{ members.length }} 位成员</p>
      </div>
      <el-button type="primary" :icon="Plus" :disabled="!isOwner">
        增加成员
      </el-button>
    </div>

    <div class="data-surface member-surface" v-loading="loading">
      <el-result
        v-if="loadError"
        icon="error"
        title="项目成员暂时无法加载"
      >
        <template #extra>
          <el-button type="primary" @click="loadMembers">重新加载</el-button>
        </template>
      </el-result>

      <el-table
        v-else-if="members.length"
        :data="members"
        row-key="id"
        class="member-table"
      >
        <el-table-column label="成员名称" width="300">
          <template #default="{ row }">
            <div class="member-name-cell">
              <strong>{{ memberDisplayName(row) }}</strong>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="唯一名称" width="220">
          <template #default="{ row }">
            <span class="member-username">{{ row.username }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成员身份" width="150">
          <template #default="{ row }">
            <el-select
              v-if="canEditMemberRole(row)"
              :model-value="row.role"
              class="member-role-select"
              size="small"
              :loading="isRoleUpdating(row.id)"
              :disabled="isRoleUpdating(row.id)"
              :aria-label="`设置 ${row.username} 的成员身份`"
              @change="(role) => changeMemberRole(row, role)"
            >
              <el-option
                v-for="option in editableRoleOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <el-tag v-else :type="roleTagType(row.role)" effect="plain">
              {{ roleLabels[row.role] || row.role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="删除成员" width="110" align="center">
          <template #default="{ row }">
            <el-tooltip v-if="canRemoveMember(row)" content="删除成员" placement="top">
              <el-button
                :icon="Delete"
                circle
                text
                type="danger"
                aria-label="删除成员"
              />
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column min-width="1" />
      </el-table>

      <el-empty v-else :image-size="72" description="当前项目还没有成员" />
    </div>
  </section>
</template>
