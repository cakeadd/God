<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { Plus, RefreshRight, View } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createTestRun,
  getExecution,
  getTestRun,
  getTestRuns,
  rerunTestRun,
} from '../api/executions'
import { getTestCases } from '../api/testcases'
import AppPagination from '../components/AppPagination.vue'
import ExecutionDetailDialog from '../components/ExecutionDetailDialog.vue'
import { useProjectWorkspace } from '../composables/projectWorkspace'

const workspace = useProjectWorkspace()
const testRuns = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const loadError = ref(false)

const createVisible = ref(false)
const createLoading = ref(false)
const caseLoading = ref(false)
const caseLoadError = ref(false)
const availableTestCases = ref([])
const selectedTestCases = ref([])
const caseTableRef = ref(null)
const createForm = reactive({
  name: '',
  search: '',
})

const detailVisible = ref(false)
const detailLoading = ref(false)
const selectedTestRun = ref(null)
const executionDetailVisible = ref(false)
const executionDetailLoading = ref(false)
const selectedExecution = ref(null)
const rerunningTestRunIds = ref(new Set())

let pollingTimer
let latestListRequestId = 0
let latestDetailRequestId = 0
let syncingSelection = false

const canCreate = computed(() => ['owner', 'member'].includes(workspace.project?.my_role))
const createDirty = computed(() => (
  Boolean(createForm.name.trim()) || selectedTestCases.value.length > 0
))
const filteredTestCases = computed(() => {
  const search = createForm.search.trim().toLowerCase()
  if (!search) return availableTestCases.value

  return availableTestCases.value.filter((testCase) => (
    testCase.name.toLowerCase().includes(search)
    || testCase.endpoint_name.toLowerCase().includes(search)
    || testCase.endpoint_path.toLowerCase().includes(search)
  ))
})
const detailRows = computed(() => {
  if (!selectedTestRun.value) return []

  const executionsByCase = new Map(
    (selectedTestRun.value.executions || []).map((execution) => [
      execution.test_case,
      execution,
    ]),
  )

  return (selectedTestRun.value.test_cases || []).map((testCase) => {
    const execution = executionsByCase.get(testCase.id)
    if (execution) {
      return {
        ...execution,
        rowKey: `execution-${execution.id}`,
      }
    }

    return {
      id: null,
      rowKey: `pending-${testCase.id}`,
      test_case: testCase.id,
      test_case_name: testCase.name,
      status: 'pending',
      response_status_code: null,
      duration_ms: null,
      failure_message: '',
      error_message: '',
    }
  })
})

const runStatusLabels = {
  pending: '等待中',
  running: '执行中',
  completed: '已完成',
  error: '异常',
}
const executionStatusLabels = {
  pending: '等待中',
  running: '执行中',
  passed: '通过',
  failed: '失败',
  error: '异常',
}

function isActiveRun(testRun) {
  return ['pending', 'running'].includes(testRun?.status)
}

function canRerun(testRun) {
  return canCreate.value && ['completed', 'error'].includes(testRun?.status)
}

function isRerunning(testRunId) {
  return rerunningTestRunIds.value.has(testRunId)
}

function rerunTooltip(testRun) {
  if (!canCreate.value) return '当前角色无权再次执行批次'
  if (isActiveRun(testRun)) return '批次尚未结束，暂不能再次执行'
  return '再次执行'
}

function runStatusTagType(status) {
  return {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    error: 'danger',
  }[status] || 'info'
}

function executionStatusTagType(status) {
  return {
    pending: 'info',
    running: 'warning',
    passed: 'success',
    failed: 'danger',
    error: 'danger',
  }[status] || 'info'
}

function resultLabel(testRun) {
  if (testRun.status === 'pending') return '尚未开始'
  if (testRun.status === 'running') return '统计中'
  if (testRun.status === 'error') return '批次异常'
  if (testRun.failed_count > 0 || testRun.error_count > 0) return '存在问题'
  return '全部通过'
}

function resultTagType(testRun) {
  if (testRun.status === 'error' || testRun.failed_count > 0) return 'danger'
  if (testRun.error_count > 0 || isActiveRun(testRun)) return 'warning'
  return 'success'
}

function displayRunName(testRun) {
  return testRun.name || `批次 #${testRun.id}`
}

function progressPercentage(testRun) {
  if (!testRun.total_count) return 0
  return Math.round(testRun.completed_count / testRun.total_count * 100)
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

function formatDuration(value) {
  return value === null || value === undefined ? '-' : `${value} ms`
}

function apiErrorMessage(error, fallback) {
  const data = error.response?.data
  if (typeof data === 'string') return data
  if (typeof data?.detail === 'string') return data.detail

  for (const key of ['name', 'test_case_ids', 'non_field_errors']) {
    const value = data?.[key]
    if (Array.isArray(value) && value.length) return String(value[0])
    if (typeof value === 'string') return value
  }
  return fallback
}

async function loadTestRuns({ silent = false } = {}) {
  if (!workspace.project?.id) return

  const requestId = ++latestListRequestId
  if (!silent) {
    loading.value = true
    loadError.value = false
  }

  try {
    const response = await getTestRuns(workspace.project.id, {
      page: currentPage.value,
      page_size: pageSize.value,
    })
    if (requestId !== latestListRequestId) return
    testRuns.value = response.data.results
    total.value = response.data.count
  } catch (error) {
    if (requestId !== latestListRequestId || silent) return
    loadError.value = true
    ElMessage.error(apiErrorMessage(error, '批量执行列表加载失败'))
  } finally {
    if (!silent && requestId === latestListRequestId) {
      loading.value = false
    }
  }
}

async function loadTestRunDetail(testRunId, { silent = false } = {}) {
  const requestId = ++latestDetailRequestId
  if (!silent) detailLoading.value = true

  try {
    const response = await getTestRun(workspace.project.id, testRunId)
    if (requestId !== latestDetailRequestId || !detailVisible.value) return
    selectedTestRun.value = response.data
  } catch (error) {
    if (requestId !== latestDetailRequestId || silent) return
    detailVisible.value = false
    ElMessage.error(apiErrorMessage(error, '批次详情加载失败'))
  } finally {
    if (!silent && requestId === latestDetailRequestId) {
      detailLoading.value = false
    }
  }
}

function schedulePolling() {
  clearTimeout(pollingTimer)
  const pageHasActiveRun = testRuns.value.some(isActiveRun)
  const detailIsActive = detailVisible.value && isActiveRun(selectedTestRun.value)
  if (!pageHasActiveRun && !detailIsActive) return

  pollingTimer = setTimeout(async () => {
    const requests = [loadTestRuns({ silent: true })]
    if (detailVisible.value && selectedTestRun.value?.id) {
      requests.push(loadTestRunDetail(selectedTestRun.value.id, { silent: true }))
    }
    await Promise.all(requests)
    schedulePolling()
  }, 2000)
}

async function refreshList() {
  clearTimeout(pollingTimer)
  await loadTestRuns()
  schedulePolling()
}

async function changePage(page) {
  currentPage.value = page
  await refreshList()
}

async function changePageSize(size) {
  pageSize.value = size
  currentPage.value = 1
  await refreshList()
}

async function loadAvailableTestCases() {
  caseLoading.value = true
  caseLoadError.value = false
  availableTestCases.value = []

  try {
    const allTestCases = []
    let page = 1
    let expectedCount = 1

    // 创建批次需要跨分页选择，逐页读取当前项目全部启用用例。
    while (allTestCases.length < expectedCount) {
      const response = await getTestCases(workspace.project.id, {
        page,
        page_size: 100,
      })
      expectedCount = response.data.count
      if (!response.data.results.length) break
      allTestCases.push(...response.data.results)
      page += 1
    }

    availableTestCases.value = allTestCases
  } catch (error) {
    caseLoadError.value = true
    ElMessage.error(apiErrorMessage(error, '可执行用例加载失败'))
  } finally {
    caseLoading.value = false
  }
}

async function openCreate() {
  if (!canCreate.value) return

  createForm.name = ''
  createForm.search = ''
  selectedTestCases.value = []
  createVisible.value = true
  await nextTick()
  caseTableRef.value?.clearSelection()
  await loadAvailableTestCases()
}

function isCaseSelectable(testCase) {
  return selectedTestCases.value.some((item) => item.id === testCase.id)
    || selectedTestCases.value.length < 20
}

async function handleCaseSelectionChange(selection) {
  if (syncingSelection) return

  if (selection.length <= 20) {
    selectedTestCases.value = selection
    return
  }

  syncingSelection = true
  const limitedSelection = selection.slice(0, 20)
  selectedTestCases.value = limitedSelection
  await nextTick()
  caseTableRef.value?.clearSelection()
  limitedSelection.forEach((testCase) => {
    caseTableRef.value?.toggleRowSelection(testCase, true)
  })
  syncingSelection = false
  ElMessage.warning('一次最多选择 20 条测试用例')
}

function handleCaseRowClick(testCase, column) {
  if (column?.type === 'selection') return

  const selected = selectedTestCases.value.some((item) => item.id === testCase.id)
  if (!selected && selectedTestCases.value.length >= 20) {
    ElMessage.warning('一次最多选择 20 条测试用例')
    return
  }
  caseTableRef.value?.toggleRowSelection(testCase, !selected)
}

async function confirmDiscardCreate() {
  if (!createDirty.value) return true

  try {
    await ElMessageBox.confirm(
      '当前批次配置尚未提交，确认放弃吗？',
      '放弃创建批次',
      {
        confirmButtonText: '放弃',
        cancelButtonText: '继续编辑',
        type: 'warning',
      },
    )
    return true
  } catch {
    return false
  }
}

async function requestCloseCreate() {
  if (createLoading.value) return
  if (await confirmDiscardCreate()) createVisible.value = false
}

async function beforeCloseCreate(done) {
  if (createLoading.value) return
  if (await confirmDiscardCreate()) done()
}

async function submitTestRun() {
  if (!selectedTestCases.value.length) {
    ElMessage.warning('请至少选择 1 条测试用例')
    return
  }

  createLoading.value = true
  try {
    const response = await createTestRun(workspace.project.id, {
      name: createForm.name.trim(),
      test_case_ids: selectedTestCases.value.map((testCase) => testCase.id),
    })
    ElMessage.success('批量执行已提交')

    createForm.name = ''
    createForm.search = ''
    selectedTestCases.value = []
    createVisible.value = false
    currentPage.value = 1
    await loadTestRuns()
    await openTestRun(response.data)
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '批量执行提交失败'))
  } finally {
    createLoading.value = false
    schedulePolling()
  }
}

async function openTestRun(testRun) {
  selectedTestRun.value = {
    ...testRun,
    test_cases: [],
    executions: [],
  }
  detailVisible.value = true
  await loadTestRunDetail(testRun.id)
  schedulePolling()
}

async function handleRerun(testRun) {
  if (!canRerun(testRun) || isRerunning(testRun.id)) return

  try {
    await ElMessageBox.confirm(
      `确认再次执行“${displayRunName(testRun)}”中的 ${testRun.total_count} 条测试用例吗？将使用这些用例当前保存的配置创建新批次，原执行结果不会受到影响。`,
      '再次执行批次',
      {
        confirmButtonText: '再次执行',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  rerunningTestRunIds.value = new Set([
    ...rerunningTestRunIds.value,
    testRun.id,
  ])
  try {
    const response = await rerunTestRun(workspace.project.id, testRun.id)
    ElMessage.success('新的批量执行已提交')
    currentPage.value = 1
    await loadTestRuns()
    await openTestRun(response.data)
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '批次再次执行失败'))
    if (error.response?.status === 503) {
      currentPage.value = 1
      await loadTestRuns()
    }
  } finally {
    const nextIds = new Set(rerunningTestRunIds.value)
    nextIds.delete(testRun.id)
    rerunningTestRunIds.value = nextIds
    schedulePolling()
  }
}

function handleDetailClosed() {
  latestDetailRequestId += 1
  selectedTestRun.value = null
  schedulePolling()
}

async function openExecutionDetail(execution) {
  if (!execution.id) return

  selectedExecution.value = null
  executionDetailVisible.value = true
  executionDetailLoading.value = true
  try {
    const response = await getExecution(workspace.project.id, execution.id)
    selectedExecution.value = response.data
  } catch (error) {
    executionDetailVisible.value = false
    ElMessage.error(apiErrorMessage(error, '执行记录详情加载失败'))
  } finally {
    executionDetailLoading.value = false
  }
}

onMounted(async () => {
  await loadTestRuns()
  schedulePolling()
})
onBeforeUnmount(() => {
  clearTimeout(pollingTimer)
  latestListRequestId += 1
  latestDetailRequestId += 1
})
</script>

<template>
  <section class="test-run-section">
    <div class="page-heading test-run-heading">
      <div>
        <h2>批量执行</h2>
        <p>共 {{ total }} 个执行批次</p>
      </div>
    </div>

    <div class="test-run-toolbar">
      <el-button type="primary" :icon="Plus" :disabled="!canCreate" @click="openCreate">
        创建批次
      </el-button>
    </div>

    <div class="data-surface test-run-surface" v-loading="loading">
      <el-result v-if="loadError" icon="error" title="批量执行列表暂时无法加载">
        <template #extra>
          <el-button type="primary" @click="refreshList">重新加载</el-button>
        </template>
      </el-result>

      <el-table
        v-else-if="testRuns.length"
        :data="testRuns"
        row-key="id"
        class="test-run-table"
        @row-click="openTestRun"
      >
        <el-table-column label="批次名称" min-width="155" show-overflow-tooltip>
          <template #default="{ row }">
            <strong>{{ displayRunName(row) }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="任务状态" width="100">
          <template #default="{ row }">
            <el-tag :type="runStatusTagType(row.status)" effect="plain">
              {{ runStatusLabels[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="执行进度" width="145">
          <template #default="{ row }">
            <div class="test-run-progress">
              <span>{{ row.completed_count }}/{{ row.total_count }}</span>
              <el-progress :percentage="progressPercentage(row)" :show-text="false" :stroke-width="5" />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="执行结果" width="205">
          <template #default="{ row }">
            <div class="test-run-result">
              <el-tag :type="resultTagType(row)" effect="plain">{{ resultLabel(row) }}</el-tag>
              <span>通过 {{ row.passed_count }} / 失败 {{ row.failed_count }} / 异常 {{ row.error_count }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="总耗时" width="105">
          <template #default="{ row }">{{ formatDuration(row.duration_ms) }}</template>
        </el-table-column>
        <el-table-column prop="executed_by_username" label="发起人" width="90" />
        <el-table-column label="发起时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" align="center">
          <template #default="{ row }">
            <div class="table-actions" @click.stop>
              <el-tooltip content="查看批次详情" placement="top">
                <el-button :icon="View" circle text aria-label="查看批次详情" @click="openTestRun(row)" />
              </el-tooltip>
              <el-tooltip :content="rerunTooltip(row)" placement="top">
                <span>
                  <el-button
                    :icon="RefreshRight"
                    circle
                    text
                    :loading="isRerunning(row.id)"
                    :disabled="!canRerun(row) || isRerunning(row.id)"
                    aria-label="再次执行批次"
                    @click="handleRerun(row)"
                  />
                </span>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-else :image-size="72" description="当前项目还没有批量执行记录" />

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

    <el-dialog
      v-model="createVisible"
      title="创建批量执行"
      width="860px"
      align-center
      class="test-run-create-dialog"
      :close-on-click-modal="false"
      :before-close="beforeCloseCreate"
    >
      <el-form label-position="top">
        <el-form-item label="批次名称（选填）">
          <el-input
            v-model="createForm.name"
            maxlength="100"
            show-word-limit
            placeholder="例如：核心接口冒烟测试"
          />
        </el-form-item>
      </el-form>

      <el-input
        v-model="createForm.search"
        class="test-run-case-search"
        clearable
        placeholder="搜索用例名称、接口名称或路径"
        aria-label="搜索待执行测试用例"
      />

      <div class="test-run-case-surface" v-loading="caseLoading">
        <el-result v-if="caseLoadError" icon="error" title="测试用例暂时无法加载">
          <template #extra>
            <el-button type="primary" @click="loadAvailableTestCases">重新加载</el-button>
          </template>
        </el-result>
        <el-table
          v-else
          ref="caseTableRef"
          :data="filteredTestCases"
          row-key="id"
          height="360"
          class="test-run-case-table"
          @selection-change="handleCaseSelectionChange"
          @row-click="handleCaseRowClick"
        >
          <el-table-column type="selection" width="52" reserve-selection :selectable="isCaseSelectable" />
          <el-table-column prop="name" label="测试用例" min-width="190" show-overflow-tooltip />
          <el-table-column label="关联接口" min-width="220">
            <template #default="{ row }">
              <div class="test-run-case-endpoint">
                <el-tag effect="plain">{{ row.endpoint_method }}</el-tag>
                <span>{{ row.endpoint_name }}</span>
                <code>{{ row.endpoint_path }}</code>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="运行环境" width="135">
            <template #default="{ row }">{{ row.environment_name || '跟随默认环境' }}</template>
          </el-table-column>
          <el-table-column label="期望状态码" width="105">
            <template #default="{ row }">HTTP {{ row.expected_status_code }}</template>
          </el-table-column>
        </el-table>
      </div>

      <template #footer>
        <div class="test-run-create-footer">
          <span>已选择 {{ selectedTestCases.length }}/20 条</span>
          <div class="dialog-actions">
            <el-button :disabled="createLoading" @click="requestCloseCreate">取消</el-button>
            <el-button
              type="primary"
              :loading="createLoading"
              :disabled="selectedTestCases.length < 1 || selectedTestCases.length > 20"
              @click="submitTestRun"
            >
              启动批量执行
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="detailVisible"
      title="批次详情"
      width="980px"
      align-center
      class="test-run-detail-dialog"
      @closed="handleDetailClosed"
    >
      <div v-loading="detailLoading" class="test-run-detail">
        <template v-if="selectedTestRun">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="批次名称" :span="2">
              {{ displayRunName(selectedTestRun) }}
            </el-descriptions-item>
            <el-descriptions-item label="任务状态">
              <el-tag :type="runStatusTagType(selectedTestRun.status)" effect="plain">
                {{ runStatusLabels[selectedTestRun.status] || selectedTestRun.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="执行进度">
              {{ selectedTestRun.completed_count }}/{{ selectedTestRun.total_count }}
            </el-descriptions-item>
            <el-descriptions-item label="执行结果">
              <el-tag :type="resultTagType(selectedTestRun)" effect="plain">
                {{ resultLabel(selectedTestRun) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="总耗时">{{ formatDuration(selectedTestRun.duration_ms) }}</el-descriptions-item>
            <el-descriptions-item label="通过">{{ selectedTestRun.passed_count }}</el-descriptions-item>
            <el-descriptions-item label="失败">{{ selectedTestRun.failed_count }}</el-descriptions-item>
            <el-descriptions-item label="异常">{{ selectedTestRun.error_count }}</el-descriptions-item>
            <el-descriptions-item label="发起人">{{ selectedTestRun.executed_by_username }}</el-descriptions-item>
            <el-descriptions-item label="开始时间">{{ formatTime(selectedTestRun.started_at) }}</el-descriptions-item>
            <el-descriptions-item label="结束时间">{{ formatTime(selectedTestRun.finished_at) }}</el-descriptions-item>
          </el-descriptions>

          <el-alert
            v-if="selectedTestRun.error_message"
            class="test-run-detail__error"
            type="error"
            :closable="false"
            :title="selectedTestRun.error_message"
          />

          <h3>执行明细</h3>
          <el-table
            :data="detailRows"
            :row-key="(row) => row.rowKey"
            max-height="360"
            class="test-run-detail-table"
            @row-click="openExecutionDetail"
          >
            <el-table-column label="状态" width="96">
              <template #default="{ row }">
                <el-tag :type="executionStatusTagType(row.status)" effect="plain">
                  {{ executionStatusLabels[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="test_case_name" label="测试用例" min-width="200" show-overflow-tooltip />
            <el-table-column label="响应状态码" width="115">
              <template #default="{ row }">{{ row.response_status_code ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="耗时" width="105">
              <template #default="{ row }">{{ formatDuration(row.duration_ms) }}</template>
            </el-table-column>
            <el-table-column label="问题原因" min-width="230" show-overflow-tooltip>
              <template #default="{ row }">{{ row.failure_message || row.error_message || '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="76" align="center">
              <template #default="{ row }">
                <div class="table-actions" @click.stop>
                  <el-tooltip content="查看执行详情" placement="top">
                    <el-button
                      :icon="View"
                      circle
                      text
                      :disabled="!row.id"
                      aria-label="查看执行详情"
                      @click="openExecutionDetail(row)"
                    />
                  </el-tooltip>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
      <template #footer>
        <el-button type="primary" @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <ExecutionDetailDialog
      v-model="executionDetailVisible"
      :loading="executionDetailLoading"
      :execution="selectedExecution"
    />
  </section>
</template>
