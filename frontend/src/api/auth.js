import http from './http'

export function login(credentials) {
  return http.post('/auth/login/', credentials)
}

export function register(data) {
  return http.post('/auth/register/', data)
}

export function getCurrentUser() {
  return http.get('/auth/me/')
}

export function updateCurrentUser(data) {
  return http.patch('/auth/me/', data)
}

export function changePassword(data) {
  return http.post('/auth/change-password/', data)
}
