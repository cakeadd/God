<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Delete, Edit, Plus, Search, View } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createEnvironment,
  deactivateEnvironment,
  getEnvironment,
  getEnvironments,
  updateEnvironment,
} from '../api/environments'
import AppPagination from '../components/AppPagination.vue'
import { useProjectWorkspace } from '../composables/projectWorkspace'

const workspace = useProjectWorkspace()
const environments = ref([])
const loading = ref(false)
const loadError = ref(false)
const keyword = ref('')
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const dialogVisible = ref(false)
const dialogMode = ref('create')
const detailLoading = ref(false)
const saving = ref(false)
const selectedEnvironment = ref(null)
const formRef = ref()
const initialFormState = ref(null)
const removingEnvironmentIds = ref(new Set())

const editableRoles = ['owner', 'member']
const canEdit = computed(() => editableRoles.includes(workspace.project?.my_role))
const hasListFilters = computed(() => Boolean(keyword.value.trim()))
const dialogTitle = computed(() => ({
  create: '新增环境',
  edit: '编辑环境',
  view: '查看环境',
}[dialogMode.value]))
const formReadOnly = computed(() => detailLoading.value || dialogMode.value === 'view')

const form = reactive({
  name: '',
  baseUrl: '',
  variablesText: '{}',
  description: '',
  isDefault: false,
})

let environmentSearchTimer
let latestEnvironmentRequestId = 0

function normalizeJsonValue(value) {
  if (Array.isArray(value)) {
    return value.map(normalizeJsonValue)
  }

  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, normalizeJsonValue(value[key])]),
    )
  }

  return value
}

function parseJsonObject(value, label) {
  const source = value.trim() || '{}'
  let parsed

  try {
    parsed = JSON.parse(source)
  } catch {
    throw new Error(`${label}必须是合法 JSON`)
  }

  if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error(`${label}必须是 JSON 对象`)
  }

  return parsed
}

function comparableJsonValue(value) {
  try {
    return {
      valid: true,
      value: normalizeJsonValue(parseJsonObject(value, '环境变量')),
    }
  } catch {
    return {
      valid: false,
      value: value.trim(),
    }
  }
}

function currentFormState() {
  return {
    name: form.name.trim(),
    baseUrl: form.baseUrl.trim(),
    variables: comparableJsonValue(form.variablesText),
    description: form.description.trim(),
    isDefault: form.isDefault,
  }
}

const hasFormChanges = computed(() => (
  initialFormState.value !== null
  && JSON.stringify(currentFormState()) !== JSON.stringify(initialFormState.value)
))
const canSubmit = computed(() => (
  dialogMode.value === 'view'
    ? false
    : dialogMode.value === 'create'
    ? Boolean(form.name.trim() && form.baseUrl.trim())
    : hasFormChanges.value
))

function validateBaseUrl(_rule, value, callback) {
  const source = value.trim()
  if (!source) {
    callback(new Error('请输入基础地址'))
    return
  }

  try {
    const url = new URL(source)
    if (!['http:', 'https:'].includes(url.protocol)) {
      throw new Error('unsupported protocol')
    }
  } catch {
    callback(new Error('基础地址必须是完整的 http 或 https URL'))
    return
  }

  callback()
}

function jsonObjectValidator(_rule, value, callback) {
  try {
    parseJsonObject(value, '环境变量')
    callback()
  } catch (error) {
    callback(error)
  }
}

const rules = {
  name: [
    { required: true, message: '请输入环境名称', trigger: 'blur' },
    { max: 100, message: '环境名称不能超过 100 个字符', trigger: 'blur' },
  ],
  baseUrl: [{ validator: validateBaseUrl, trigger: 'blur' }],
  variablesText: [{ validator: jsonObjectValidator, trigger: 'blur' }],
  description: [{ max: 1000, message: '环境描述不能超过 1000 个字符', trigger: 'blur' }],
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

function prettyJson(value) {
  return JSON.stringify(value || {}, null, 2)
}

function fillForm(environment = null) {
  form.name = environment?.name || ''
  form.baseUrl = environment?.base_url || ''
  form.variablesText = prettyJson(environment?.variables)
  form.description = environment?.description || ''
  form.isDefault = environment?.is_default || false
  formRef.value?.clearValidate()
}

function captureFormState() {
  initialFormState.value = currentFormState()
}

function apiErrorMessage(error, fallback) {
  const data = error.response?.data
  if (!data) return fallback
  if (typeof data.detail === 'string') return data.detail

  const fieldLabels = {
    name: '环境名称',
    base_url: '基础地址',
    variables: '环境变量',
    description: '环境描述',
    is_default: '默认环境',
    non_field_errors: '环境配置',
  }
  const firstEntry = Object.entries(data)[0]
  if (!firstEntry) return fallback
  const [field, messages] = firstEntry
  const message = Array.isArray(messages) ? messages[0] : messages
  return `${fieldLabels[field] || field}：${message}`
}

async function loadEnvironments() {
  if (!workspace.project?.id) return

  // 只接收最后一次请求结果，避免快速搜索或翻页时旧响应覆盖新页面。
  const requestId = ++latestEnvironmentRequestId
  loading.value = true
  loadError.value = false
  try {
    const response = await getEnvironments(workspace.project.id, {
      page: currentPage.value,
      page_size: pageSize.value,
      search: keyword.value.trim() || undefined,
    })
    if (requestId !== latestEnvironmentRequestId) return
    environments.value = response.data.results
    total.value = response.data.count
  } catch (error) {
    if (requestId !== latestEnvironmentRequestId) return
    loadError.value = true
    ElMessage.error(apiErrorMessage(error, '环境列表加载失败'))
  } finally {
    if (requestId === latestEnvironmentRequestId) {
      loading.value = false
    }
  }
}

function changeEnvironmentPage(page) {
  currentPage.value = page
  loadEnvironments()
}

function changeEnvironmentPageSize(size) {
  pageSize.value = size
  currentPage.value = 1
  loadEnvironments()
}

function scheduleEnvironmentSearch() {
  clearTimeout(environmentSearchTimer)
  environmentSearchTimer = setTimeout(() => {
    currentPage.value = 1
    loadEnvironments()
  }, 300)
}

function openCreate() {
  if (!canEdit.value) return
  selectedEnvironment.value = null
  dialogMode.value = 'create'
  detailLoading.value = false
  fillForm()
  captureFormState()
  dialogVisible.value = true
}

async function openEdit(environment) {
  if (!canEdit.value) return
  selectedEnvironment.value = environment
  dialogMode.value = 'edit'
  dialogVisible.value = true
  detailLoading.value = true
  initialFormState.value = null

  try {
    const response = await getEnvironment(workspace.project.id, environment.id)
    selectedEnvironment.value = response.data
    fillForm(response.data)
    captureFormState()
  } catch (error) {
    dialogVisible.value = false
    ElMessage.error(apiErrorMessage(error, '环境详情加载失败'))
  } finally {
    detailLoading.value = false
  }
}

async function openView(environment) {
  selectedEnvironment.value = environment
  dialogMode.value = 'view'
  dialogVisible.value = true
  detailLoading.value = true
  initialFormState.value = null

  try {
    const response = await getEnvironment(workspace.project.id, environment.id)
    selectedEnvironment.value = response.data
    fillForm(response.data)
  } catch (error) {
    dialogVisible.value = false
    ElMessage.error(apiErrorMessage(error, '环境详情加载失败'))
  } finally {
    detailLoading.value = false
  }
}

async function confirmDiscardChanges() {
  if (dialogMode.value === 'view') return true
  if (!hasFormChanges.value) return true

  const isCreate = dialogMode.value === 'create'
  try {
    await ElMessageBox.confirm(
      isCreate ? '当前环境尚未创建，确认放弃吗？' : '当前修改尚未保存，确认放弃吗？',
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

async function handleDialogClose(done) {
  if (saving.value) return
  if (await confirmDiscardChanges()) done()
}

async function cancelDialog() {
  if (saving.value) return
  if (await confirmDiscardChanges()) {
    dialogVisible.value = false
  }
}

function resetDialog() {
  selectedEnvironment.value = null
  initialFormState.value = null
  dialogMode.value = 'create'
  fillForm()
}

function isRemoving(environmentId) {
  return removingEnvironmentIds.value.has(environmentId)
}

async function deactivateSelectedEnvironment(environment) {
  if (!canEdit.value || isRemoving(environment.id)) return

  try {
    await ElMessageBox.confirm(
      `确认停用环境“${environment.name}”吗？停用后它不能再用于新的测试用例和执行任务，但历史关联与执行记录会保留。`,
      '停用环境',
      {
        confirmButtonText: '确认停用',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  removingEnvironmentIds.value = new Set([
    ...removingEnvironmentIds.value,
    environment.id,
  ])
  try {
    await deactivateEnvironment(workspace.project.id, environment.id)

    // 当前页仅剩一条时先回退页码，避免停用后落到空白页。
    if (environments.value.length === 1 && currentPage.value > 1) {
      currentPage.value -= 1
    }
    await loadEnvironments()
    ElMessage.success('环境已停用')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '环境停用失败，请稍后重试'))
  } finally {
    const nextRemovingIds = new Set(removingEnvironmentIds.value)
    nextRemovingIds.delete(environment.id)
    removingEnvironmentIds.value = nextRemovingIds
  }
}

function buildPayload() {
  return {
    name: form.name.trim(),
    base_url: form.baseUrl.trim(),
    variables: parseJsonObject(form.variablesText, '环境变量'),
    description: form.description.trim(),
    is_default: form.isDefault,
  }
}

async function submitEnvironment() {
  if (dialogMode.value === 'view') return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid || !canSubmit.value) return

  const isCreate = dialogMode.value === 'create'
  if (!isCreate && !selectedEnvironment.value) return

  saving.value = true
  try {
    const response = isCreate
      ? await createEnvironment(workspace.project.id, buildPayload())
      : await updateEnvironment(
        workspace.project.id,
        selectedEnvironment.value.id,
        buildPayload(),
      )

    selectedEnvironment.value = response.data
    dialogVisible.value = false
    if (isCreate) currentPage.value = 1
    await loadEnvironments()
    ElMessage.success(isCreate ? '环境已创建' : '环境已更新')
  } catch (error) {
    ElMessage.error(apiErrorMessage(
      error,
      dialogMode.value === 'create' ? '环境创建失败，请稍后重试' : '环境保存失败，请稍后重试',
    ))
  } finally {
    saving.value = false
  }
}

watch(keyword, scheduleEnvironmentSearch)
onMounted(loadEnvironments)
onBeforeUnmount(() => clearTimeout(environmentSearchTimer))
</script>

<template>
  <section class="environment-section">
    <div class="page-heading environment-heading">
      <div>
        <h2>环境管理</h2>
        <p>共 {{ total }} 个启用环境</p>
      </div>
    </div>

    <div class="environment-toolbar">
      <el-input
        v-model="keyword"
        class="environment-toolbar__search"
        :prefix-icon="Search"
        clearable
        placeholder="搜索环境名称"
        aria-label="搜索环境名称"
      />
      <el-button type="primary" :icon="Plus" :disabled="!canEdit" @click="openCreate">
        新增环境
      </el-button>
    </div>

    <div class="data-surface environment-surface" v-loading="loading">
      <el-result
        v-if="loadError"
        icon="error"
        title="环境列表暂时无法加载"
      >
        <template #extra>
          <el-button type="primary" @click="loadEnvironments">重新加载</el-button>
        </template>
      </el-result>

      <el-table
        v-else-if="environments.length"
        :data="environments"
        row-key="id"
        class="environment-table"
        @row-click="openView"
      >
        <el-table-column prop="name" label="环境名称" width="180" />
        <el-table-column label="基础地址" width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <code class="environment-base-url">{{ row.base_url }}</code>
          </template>
        </el-table-column>
        <el-table-column label="默认环境" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="描述" width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '-' }}</template>
        </el-table-column>
        <el-table-column label="更新时间" width="176">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="132" align="center">
          <template #default="{ row }">
            <div class="table-actions" @click.stop>
              <el-tooltip content="查看" placement="top">
                <el-button :icon="View" circle text aria-label="查看环境" @click="openView(row)" />
              </el-tooltip>
              <el-tooltip content="编辑" placement="top">
                <el-button
                  :icon="Edit"
                  circle
                  text
                  :disabled="!canEdit || isRemoving(row.id)"
                  aria-label="编辑环境"
                  @click="openEdit(row)"
                />
              </el-tooltip>
              <el-tooltip content="停用" placement="top">
                <el-button
                  :icon="Delete"
                  circle
                  text
                  type="danger"
                  :loading="isRemoving(row.id)"
                  :disabled="!canEdit || isRemoving(row.id)"
                  aria-label="停用环境"
                  @click="deactivateSelectedEnvironment(row)"
                />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column min-width="1" />
      </el-table>

      <el-empty
        v-else
        :image-size="72"
        :description="hasListFilters ? '没有匹配的环境' : '当前项目还没有启用环境'"
      />

      <AppPagination
        v-if="total > 0 && !loadError"
        :total="total"
        :current-page="currentPage"
        :page-size="pageSize"
        :disabled="loading"
        @page-change="changeEnvironmentPage"
        @page-size-change="changeEnvironmentPageSize"
      />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="680px"
      class="environment-dialog"
      align-center
      destroy-on-close
      :before-close="handleDialogClose"
      @closed="resetDialog"
    >
      <div v-loading="detailLoading">
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
          <el-form-item label="环境名称" prop="name">
            <el-input v-model="form.name" maxlength="100" show-word-limit :disabled="formReadOnly" />
          </el-form-item>
          <el-form-item label="基础地址" prop="baseUrl">
            <el-input
              v-model="form.baseUrl"
              placeholder="https://api.example.com"
              :disabled="formReadOnly"
            />
          </el-form-item>
          <el-form-item label="环境变量（JSON 对象）" prop="variablesText">
            <el-input
              v-model="form.variablesText"
              type="textarea"
              :autosize="{ minRows: 6, maxRows: 12 }"
              spellcheck="false"
              class="json-editor"
              :disabled="formReadOnly"
            />
          </el-form-item>
          <el-form-item label="环境描述" prop="description">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="3"
              maxlength="1000"
              show-word-limit
              :disabled="formReadOnly"
            />
          </el-form-item>
          <el-form-item label="设为默认环境" prop="isDefault">
            <el-switch v-model="form.isDefault" :disabled="formReadOnly" />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <div v-if="dialogMode === 'view'" class="dialog-actions">
          <el-button type="primary" @click="dialogVisible = false">关闭</el-button>
        </div>
        <div v-else class="dialog-actions">
          <el-button :disabled="saving" @click="cancelDialog">取消</el-button>
          <el-button
            type="primary"
            :loading="saving"
            :disabled="detailLoading || !canSubmit"
            @click="submitEnvironment"
          >
            {{ dialogMode === 'create' ? '创建环境' : '保存修改' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>
