import http from './http'

export function getProjectMembers(projectId) {
  return http.get(`/projects/${projectId}/members/`)
}

export function updateProjectMemberRole(projectId, memberId, role) {
  return http.patch(`/projects/${projectId}/members/${memberId}/`, { role })
}
