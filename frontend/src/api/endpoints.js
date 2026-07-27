import http from './http'

export function getEndpoints(projectId, params = {}) {
  return http.get(`/projects/${projectId}/endpoints/`, { params })
}

export function getEndpoint(projectId, endpointId) {
  return http.get(`/projects/${projectId}/endpoints/${endpointId}/`)
}

export function createEndpoint(projectId, data) {
  return http.post(`/projects/${projectId}/endpoints/`, data)
}

export function updateEndpoint(projectId, endpointId, data) {
  return http.patch(`/projects/${projectId}/endpoints/${endpointId}/`, data)
}

export function deactivateEndpoint(projectId, endpointId) {
  return http.delete(`/projects/${projectId}/endpoints/${endpointId}/`)
}
