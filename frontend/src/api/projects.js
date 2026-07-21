import http from './http'

export function getProjects() {
  return http.get('/projects/')
}

export function getProject(projectId) {
  return http.get(`/projects/${projectId}/`)
}
