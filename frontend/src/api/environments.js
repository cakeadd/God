import http from './http'

export function getEnvironments(projectId, params = {}) {
  return http.get(`/projects/${projectId}/environments/`, { params })
}

export function getEnvironment(projectId, environmentId) {
  return http.get(`/projects/${projectId}/environments/${environmentId}/`)
}

export function createEnvironment(projectId, data) {
  return http.post(`/projects/${projectId}/environments/`, data)
}

export function updateEnvironment(projectId, environmentId, data) {
  return http.patch(`/projects/${projectId}/environments/${environmentId}/`, data)
}

export function deactivateEnvironment(projectId, environmentId) {
  return http.delete(`/projects/${projectId}/environments/${environmentId}/`)
}
