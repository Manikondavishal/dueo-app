import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;
export const API = `${BASE}/api`;

const client = axios.create({ baseURL: API, withCredentials: true });

export const api = {
  health: () => client.get("/health").then((r) => r.data),
  me: () => client.get("/auth/me").then((r) => r.data),
  requestInvite: (payload) => client.post("/invite/request", payload).then((r) => r.data),
  requestCode: (email) => client.post("/auth/request-code", { email }).then((r) => r.data),
  verifyCode: (email, code) => client.post("/auth/verify", { email, code }).then((r) => r.data),
  consumeInvite: (token) => client.post("/auth/invite/consume", { token }).then((r) => r.data),
  logout: () => client.post("/auth/logout").then((r) => r.data),
  context: () => client.get("/app/context").then((r) => r.data),
  setup: (payload) => client.post("/app/setup", payload).then((r) => r.data),
  // admin
  adminLeads: (status) => client.get("/admin/leads", { params: status ? { status } : {} }).then((r) => r.data),
  adminLeadAction: (id, action, note = "") =>
    client.post(`/admin/leads/${id}/action`, { action, note }).then((r) => r.data),
  adminUsers: () => client.get("/admin/users").then((r) => r.data),
  adminSuspend: (id) => client.post(`/admin/users/${id}/suspend`).then((r) => r.data),
  adminRestore: (id) => client.post(`/admin/users/${id}/restore`).then((r) => r.data),
  adminOutbox: () => client.get("/admin/outbox").then((r) => r.data),
};

export function refId() {
  return "err_" + Math.random().toString(36).slice(2, 8);
}

export default client;
