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
