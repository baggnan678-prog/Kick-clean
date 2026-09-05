// Configuration et fonctions partagées par toutes les pages ProxiServices.
// Aucune dépendance externe : fetch natif + localStorage pour la session.

const PRODUCTION_API_BASE_URL = "https://proxiservices-backend.vercel.app";
const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_BASE_URL = window.localStorage.getItem("ps_api_base_url")
  || (isLocalHost ? "http://localhost:8000" : PRODUCTION_API_BASE_URL);

const Session = {
  get accessToken() { return localStorage.getItem("ps_access_token"); },
  get refreshToken() { return localStorage.getItem("ps_refresh_token"); },
  get user() {
    const raw = localStorage.getItem("ps_user");
    return raw ? JSON.parse(raw) : null;
  },
  save(tokens, user) {
    localStorage.setItem("ps_access_token", tokens.access_token);
    localStorage.setItem("ps_refresh_token", tokens.refresh_token);
    if (user) localStorage.setItem("ps_user", JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem("ps_access_token");
    localStorage.removeItem("ps_refresh_token");
    localStorage.removeItem("ps_user");
  },
};

async function apiRequest(path, { method = "GET", body, auth = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && Session.accessToken) {
    headers["Authorization"] = `Bearer ${Session.accessToken}`;
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  const text = await response.text();
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }

  if (!response.ok) {
    const detail = (data && data.detail) ? data.detail : `Erreur ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

async function apiUpload(path, formData) {
  const headers = {};
  if (Session.accessToken) {
    headers["Authorization"] = `Bearer ${Session.accessToken}`;
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });

  let data = null;
  const text = await response.text();
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }

  if (!response.ok) {
    const detail = (data && data.detail) ? data.detail : `Erreur ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function requireAuth(allowedRoles) {
  const user = Session.user;
  if (!user || !Session.accessToken) {
    window.location.href = "login.html";
    return null;
  }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    window.location.href = "index.html";
    return null;
  }
  return user;
}

function renderUserBar(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const user = Session.user;
  if (!user) {
    el.innerHTML = `<a href="login.html" class="btn btn-outline" style="padding:0.4rem 1rem;">Connexion</a>`;
    return;
  }
  el.innerHTML = `
    <span>${user.full_name} · ${user.role}</span>
    <button id="ps-logout-btn">Déconnexion</button>
  `;
  document.getElementById("ps-logout-btn").addEventListener("click", () => {
    Session.clear();
    window.location.href = "index.html";
  });
}
