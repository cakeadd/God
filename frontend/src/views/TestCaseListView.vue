<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Delete, Edit, Plus, Search, VideoPlay, View } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getEndpoints } from '../api/endpoints'
import { getEnvironments } from '../api/environments'
import {
  createTestCase,
  deactivateTestCase,
  getTestCase,
  getTestCases,
  updateTestCase,
} from '../api/testcases'
import { executeTestCase } from '../api/executions'
import AppPagination from '../components/AppPagination.vue'
import { useProjectWorkspace } from '../composables/projectWorkspace'

const workspace = useProjectWorkspace()
const testCases = ref([])
const endpointOptions = ref([])
const environmentOptions = ref([])
const loading = ref(false)
const filterLoading = ref(false)
const loadError = ref(false)
const keyword = ref('')
const endpointFilter = ref('')
const environmentFilter = ref('')
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const detailVisible = ref(false)
const detailLoading = ref(false)
const selectedTestCase = ref(null)
const createVisible = ref(false)
const createSaving = ref(false)
const createFormRef = ref()
const initialCreateState = ref(null)
const formMode = ref('create')
const formLoading = ref(false)
const editingTestCase = ref(null)
const legacyStatusAssertions = ref([])
const deactivatingTestCaseIds = ref(new Set())
const executingTestCaseIds = ref(new Set())

const editableRoles = ['owner', 'member']
const canCreate = computed(() => editableRoles.includes(workspace.project?.my_role))
const canEdit = canCreate
const formTitle = computed(() => (
  formMode.value === 'create' ? '新增测试用例' : '编辑测试用例'
))

const createForm = reactive({
  name: '',
  endpointId: '',
  environmentId: '',
  description: '',
  headersText: '{}',
  queryParamsText: '{}',
  bodyText: '{}',
  expectedStatusCode: 200,
  assertions: [],
})

let searchTimer
let latestRequestId = 0
let assertionSequence = 0

function methodTagType(method) {
  return {
    GET: 'success',
    POST: 'primary',
    PUT: 'warning',
    PATCH: 'warning',
    DELETE: 'danger',
  }[method] || 'info'
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
  return JSON.stringify(value ?? {}, null, 2)
}

function parseJsonObject(source, label) {
  const normalized = source.trim()
  if (!normalized) return {}

  let value
  try {
    value = JSON.parse(normalized)
  } catch {
    throw new Error(`${label}必须是有效的 JSON`)
  }

  if (value === null || Array.isArray(value) || typeof value !== 'object') {
    throw new Error(`${label}必须是 JSON 对象`)
  }
  return value
}

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

function parseAssertionExpected(source) {
  if (!source.trim()) {
    throw new Error('请输入期望值')
  }

  try {
    return JSON.parse(source)
  } catch {
    throw new Error('期望值必须是有效 JSON，例如 1、true 或 "success"')
  }
}

function assertionExpectedValidator(_rule, value, callback) {
  try {
    parseAssertionExpected(value)
    callback()
  } catch (error) {
    callback(error)
  }
}

const createRules = {
  name: [
    { required: true, message: '请输入用例名称', trigger: 'blur' },
    { max: 100, message: '用例名称不能超过 100 个字符', trigger: 'blur' },
  ],
  endpointId: [{ required: true, message: '请选择关联接口', trigger: 'change' }],
  description: [{ max: 1000, message: '用例描述不能超过 1000 个字符', trigger: 'blur' }],
  expectedStatusCode: [
    { required: true, message: '请输入期望状态码', trigger: 'change' },
    { type: 'number', min: 100, max: 599, message: '状态码必须在 100 到 599 之间', trigger: 'change' },
  ],
  headersText: [{ validator: jsonObjectValidator('请求头覆盖'), trigger: 'blur' }],
  queryParamsText: [{ validator: jsonObjectValidator('Query 参数覆盖'), trigger: 'blur' }],
  bodyText: [{ validator: jsonObjectValidator('请求体覆盖'), trigger: 'blur' }],
}

function currentCreateState() {
  return {
    name: createForm.name,
    endpointId: createForm.endpointId,
    environmentId: createForm.environmentId,
    description: createForm.description,
    headersText: createForm.headersText,
    queryParamsText: createForm.queryParamsText,
    bodyText: createForm.bodyText,
    expectedStatusCode: createForm.expectedStatusCode,
    assertions: createForm.assertions.map(({ path, expectedText }) => ({ path, expectedText })),
  }
}

const hasCreateChanges = computed(() => (
  initialCreateState.value !== null
  && JSON.stringify(currentCreateState()) !== JSON.stringify(initialCreateState.value)
))

const formEndpointOptions = computed(() => {
  const current = editingTestCase.value
  if (
    formMode.value !== 'edit'
    || !current
    || current.endpoint_is_active
    || endpointOptions.value.some((item) => item.id === current.endpoint)
  ) {
    return endpointOptions.value
  }

  return [
    ...endpointOptions.value,
    {
      id: current.endpoint,
      name: current.endpoint_name,
      method: current.endpoint_method,
      path: current.endpoint_path,
      isInactive: true,
    },
  ]
})

const formEnvironmentOptions = computed(() => {
  const current = editingTestCase.value
  if (
    formMode.value !== 'edit'
    || !current?.environment
    || current.environment_is_active
    || environmentOptions.value.some((item) => item.id === current.environment)
  ) {
    return environmentOptions.value
  }

  return [
    ...environmentOptions.value,
    {
      id: current.environment,
      name: current.environment_name,
      isInactive: true,
    },
  ]
})

function apiErrorMessage(error, fallback) {
  const data = error.response?.data
  if (!data) return fallback
  if (typeof data.detail === 'string') return data.detail

  const firstEntry = Object.entries(data)[0]
  if (!firstEntry) return fallback
  const [field, messages] = firstEntry
  const message = Array.isArray(messages) ? messages[0] : messages
  const labels = {
    name: '用例名称',
    endpoint: '关联接口',
    environment: '运行环境',
    headers: '请求头覆盖',
    query_params: 'Query 参数覆盖',
    body: '请求体覆盖',
    expected_status_code: '期望状态码',
    assertions: '断言规则',
    non_field_errors: '测试用例配置',
  }
  return `${labels[field] || field}：${message}`
}

async function loadFilterOptions() {
  filterLoading.value = true
  try {
    const [endpointResponse, environmentResponse] = await Promise.all([
      getEndpoints(workspace.project.id, { page_size: 100 }),
      getEnvironments(workspace.project.id, { page_size: 100 }),
    ])
    endpointOptions.value = endpointResponse.data.results
    environmentOptions.value = environmentResponse.data.results
  } catch (error) {
    endpointOptions.value = []
    environmentOptions.value = []
    ElMessage.error(apiErrorMessage(error, '测试用例筛选项加载失败'))
  } finally {
    filterLoading.value = false
  }
}

async function loadTestCases() {
  const requestId = ++latestRequestId
  loading.value = true
  loadError.value = false

  try {
    const response = await getTestCases(workspace.project.id, {
      page: currentPage.value,
      page_size: pageSize.value,
      search: keyword.value.trim() || undefined,
      endpoint: endpointFilter.value || undefined,
      environment: environmentFilter.value || undefined,
    })
    if (requestId !== latestRequestId) return
    testCases.value = response.data.results
    total.value = response.data.count
  } catch (error) {
    if (requestId !== latestRequestId) return
    loadError.value = true
    ElMessage.error(apiErrorMessage(error, '测试用例列表加载失败'))
  } finally {
    if (requestId === latestRequestId) loading.value = false
  }
}

async function openTestCase(testCase) {
  detailVisible.value = true
  detailLoading.value = true
  selectedTestCase.value = null

  try {
    const response = await getTestCase(workspace.project.id, testCase.id)
    selectedTestCase.value = response.data
  } catch (error) {
    detailVisible.value = false
    ElMessage.error(apiErrorMessage(error, '测试用例详情加载失败'))
  } finally {
    detailLoading.value = false
  }
}

function resetCreateForm() {
  Object.assign(createForm, {
    name: '',
    endpointId: '',
    environmentId: '',
    description: '',
    headersText: '{}',
    queryParamsText: '{}',
    bodyText: '{}',
    expectedStatusCode: 200,
    assertions: [],
  })
  createFormRef.value?.clearValidate()
}

function fillForm(testCase) {
  legacyStatusAssertions.value = (testCase?.assertions || []).filter(
    (assertion) => assertion.type === 'status_code',
  )
  createForm.name = testCase?.name || ''
  createForm.endpointId = testCase?.endpoint || ''
  createForm.environmentId = testCase?.environment || ''
  createForm.description = testCase?.description || ''
  createForm.headersText = prettyJson(testCase?.headers)
  createForm.queryParamsText = prettyJson(testCase?.query_params)
  createForm.bodyText = prettyJson(testCase?.body)
  createForm.expectedStatusCode = testCase?.expected_status_code ?? 200
  createForm.assertions = (testCase?.assertions || [])
    .filter((assertion) => assertion.type === 'json_field_equals')
    .map((assertion) => {
      assertionSequence += 1
      return {
        id: assertionSequence,
        path: assertion.path,
        expectedText: JSON.stringify(assertion.expected),
      }
    })
  createFormRef.value?.clearValidate()
}

function openCreate() {
  if (!canCreate.value) return
  formMode.value = 'create'
  editingTestCase.value = null
  legacyStatusAssertions.value = []
  resetCreateForm()
  initialCreateState.value = currentCreateState()
  createVisible.value = true
}

async function openEdit(testCase) {
  if (!canEdit.value || isDeactivating(testCase.id) || isExecuting(testCase.id)) return

  formMode.value = 'edit'
  editingTestCase.value = testCase
  initialCreateState.value = null
  createVisible.value = true
  formLoading.value = true

  try {
    const response = await getTestCase(workspace.project.id, testCase.id)
    editingTestCase.value = response.data
    fillForm(response.data)
    initialCreateState.value = currentCreateState()
  } catch (error) {
    createVisible.value = false
    ElMessage.error(apiErrorMessage(error, '测试用例详情加载失败'))
  } finally {
    formLoading.value = false
  }
}

function addAssertion() {
  assertionSequence += 1
  createForm.assertions.push({
    id: assertionSequence,
    path: '',
    expectedText: '',
  })
}

function removeAssertion(index) {
  createForm.assertions.splice(index, 1)
}

async function confirmDiscardForm() {
  if (!hasCreateChanges.value) return true

  const isCreate = formMode.value === 'create'

  try {
    await ElMessageBox.confirm(
      isCreate ? '当前测试用例尚未创建，确认放弃吗？' : '当前修改尚未保存，确认放弃吗？',
      isCreate ? '放弃新增' : '放弃修改',
      {
        confirmButtonText: '确认放弃',
        cancelButtonText: isCreate ? '继续填写' : '继续编辑',
        type: 'warning',
      },
    )
    return true
  } catch {
    return false
  }
}

async function handleFormClose(done) {
  if (createSaving.value || formLoading.value) return
  if (!(await confirmDiscardForm())) return
  initialCreateState.value = null
  editingTestCase.value = null
  legacyStatusAssertions.value = []
  done()
}

async function cancelForm() {
  if (createSaving.value || !(await confirmDiscardForm())) return
  initialCreateState.value = null
  editingTestCase.value = null
  legacyStatusAssertions.value = []
  createVisible.value = false
}

function buildCreatePayload() {
  return {
    name: createForm.name.trim(),
    endpoint: createForm.endpointId,
    environment: createForm.environmentId || null,
    description: createForm.description.trim(),
    headers: parseJsonObject(createForm.headersText, '请求头覆盖'),
    query_params: parseJsonObject(createForm.queryParamsText, 'Query 参数覆盖'),
    body: parseJsonObject(createForm.bodyText, '请求体覆盖'),
    expected_status_code: createForm.expectedStatusCode,
    assertions: buildJsonAssertions(),
  }
}

function buildJsonAssertions() {
  return createForm.assertions.map((assertion) => ({
      type: 'json_field_equals',
      path: assertion.path.trim(),
      expected: parseAssertionExpected(assertion.expectedText),
    }))
}

function buildUpdatePayload() {
  const current = currentCreateState()
  const initial = initialCreateState.value
  const payload = {}

  if (current.name !== initial.name) payload.name = current.name.trim()
  if (current.endpointId !== initial.endpointId) payload.endpoint = current.endpointId
  if (current.environmentId !== initial.environmentId) {
    payload.environment = current.environmentId || null
  }
  if (current.description !== initial.description) payload.description = current.description.trim()
  if (current.headersText !== initial.headersText) {
    payload.headers = parseJsonObject(current.headersText, '请求头覆盖')
  }
  if (current.queryParamsText !== initial.queryParamsText) {
    payload.query_params = parseJsonObject(current.queryParamsText, 'Query 参数覆盖')
  }
  if (current.bodyText !== initial.bodyText) {
    payload.body = parseJsonObject(current.bodyText, '请求体覆盖')
  }
  if (current.expectedStatusCode !== initial.expectedStatusCode) {
    payload.expected_status_code = current.expectedStatusCode
  }
  if (JSON.stringify(current.assertions) !== JSON.stringify(initial.assertions)) {
    payload.assertions = [
      ...legacyStatusAssertions.value,
      ...buildJsonAssertions(),
    ]
  }

  return payload
}

async function submitForm() {
  const valid = await createFormRef.value.validate().catch(() => false)
  if (!valid || (formMode.value === 'edit' && !hasCreateChanges.value)) return

  createSaving.value = true
  try {
    const isCreate = formMode.value === 'create'
    await (isCreate
      ? createTestCase(workspace.project.id, buildCreatePayload())
      : updateTestCase(
        workspace.project.id,
        editingTestCase.value.id,
        buildUpdatePayload(),
      ))
    initialCreateState.value = null
    editingTestCase.value = null
    legacyStatusAssertions.value = []
    createVisible.value = false
    if (isCreate) currentPage.value = 1
    await loadTestCases()
    ElMessage.success(isCreate ? '测试用例已创建' : '测试用例已更新')
  } catch (error) {
    ElMessage.error(apiErrorMessage(
      error,
      formMode.value === 'create' ? '测试用例创建失败，请稍后重试' : '测试用例保存失败，请稍后重试',
    ))
  } finally {
    createSaving.value = false
  }
}

function isDeactivating(testCaseId) {
  return deactivatingTestCaseIds.value.has(testCaseId)
}

async function confirmDeactivate(testCase) {
  if (!canEdit.value || isDeactivating(testCase.id) || isExecuting(testCase.id)) return

  try {
    await ElMessageBox.confirm(
      `停用“${testCase.name}”后，它将从启用列表移除且不能再发起新的单次执行。历史执行记录会保留；尚未执行到它的批量任务会记录“测试用例已停用”错误后继续。`,
      '停用测试用例',
      {
        confirmButtonText: '确认停用',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  deactivatingTestCaseIds.value = new Set([
    ...deactivatingTestCaseIds.value,
    testCase.id,
  ])
  try {
    await deactivateTestCase(workspace.project.id, testCase.id)
    if (testCases.value.length === 1 && currentPage.value > 1) {
      currentPage.value -= 1
    }
    await loadTestCases()
    ElMessage.success('测试用例已停用')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '测试用例停用失败，请稍后重试'))
  } finally {
    const nextIds = new Set(deactivatingTestCaseIds.value)
    nextIds.delete(testCase.id)
    deactivatingTestCaseIds.value = nextIds
  }
}

function isExecuting(testCaseId) {
  return executingTestCaseIds.value.has(testCaseId)
}

async function executeCase(testCase) {
  if (!canEdit.value || isExecuting(testCase.id) || isDeactivating(testCase.id)) return

  executingTestCaseIds.value = new Set([
    ...executingTestCaseIds.value,
    testCase.id,
  ])
  try {
    const response = await executeTestCase(workspace.project.id, testCase.id)
    const statusLabels = {
      passed: '通过',
      failed: '失败',
      error: '异常',
    }
    ElMessage.success(`执行完成：${statusLabels[response.data.status] || response.data.status}`)
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '测试用例执行失败，请稍后重试'))
  } finally {
    const nextIds = new Set(executingTestCaseIds.value)
    nextIds.delete(testCase.id)
    executingTestCaseIds.value = nextIds
  }
}

function changePage(page) {
  currentPage.value = page
  loadTestCases()
}

function changePageSize(size) {
  pageSize.value = size
  currentPage.value = 1
  loadTestCases()
}

function scheduleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    loadTestCases()
  }, 300)
}

function applyRelationFilters() {
  currentPage.value = 1
  loadTestCases()
}

watch(keyword, scheduleSearch)
watch([endpointFilter, environmentFilter], applyRelationFilters)
onMounted(() => {
  loadFilterOptions()
  loadTestCases()
})
onBeforeUnmount(() => clearTimeout(searchTimer))
</script>

<template>
  <section class="testcase-section">
    <div class="page-heading testcase-heading">
      <div>
        <h2>测试用例</h2>
        <p>共 {{ total }} 个启用用例</p>
      </div>
    </div>

    <div class="testcase-toolbar">
      <el-input
        v-model="keyword"
        class="testcase-toolbar__search"
        :prefix-icon="Search"
        clearable
        placeholder="搜索用例名称、接口名称或路径"
        aria-label="搜索用例名称、接口名称或路径"
      />
      <el-select
        v-model="endpointFilter"
        clearable
        filterable
        :loading="filterLoading"
        placeholder="全部接口"
        aria-label="筛选关联接口"
      >
        <el-option
          v-for="endpoint in endpointOptions"
          :key="endpoint.id"
          :label="`${endpoint.method} ${endpoint.name}`"
          :value="endpoint.id"
        />
      </el-select>
      <el-select
        v-model="environmentFilter"
        clearable
        filterable
        :loading="filterLoading"
        placeholder="全部环境"
        aria-label="筛选运行环境"
      >
        <el-option
          v-for="environment in environmentOptions"
          :key="environment.id"
          :label="environment.name"
          :value="environment.id"
        />
      </el-select>
      <el-button type="primary" :icon="Plus" :disabled="!canCreate" @click="openCreate">
        新增测试用例
      </el-button>
    </div>

    <div class="data-surface testcase-surface" v-loading="loading">
      <el-result v-if="loadError" icon="error" title="测试用例列表暂时无法加载">
        <template #extra>
          <el-button type="primary" @click="loadTestCases">重新加载</el-button>
        </template>
      </el-result>

      <el-table
        v-else-if="testCases.length"
        :data="testCases"
        row-key="id"
        class="testcase-table"
        @row-click="openTestCase"
      >
        <el-table-column label="用例" width="190">
          <template #default="{ row }">
            <div class="testcase-name-cell">
              <strong>{{ row.name }}</strong>
              <span>{{ row.description || '暂无描述' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="关联接口" width="215">
          <template #default="{ row }">
            <div class="testcase-endpoint-cell">
              <div>
                <el-tag :type="methodTagType(row.endpoint_method)" effect="plain">
                  {{ row.endpoint_method }}
                </el-tag>
                <strong>{{ row.endpoint_name }}</strong>
                <el-tag v-if="!row.endpoint_is_active" type="danger" effect="plain">已停用</el-tag>
              </div>
              <code>{{ row.endpoint_path }}</code>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="运行环境" width="135">
          <template #default="{ row }">
            <span v-if="!row.environment">跟随默认环境</span>
            <div v-else class="testcase-environment-cell">
              <span>{{ row.environment_name }}</span>
              <el-tag v-if="!row.environment_is_active" type="danger" effect="plain">已停用</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="预期结果" width="115">
          <template #default="{ row }">
            <div class="testcase-result-cell">
              <strong>HTTP {{ row.expected_status_code }}</strong>
              <span>{{ row.assertion_count }} 条断言</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_username" label="创建人" width="90" />
        <el-table-column label="更新时间" width="150">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="164" align="center">
          <template #default="{ row }">
            <div class="table-actions testcase-actions" @click.stop>
              <el-tooltip content="执行测试用例" placement="top">
                <el-button
                  :icon="VideoPlay"
                  circle
                  text
                  type="primary"
                  :loading="isExecuting(row.id)"
                  :disabled="!canEdit || isExecuting(row.id) || isDeactivating(row.id)"
                  aria-label="执行测试用例"
                  @click="executeCase(row)"
                />
              </el-tooltip>
              <el-tooltip content="查看" placement="top">
                <el-button :icon="View" circle text aria-label="查看测试用例" @click="openTestCase(row)" />
              </el-tooltip>
              <el-tooltip content="编辑" placement="top">
                <el-button
                  :icon="Edit"
                  circle
                  text
                  :disabled="!canEdit || isDeactivating(row.id) || isExecuting(row.id)"
                  aria-label="编辑测试用例"
                  @click="openEdit(row)"
                />
              </el-tooltip>
              <el-tooltip content="停用" placement="top">
                <el-button
                  :icon="Delete"
                  circle
                  text
                  type="danger"
                  :loading="isDeactivating(row.id)"
                  :disabled="!canEdit || isDeactivating(row.id) || isExecuting(row.id)"
                  aria-label="停用测试用例"
                  @click="confirmDeactivate(row)"
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
        :description="keyword || endpointFilter || environmentFilter ? '没有匹配的测试用例' : '当前项目还没有启用测试用例'"
      />

      <AppPagination
        v-if="total > 0 && !loadError"
        :total="total"
        :current-page="currentPage"
        :page-size="pageSize"
        :disabled="loading"
        @page-change="changePage"
        @page-size-change="changePageSize"
      />
    </div>

    <el-dialog v-model="detailVisible" title="查看测试用例" width="760px" align-center>
      <div v-loading="detailLoading" class="testcase-detail">
        <template v-if="selectedTestCase">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="用例名称" :span="2">
              {{ selectedTestCase.name }}
            </el-descriptions-item>
            <el-descriptions-item label="关联接口">
              {{ selectedTestCase.endpoint_method }} {{ selectedTestCase.endpoint_name }}
            </el-descriptions-item>
            <el-descriptions-item label="运行环境">
              {{ selectedTestCase.environment_name || '跟随默认环境' }}
            </el-descriptions-item>
            <el-descriptions-item label="接口路径">
              <code>{{ selectedTestCase.endpoint_path }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="期望状态码">
              HTTP {{ selectedTestCase.expected_status_code }}
            </el-descriptions-item>
            <el-descriptions-item label="创建人">
              {{ selectedTestCase.created_by_username }}
            </el-descriptions-item>
            <el-descriptions-item label="更新时间">
              {{ formatTime(selectedTestCase.updated_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="用例描述" :span="2">
              {{ selectedTestCase.description || '-' }}
            </el-descriptions-item>
          </el-descriptions>

          <div class="testcase-detail__json-grid">
            <section><h3>请求头覆盖</h3><pre>{{ prettyJson(selectedTestCase.headers) }}</pre></section>
            <section><h3>Query 参数覆盖</h3><pre>{{ prettyJson(selectedTestCase.query_params) }}</pre></section>
            <section><h3>请求体覆盖</h3><pre>{{ prettyJson(selectedTestCase.body) }}</pre></section>
            <section><h3>断言规则</h3><pre>{{ prettyJson(selectedTestCase.assertions) }}</pre></section>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button type="primary" @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="createVisible"
      :title="formTitle"
      width="860px"
      class="testcase-dialog"
      align-center
      destroy-on-close
      :before-close="handleFormClose"
    >
      <el-form
        ref="createFormRef"
        v-loading="formLoading"
        :model="createForm"
        :rules="createRules"
        label-position="top"
      >
        <section class="testcase-form__section">
          <h3>基本信息</h3>
          <div class="testcase-form__grid">
            <el-form-item label="用例名称" prop="name">
              <el-input v-model="createForm.name" maxlength="100" show-word-limit />
            </el-form-item>
            <el-form-item label="期望状态码" prop="expectedStatusCode">
              <el-input-number
                v-model="createForm.expectedStatusCode"
                :min="100"
                :max="599"
                controls-position="right"
              />
            </el-form-item>
            <el-form-item label="关联接口" prop="endpointId">
              <el-select
                v-model="createForm.endpointId"
                filterable
                :loading="filterLoading"
                placeholder="请选择关联接口"
              >
                <el-option
                  v-for="endpoint in formEndpointOptions"
                  :key="endpoint.id"
                  :label="`${endpoint.isInactive ? '[已停用] ' : ''}${endpoint.method} ${endpoint.name} · ${endpoint.path}`"
                  :value="endpoint.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="运行环境" prop="environmentId">
              <el-select
                v-model="createForm.environmentId"
                filterable
                :loading="filterLoading"
                placeholder="跟随默认环境"
              >
                <el-option label="跟随默认环境" value="" />
                <el-option
                  v-for="environment in formEnvironmentOptions"
                  :key="environment.id"
                  :label="`${environment.isInactive ? '[已停用] ' : ''}${environment.name}`"
                  :value="environment.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item class="testcase-form__full" label="用例描述" prop="description">
              <el-input
                v-model="createForm.description"
                type="textarea"
                :rows="3"
                maxlength="1000"
                show-word-limit
              />
            </el-form-item>
          </div>
        </section>

        <section class="testcase-form__section">
          <h3>请求覆盖</h3>
          <div class="testcase-json-grid">
            <el-form-item label="请求头覆盖（JSON 对象）" prop="headersText">
              <el-input
                v-model="createForm.headersText"
                type="textarea"
                :autosize="{ minRows: 5, maxRows: 10 }"
                spellcheck="false"
                class="json-editor"
              />
            </el-form-item>
            <el-form-item label="Query 参数覆盖（JSON 对象）" prop="queryParamsText">
              <el-input
                v-model="createForm.queryParamsText"
                type="textarea"
                :autosize="{ minRows: 5, maxRows: 10 }"
                spellcheck="false"
                class="json-editor"
              />
            </el-form-item>
            <el-form-item class="testcase-form__full" label="请求体覆盖（JSON 对象）" prop="bodyText">
              <el-input
                v-model="createForm.bodyText"
                type="textarea"
                :autosize="{ minRows: 6, maxRows: 12 }"
                spellcheck="false"
                class="json-editor"
              />
            </el-form-item>
          </div>
        </section>

        <section class="testcase-form__section">
          <div class="testcase-assertions__heading">
            <h3>JSON 字段断言</h3>
            <el-button :icon="Plus" @click="addAssertion">添加断言</el-button>
          </div>

          <div v-if="createForm.assertions.length" class="testcase-assertions">
            <div
              v-for="(assertion, index) in createForm.assertions"
              :key="assertion.id"
              class="testcase-assertion-row"
            >
              <el-form-item
                label="JSON 路径"
                :prop="`assertions.${index}.path`"
                :rules="[{ required: true, message: '请输入 JSON 路径', trigger: 'blur' }]"
              >
                <el-input v-model="assertion.path" placeholder="data.user.id" />
              </el-form-item>
              <el-form-item
                label="期望值（JSON）"
                :prop="`assertions.${index}.expectedText`"
                :rules="[{ validator: assertionExpectedValidator, trigger: 'blur' }]"
              >
                <el-input v-model="assertion.expectedText" placeholder='1、true 或 "success"' />
              </el-form-item>
              <el-tooltip content="删除断言" placement="top">
                <el-button
                  :icon="Delete"
                  circle
                  text
                  type="danger"
                  aria-label="删除断言"
                  @click="removeAssertion(index)"
                />
              </el-tooltip>
            </div>
          </div>
          <div v-else class="testcase-assertions__empty">暂无 JSON 字段断言</div>
        </section>
      </el-form>

      <template #footer>
        <div class="dialog-actions">
          <el-button :disabled="createSaving || formLoading" @click="cancelForm">取消</el-button>
          <el-button
            type="primary"
            :loading="createSaving"
            :disabled="formLoading || (formMode === 'edit' && !hasCreateChanges)"
            @click="submitForm"
          >
            {{ formMode === 'create' ? '创建测试用例' : '保存修改' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>
