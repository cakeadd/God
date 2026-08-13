import http from './http'

export function executeTestCase(projectId, testCaseId) {
  return http.post(`/projects/${projectId}/testcases/${testCaseId}/execute/`)
}

export function getExecutions(projectId, params = {}) {
  return http.get(`/projects/${projectId}/executions/`, { params })
}

export function getExecution(projectId, executionId) {
  return http.get(`/projects/${projectId}/executions/${executionId}/`)
}

export function getTestRuns(projectId, params = {}) {
  return http.get(`/projects/${projectId}/test-runs/`, { params })
}

export function createTestRun(projectId, data) {
  return http.post(`/projects/${projectId}/test-runs/`, data)
}

export function getTestRun(projectId, testRunId) {
  return http.get(`/projects/${projectId}/test-runs/${testRunId}/`)
}

export function rerunTestRun(projectId, testRunId) {
  return http.post(`/projects/${projectId}/test-runs/${testRunId}/rerun/`)
}
