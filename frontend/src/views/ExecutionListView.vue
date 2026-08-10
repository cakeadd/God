<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Search, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { getExecution, getExecutions } from '../api/executions'
import AppPagination from '../components/AppPagination.vue'
import { useProjectWorkspace } from '../composables/projectWorkspace'

const workspace = useProjectWorkspace()
const executions = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const loading = ref(false)
const loadError = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const selectedExecution = ref(null)

let executionSearchTimer
let latestExecutionRequestId = 0

const statusLabels = {
  pending: '等待中',
  running: '执行中',
  passed: '通过',
  failed: '失败',
  error: '异常',
}

function statusTagType(status) {
  return {
    pending: 'info',
    running: 'warning',
    passed: 'success',
    failed: 'danger',
    error: 'danger',
  }[status] || 'info'
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

function prettyJson(value) {
  return JSON.stringify(value ?? {}, null, 2)
}

function apiErrorMessage(error, fallback) {
  const data = error.response?.data
  if (typeof data?.detail === 'string') return data.detail
  return fallback
}

async function loadExecutions() {
  if (!workspace.project?.id) return

  // 只接收最后一次请求结果，避免搜索时旧响应覆盖新页面。
  const requestId = ++latestExecutionRequestId
  loading.value = true
  loadError.value = false
  try {
    const response = await getExecutions(workspace.project.id, {
      page: currentPage.value,
      page_size: pageSize.value,
      search: keyword.value.trim() || undefined,
    })
    if (requestId !== latestExecutionRequestId) return
    executions.value = response.data.results
    total.value = response.data.count
  } catch (error) {
    if (requestId !== latestExecutionRequestId) return
    loadError.value = true
    ElMessage.error(apiErrorMessage(error, '执行记录加载失败'))
  } finally {
    if (requestId === latestExecutionRequestId) {
      loading.value = false
    }
  }
}

async function openExecution(execution) {
  selectedExecution.value = null
  detailVisible.value = true
  detailLoading.value = true
  try {
    const response = await getExecution(workspace.project.id, execution.id)
    selectedExecution.value = response.data
  } catch (error) {
    detailVisible.value = false
    ElMessage.error(apiErrorMessage(error, '执行记录详情加载失败'))
  } finally {
    detailLoading.value = false
  }
}

function changePage(page) {
  currentPage.value = page
  loadExecutions()
}

function changePageSize(size) {
  pageSize.value = size
  currentPage.value = 1
  loadExecutions()
}

function scheduleExecutionSearch() {
  clearTimeout(executionSearchTimer)
  executionSearchTimer = setTimeout(() => {
    currentPage.value = 1
    loadExecutions()
  }, 300)
}

watch(keyword, scheduleExecutionSearch)
onMounted(loadExecutions)
onBeforeUnmount(() => clearTimeout(executionSearchTimer))
</script>

<template>
  <section class="execution-section">
    <div class="page-heading execution-heading">
      <div>
        <h2>执行记录</h2>
        <p>共 {{ total }} 条执行记录</p>
      </div>
    </div>

    <div class="execution-toolbar">
      <el-input
        v-model="keyword"
        class="execution-toolbar__search"
        :prefix-icon="Search"
        clearable
        placeholder="搜索状态、测试用例或执行人"
        aria-label="搜索状态、测试用例或执行人"
      />
    </div>

    <div class="data-surface execution-surface" v-loading="loading">
      <el-result v-if="loadError" icon="error" title="执行记录暂时无法加载">
        <template #extra>
          <el-button type="primary" @click="loadExecutions">重新加载</el-button>
        </template>
      </el-result>

      <el-table
        v-else-if="executions.length"
        :data="executions"
        row-key="id"
        class="execution-table"
        @row-click="openExecution"
      >
        <el-table-column label="状态" width="104">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="plain">
              {{ statusLabels[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="test_case_name" label="测试用例" min-width="220" />
        <el-table-column label="耗时" width="126">
          <template #default="{ row }">{{ formatDuration(row.duration_ms) }}</template>
        </el-table-column>
        <el-table-column label="执行时间" width="170">
          <template #default="{ row }">{{ formatTime(row.finished_at || row.started_at || row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="executed_by_username" label="执行人" width="120" />
        <el-table-column label="操作" width="76" align="center">
          <template #default="{ row }">
            <div class="table-actions" @click.stop>
              <el-tooltip content="查看执行详情" placement="top">
                <el-button :icon="View" circle text aria-label="查看执行详情" @click="openExecution(row)" />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-else
        :image-size="72"
        :description="keyword ? '没有匹配的执行记录' : '当前项目还没有执行记录'"
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

    <el-dialog v-model="detailVisible" title="执行详情" width="860px" align-center>
      <div v-loading="detailLoading" class="execution-detail">
        <template v-if="selectedExecution">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="执行状态">
              <el-tag :type="statusTagType(selectedExecution.status)" effect="plain">
                {{ statusLabels[selectedExecution.status] || selectedExecution.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="测试用例">{{ selectedExecution.test_case_name }}</el-descriptions-item>
            <el-descriptions-item label="运行环境">
              {{ selectedExecution.environment_name || '跟随默认环境' }}
            </el-descriptions-item>
            <el-descriptions-item label="执行人">{{ selectedExecution.executed_by_username }}</el-descriptions-item>
            <el-descriptions-item label="执行时间">
              {{ formatTime(selectedExecution.finished_at || selectedExecution.started_at || selectedExecution.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="耗时">{{ formatDuration(selectedExecution.duration_ms) }}</el-descriptions-item>
            <el-descriptions-item label="响应状态码">{{ selectedExecution.response_status_code || '-' }}</el-descriptions-item>
            <el-descriptions-item label="实际请求" :span="2">
              <code>{{ selectedExecution.request_method || '-' }} {{ selectedExecution.request_url || '' }}</code>
            </el-descriptions-item>
          </el-descriptions>

          <section v-if="selectedExecution.failure_message" class="execution-detail__message execution-detail__message--failure">
            <h3>断言失败原因</h3>
            <pre>{{ selectedExecution.failure_message }}</pre>
          </section>
          <section v-if="selectedExecution.error_message" class="execution-detail__message execution-detail__message--error">
            <h3>系统错误</h3>
            <pre>{{ selectedExecution.error_message }}</pre>
          </section>

          <div class="execution-detail__json-grid">
            <section><h3>请求头</h3><pre>{{ prettyJson(selectedExecution.request_headers) }}</pre></section>
            <section><h3>Query 参数</h3><pre>{{ prettyJson(selectedExecution.request_query_params) }}</pre></section>
            <section><h3>请求体</h3><pre>{{ prettyJson(selectedExecution.request_body) }}</pre></section>
            <section><h3>响应头</h3><pre>{{ prettyJson(selectedExecution.response_headers) }}</pre></section>
            <section class="execution-detail__response-body"><h3>响应体</h3><pre>{{ prettyJson(selectedExecution.response_body) }}</pre></section>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button type="primary" @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </section>
</template>
