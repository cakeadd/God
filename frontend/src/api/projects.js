import http from './http'

export function getProjects() {
  return http.get('/projects/')
}
