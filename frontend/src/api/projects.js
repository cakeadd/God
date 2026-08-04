import http from './http'

export function getProjects() {
  return http.get('/projects/')
}

export function createProject(data) {
  return http.post('/projects/', data)
}

export function getProject(projectId) {
  return http.get(`/projects/${projectId}/`)
}

export function updateProject(projectId, data) {
  return http.patch(`/projects/${projectId}/`, data)
}

export function archiveProject(projectId) {
  return http.delete(`/projects/${projectId}/`)
}
