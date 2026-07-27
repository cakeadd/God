import http from './http'

export function getProjectMembers(projectId, params = {}) {
  return http.get(`/projects/${projectId}/members/`, { params })
}

export function getProjectMemberCandidates(projectId) {
  return http.get(`/projects/${projectId}/member-candidates/`)
}

export function addProjectMember(projectId, userId, role) {
  return http.post(`/projects/${projectId}/members/`, {
    user: userId,
    role,
  })
}

export function updateProjectMemberRole(projectId, memberId, role) {
  return http.patch(`/projects/${projectId}/members/${memberId}/`, { role })
}

export function removeProjectMember(projectId, memberId) {
  return http.delete(`/projects/${projectId}/members/${memberId}/`)
}
