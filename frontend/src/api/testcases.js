import http from './http'

export function getTestCases(projectId, params = {}) {
  return http.get(`/projects/${projectId}/testcases/`, { params })
}

export function getTestCase(projectId, testCaseId) {
  return http.get(`/projects/${projectId}/testcases/${testCaseId}/`)
}

export function createTestCase(projectId, data) {
  return http.post(`/projects/${projectId}/testcases/`, data)
}

export function updateTestCase(projectId, testCaseId, data) {
  return http.patch(`/projects/${projectId}/testcases/${testCaseId}/`, data)
}

export function deactivateTestCase(projectId, testCaseId) {
  return http.delete(`/projects/${projectId}/testcases/${testCaseId}/`)
}
