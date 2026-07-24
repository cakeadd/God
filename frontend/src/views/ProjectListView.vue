<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createProject,
  getProject,
  getProjects,
  updateProject,
} from '../api/projects'

const router = useRouter()
const projects = ref([])
const loading = ref(false)
const loadError = ref(false)
const projectDialogVisible = ref(false)
const projectDialogMode = ref('create')
const projectDialogLoading = ref(false)
const projectSaving = ref(false)
const editingProject = ref(null)
const projectFormRef = ref()
const projectForm = reactive({
  name: '',
  description: '',
})
const initialProjectForm = ref({
  name: '',
  description: '',
})

const roleLabels = {
  owner: '拥有者',
  member: '成员',
  viewer: '访客',
}

const hasProjects = computed(() => projects.value.length > 0)
const projectDialogTitle = computed(() => (
  projectDialogMode.value === 'create' ? '新增项目' : '编辑项目'
))
const hasProjectChanges = computed(() => (
  projectForm.name.trim() !== initialProjectForm.value.name
  || projectForm.description.trim() !== initialProjectForm.value.description
))
const canSubmitProject = computed(() => (
  projectDialogMode.value === 'create'
    ? Boolean(projectForm.name.trim())
    : hasProjectChanges.value
))

function validateProjectName(_rule, value, callback) {
  if (!value.trim()) {
    callback(new Error('请输入项目名称'))
    return
  }
  callback()
}

const projectRules = {
  name: [
    { validator: validateProjectName, trigger: 'blur' },
    { max: 100, message: '项目名称不能超过 100 个字符', trigger: 'blur' },
  ],
}

function formatTime(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function openProject(project) {
  router.push({
    name: 'project-endpoints',
    params: { projectId: project.id },
  })
}

function fillProjectForm(project = null) {
  const name = project?.name || ''
  const description = project?.description || ''

  projectForm.name = name
  projectForm.description = description
  initialProjectForm.value = { name, description }
  projectFormRef.value?.clearValidate()
}

function projectApiErrorMessage(error, fallback) {
  const data = error.response?.data
  if (!data) return fallback
  if (typeof data.detail === 'string') return data.detail

  const firstEntry = Object.entries(data)[0]
  if (!firstEntry) return fallback
  const [field, messages] = firstEntry
  const message = Array.isArray(messages) ? messages[0] : messages
  const fieldLabels = {
    name: '项目名称',
    description: '项目描述',
  }
  return `${fieldLabels[field] || field}：${message}`
}

function openCreate() {
  editingProject.value = null
  projectDialogMode.value = 'create'
  projectDialogLoading.value = false
  fillProjectForm()
  projectDialogVisible.value = true
}

async function openEdit(project) {
  editingProject.value = project
  projectDialogMode.value = 'edit'
  fillProjectForm(project)
  projectDialogVisible.value = true
  projectDialogLoading.value = true

  try {
    const response = await getProject(project.id)
    editingProject.value = response.data
    fillProjectForm(response.data)
  } catch (error) {
    projectDialogVisible.value = false
    ElMessage.error(projectApiErrorMessage(error, '项目详情加载失败'))
  } finally {
    projectDialogLoading.value = false
  }
}

async function confirmDiscardChanges() {
  if (!hasProjectChanges.value) return true

  const isCreate = projectDialogMode.value === 'create'

  try {
    await ElMessageBox.confirm(
      isCreate ? '当前项目尚未创建，确认放弃吗？' : '当前修改尚未保存，确认放弃吗？',
      isCreate ? '放弃创建' : '放弃修改',
      {
        confirmButtonText: isCreate ? '确认放弃创建' : '确认放弃',
        cancelButtonText: isCreate ? '继续填写' : '继续编辑',
        type: 'warning',
      },
    )
    return true
  } catch {
    return false
  }
}

async function handleProjectDialogClose(done) {
  if (projectSaving.value) return
  if (await confirmDiscardChanges()) done()
}

async function cancelProjectDialog() {
  if (projectSaving.value) return
  if (await confirmDiscardChanges()) {
    projectDialogVisible.value = false
  }
}

function resetProjectDialog() {
  editingProject.value = null
  projectDialogMode.value = 'create'
  projectForm.name = ''
  projectForm.description = ''
  initialProjectForm.value = { name: '', description: '' }
}

async function submitProject() {
  const valid = await projectFormRef.value.validate().catch(() => false)
  if (!valid || !canSubmitProject.value) return

  const isCreate = projectDialogMode.value === 'create'
  if (!isCreate && !editingProject.value) return

  projectSaving.value = true
  try {
    const payload = {
      name: projectForm.name.trim(),
      description: projectForm.description.trim(),
    }
    // 创建后插入列表，编辑后替换原记录，两种模式都避免额外刷新。
    const response = isCreate
      ? await createProject(payload)
      : await updateProject(editingProject.value.id, payload)
    const savedProject = response.data

    if (isCreate) {
      projects.value.unshift(savedProject)
      loadError.value = false
    } else {
      const projectIndex = projects.value.findIndex(
        (project) => project.id === savedProject.id,
      )
      if (projectIndex !== -1) {
        projects.value.splice(projectIndex, 1, savedProject)
      }
    }

    editingProject.value = savedProject
    fillProjectForm(savedProject)
    projectDialogVisible.value = false
    ElMessage.success(isCreate ? '项目已创建' : '项目已更新')
  } catch (error) {
    if (!isCreate && error.response?.status === 404) {
      projectDialogVisible.value = false
      ElMessage.error('项目不存在或无权访问')
      await loadProjects()
      return
    }
    ElMessage.error(projectApiErrorMessage(
      error,
      isCreate ? '项目创建失败，请稍后重试' : '项目保存失败，请稍后重试',
    ))
  } finally {
    projectSaving.value = false
  }
}

async function loadProjects() {
  loading.value = true
  loadError.value = false
  try {
    const response = await getProjects()
    projects.value = response.data
  } catch {
    loadError.value = true
    ElMessage.error('项目列表加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadProjects)
</script>

<template>
  <section class="workspace-section">
    <div class="page-heading">
      <div>
        <h1>项目</h1>
        <p>你参与的接口测试项目</p>
      </div>
      <div class="page-heading__actions">
        <el-button type="primary" :icon="Plus" @click="openCreate">
          新增项目
        </el-button>
        <el-tooltip content="刷新项目列表" placement="bottom">
          <el-button :icon="Refresh" circle :loading="loading" aria-label="刷新项目列表" @click="loadProjects" />
        </el-tooltip>
      </div>
    </div>

    <div class="data-surface" v-loading="loading">
      <el-alert
        v-if="loadError"
        title="项目列表暂时无法加载"
        type="error"
        :closable="false"
        show-icon
      />

      <el-table
        v-else-if="hasProjects"
        :data="projects"
        class="project-table"
        row-key="id"
        @row-click="openProject"
      >
        <el-table-column label="项目" min-width="260">
          <template #default="{ row }">
            <div class="project-name-cell">
              <strong>{{ row.name }}</strong>
              <span>{{ row.description || '暂无描述' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag effect="plain" type="success">{{ roleLabels[row.my_role] || row.my_role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="owner_username" label="拥有者" width="150" />
        <el-table-column label="更新时间" width="190">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="编辑" width="72" align="center">
          <template #default="{ row }">
            <el-tooltip v-if="row.my_role === 'owner'" content="编辑项目" placement="top">
              <el-button
                :icon="Edit"
                circle
                text
                aria-label="编辑项目"
                @click.stop="openEdit(row)"
              />
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="删除" width="72" align="center">
          <template #default="{ row }">
            <el-tooltip v-if="row.my_role === 'owner'" content="删除项目" placement="top">
              <el-button
                :icon="Delete"
                circle
                text
                type="danger"
                aria-label="删除项目"
                @click.stop
              />
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-else :image-size="72" description="你还没有参与任何项目" />
    </div>

    <el-dialog
      v-model="projectDialogVisible"
      :title="projectDialogTitle"
      width="560px"
      align-center
      destroy-on-close
      :before-close="handleProjectDialogClose"
      @closed="resetProjectDialog"
    >
      <div v-loading="projectDialogLoading">
        <el-form
          ref="projectFormRef"
          :model="projectForm"
          :rules="projectRules"
          label-position="top"
        >
          <el-form-item label="项目名称" prop="name">
            <el-input
              v-model="projectForm.name"
              maxlength="100"
              show-word-limit
              :disabled="projectDialogLoading"
            />
          </el-form-item>
          <el-form-item label="项目描述" prop="description">
            <el-input
              v-model="projectForm.description"
              type="textarea"
              :rows="6"
              :disabled="projectDialogLoading"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <div class="dialog-actions">
          <el-button :disabled="projectSaving" @click="cancelProjectDialog">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="projectSaving"
            :disabled="projectDialogLoading || !canSubmitProject"
            @click="submitProject"
          >
            {{ projectDialogMode === 'create' ? '创建项目' : '保存修改' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>
