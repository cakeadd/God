<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  execution: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

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
</script>

<template>
  <el-dialog v-model="visible" title="执行详情" width="860px" align-center append-to-body>
    <div v-loading="loading" class="execution-detail">
      <template v-if="execution">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="执行状态">
            <el-tag :type="statusTagType(execution.status)" effect="plain">
              {{ statusLabels[execution.status] || execution.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="测试用例">{{ execution.test_case_name }}</el-descriptions-item>
          <el-descriptions-item label="运行环境">
            {{ execution.environment_name || '跟随默认环境' }}
          </el-descriptions-item>
          <el-descriptions-item label="来源">{{ execution.test_run_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="执行人">{{ execution.executed_by_username }}</el-descriptions-item>
          <el-descriptions-item label="执行时间">
            {{ formatTime(execution.finished_at || execution.started_at || execution.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatDuration(execution.duration_ms) }}</el-descriptions-item>
          <el-descriptions-item label="响应状态码">{{ execution.response_status_code ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="实际请求" :span="2">
            <code>{{ execution.request_method || '-' }} {{ execution.request_url || '' }}</code>
          </el-descriptions-item>
        </el-descriptions>

        <section v-if="execution.failure_message" class="execution-detail__message execution-detail__message--failure">
          <h3>断言失败原因</h3>
          <pre>{{ execution.failure_message }}</pre>
        </section>
        <section v-if="execution.error_message" class="execution-detail__message execution-detail__message--error">
          <h3>系统错误</h3>
          <pre>{{ execution.error_message }}</pre>
        </section>

        <div class="execution-detail__json-grid">
          <section><h3>请求头</h3><pre>{{ prettyJson(execution.request_headers) }}</pre></section>
          <section><h3>Query 参数</h3><pre>{{ prettyJson(execution.request_query_params) }}</pre></section>
          <section><h3>请求体</h3><pre>{{ prettyJson(execution.request_body) }}</pre></section>
          <section><h3>响应头</h3><pre>{{ prettyJson(execution.response_headers) }}</pre></section>
          <section class="execution-detail__response-body"><h3>响应体</h3><pre>{{ prettyJson(execution.response_body) }}</pre></section>
        </div>
      </template>
    </div>
    <template #footer>
      <el-button type="primary" @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>
