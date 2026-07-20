import http from './http'

export function login(credentials) {
  return http.post('/auth/login/', credentials)
}

export function getCurrentUser() {
  return http.get('/auth/me/')
}
