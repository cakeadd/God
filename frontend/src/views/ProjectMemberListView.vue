<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Delete, Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  addProjectMember,
  getProjectMemberCandidates,
  getProjectMembers,
  removeProjectMember,
  updateProjectMemberRole,
} from '../api/projectMembers'
import AppPagination from '../components/AppPagination.vue'
import { useProjectWorkspace } from '../composables/projectWorkspace'
import { useAuthStore } from '../stores/auth'

const workspace = useProjectWorkspace()
const authStore = useAuthStore()
const members = ref([])
const loading = ref(false)
const loadError = ref(false)
const keyword = ref('')
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const updatingMemberIds = ref(new Set())
const removingMemberIds = ref(new Set())
const addDialogVisible = ref(false)
const candidateUsers = ref([])
const candidateLoading = ref(false)
const candidateLoadError = ref(false)
const candidateKeyword = ref('')
const selectedCandidateId = ref(null)
const selectedRole = ref('member')
const addingMember = ref(false)

const isOwner = computed(() => workspace.project?.my_role === 'owner')
const memberEmptyDescription = computed(() => (
  keyword.value.trim() ? '没有匹配的项目成员' : '当前项目还没有成员'
))
const filteredCandidateUsers = computed(() => {
  const normalizedKeyword = candidateKeyword.value.trim().toLowerCase()
  if (!normalizedKeyword) return candidateUsers.value

  return candidateUsers.value.filter((user) => (
    [user.username, user.nickname]
      .some((value) => value?.toLowerCase().includes(normalizedKeyword))
  ))
})
const candidateEmptyDescription = computed(() => (
  candidateKeyword.value.trim() ? '没有匹配的用户' : '当前没有可展示的用户'
))
const roleLabels = {
  owner: '拥有者',
  member: '成员',
  viewer: '只读成员',
}
const editableRoleOptions = [
  { label: '成员', value: 'member' },
  { label: '只读成员', value: 'viewer' },
]

let memberSearchTimer
let latestMemberRequestId = 0

function roleTagType(role) {
  return {
    owner: 'success',
    member: 'primary',
    viewer: 'info',
  }[role] || 'info'
}

function candidateDisplayName(user) {
  return user.nickname || user.username
}

function candidateStatusLabel(user) {
  return user.is_project_member
    ? `已加入 · ${roleLabels[user.project_role] || user.project_role}`
    : '未加入'
}

function candidateStatusType(user) {
  return user.is_project_member ? 'info' : 'success'
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

function isMemberRemoving(memberId) {
  return removingMemberIds.value.has(memberId)
}

function setMemberRemoving(memberId, removing) {
  const nextIds = new Set(removingMemberIds.value)
  if (removing) {
    nextIds.add(memberId)
  } else {
    nextIds.delete(memberId)
  }
  removingMemberIds.value = nextIds
}

function roleUpdateErrorMessage(error) {
  const data = error.response?.data
  if (error.response?.status === 404) return '项目或成员不存在，或无权访问'
  if (error.response?.status === 403) return data?.detail || '只有拥有者可以修改成员身份'

  const roleMessage = Array.isArray(data?.role) ? data.role[0] : data?.role
  return roleMessage || data?.detail || '成员身份修改失败，请稍后重试'
}

function memberRemovalErrorMessage(error) {
  const data = error.response?.data
  if (error.response?.status === 404) return '项目或成员不存在，或无权访问'
  if (error.response?.status === 403) return data?.detail || '只有拥有者可以移除项目成员'
  return data?.detail || '成员移除失败，请稍后重试'
}

function memberAdditionErrorMessage(error) {
  const data = error.response?.data
  if (error.response?.status === 404) return '项目或用户不存在，或无权访问'
  if (error.response?.status === 403) return data?.detail || '只有拥有者可以增加项目成员'

  const userMessage = Array.isArray(data?.user) ? data.user[0] : data?.user
  const roleMessage = Array.isArray(data?.role) ? data.role[0] : data?.role
  return userMessage || roleMessage || data?.detail || '成员添加失败，请稍后重试'
}

async function loadMemberCandidates() {
  candidateLoading.value = true
  candidateLoadError.value = false

  try {
    const response = await getProjectMemberCandidates(workspace.project.id)
    candidateUsers.value = response.data
  } catch (error) {
    candidateLoadError.value = true
    ElMessage.error(memberAdditionErrorMessage(error))
  } finally {
    candidateLoading.value = false
  }
}

async function openAddMemberDialog() {
  if (!isOwner.value) return

  candidateKeyword.value = ''
  selectedCandidateId.value = null
  selectedRole.value = 'member'
  addDialogVisible.value = true
  await loadMemberCandidates()
}

function selectCandidate(user) {
  if (!user.is_project_member) {
    selectedCandidateId.value = user.id
  }
}

async function addMember() {
  if (!selectedCandidateId.value || addingMember.value) return

  addingMember.value = true
  try {
    await addProjectMember(
      workspace.project.id,
      selectedCandidateId.value,
      selectedRole.value,
    )
    currentPage.value = 1
    await loadMembers()
    ElMessage.success('项目成员已添加')
    addDialogVisible.value = false
  } catch (error) {
    ElMessage.error(memberAdditionErrorMessage(error))
    if (error.response?.status === 400) {
      await loadMemberCandidates()
    }
  } finally {
    addingMember.value = false
  }
}

async function handleAddDialogClose(done) {
  if (addingMember.value) return
  if (!selectedCandidateId.value) {
    done()
    return
  }

  try {
    await ElMessageBox.confirm(
      '当前选择尚未添加，确认放弃吗？',
      '放弃添加成员',
      {
        confirmButtonText: '确认放弃',
        cancelButtonText: '继续编辑',
        type: 'warning',
      },
    )
    done()
  } catch {
    // 用户选择继续编辑时保持弹窗和当前选择不变。
  }
}

function closeAddMemberDialog() {
  handleAddDialogClose(() => {
    addDialogVisible.value = false
  })
}

function resetAddMemberDialog() {
  candidateUsers.value = []
  candidateKeyword.value = ''
  selectedCandidateId.value = null
  selectedRole.value = 'member'
  candidateLoadError.value = false
}

async function changeMemberRole(member, nextRole) {
  if (
    nextRole === member.role
    || isRoleUpdating(member.id)
    || isMemberRemoving(member.id)
  ) return

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

async function removeMember(member) {
  if (!canRemoveMember(member) || isMemberRemoving(member.id)) return

  const displayName = memberDisplayName(member)
  const memberLabel = displayName === member.username
    ? member.username
    : `${displayName}（${member.username}）`

  try {
    await ElMessageBox.confirm(
      `确认将“${memberLabel}”移出项目吗？移除后该用户将立即失去项目访问权限，其创建的接口、用例和历史执行记录仍会保留。`,
      '移除项目成员',
      {
        confirmButtonText: '确认移除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  setMemberRemoving(member.id, true)
  try {
    await removeProjectMember(workspace.project.id, member.id)
    if (members.value.length === 1 && currentPage.value > 1) {
      currentPage.value -= 1
    }
    await loadMembers()
    ElMessage.success('成员已移出项目')
  } catch (error) {
    ElMessage.error(memberRemovalErrorMessage(error))
    if (error.response?.status === 404) {
      await loadMembers()
    }
  } finally {
    setMemberRemoving(member.id, false)
  }
}

async function loadMembers() {
  // 只接收最后一次请求结果，避免快速搜索或翻页时旧响应覆盖新页面。
  const requestId = ++latestMemberRequestId
  loading.value = true
  loadError.value = false

  try {
    const response = await getProjectMembers(workspace.project.id, {
      page: currentPage.value,
      page_size: pageSize.value,
      search: keyword.value.trim() || undefined,
    })
    if (requestId !== latestMemberRequestId) return

    members.value = response.data.results
    total.value = response.data.count
  } catch (error) {
    if (requestId !== latestMemberRequestId) return
    loadError.value = true
    const message = error.response?.status === 404
      ? '项目不存在或无权访问'
      : '项目成员加载失败'
    ElMessage.error(message)
  } finally {
    if (requestId === latestMemberRequestId) {
      loading.value = false
    }
  }
}

function changeMemberPage(page) {
  currentPage.value = page
  loadMembers()
}

function changeMemberPageSize(size) {
  pageSize.value = size
  currentPage.value = 1
  loadMembers()
}

function scheduleMemberSearch() {
  clearTimeout(memberSearchTimer)
  memberSearchTimer = setTimeout(() => {
    currentPage.value = 1
    loadMembers()
  }, 300)
}

watch(keyword, scheduleMemberSearch)
onMounted(loadMembers)
onBeforeUnmount(() => clearTimeout(memberSearchTimer))
</script>

<template>
  <section class="member-section">
    <div class="page-heading member-heading">
      <div>
        <h2>项目成员</h2>
        <p>共 {{ total }} 位成员</p>
      </div>
    </div>

    <div class="member-toolbar">
      <el-input
        v-model="keyword"
        class="member-toolbar__search"
        :prefix-icon="Search"
        clearable
        placeholder="搜索成员名称或唯一名称"
        aria-label="搜索成员名称或唯一名称"
      />
      <el-button
        type="primary"
        :icon="Plus"
        :disabled="!isOwner"
        @click="openAddMemberDialog"
      >
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
              :disabled="isRoleUpdating(row.id) || isMemberRemoving(row.id)"
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
        <el-table-column label="移除成员" width="110" align="center">
          <template #default="{ row }">
            <el-tooltip v-if="canRemoveMember(row)" content="移除成员" placement="top">
              <el-button
                :icon="Delete"
                circle
                text
                type="danger"
                :loading="isMemberRemoving(row.id)"
                :disabled="isRoleUpdating(row.id) || isMemberRemoving(row.id)"
                aria-label="移除成员"
                @click="removeMember(row)"
              />
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column min-width="1" />
      </el-table>

      <el-empty v-else :image-size="72" :description="memberEmptyDescription" />

      <AppPagination
        v-if="total > 0 && !loadError"
        :total="total"
        :current-page="currentPage"
        :page-size="pageSize"
        :disabled="loading"
        @page-change="changeMemberPage"
        @page-size-change="changeMemberPageSize"
      />
    </div>
  </section>

  <el-dialog
    v-model="addDialogVisible"
    title="增加项目成员"
    width="720px"
    class="member-add-dialog"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    :before-close="handleAddDialogClose"
    @closed="resetAddMemberDialog"
  >
    <p class="member-add-description">
      选择一个已注册用户，并设置其在当前项目中的身份。
    </p>

    <el-input
      v-model="candidateKeyword"
      :prefix-icon="Search"
      clearable
      placeholder="搜索成员名称或唯一名称"
      aria-label="搜索待添加用户"
      class="member-candidate-search"
    />

    <div class="member-candidate-surface" v-loading="candidateLoading">
      <el-result
        v-if="candidateLoadError"
        icon="error"
        title="用户列表暂时无法加载"
      >
        <template #extra>
          <el-button type="primary" @click="loadMemberCandidates">重新加载</el-button>
        </template>
      </el-result>

      <el-table
        v-else-if="filteredCandidateUsers.length"
        :data="filteredCandidateUsers"
        row-key="id"
        height="340"
        class="member-candidate-table"
        @row-click="selectCandidate"
      >
        <el-table-column label="选择" width="72" align="center">
          <template #default="{ row }">
            <el-radio
              v-model="selectedCandidateId"
              :value="row.id"
              :disabled="row.is_project_member"
              :aria-label="`选择 ${row.username}`"
              @click.stop
            >
              <span class="visually-hidden">选择 {{ row.username }}</span>
            </el-radio>
          </template>
        </el-table-column>
        <el-table-column label="成员名称" min-width="180">
          <template #default="{ row }">
            <strong>{{ candidateDisplayName(row) }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="唯一名称" min-width="170">
          <template #default="{ row }">
            <span class="member-username">{{ row.username }}</span>
          </template>
        </el-table-column>
        <el-table-column label="当前状态" width="160">
          <template #default="{ row }">
            <el-tag :type="candidateStatusType(row)" effect="plain">
              {{ candidateStatusLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-else
        :image-size="64"
        :description="candidateEmptyDescription"
      />
    </div>

    <template #footer>
      <div class="member-add-footer">
        <div class="member-role-picker">
          <span>成员身份</span>
          <el-select
            v-model="selectedRole"
            :disabled="!selectedCandidateId || addingMember"
            aria-label="选择成员身份"
          >
            <el-option
              v-for="option in editableRoleOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>
        <div class="dialog-actions">
          <el-button :disabled="addingMember" @click="closeAddMemberDialog">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="addingMember"
            :disabled="!selectedCandidateId || candidateLoadError"
            @click="addMember"
          >
            确认添加
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>
