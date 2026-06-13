const state = {
  user: null,
  models: [],
  dashboardPage: 1,
  dashboardPerPage: 8,
  dashboardTotalPages: 1,
  dashboardSearch: "",
  dashboardScope: "mine",
  historySearch: "",
  historySortBy: "detect_time",
  historySortOrder: "desc",
  adminSelectedUserId: null,
  adminSelectedUserIds: new Set(),
  batchCancelled: false,
  batchAbortController: null,
};

const BATCH_RECOMMENDED_LIMIT = 100;
const ADMIN_ALLOWED_VIEWS = new Set(["dashboard", "history", "logs", "admin"]);

const titles = {
  dashboard: ["仪表盘", "系统运行概览与近期检测趋势"],
  single: ["单条检测", "单条域名或 URL 风险识别"],
  batch: ["批量检测", "多条域名或 URL 快速筛查"],
  features: ["特征分析", "URL 解析与统计特征解释"],
  datasets: ["数据集管理", "样本导入、标注与查询"],
  models: ["模型中心", "训练实验与模型版本记录"],
  modelManage: ["模型管理", "模型启用、删除与版本维护"],
  history: ["检测历史", "检测记录追踪与结果复核入口"],
  logs: ["系统日志", "关键操作留痕与审计追踪"],
  reviews: ["人工复核", "误报、漏报和人工确认记录"],
  admin: ["管理员中心", "用户、模型与使用情况总览"],
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const textMap = {
  benign: "正常",
  safe: "安全",
  normal: "正常",
  suspicious: "可疑",
  "needs_review": "待复核",
  "needs-review": "待复核",
  "high-risk": "高危",
  malicious: "恶意",
  phishing: "钓鱼",
  dga: "DGA 域名",
  malware: "恶意软件",
  "phishing_or_malicious": "钓鱼或恶意",
  "phishing-or-malicious": "钓鱼或恶意",
  active: "启用中",
  inactive: "未启用",
  completed: "已完成",
  pending: "待处理",
  failed: "失败",
  confirmed: "确认正确",
  "false_positive": "误报",
  "false-positive": "误报",
  "false_negative": "漏报",
  "false-negative": "漏报",
  watch: "待观察",
  login: "登录",
  logout: "退出",
  register: "注册",
  detect_single: "单条检测",
  detect_batch_item: "批量检测明细",
  detect_batch_file: "文件批量检测",
  feature_analyze: "特征分析",
  dataset_import: "样本导入",
  dataset_label_update: "标签修改",
  model_train: "模型训练",
  model_import_local: "本地模型导入",
  model_activate: "模型启用",
  model_delete: "模型删除",
  password_change: "修改密码",
  model_seed_demo: "初始化模型创建",
  review_create: "人工复核",
  user: "用户",
  admin: "管理员",
  frozen: "已冻结",
};

function displayText(value) {
  if (value === null || value === undefined || value === "") return "-";
  const key = String(value);
  return textMap[key] || textMap[key.replaceAll("_", "-")] || key;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatLogDetail(value) {
  if (!value) return "-";
  try {
    return escapeHtml(JSON.stringify(JSON.parse(value), null, 2));
  } catch {
    return escapeHtml(value);
  }
}

async function api(path, options = {}) {
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const response = await fetch(path, {
    headers: isFormData
      ? { ...(options.headers || {}) }
      : options.body
        ? { "Content-Type": "application/json", ...(options.headers || {}) }
        : { ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.message || `HTTP ${response.status}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2600);
}

function tag(value) {
  const text = value || "-";
  return `<span class="tag ${String(text).replaceAll("_", "-")}">${displayText(text)}</span>`;
}

function formatDate(value) {
  if (!value) return "-";
  const raw = String(value).trim().replace(" ", "T");
  const hasTimezone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(raw);
  const date = new Date(hasTimezone ? raw : `${raw}+08:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date).replaceAll("/", "-");
}

function beijingDateStamp() {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date()).replaceAll("/", "");
}

function renderRows(target, rows, emptyText = "暂无数据") {
  const node = $(target);
  const colspan = Math.max(
    1,
    node?.closest("table")?.querySelectorAll("thead th").length || 8
  );
  node.innerHTML = rows.length
    ? rows.join("")
    : `<tr><td colspan="${colspan}">${emptyText}</td></tr>`;
}

function renderBars(target, data) {
  const entries = Object.entries(data || {});
  const max = entries.reduce((best, [, count]) => Math.max(best, count), 1);
  $(target).innerHTML = entries.length
    ? entries
        .map(([label, count]) => {
          const width = Math.max(4, Math.round((count / max) * 100));
          return `
            <div class="bar-row">
              <span>${displayText(label)}</span>
              <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
              <strong>${count}</strong>
            </div>`;
        })
        .join("")
    : `<div class="bar-row"><span>暂无数据</span><div class="bar-track"></div><strong>0</strong></div>`;
}

function renderPieChart(target, data) {
  const entries = Object.entries(data || {}).filter(([, count]) => Number(count) > 0);
  const colors = ["#2457d6", "#0f7b73", "#b7791f", "#b42318", "#5b5fc7", "#0891b2", "#16a34a"];
  const total = entries.reduce((sum, [, count]) => sum + Number(count), 0);
  const node = $(target);
  if (!entries.length || total <= 0) {
    node.innerHTML = `
      <div class="pie-empty">
        <strong>暂无数据</strong>
        <span>完成检测后将在这里生成统计图</span>
      </div>`;
    return;
  }

  let cursor = 0;
  const segments = entries.map(([label, count], index) => {
    const start = cursor;
    const value = Number(count);
    cursor += (value / total) * 360;
    return `${colors[index % colors.length]} ${start}deg ${cursor}deg`;
  });
  node.innerHTML = `
    <div class="pie-wrap">
      <div class="pie-visual" style="background: conic-gradient(${segments.join(", ")})">
        <div><strong>${total}</strong><span>总数</span></div>
      </div>
      <div class="pie-legend">
        ${entries
          .map(([label, count], index) => {
            const percent = Math.round((Number(count) / total) * 100);
            return `
              <div class="pie-legend-row">
                <span class="pie-dot" style="background:${colors[index % colors.length]}"></span>
                <span>${displayText(label)}</span>
                <strong>${count} / ${percent}%</strong>
              </div>`;
          })
          .join("")}
      </div>
    </div>`;
}

function formatMetric(value) {
  if (value === null || value === undefined) return "-";
  return Number(value).toFixed(3);
}

function shortPath(value) {
  if (!value) return "-";
  if (String(value).startsWith("database://")) return "数据库存储";
  const parts = String(value).split(/[\\/]/);
  return parts.slice(-2).join("/");
}

function modelSourceText(item) {
  if (!item.owner_id) return "系统默认";
  if (item.owner_id === state.user?.id) return item.storage_type === "database" ? "我的导入" : "我的训练";
  return `用户 #${item.owner_id}`;
}

function modelActions(item) {
  if (state.user?.role === "admin") return `<span class="tag">监管查看</span>`;
  const canActivate = item.owner_id === null || item.owner_id === undefined || item.owner_id === state.user?.id;
  const canDelete = item.owner_id === state.user?.id;
  if (!canActivate && !canDelete) return `<span class="tag">不可操作</span>`;
  return `
    ${
      canActivate
        ? `<button type="button" class="mini-button" data-action="activate-model" data-id="${item.id}" ${
            item.is_active ? "disabled" : ""
          }>启用</button>`
        : ""
    }
    ${
      canDelete
        ? `<button type="button" class="mini-button danger" data-action="delete-model" data-id="${item.id}" data-name="${escapeHtml(item.model_name)}">删除</button>`
        : ""
    }
  `;
}

function localizedPayload(data) {
  if (!data || typeof data !== "object") return data;
  return {
    ...data,
    risk_level_text: displayText(data.risk_level),
    predict_label_text: displayText(data.predict_label),
    model: data.model
      ? {
          ...data.model,
          status_text: displayText(data.model.is_active ? "active" : "inactive"),
        }
      : data.model,
  };
}

function renderSingleDetectionDetail(data) {
  const features = data.features || {};
  const rows = [
    ["检测输入", data.input_text],
    ["解析域名", data.parsed_domain],
    ["检测模型", data.model?.model_name || "-"],
    ["模型类型", data.model?.model_type || "-"],
    ["结果说明", data.explain_text || "-"],
    ["域名长度", features.domain_length],
    ["路径长度", features.path_length],
    ["点号数量", features.dot_count],
    ["连字符数量", features.hyphen_count],
    ["数字比例", features.digit_ratio],
    ["熵值", features.entropy_value],
  ];
  $("#singleOutput").innerHTML = `
    <div class="single-detail-title">检测详情</div>
    <div class="single-detail-grid">
      ${rows
        .map(
          ([label, value]) => `
            <div>
              <span>${label}</span>
              <strong>${escapeHtml(value ?? "-")}</strong>
            </div>`
        )
        .join("")}
    </div>`;
}

function setBatchProgress({ title, current, done = 0, total = 0, log } = {}) {
  $("#batchProgressPanel").classList.remove("hidden");
  if (title !== undefined) $("#batchProgressTitle").textContent = title;
  if (current !== undefined) $("#batchCurrentTarget").textContent = current;
  $("#batchProgressCount").textContent = `${done} / ${total}`;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;
  $("#batchProgressBar").style.width = `${percent}%`;
  if (log) {
    const node = document.createElement("div");
    node.textContent = log;
    $("#batchProgressLog").prepend(node);
  }
}

function modelLabel(model) {
  if (!model) return "暂无可用模型";
  const active = model.is_active ? " / 启用中" : "";
  return `${model.model_name}（${model.model_type}${active}）`;
}

function populateModelSelects(models) {
  state.models = models || [];
  const activeModel = state.models.find((item) => item.is_active);
  const options = state.models.length
    ? state.models.map((item) => `<option value="${item.id}">${modelLabel(item)}</option>`).join("")
    : `<option value="active">暂无可用模型</option>`;

  ["#singleModelSelect", "#batchModelSelect"].forEach((selector) => {
    const node = $(selector);
    if (!node) return;
    node.innerHTML = options;
    node.value = activeModel ? String(activeModel.id) : "active";
    node.disabled = !state.models.length;
  });
}

function clearModelUiState(emptyText = "暂无模型数据") {
  state.models = [];
  ["#singleModelSelect", "#batchModelSelect"].forEach((selector) => {
    const node = $(selector);
    if (node) {
      node.innerHTML = `<option value="active">暂无可用模型</option>`;
      node.disabled = true;
    }
  });
  renderRows("#modelRows", [], emptyText);
  renderRows("#taskRows", [], emptyText === "正在加载模型..." ? "正在加载训练任务..." : "暂无训练任务");
  renderRows("#modelManageRows", [], emptyText);
}

async function loadModelOptions() {
  const models = await api("/api/models");
  populateModelSelects(models.items || []);
  return models;
}

async function handleModelSelectChange(event) {
  const modelId = event.target.value;
  if (!modelId || modelId === "active") return;
  event.target.disabled = true;
  try {
    await api(`/api/models/${modelId}/activate`, { method: "PUT" });
    await loadModelOptions();
    const activeModel = state.models.find((item) => String(item.id) === String(modelId));
    $("#engineBadge").textContent = activeModel ? activeModel.model_name : "启发式规则基线";
    toast("当前检测模型已切换");
  } finally {
    event.target.disabled = false;
  }
}

function setAuthView(showAuth) {
  $("#authScreen").classList.toggle("hidden", !showAuth);
  $("#appShell").classList.toggle("hidden", showAuth);
}

function setTopbarUser(user) {
  $("#currentUser").textContent = user?.username || "-";
  $("#currentRole").textContent = displayText(user?.role) || "-";
  $("#heroSession").textContent = user ? `${user.username} / ${displayText(user.role)}` : "-";
  state.dashboardScope = user?.role === "admin" ? "all" : "mine";
  document.body.classList.toggle("admin-mode", user?.role === "admin");
  $$(".nav-item").forEach((item) => {
    const view = item.dataset.view;
    const hiddenForAdmin = user?.role === "admin" && !ADMIN_ALLOWED_VIEWS.has(view);
    const hiddenForUser = user?.role !== "admin" && view === "admin";
    item.classList.toggle("hidden", hiddenForAdmin || hiddenForUser);
  });
}

function canAccessView(view) {
  if (view === "admin") return state.user?.role === "admin";
  return state.user?.role !== "admin" || ADMIN_ALLOWED_VIEWS.has(view);
}

function resetSessionUiState() {
  state.dashboardPage = 1;
  state.dashboardTotalPages = 1;
  state.dashboardSearch = "";
  state.historySearch = "";
  state.historySortBy = "detect_time";
  state.historySortOrder = "desc";
  state.adminSelectedUserId = null;
  state.adminSelectedUserIds.clear();
  state.batchCancelled = false;
  state.batchAbortController = null;
  clearModelUiState();
  if ($("#recentSearchInput")) $("#recentSearchInput").value = "";
  if ($("#historySearchInput")) $("#historySearchInput").value = "";
  if ($("#passwordModal")) closePasswordModal();
}

function switchView(view) {
  if (!canAccessView(view)) {
    toast("管理员账号仅用于监管，请使用管理员中心查看用户数据");
    view = "admin";
  }
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  $$(".view").forEach((item) => item.classList.toggle("active", item.id === `view-${view}`));
  const [title, subtitle] = titles[view];
  $("#viewTitle").textContent = title;
  $("#viewSubtitle").textContent = subtitle;

  if (view === "dashboard") loadDashboard();
  if (view === "single" || view === "batch") loadModelOptions();
  if (view === "features") loadFeatureDefault();
  if (view === "datasets") loadDatasets();
  if (view === "models") loadModels();
  if (view === "modelManage") loadModelManage();
  if (view === "history") loadHistory();
  if (view === "logs") loadLogs();
  if (view === "reviews") loadReviews();
  if (view === "admin") loadAdmin();
}

function jumpFromDashboard(target) {
  const view = target?.dataset?.jumpView;
  if (!view) return;
  if (!canAccessView(view)) {
    switchView("admin");
    return;
  }
  switchView(view);
}

async function loadHealth() {
  try {
    await api("/api/health");
    $("#apiStatus").textContent = "在线";
  } catch {
    $("#apiStatus").textContent = "离线";
  }
}

async function loadMe() {
  try {
    const data = await api("/api/auth/me");
    state.user = data.user;
    setTopbarUser(data.user);
    setAuthView(false);
    await loadModelOptions();
    await loadDashboard();
    return true;
  } catch {
    state.user = null;
    setTopbarUser(null);
    setAuthView(true);
    return false;
  }
}

async function refreshCaptcha() {
  const src = `/api/auth/captcha-image?ts=${Date.now()}`;
  const loginImage = $("#loginCaptchaImage");
  const registerImage = $("#registerCaptchaImage");
  if (loginImage) loginImage.src = src;
  if (registerImage) registerImage.src = src;
}

async function loadDashboard() {
  const scope = state.user?.role === "admin" ? "all" : state.dashboardScope;
  const data = await api(`/api/dashboard/summary?scope=${encodeURIComponent(scope)}`);
  const riskDistribution = data.risk_distribution || {};
  state.dashboardScope = data.stats_scope || scope;
  $("#metricSamples").textContent = data.sample_total;
  $("#metricDetections").textContent = data.detection_total;
  $("#metricModels").textContent = data.model_total;
  $("#metricTasks").textContent = data.task_total;
  $("#heroModelCard")?.classList.toggle("hidden", state.user?.role === "admin");
  $("#engineBadge").textContent =
    state.user?.role === "admin"
      ? "管理员监管模式"
      : data.active_model
        ? data.active_model.model_name
        : "启发式规则基线";
  $("#sessionBadge").textContent = state.user ? `已登录：${state.user.username}` : "未登录";
  $("#heroModel").textContent = data.active_model ? data.active_model.model_name : "无启用模型";
  $("#heroRisk").textContent = riskDistribution["high-risk"] || riskDistribution.suspicious || 0;
  const scopeLabel = state.dashboardScope === "all" ? "所有账号综合统计" : "我的账号统计";
  $("#dashboardScopeText").textContent = state.user?.role === "admin" ? "管理员视图：所有账号综合统计" : scopeLabel;
  $("#toggleDashboardScope").textContent = state.dashboardScope === "all" ? "查看我的统计" : "查看所有账号";
  $("#toggleDashboardScope").classList.toggle("hidden", state.user?.role === "admin");
  renderPieChart("#riskBars", riskDistribution);
  renderPieChart("#detectLabelBars", data.detection_label_distribution);
  await loadRecentDetections();
}

async function toggleDashboardScope() {
  state.dashboardScope = state.dashboardScope === "all" ? "mine" : "all";
  await loadDashboard();
}

async function loadRecentDetections() {
  const params = new URLSearchParams({
    page: String(state.dashboardPage),
    per_page: String(state.dashboardPerPage),
    scope: "mine",
  });
  if (state.dashboardSearch) params.set("q", state.dashboardSearch);
  const history = await api(`/api/detect/history?${params.toString()}`);
  renderRows(
    "#recentRows",
    (history.items || []).map(
      (item) => `
        <tr>
          <td>${item.input_text}</td>
          <td>${item.parsed_domain}</td>
          <td>${tag(item.predict_label)}</td>
          <td>${tag(item.risk_level)}</td>
          <td>${formatDate(item.detect_time)}</td>
        </tr>`
    )
  );
  state.dashboardTotalPages = history.pages || 1;
  $("#recentPageInfo").textContent = `${state.dashboardSearch ? "搜索结果：" : ""}第 ${
    history.page || state.dashboardPage
  } / ${
    state.dashboardTotalPages
  } 页，共 ${history.total || 0} 条`;
  $("#recentPrevPage").disabled = state.dashboardPage <= 1;
  $("#recentNextPage").disabled = state.dashboardPage >= state.dashboardTotalPages;
}

async function changeRecentPage(delta) {
  const nextPage = Math.max(1, Math.min(state.dashboardTotalPages, state.dashboardPage + delta));
  if (nextPage === state.dashboardPage) return;
  state.dashboardPage = nextPage;
  await loadRecentDetections();
}

async function searchRecentDetections() {
  state.dashboardSearch = $("#recentSearchInput").value.trim();
  state.dashboardPage = 1;
  await loadRecentDetections();
}

async function clearRecentSearch() {
  $("#recentSearchInput").value = "";
  state.dashboardSearch = "";
  state.dashboardPage = 1;
  await loadRecentDetections();
}

async function exportDetectionHistory() {
  const params = new URLSearchParams();
  if (state.dashboardSearch) params.set("q", state.dashboardSearch);
  const query = params.toString();
  const response = await fetch(`/api/detect/history/export${query ? `?${query}` : ""}`);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.message || `HTTP ${response.status}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const stamp = beijingDateStamp();
  link.href = url;
  link.download = `detection_history_${stamp}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  toast("检测历史已导出");
}

async function handleLogin(event) {
  event.preventDefault();
  try {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: $("#loginUsername").value.trim(),
        password: $("#loginPassword").value,
        captcha: $("#loginCaptcha").value.trim(),
      }),
    });
    state.user = data.user;
    setTopbarUser(data.user);
    setAuthView(false);
    resetSessionUiState();
    switchView("dashboard");
    toast(`已登录：${data.user.username}`);
    $("#loginCaptcha").value = "";
  } catch (error) {
    await refreshCaptcha();
    toast(error.message);
  }
}

async function handleRegister(event) {
  event.preventDefault();
  try {
    const data = await api("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({
        username: $("#registerUsername").value.trim(),
        password: $("#registerPassword").value,
        captcha: $("#registerCaptcha").value.trim(),
      }),
    });
    state.user = data.user;
    setTopbarUser(data.user);
    setAuthView(false);
    resetSessionUiState();
    switchView("dashboard");
    toast("注册并自动登录成功");
    $("#registerCaptcha").value = "";
  } catch (error) {
    await refreshCaptcha();
    toast(error.message);
  }
}

async function handleLogout() {
  await api("/api/auth/logout", { method: "POST" });
  state.user = null;
  setTopbarUser(null);
  setAuthView(true);
  toast("已退出登录");
  await refreshCaptcha();
}

function openPasswordModal() {
  $("#passwordForm").reset();
  $("#passwordModal").classList.remove("hidden");
  $("#oldPassword").focus();
}

function closePasswordModal() {
  $("#passwordModal").classList.add("hidden");
  $("#passwordForm").reset();
}

async function handlePasswordChange(event) {
  event.preventDefault();
  const oldPassword = $("#oldPassword").value;
  const newPassword = $("#newPassword").value;
  const confirmPassword = $("#confirmPassword").value;
  if (newPassword !== confirmPassword) {
    toast("两次输入的新密码不一致");
    return;
  }
  const button = $("#submitPasswordChange");
  button.disabled = true;
  button.textContent = "修改中...";
  try {
    await api("/api/auth/password", {
      method: "PUT",
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      }),
    });
    closePasswordModal();
    toast("密码已修改");
  } finally {
    button.disabled = false;
    button.textContent = "确认修改";
  }
}

async function handleDeleteAccount() {
  const confirmed = window.confirm("注销后将删除该账号下的检测记录、复核记录和自训练模型，且无法恢复。确认继续吗？");
  if (!confirmed) return;
  await api("/api/auth/account", {
    method: "DELETE",
    body: JSON.stringify({ confirm: true }),
  });
  state.user = null;
  setTopbarUser(null);
  setAuthView(true);
  toast("账号已注销");
  await refreshCaptcha();
}

async function handleSingleDetect(event) {
  event.preventDefault();
  try {
    const data = await api("/api/detect/single", {
      method: "POST",
      body: JSON.stringify({
        input_text: $("#singleInput").value.trim(),
        model_id: $("#singleModelSelect").value,
      }),
    });
    $("#singleRiskLevel").innerHTML = tag(data.risk_level);
    $("#singleRiskScore").textContent = data.risk_score;
    $("#singleLabel").innerHTML = tag(data.predict_label);
    renderSingleDetectionDetail(data);
    toast("检测完成");
    await loadModelOptions();
    if ($("#view-dashboard").classList.contains("active")) await loadDashboard();
  } catch (error) {
    if (error.status === 401) return handleAuthRequired();
    throw error;
  }
}

async function handleBatchDetect(event) {
  event.preventDefault();
  try {
    const items = $("#batchInput").value
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const data = await api("/api/detect/batch", {
      method: "POST",
      body: JSON.stringify({
        items,
        model_id: $("#batchModelSelect").value,
      }),
    });
    renderRows(
      "#batchRows",
      data.results.map(
        (item) => `
          <tr>
            <td>${item.input_text}</td>
            <td>${item.parsed_domain}</td>
            <td>${tag(item.predict_label)}</td>
            <td>${tag(item.risk_level)}</td>
            <td>${item.risk_score}</td>
            <td>${item.model?.model_name || "-"}</td>
          </tr>`
      )
    );
    toast(`完成 ${data.total} 条检测`);
    await loadModelOptions();
    if ($("#view-dashboard").classList.contains("active")) await loadDashboard();
  } catch (error) {
    if (error.status === 401) return handleAuthRequired();
    throw error;
  }
}

async function handleBatchFileDetect() {
  const fileInput = $("#batchFile");
  const file = fileInput.files?.[0];
  if (!file) {
    toast("请先选择文件");
    return;
  }
  state.batchCancelled = false;
  state.batchAbortController = null;
  $("#uploadBatchFile").disabled = true;
  $("#stopBatchFile").disabled = false;
  $("#batchRows").innerHTML = "";
  $("#batchProgressLog").innerHTML = "";
  setBatchProgress({
    title: "文件解析中",
    current: `正在解析文件：${file.name}`,
    done: 0,
    total: 0,
    log: "文件解析中...",
  });

  const formData = new FormData();
  formData.append("file", file);
  formData.append("limit", String(BATCH_RECOMMENDED_LIMIT + 1));
  try {
    state.batchAbortController = new AbortController();
    const parsed = await api("/api/detect/extract-file", {
      method: "POST",
      signal: state.batchAbortController.signal,
      body: formData,
    });
    state.batchAbortController = null;
    const parsedItems = parsed.items || [];
    const hasTooManyItems = parsed.total_extracted > BATCH_RECOMMENDED_LIMIT || parsedItems.length > BATCH_RECOMMENDED_LIMIT;
    const items = parsedItems.slice(0, BATCH_RECOMMENDED_LIMIT);
    $("#batchFileInfo").textContent = `${parsed.file_name || file.name} / ${
      parsed.source_format || "unknown"
    } / 已识别 ${parsed.total_extracted || parsedItems.length} 条${
      hasTooManyItems ? `（建议不超过 ${BATCH_RECOMMENDED_LIMIT} 条，本次仅分析前 ${items.length} 条）` : ""
    }`;
    setBatchProgress({
      title: hasTooManyItems ? "文件内容过多" : "文件解析完毕",
      current: hasTooManyItems
        ? `共识别 ${parsed.total_extracted || parsedItems.length} 条，建议导入数据集不要超过 ${BATCH_RECOMMENDED_LIMIT} 条；可点击“终止分析”取消。`
        : `已提取 ${items.length} 条，准备开始分析`,
      done: 0,
      total: items.length,
      log: hasTooManyItems
        ? `文件内容过多，系统仅保留前 ${items.length} 条进入检测队列。`
        : `文件分析目标提取完成：${items.length} 条`,
    });

    const rows = [];
    for (let index = 0; index < items.length; index += 1) {
      if (state.batchCancelled) {
        setBatchProgress({
          title: "分析已终止",
          current: `用户已终止，已完成 ${index} / ${items.length} 条`,
          done: index,
          total: items.length,
          log: "分析已被手动终止。",
        });
        break;
      }
      const target = items[index];
      setBatchProgress({
        title: "文件分析中",
        current: `正在分析 ${target}`,
        done: index,
        total: items.length,
        log: `正在分析 ${target}`,
      });
      state.batchAbortController = new AbortController();
      const item = await api("/api/detect/single", {
        method: "POST",
        signal: state.batchAbortController.signal,
        body: JSON.stringify({
          input_text: target,
          model_id: $("#batchModelSelect").value,
        }),
      });
      state.batchAbortController = null;
      rows.push(`
        <tr>
          <td>${item.input_text}</td>
          <td>${item.parsed_domain}</td>
          <td>${tag(item.predict_label)}</td>
          <td>${tag(item.risk_level)}</td>
          <td>${item.risk_score}</td>
          <td>${item.model?.model_name || "-"}</td>
        </tr>`);
      if ((index + 1) % 10 === 0 || index === items.length - 1) {
        renderRows("#batchRows", rows);
      }
      setBatchProgress({
        title: "文件分析中",
        current: `已完成 ${target}`,
        done: index + 1,
        total: items.length,
      });
    }
    if (!state.batchCancelled) {
      setBatchProgress({
        title: "文件分析完毕",
        current: `全部完成，共分析 ${items.length} 条`,
        done: items.length,
        total: items.length,
        log: "文件分析完毕",
      });
      toast(`文件批量检测完成：${items.length} 条`);
    }
    await loadModelOptions();
    if ($("#view-dashboard").classList.contains("active")) await loadDashboard();
  } catch (error) {
    if (error.name === "AbortError") {
      setBatchProgress({
        title: "分析已终止",
        current: "当前请求已取消，后续目标不会继续分析。",
        done: 0,
        total: 0,
        log: "分析已被手动终止。",
      });
      return;
    }
    setBatchProgress({
      title: "文件分析失败",
      current: error.message,
      done: 0,
      total: 0,
      log: `失败：${error.message}`,
    });
    throw error;
  } finally {
    $("#uploadBatchFile").disabled = false;
    $("#stopBatchFile").disabled = true;
    state.batchAbortController = null;
  }
}

function stopBatchFileDetect() {
  state.batchCancelled = true;
  if (state.batchAbortController) {
    state.batchAbortController.abort();
  }
  setBatchProgress({
    title: "正在终止",
    current: "已收到终止指令，正在停止当前文件分析流程。",
    log: "用户点击了终止分析。",
  });
}

function renderFeatureResult(data) {
  const features = data.features || {};
  $("#featureLength").textContent = features.domain_length ?? "-";
  $("#featureEntropy").textContent = features.entropy_value ?? "-";
  $("#featureDigitRatio").textContent = features.digit_ratio ?? "-";
  $("#featureHyphen").textContent = features.hyphen_count ?? "-";
  $("#featureSubdomain").textContent = features.subdomain_count ?? "-";
  $("#featureParsed").textContent = JSON.stringify(data.parsed || {}, null, 2);
  $("#featureHints").innerHTML = (data.risk_hints || [])
    .map((item) => `<div class="hint-item">${item}</div>`)
    .join("");
}

async function handleFeatureAnalyze(event) {
  event.preventDefault();
  const data = await api("/api/features/analyze", {
    method: "POST",
    body: JSON.stringify({ input_text: $("#featureInput").value.trim() }),
  });
  renderFeatureResult(data);
  toast("特征分析完成");
}

async function loadFeatureDefault() {
  if ($("#featureParsed").textContent !== "等待分析") return;
  const data = await api("/api/features/analyze", {
    method: "POST",
    body: JSON.stringify({ input_text: $("#featureInput").value.trim() }),
  });
  renderFeatureResult(data);
}

async function loadDatasets() {
  const params = new URLSearchParams();
  const keyword = $("#datasetSearchInput")?.value.trim();
  const label = $("#datasetLabelFilter")?.value;
  const sampleType = $("#datasetTypeFilter")?.value;
  if (keyword) params.set("q", keyword);
  if (label) params.set("label", label);
  if (sampleType) params.set("sample_type", sampleType);
  const query = params.toString();
  const data = await api(`/api/datasets${query ? `?${query}` : ""}`);
  renderRows(
    "#datasetRows",
    data.items.map(
      (item) => `
        <tr>
          <td>${item.domain}</td>
          <td>${tag(item.label)}</td>
          <td>${displayText(item.sample_type)}</td>
          <td>${item.source || "-"}</td>
        </tr>`
    )
  );
}

async function handleDatasetImport(event) {
  event.preventDefault();
  const file = $("#datasetFile").files?.[0];
  let body;
  if (file) {
    body = new FormData();
    body.append("file", file);
    body.append("label", $("#datasetLabel").value);
    body.append("sample_type", $("#datasetType").value);
    body.append("source", $("#datasetSource").value.trim());
  } else {
    body = JSON.stringify({
      text_block: $("#datasetText").value,
      label: $("#datasetLabel").value,
      sample_type: $("#datasetType").value,
      source: $("#datasetSource").value.trim(),
    });
  }
  const data = await api("/api/datasets/import", {
    method: "POST",
    body,
  });
  toast(`导入 ${data.imported} 条，跳过 ${data.skipped} 条`);
  if (file) {
    $("#datasetFile").value = "";
    $("#datasetFileInfo").textContent = "未选择文件，可直接粘贴文本导入";
  }
  await loadDatasets();
  await loadDashboard();
}

async function loadModels() {
  clearModelUiState("正在加载模型...");
  const models = await api("/api/models");
  populateModelSelects(models.items || []);
  renderRows(
    "#modelRows",
    models.items.map(
      (item) => `
        <tr>
          <td>${escapeHtml(item.model_name)}</td>
          <td>${escapeHtml(item.model_type)}</td>
          <td>${escapeHtml(item.version)}</td>
          <td>${modelSourceText(item)}</td>
          <td>${tag(item.is_active ? "active" : "inactive")}</td>
        </tr>`
    )
  );

  const tasks = await api("/api/models/tasks");
  renderRows(
    "#taskRows",
    tasks.items.map(
      (item) => `
        <tr>
          <td>${item.id}</td>
          <td>${item.model_type}</td>
          <td>${item.dataset_size}</td>
          <td>${tag(item.status)}</td>
          <td>${formatDate(item.finished_at)}</td>
        </tr>`
    )
  );
}

async function loadModelManage() {
  clearModelUiState("正在加载模型...");
  const models = await api("/api/models");
  populateModelSelects(models.items || []);
  renderRows(
    "#modelManageRows",
    models.items.map(
      (item) => `
        <tr>
          <td>${item.id}</td>
          <td>${escapeHtml(item.model_name)}</td>
          <td>${escapeHtml(item.model_type)}</td>
          <td>${escapeHtml(item.feature_type)}</td>
          <td>${modelSourceText(item)}</td>
          <td>${tag(item.is_active ? "active" : "inactive")}</td>
          <td title="${item.file_path || ""}">${shortPath(item.file_path)}</td>
          <td>
            <div class="table-actions">
              ${modelActions(item)}
            </div>
          </td>
        </tr>`
    )
  );
}

async function handleModelManageClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;

  const modelId = button.dataset.id;
  if (button.dataset.action === "activate-model") {
    await api(`/api/models/${modelId}/activate`, { method: "PUT" });
    toast("模型已启用");
  }

  if (button.dataset.action === "delete-model") {
    const name = button.dataset.name || `#${modelId}`;
    const confirmed = window.confirm(`确定删除模型 ${name} 吗？检测历史会保留，但模型引用会置空。`);
    if (!confirmed) return;
    await api(`/api/models/${modelId}`, {
      method: "DELETE",
      body: JSON.stringify({ delete_file: false }),
    });
    toast("模型已删除");
  }

  await loadModelManage();
  await loadModelOptions();
  await loadDashboard();
}

function openLocalTrainer() {
  let maybeOpened = false;
  const markOpened = () => {
    maybeOpened = true;
  };
  window.addEventListener("blur", markOpened, { once: true });
  document.addEventListener("visibilitychange", markOpened, { once: true });
  toast("正在尝试打开本地训练助手...");
  window.location.href = "domaintrainer://open";
  window.setTimeout(() => {
    window.removeEventListener("blur", markOpened);
    document.removeEventListener("visibilitychange", markOpened);
    if (!maybeOpened) {
      toast("如果本地训练助手未打开，请先下载并运行安装脚本。");
    }
  }, 2500);
}

async function handleLocalModelImport(event) {
  event.preventDefault();
  const modelFile = $("#localModelFile").files?.[0];
  if (!modelFile) {
    toast("请先选择 .joblib 模型文件");
    return;
  }
  const body = new FormData();
  body.append("model_file", modelFile);
  const metricFile = $("#localMetricFile").files?.[0];
  if (metricFile) body.append("metric_file", metricFile);
  body.append("model_name", $("#localModelName").value.trim());
  body.append("activate", $("#localModelActivate").checked ? "true" : "false");

  const button = $("#importLocalModel");
  button.disabled = true;
  button.textContent = "导入中...";
  try {
    const data = await api("/api/models/import-local", { method: "POST", body });
    toast(`已导入模型：${data.model?.model_name || modelFile.name}`);
    $("#localModelImportForm").reset();
    $("#localModelActivate").checked = true;
    $("#localModelFileInfo").textContent = "请选择本地训练助手生成的 .joblib 文件";
    await loadModels();
    await loadModelOptions();
    await loadDashboard();
  } finally {
    button.disabled = false;
    button.textContent = "导入并登记模型";
  }
}

async function loadHistory() {
  const params = new URLSearchParams({
    page: "1",
    per_page: "100",
    sort_by: state.historySortBy,
    sort_order: state.historySortOrder,
  });
  if (state.historySearch) params.set("q", state.historySearch);
  const data = await api(`/api/detect/history?${params.toString()}`);
  renderRows(
    "#historyRows",
    data.items.map(
      (item) => `
        <tr>
          <td>${item.id}</td>
          <td>${item.input_text}</td>
          <td>${item.parsed_domain}</td>
          <td>${item.model_name || "-"}</td>
          <td>${tag(item.predict_label)}</td>
          <td>${tag(item.risk_level)}</td>
          <td>${item.risk_score}</td>
          <td>${formatDate(item.detect_time)}</td>
        </tr>`
    )
  );
  updateHistorySortHeaders();
}

function updateHistorySortHeaders() {
  $$("[data-history-sort]").forEach((button) => {
    const active = button.dataset.historySort === state.historySortBy;
    button.classList.toggle("active", active);
    button.dataset.order = active ? state.historySortOrder : "";
  });
}

async function handleHistoryHeaderSort(event) {
  const button = event.target.closest("[data-history-sort]");
  if (!button) return;
  const sortBy = button.dataset.historySort;
  if (state.historySortBy === sortBy) {
    state.historySortOrder = state.historySortOrder === "asc" ? "desc" : "asc";
  } else {
    state.historySortBy = sortBy;
    state.historySortOrder = sortBy === "risk_score" || sortBy === "detect_time" || sortBy === "id" ? "desc" : "asc";
  }
  await loadHistory();
}

async function loadAdmin() {
  const data = await api("/api/admin/users");
  const validIds = new Set((data.items || []).map((item) => item.id));
  state.adminSelectedUserIds = new Set(
    Array.from(state.adminSelectedUserIds).filter((id) => validIds.has(id))
  );
  renderRows(
    "#adminUserRows",
    data.items.map(
      (item) => `
        <tr data-user-id="${item.id}" class="clickable-row">
          <td><input type="checkbox" class="admin-user-check" data-user-id="${item.id}" ${
            state.adminSelectedUserIds.has(item.id) ? "checked" : ""
          } ${item.role === "admin" ? "disabled" : ""}></td>
          <td>${item.id}</td>
          <td>${item.username}</td>
          <td>${displayText(item.role)}</td>
          <td>${displayText(item.status)}</td>
          <td>${item.detection_count}</td>
          <td>${item.review_count}</td>
          <td>${item.model_count}</td>
        </tr>`
      )
    );
  updateAdminSelectionControls(data.items || []);
  if (!state.adminSelectedUserId && data.items.length) {
    state.adminSelectedUserId = data.items[0].id;
  }
  await loadAdminDetail();
}

function updateAdminSelectionControls(users = []) {
  const selectableIds = users.length
    ? users.filter((item) => item.role !== "admin").map((item) => item.id)
    : $$("#adminUserRows .admin-user-check:not(:disabled)").map((item) => Number(item.dataset.userId));
  const selectedCount = selectableIds.filter((id) => state.adminSelectedUserIds.has(id)).length;
  const allNode = $("#adminSelectAllUsers");
  if (allNode) {
    allNode.checked = selectableIds.length > 0 && selectedCount === selectableIds.length;
    allNode.indeterminate = selectedCount > 0 && selectedCount < selectableIds.length;
    allNode.disabled = selectableIds.length === 0;
  }
  $("#freezeSelectedUsers").disabled = selectedCount === 0;
  $("#unfreezeSelectedUsers").disabled = selectedCount === 0;
}

async function updateSelectedUserStatus(status) {
  const userIds = Array.from(state.adminSelectedUserIds);
  if (!userIds.length) {
    toast("请先选择需要处理的账号");
    return;
  }
  await api("/api/admin/users/status", {
    method: "PUT",
    body: JSON.stringify({ user_ids: userIds, status }),
  });
  toast(status === "frozen" ? "已冻结选中账号" : "已解除选中账号冻结");
  state.adminSelectedUserIds.clear();
  await loadAdmin();
}

async function loadAdminDetail() {
  if (!state.adminSelectedUserId) {
    $("#adminUserMeta").textContent = "请选择左侧用户查看明细";
    renderRows("#adminDetectionRows", []);
    renderRows("#adminReviewRows", []);
    renderRows("#adminModelRows", []);
    return;
  }
  const data = await api(`/api/admin/users/${state.adminSelectedUserId}/detail`);
  $("#adminUserMeta").textContent =
    `${data.user.username} / ${displayText(data.user.role)} / ${displayText(data.user.status)}`;
  renderRows(
    "#adminDetectionRows",
    (data.detections || []).map(
      (item) => `
        <tr>
          <td>${item.id}</td>
          <td>${item.input_text}</td>
          <td>${item.model_name || "-"}</td>
          <td>${tag(item.predict_label)}</td>
          <td>${tag(item.risk_level)}</td>
        </tr>`
    )
  );
  renderRows(
    "#adminReviewRows",
    (data.reviews || []).map(
      (item) => `
        <tr>
          <td>${item.record_id}</td>
          <td>${displayText(item.review_result)}</td>
          <td>${displayText(item.correct_label)}</td>
          <td>${formatDate(item.created_at)}</td>
        </tr>`
    )
  );
  renderRows(
    "#adminModelRows",
    (data.models || []).map(
      (item) => `
        <tr>
          <td>${item.id}</td>
          <td>${item.model_name}</td>
          <td>${item.model_type}</td>
          <td>${tag(item.is_active ? "active" : "inactive")}</td>
        </tr>`
    )
  );
}

async function searchHistory() {
  state.historySearch = $("#historySearchInput").value.trim();
  await loadHistory();
}

async function clearHistorySearch() {
  $("#historySearchInput").value = "";
  state.historySearch = "";
  state.historySortBy = "detect_time";
  state.historySortOrder = "desc";
  await loadHistory();
}

async function loadLogs() {
  const action = $("#logActionFilter").value;
  const limit = $("#logLimit").value;
  const params = new URLSearchParams({ limit });
  if (action) params.set("action_type", action);
  const data = await api(`/api/logs?${params.toString()}`);
  renderRows(
    "#logRows",
    data.items.map(
      (item) => `
        <tr>
          <td>${item.id}</td>
          <td>${item.user_id || "-"}</td>
          <td>${displayText(item.action_type)}</td>
          <td>${displayText(item.target_type) || "-"} / ${item.target_id || "-"}</td>
          <td class="log-detail">${item.detail || "-"}</td>
          <td>${item.ip_address || "-"}</td>
          <td>${formatDate(item.created_at)}</td>
        </tr>`
    )
  );
}

async function loadReviews() {
  const data = await api("/api/reviews");
  renderRows(
    "#reviewRows",
    data.items.map(
      (item) => `
        <tr>
          <td>${item.record_id}</td>
          <td>${tag(item.review_result)}</td>
          <td>${displayText(item.correct_label)}</td>
          <td>${formatDate(item.created_at)}</td>
        </tr>`
    )
  );
}

async function handleReview(event) {
  event.preventDefault();
  const recordId = Number($("#reviewRecordId").value);
  if (!recordId) {
    toast("请填写检测记录 ID");
    return;
  }
  await api("/api/reviews", {
    method: "POST",
    body: JSON.stringify({
      record_id: recordId,
      review_result: $("#reviewResult").value,
      correct_label: $("#correctLabel").value,
      comment: $("#reviewComment").value.trim(),
    }),
  });
  toast("复核已提交");
  await loadReviews();
  if ($("#view-dashboard")?.classList.contains("active")) await loadDashboard();
}

function handleAuthRequired() {
  state.user = null;
  setAuthView(true);
  toast("请先登录");
}

function bindEvents() {
  $$(".nav-item").forEach((item) =>
    item.addEventListener("click", () => switchView(item.dataset.view))
  );
  $("#view-dashboard").addEventListener("click", (event) => {
    if (event.target.closest("#toggleDashboardScope, input, select, textarea, a")) return;
    const target = event.target.closest("[data-jump-view]");
    if (!target) return;
    jumpFromDashboard(target);
  });
  $("#view-dashboard").addEventListener("keydown", (event) => {
    const target = event.target.closest("[data-jump-view][role='button']");
    if (!target) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      jumpFromDashboard(target);
    }
  });
  $$(".auth-tab").forEach((item) =>
    item.addEventListener("click", async () => {
      $$(".auth-tab").forEach((tab) => tab.classList.toggle("active", tab === item));
      $$(".auth-form").forEach((form) => form.classList.remove("active"));
      $(`#${item.dataset.authTab}Form`).classList.add("active");
      if (!$("#loginCaptchaImage").src || !$("#registerCaptchaImage").src) {
        await refreshCaptcha();
      }
    })
  );
  $("#loginForm").addEventListener("submit", handleLogin);
  $("#registerForm").addEventListener("submit", handleRegister);
  $("#refreshCaptcha").addEventListener("click", refreshCaptcha);
  $("#refreshCaptchaRegister").addEventListener("click", refreshCaptcha);
  $("#changePasswordButton").addEventListener("click", openPasswordModal);
  $("#passwordForm").addEventListener("submit", handlePasswordChange);
  $("#closePasswordModal").addEventListener("click", closePasswordModal);
  $("#cancelPasswordChange").addEventListener("click", closePasswordModal);
  $("#passwordModal").addEventListener("click", (event) => {
    if (event.target.id === "passwordModal") closePasswordModal();
  });
  $("#logoutButton").addEventListener("click", handleLogout);
  $("#deleteAccountButton").addEventListener("click", handleDeleteAccount);
  $("#singleForm").addEventListener("submit", handleSingleDetect);
  $("#singleModelSelect").addEventListener("change", handleModelSelectChange);
  $("#batchForm").addEventListener("submit", handleBatchDetect);
  $("#batchModelSelect").addEventListener("change", handleModelSelectChange);
  $("#uploadBatchFile").addEventListener("click", handleBatchFileDetect);
  $("#stopBatchFile").addEventListener("click", stopBatchFileDetect);
  $("#recentPrevPage").addEventListener("click", () => changeRecentPage(-1));
  $("#recentNextPage").addEventListener("click", () => changeRecentPage(1));
  $("#toggleDashboardScope").addEventListener("click", toggleDashboardScope);
  $("#jumpToHistory").addEventListener("click", () => switchView("history"));
  $("#exportRecentHistory").addEventListener("click", exportDetectionHistory);
  $("#searchRecentHistory").addEventListener("click", searchRecentDetections);
  $("#clearRecentSearch").addEventListener("click", clearRecentSearch);
  $("#recentSearchInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchRecentDetections();
    }
  });
  $("#batchFile").addEventListener("change", () => {
    const file = $("#batchFile").files?.[0];
    $("#batchFileInfo").textContent = file
      ? `已选择：${file.name}`
      : "未选择文件";
  });
  $("#featureForm").addEventListener("submit", handleFeatureAnalyze);
  $("#datasetForm").addEventListener("submit", handleDatasetImport);
  $("#refreshDatasets").addEventListener("click", loadDatasets);
  $("#searchDatasets").addEventListener("click", loadDatasets);
  $("#datasetSearchInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadDatasets();
    }
  });
  $("#datasetLabelFilter").addEventListener("change", loadDatasets);
  $("#datasetTypeFilter").addEventListener("change", loadDatasets);
  $("#datasetFile").addEventListener("change", () => {
    const file = $("#datasetFile").files?.[0];
    $("#datasetFileInfo").textContent = file
      ? `已选择：${file.name}，导入时将使用当前标签和类型`
      : "未选择文件，可直接粘贴文本导入";
  });
  $("#refreshModels").addEventListener("click", loadModels);
  $("#openLocalTrainer").addEventListener("click", openLocalTrainer);
  $("#localModelImportForm").addEventListener("submit", handleLocalModelImport);
  $("#localModelFile").addEventListener("change", () => {
    const modelFile = $("#localModelFile").files?.[0];
    const metricFile = $("#localMetricFile").files?.[0];
    $("#localModelFileInfo").textContent = modelFile
      ? `已选择：${modelFile.name}${metricFile ? `，指标：${metricFile.name}` : ""}`
      : "请选择本地训练助手生成的 .joblib 文件";
  });
  $("#localMetricFile").addEventListener("change", () => {
    const modelFile = $("#localModelFile").files?.[0];
    const metricFile = $("#localMetricFile").files?.[0];
    $("#localModelFileInfo").textContent = modelFile
      ? `已选择：${modelFile.name}${metricFile ? `，指标：${metricFile.name}` : ""}`
      : "请选择本地训练助手生成的 .joblib 文件";
  });
  $("#refreshModelManage").addEventListener("click", loadModelManage);
  $("#modelManageRows").addEventListener("click", handleModelManageClick);
  $("#refreshHistory").addEventListener("click", loadHistory);
  $("#searchHistory").addEventListener("click", searchHistory);
  $("#clearHistorySearch").addEventListener("click", clearHistorySearch);
  $$(".sort-header").forEach((item) => item.addEventListener("click", handleHistoryHeaderSort));
  $("#historySearchInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchHistory();
    }
  });
  $("#refreshLogs").addEventListener("click", loadLogs);
  $("#logActionFilter").addEventListener("change", loadLogs);
  $("#logLimit").addEventListener("change", loadLogs);
  $("#reviewForm").addEventListener("submit", handleReview);
  $("#refreshReviews").addEventListener("click", loadReviews);
  $("#adminUserRows").addEventListener("click", async (event) => {
    const checkbox = event.target.closest(".admin-user-check");
    if (checkbox) {
      const userId = Number(checkbox.dataset.userId);
      if (checkbox.checked) {
        state.adminSelectedUserIds.add(userId);
      } else {
        state.adminSelectedUserIds.delete(userId);
      }
      updateAdminSelectionControls();
      return;
    }
    const row = event.target.closest("tr[data-user-id]");
    if (!row) return;
    state.adminSelectedUserId = Number(row.dataset.userId);
    await loadAdminDetail();
  });
  $("#adminSelectAllUsers").addEventListener("change", async (event) => {
    const checked = event.target.checked;
    $$("#adminUserRows .admin-user-check:not(:disabled)").forEach((item) => {
      item.checked = checked;
      const userId = Number(item.dataset.userId);
      if (checked) {
        state.adminSelectedUserIds.add(userId);
      } else {
        state.adminSelectedUserIds.delete(userId);
      }
    });
    updateAdminSelectionControls();
  });
  $("#freezeSelectedUsers").addEventListener("click", () => updateSelectedUserStatus("frozen"));
  $("#unfreezeSelectedUsers").addEventListener("click", () => updateSelectedUserStatus("active"));
}

async function boot() {
  bindEvents();
  await loadHealth();
  const authenticated = await loadMe();
  if (!authenticated) {
    setAuthView(true);
    await refreshCaptcha();
  }
}

boot().catch((error) => toast(error.message));
