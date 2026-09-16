const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
let accessToken = null;

function getThreadId() {
  const key = "shopora-thread-id";
  let id = localStorage.getItem(key);
  if (!id) { id = crypto.randomUUID(); localStorage.setItem(key, id); }
  return id;
}

async function rawRequest(path, options = {}, retry = true) {
  const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, credentials: "include" });
  if (response.status === 401 && retry && path !== "/auth/login" && path !== "/auth/register" && path !== "/auth/refresh") {
    try {
      const refreshed = await rawRequest("/auth/refresh", { method: "POST" }, false);
      accessToken = refreshed.access_token;
      return rawRequest(path, options, false);
    } catch { accessToken = null; }
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { const body = await response.json(); detail = body.detail || detail; } catch { /* response body wasn't JSON; fall back to the generic message above */ }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

export async function login(email, password) {
  const data = await rawRequest("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, false);
  accessToken = data.access_token;
  return rawRequest("/auth/me");
}

export async function register(name, email, password) {
  const data = await rawRequest("/auth/register", { method: "POST", body: JSON.stringify({ name, email, password }) }, false);
  accessToken = data.access_token;
  return rawRequest("/auth/me");
}

export async function restoreSession() {
  try {
    const data = await rawRequest("/auth/refresh", { method: "POST" }, false);
    accessToken = data.access_token;
    return rawRequest("/auth/me");
  } catch { accessToken = null; return null; }
}

export async function logout() {
  try { await rawRequest("/auth/logout", { method: "POST" }, false); } finally { accessToken = null; }
}

export function getCurrentThreadId() { return getThreadId(); }
export function sendMessage(message, threadId = getThreadId()) { return rawRequest("/chat", { method: "POST", body: JSON.stringify({ message, thread_id: threadId }) }); }
export function checkHealth() { return rawRequest("/health"); }
export function fetchProducts() { return rawRequest("/products"); }
export function fetchProduct(productId) { return rawRequest(`/products/${productId}`); }
export function searchProducts(query) { return rawRequest(`/products/search?q=${encodeURIComponent(query)}`); }
export function fetchCart() { return rawRequest("/cart"); }
export function addToCartAPI(productId, _threadId, quantity = 1) { return rawRequest("/cart/add", { method: "POST", body: JSON.stringify({ product_id: productId, quantity }) }); }
export function removeFromCartAPI(productId) { return rawRequest(`/cart/${productId}`, { method: "DELETE" }); }
export function updateCartQuantityAPI(productId, quantity) { return rawRequest(`/cart/${productId}`, { method: "PATCH", body: JSON.stringify({ quantity }) }); }
export function fetchOrders() { return rawRequest("/orders"); }
export function checkoutAPI() { return rawRequest("/checkout", { method: "POST" }); }
export function fetchRecommendations() { return rawRequest("/recommendations"); }
