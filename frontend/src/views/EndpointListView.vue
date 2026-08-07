<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  Delete,
  Edit,
  Plus,
  Search,
  View,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createEndpoint,
  deactivateEndpoint,
  getEndpoint,
  getEndpoints,
  updateEndpoint,
} from '../api/endpoints'
import AppPagination from '../components/AppPagination.vue'
import { useProjectWorkspace } from '../composables/projectWorkspace'

const workspace = useProjectWorkspace()
const endpoints = ref([])
const loading = ref(false)
const loadError = ref(false)
const keyword = ref('')
const methodFilter = ref('')
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const dialogVisible = ref(false)
const dialogMode = ref('view')
const detailLoading = ref(false)
const saving = ref(false)
const selectedEndpoint = ref(null)
const formRef = ref()
const initialEditState = ref(null)

const methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
const editableRoles = ['owner', 'member']
const canEdit = computed(() => editableRoles.includes(workspace.project?.my_role))
const isReadOnly = computed(() => dialogMode.value === 'view')
const dialogTitle = computed(() => {
  if (dialogMode.value === 'create') return '新增接口'
  if (dialogMode.value === 'edit') return '编辑接口'
  return '接口详情'
})

const form = reactive({
  name: '',
  method: 'GET',
  path: '',
  description: '',
  headersText: '{}',
  queryParamsText: '{}',
  bodyText: '{}',
})

// 比较 JSON 的实际内容，避免空格、缩进和对象键顺序被误判为修改。
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
      value: normalizeJsonValue(parseJsonObject(value, 'JSON')),
    }
  } catch {
    return {
      valid: false,
      value: value.trim(),
    }
  }
}

function currentEditState() {
  return {
    name: form.name.trim(),
    method: form.method,
    path: form.path.trim(),
    description: form.description.trim(),
    headers: comparableJsonValue(form.headersText),
    queryParams: comparableJsonValue(form.queryParamsText),
    body: comparableJsonValue(form.bodyText),
  }
}

const hasEditChanges = computed(() => (
  dialogMode.value === 'edit'
  && initialEditState.value !== null
  && JSON.stringify(currentEditState()) !== JSON.stringify(initialEditState.value)
))

function jsonObjectValidator(label) {
  return (_rule, value, callback) => {
    try {
      parseJsonObject(value, label)
      callback()
    } catch (error) {
      callback(error)
    }
  }
}

const rules = {
  name: [{ required: true, message: '请输入接口名称', trigger: 'blur' }],
  method: [{ required: true, message: '请选择请求方法', trigger: 'change' }],
  path: [{ required: true, message: '请输入接口路径', trigger: 'blur' }],
  headersText: [{ validator: jsonObjectValidator('请求头'), trigger: 'blur' }],
  queryParamsText: [{ validator: jsonObjectValidator('Query 参数'), trigger: 'blur' }],
  bodyText: [{ validator: jsonObjectValidator('请求体'), trigger: 'blur' }],
}

const hasListFilters = computed(() => Boolean(keyword.value.trim() || methodFilter.value))

let endpointSearchTimer
let latestEndpointRequestId = 0

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

function methodTagType(method) {
  return {
    GET: 'success',
    POST: 'primary',
    PUT: 'warning',
    PATCH: 'warning',
    DELETE: 'danger',
  }[method] || 'info'
}

function prettyJson(value) {
  return JSON.stringify(value || {}, null, 2)
}

function fillForm(endpoint = null) {
  form.name = endpoint?.name || ''
  form.method = endpoint?.method || 'GET'
  form.path = endpoint?.path || ''
  form.description = endpoint?.description || ''
  form.headersText = prettyJson(endpoint?.headers)
  form.queryParamsText = prettyJson(endpoint?.query_params)
  form.bodyText = prettyJson(endpoint?.body)
  formRef.value?.clearValidate()
}

function captureEditState() {
  initialEditState.value = currentEditState()
}

function apiErrorMessage(error, fallback) {
  const data = error.response?.data
  if (!data) return fallback
  if (typeof data.detail === 'string') return data.detail

  const fieldLabels = {
    name: '接口名称',
    method: '请求方法',
    path: '接口路径',
    headers: '请求头',
    query_params: 'Query 参数',
    body: '请求体',
    non_field_errors: '接口配置',
  }

  const firstEntry = Object.entries(data)[0]
  if (!firstEntry) return fallback
  const [field, messages] = firstEntry
  const message = Array.isArray(messages) ? messages[0] : messages
  return `${fieldLabels[field] || field}：${message}`
}

async function loadEndpoints() {
  // 只接收最后一次请求结果，避免快速搜索或翻页时旧响应覆盖新页面。
  const requestId = ++latestEndpointRequestId
  loading.value = true
  loadError.value = false

  try {
    const response = await getEndpoints(workspace.project.id, {
      page: currentPage.value,
      page_size: pageSize.value,
      search: keyword.value.trim() || undefined,
      method: methodFilter.value || undefined,
    })
    if (requestId !== latestEndpointRequestId) return

    endpoints.value = response.data.results
    total.value = response.data.count
  } catch (error) {
    if (requestId !== latestEndpointRequestId) return
    loadError.value = true
    ElMessage.error(apiErrorMessage(error, '接口列表加载失败'))
  } finally {
    if (requestId === latestEndpointRequestId) {
      loading.value = false
    }
  }
}

function changeEndpointPage(page) {
  currentPage.value = page
  loadEndpoints()
}

function changeEndpointPageSize(size) {
  pageSize.value = size
  currentPage.value = 1
  loadEndpoints()
}

function scheduleEndpointSearch() {
  clearTimeout(endpointSearchTimer)
  endpointSearchTimer = setTimeout(() => {
    currentPage.value = 1
    loadEndpoints()
  }, 300)
}

function openCreate() {
  selectedEndpoint.value = null
  initialEditState.value = null
  dialogMode.value = 'create'
  fillForm()
  dialogVisible.value = true
}

async function openEndpoint(endpoint, mode = 'view') {
  initialEditState.value = null
  dialogVisible.value = true
  dialogMode.value = mode
  detailLoading.value = true

  try {
    const response = await getEndpoint(workspace.project.id, endpoint.id)
    selectedEndpoint.value = response.data
    fillForm(response.data)
    if (mode === 'edit') {
      captureEditState()
    } else {
      initialEditState.value = null
    }
  } catch (error) {
    dialogVisible.value = false
    ElMessage.error(apiErrorMessage(error, '接口详情加载失败'))
  } finally {
    detailLoading.value = false
  }
}

function startEdit() {
  if (!selectedEndpoint.value || !canEdit.value) return
  dialogMode.value = 'edit'
  fillForm(selectedEndpoint.value)
  captureEditState()
}

async function confirmDiscardEdit() {
  if (!hasEditChanges.value) return true

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

async function handleDialogClose(done) {
  if (saving.value) return
  if (dialogMode.value === 'edit' && !(await confirmDiscardEdit())) return
  initialEditState.value = null
  done()
}

async function cancelEdit() {
  if (saving.value) return

  if (dialogMode.value === 'create') {
    dialogVisible.value = false
    return
  }

  if (!await confirmDiscardEdit()) return

  dialogMode.value = 'view'
  fillForm(selectedEndpoint.value)
  initialEditState.value = null
}

function buildPayload() {
  return {
    name: form.name.trim(),
    method: form.method,
    path: form.path.trim(),
    description: form.description.trim(),
    headers: parseJsonObject(form.headersText, '请求头'),
    query_params: parseJsonObject(form.queryParamsText, 'Query 参数'),
    body: parseJsonObject(form.bodyText, '请求体'),
  }
}

async function submitEndpoint() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid || (dialogMode.value === 'edit' && !hasEditChanges.value)) return

  saving.value = true
  try {
    const payload = buildPayload()
    const response = dialogMode.value === 'create'
      ? await createEndpoint(workspace.project.id, payload)
      : await updateEndpoint(
        workspace.project.id,
        selectedEndpoint.value.id,
        payload,
      )

    const savedEndpoint = response.data
    const existingIndex = endpoints.value.findIndex((item) => item.id === savedEndpoint.id)
    selectedEndpoint.value = savedEndpoint
    dialogMode.value = 'view'
    fillForm(savedEndpoint)
    initialEditState.value = null
    if (existingIndex === -1) {
      currentPage.value = 1
    }
    await loadEndpoints()
    ElMessage.success(existingIndex === -1 ? '接口已创建' : '接口已更新')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '接口保存失败'))
  } finally {
    saving.value = false
  }
}

async function confirmDeactivate(endpoint) {
  try {
    await ElMessageBox.confirm(
      `停用后，“${endpoint.name}”将从当前接口列表移除，但不会物理删除数据。`,
      '停用接口',
      {
        confirmButtonText: '确认停用',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  try {
    await deactivateEndpoint(workspace.project.id, endpoint.id)
    if (endpoints.value.length === 1 && currentPage.value > 1) {
      currentPage.value -= 1
    }
    await loadEndpoints()
    if (selectedEndpoint.value?.id === endpoint.id) {
      dialogVisible.value = false
    }
    ElMessage.success('接口已停用')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '接口停用失败'))
  }
}

watch(keyword, scheduleEndpointSearch)
watch(methodFilter, () => {
  clearTimeout(endpointSearchTimer)
  currentPage.value = 1
  loadEndpoints()
})

onMounted(loadEndpoints)
onBeforeUnmount(() => clearTimeout(endpointSearchTimer))
</script>

<template>
  <section class="endpoint-section">
    <div class="page-heading endpoint-heading">
      <div>
        <h2>接口定义</h2>
        <p>共 {{ total }} 个启用接口</p>
      </div>
    </div>

    <div class="endpoint-toolbar">
      <el-input
        v-model="keyword"
        class="endpoint-toolbar__search"
        :prefix-icon="Search"
        clearable
        placeholder="搜索名称或路径"
        aria-label="搜索接口名称或路径"
      />
      <el-select v-model="methodFilter" clearable placeholder="全部方法" aria-label="筛选请求方法">
        <el-option v-for="method in methods" :key="method" :label="method" :value="method" />
      </el-select>
      <el-button type="primary" :icon="Plus" :disabled="!canEdit" @click="openCreate">
        新增接口
      </el-button>
    </div>

    <div class="data-surface endpoint-surface" v-loading="loading">
      <el-result
        v-if="loadError"
        icon="error"
        title="接口列表暂时无法加载"
      >
        <template #extra>
          <el-button type="primary" @click="loadEndpoints">重新加载</el-button>
        </template>
      </el-result>

      <el-table
        v-else-if="endpoints.length"
        :data="endpoints"
        row-key="id"
        class="endpoint-table"
        @row-click="(row) => openEndpoint(row)"
      >
        <el-table-column label="方法" width="92">
          <template #default="{ row }">
            <el-tag :type="methodTagType(row.method)" effect="plain">{{ row.method }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="接口" width="200">
          <template #default="{ row }">
            <div class="endpoint-name-cell">
              <strong>{{ row.name }}</strong>
              <code>{{ row.path }}</code>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_by_username" label="创建人" width="120" />
        <el-table-column label="更新时间" width="176">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="132" align="center">
          <template #default="{ row }">
            <div class="table-actions">
              <el-tooltip content="查看" placement="top">
                <el-button
                  :icon="View"
                  circle
                  text
                  aria-label="查看接口"
                  @click.stop="openEndpoint(row)"
                />
              </el-tooltip>
              <template v-if="canEdit">
                <el-tooltip content="编辑" placement="top">
                  <el-button
                    :icon="Edit"
                    circle
                    text
                    aria-label="编辑接口"
                    @click.stop="openEndpoint(row, 'edit')"
                  />
                </el-tooltip>
                <el-tooltip content="停用" placement="top">
                  <el-button
                    :icon="Delete"
                    circle
                    text
                    type="danger"
                    aria-label="停用接口"
                    @click.stop="confirmDeactivate(row)"
                  />
                </el-tooltip>
              </template>
            </div>
          </template>
        </el-table-column>
        <el-table-column min-width="1" />
      </el-table>

      <el-empty
        v-else
        :image-size="72"
        :description="hasListFilters ? '没有匹配的接口' : '当前项目还没有接口'"
      />

      <AppPagination
        v-if="total > 0 && !loadError"
        :total="total"
        :current-page="currentPage"
        :page-size="pageSize"
        :disabled="loading"
        @page-change="changeEndpointPage"
        @page-size-change="changeEndpointPageSize"
      />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="860px"
      class="endpoint-dialog"
      align-center
      destroy-on-close
      :before-close="handleDialogClose"
    >
      <div v-loading="detailLoading">
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
          <div class="endpoint-form-grid">
            <el-form-item label="接口名称" prop="name">
              <el-input v-model="form.name" :readonly="isReadOnly" maxlength="100" />
            </el-form-item>
            <el-form-item label="请求方法" prop="method">
              <el-select v-model="form.method" :disabled="isReadOnly">
                <el-option v-for="method in methods" :key="method" :label="method" :value="method" />
              </el-select>
            </el-form-item>
          </div>

          <el-form-item label="接口路径" prop="path">
            <el-input v-model="form.path" :readonly="isReadOnly" maxlength="255" placeholder="/api/users/" />
          </el-form-item>
          <el-form-item label="接口描述" prop="description">
            <el-input
              v-model="form.description"
              :readonly="isReadOnly"
              type="textarea"
              :rows="3"
              maxlength="1000"
              show-word-limit
            />
          </el-form-item>
          <el-form-item label="请求头（JSON 对象）" prop="headersText">
            <el-input
              v-model="form.headersText"
              :readonly="isReadOnly"
              type="textarea"
              :autosize="{ minRows: 5, maxRows: 10 }"
              spellcheck="false"
              class="json-editor"
            />
          </el-form-item>
          <el-form-item label="Query 参数（JSON 对象）" prop="queryParamsText">
            <el-input
              v-model="form.queryParamsText"
              :readonly="isReadOnly"
              type="textarea"
              :autosize="{ minRows: 5, maxRows: 10 }"
              spellcheck="false"
              class="json-editor"
            />
          </el-form-item>
          <el-form-item label="请求体（JSON 对象）" prop="bodyText">
            <el-input
              v-model="form.bodyText"
              :readonly="isReadOnly"
              type="textarea"
              :autosize="{ minRows: 5, maxRows: 12 }"
              spellcheck="false"
              class="json-editor"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <div class="dialog-actions">
          <template v-if="isReadOnly">
            <el-button type="primary" @click="dialogVisible = false">关闭</el-button>
          </template>
          <template v-else>
            <el-button :disabled="saving" @click="cancelEdit">取消</el-button>
            <el-button
              type="primary"
              :loading="saving"
              :disabled="dialogMode === 'edit' && !hasEditChanges"
              @click="submitEndpoint"
            >
              {{ dialogMode === 'create' ? '创建接口' : '保存修改' }}
            </el-button>
          </template>
        </div>
      </template>
    </el-dialog>
  </section>
</template>
