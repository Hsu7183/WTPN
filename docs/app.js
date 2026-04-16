const DATA_URL = new URL("./data/news.json", window.location.href);
const REFRESH_URL = new URL("../api/refresh-news", window.location.href);

const VIEWPORT = Object.freeze({
  locked: "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover",
  unlocked: "width=device-width, initial-scale=1, viewport-fit=cover",
});

const SECURITY = Object.freeze({
  passwordHash: "2a6dda3118910de47066df2ef71acd693ae7bb48dcba8eaea86cd75d4813863d",
  guardKey: "wtpn-auth-guard",
  maxAttempts: 5,
  lockoutMs: 5 * 60 * 1000,
});

const elements = {
  viewportMeta: document.querySelector("#viewport-meta"),
  authOverlay: document.querySelector("#auth-overlay"),
  authForm: document.querySelector("#auth-form"),
  authPassword: document.querySelector("#auth-password"),
  authKeys: [...document.querySelectorAll(".auth-key")],
  authSubmit: document.querySelector("#auth-submit"),
  authMessage: document.querySelector("#auth-message"),
  protectedApp: document.querySelector("#protected-app"),
  count: document.querySelector("#article-count"),
  lastUpdated: document.querySelector("#last-updated"),
  searchToggle: document.querySelector("#search-toggle"),
  searchPanel: document.querySelector("#search-panel"),
  searchInput: document.querySelector("#search-input"),
  sourceFilter: document.querySelector("#source-filter"),
  sortSelect: document.querySelector("#sort-select"),
  tagFilters: document.querySelector("#tag-filters"),
  resultsSummary: document.querySelector("#results-summary"),
  results: document.querySelector("#results"),
};

const state = {
  articles: [],
  sources: [],
  tags: [],
  activeTag: "all",
  eventsBound: false,
  guardTimer: null,
  searchPanelOpen: false,
};


function getTaipeiParts(value) {
  const date = new Date(value);
  const parts = new Intl.DateTimeFormat("zh-TW", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);

  return Object.fromEntries(
    parts
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );
}


function formatUpdatedAt(value) {
  const parts = getTaipeiParts(value);
  return `${parts.year}/${parts.month}/${parts.day} ${parts.hour}:${parts.minute}`;
}


function formatRocDate(value) {
  const parts = getTaipeiParts(value);
  const rocYear = Number(parts.year) - 1911;
  return `${rocYear}/${parts.month}/${parts.day}`;
}


function formatRocMonth(value) {
  const parts = getTaipeiParts(value);
  const rocYear = Number(parts.year) - 1911;
  return `${rocYear}年${parts.month}月份`;
}


function setAuthMessage(message, tone = "info") {
  elements.authMessage.textContent = message;
  if (message) {
    elements.authMessage.dataset.tone = tone;
    return;
  }

  delete elements.authMessage.dataset.tone;
}


function setAuthPasswordValue(value) {
  elements.authPassword.value = value;
}


function setAuthPadDisabled(disabled) {
  elements.authPassword.disabled = disabled;
  for (const button of elements.authKeys) {
    button.disabled = disabled;
  }
}


function setAuthBusy(isBusy) {
  setAuthPadDisabled(isBusy);
  elements.authSubmit.textContent = isBusy ? "更新中..." : "確認";
}


function isEditableTarget(target) {
  return target instanceof HTMLElement &&
    Boolean(target.closest("input, textarea, [contenteditable='true']"));
}


function getGuardState() {
  try {
    const raw = localStorage.getItem(SECURITY.guardKey);
    if (!raw) {
      return { attempts: 0, lockUntil: 0 };
    }

    const parsed = JSON.parse(raw);
    return {
      attempts: Number(parsed.attempts ?? 0),
      lockUntil: Number(parsed.lockUntil ?? 0),
    };
  } catch {
    return { attempts: 0, lockUntil: 0 };
  }
}


function saveGuardState(guard) {
  localStorage.setItem(SECURITY.guardKey, JSON.stringify(guard));
}


function clearGuardState() {
  localStorage.removeItem(SECURITY.guardKey);
}


function getRemainingLockMs() {
  const guard = getGuardState();
  return Math.max(0, guard.lockUntil - Date.now());
}


function formatRemainingLock(ms) {
  const totalSeconds = Math.ceil(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  if (minutes > 0) {
    return `${minutes}分${String(seconds).padStart(2, "0")}秒`;
  }
  return `${seconds}秒`;
}


function syncGuardUi({ resetMessage = false } = {}) {
  const remaining = getRemainingLockMs();
  const lockedOut = remaining > 0;

  if (lockedOut) {
    setAuthPadDisabled(true);
    elements.authSubmit.textContent = "確認";
    setAuthMessage(`輸入錯誤次數過多，請於 ${formatRemainingLock(remaining)} 後再試。`, "error");
    return true;
  }

  if (resetMessage) {
    setAuthMessage("");
  }

  setAuthBusy(false);
  return false;
}


function startGuardTimer() {
  window.clearInterval(state.guardTimer);
  state.guardTimer = window.setInterval(() => {
    const lockedOut = syncGuardUi();
    if (!lockedOut) {
      window.clearInterval(state.guardTimer);
      state.guardTimer = null;
      clearGuardState();
      setAuthMessage("");
    }
  }, 1000);
}


function stopGuardTimer() {
  window.clearInterval(state.guardTimer);
  state.guardTimer = null;
}


function setLocked(locked) {
  if (elements.viewportMeta) {
    elements.viewportMeta.setAttribute("content", locked ? VIEWPORT.locked : VIEWPORT.unlocked);
  }

  document.body.classList.toggle("is-locked", locked);
  elements.authOverlay.hidden = !locked;
  elements.protectedApp.setAttribute("aria-hidden", String(locked));

  if (locked) {
    syncGuardUi({ resetMessage: true });
    if (getRemainingLockMs() > 0) {
      startGuardTimer();
    }
    elements.authPassword.focus();
    return;
  }

  stopGuardTimer();
  setAuthPasswordValue("");
}


async function digestText(value) {
  const encoded = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}


function appendAuthDigit(digit) {
  if (elements.authSubmit.disabled) {
    return;
  }
  setAuthPasswordValue(`${elements.authPassword.value}${digit}`);
  elements.authPassword.focus();
}


function removeLastAuthDigit() {
  if (elements.authSubmit.disabled) {
    return;
  }
  setAuthPasswordValue(elements.authPassword.value.slice(0, -1));
  elements.authPassword.focus();
}


function setSearchPanelOpen(isOpen) {
  state.searchPanelOpen = isOpen;
  elements.searchPanel.hidden = !isOpen;
  elements.searchToggle.setAttribute("aria-expanded", String(isOpen));
  elements.searchToggle.textContent = isOpen ? "收起搜尋" : "展開搜尋";
}


function buildSourceOptions(sources) {
  const defaultOption = document.createElement("option");
  defaultOption.value = "all";
  defaultOption.textContent = "全部來源";
  elements.sourceFilter.replaceChildren(defaultOption);

  for (const source of sources) {
    const option = document.createElement("option");
    option.value = source;
    option.textContent = source;
    elements.sourceFilter.append(option);
  }
}


function buildTagButtons(tags) {
  elements.tagFilters.replaceChildren();

  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.textContent = "全部";
  allButton.dataset.tag = "all";
  allButton.className = "tag-chip is-active";
  elements.tagFilters.append(allButton);

  for (const tag of tags) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = tag;
    button.dataset.tag = tag;
    button.className = "tag-chip";
    elements.tagFilters.append(button);
  }
}


function applyPayload(payload) {
  state.articles = payload.articles ?? [];
  state.sources = payload.available_sources ?? [];
  state.tags = payload.available_tags ?? [];
  state.activeTag = "all";

  elements.count.textContent = String(payload.total_articles ?? state.articles.length);
  elements.lastUpdated.textContent = payload.generated_at
    ? formatUpdatedAt(payload.generated_at)
    : "未知";

  buildSourceOptions(state.sources);
  buildTagButtons(state.tags);

  if (!state.eventsBound) {
    bindEvents();
    state.eventsBound = true;
  }

  updateView();
}


function sortArticles(articles, sortBy) {
  const sorted = [...articles];
  if (sortBy === "oldest") {
    return sorted.sort((a, b) => a.published_at.localeCompare(b.published_at));
  }
  if (sortBy === "source") {
    return sorted.sort((a, b) => {
      return a.source.localeCompare(b.source, "zh-Hant") ||
        b.published_at.localeCompare(a.published_at);
    });
  }
  return sorted.sort((a, b) => b.published_at.localeCompare(a.published_at));
}


function filterArticles() {
  const keyword = elements.searchInput.value.trim().toLowerCase();
  const source = elements.sourceFilter.value;
  const sortBy = elements.sortSelect.value;
  const activeTag = state.activeTag;

  const filtered = state.articles.filter((article) => {
    const matchesKeyword = !keyword || article.search_text.includes(keyword);
    const matchesSource = source === "all" || article.source === source;
    const matchesTag = activeTag === "all" || article.tags.includes(activeTag);
    return matchesKeyword && matchesSource && matchesTag;
  });

  return sortArticles(filtered, sortBy);
}


function renderArticles(articles) {
  elements.results.replaceChildren();

  if (articles.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state card";
    empty.innerHTML = `
      <h3>目前沒有符合條件的新聞</h3>
      <p>可以試試其他分局名稱、事件類型，或清空篩選條件。</p>
    `;
    elements.results.append(empty);
    return;
  }

  const groups = new Map();

  for (const article of articles) {
    const key = article.published_at.slice(0, 7);
    if (!groups.has(key)) {
      groups.set(key, {
        label: formatRocMonth(article.published_at),
        articles: [],
      });
    }
    groups.get(key).articles.push(article);
  }

  const fragment = document.createDocumentFragment();
  const orderedGroupKeys = [...groups.keys()].sort((a, b) => b.localeCompare(a));

  for (const key of orderedGroupKeys) {
    const group = groups.get(key);
    const section = document.createElement("section");
    section.className = "month-group";

    const heading = document.createElement("h3");
    heading.className = "month-heading";
    heading.textContent = group.label;
    section.append(heading);

    const list = document.createElement("ul");
    list.className = "month-list";

    for (const article of group.articles) {
      const item = document.createElement("li");
      item.className = "month-item";

      const meta = document.createElement("div");
      meta.className = "month-item-meta";

      const date = document.createElement("time");
      date.className = "bullet-date";
      date.dateTime = article.published_at;
      date.textContent = formatRocDate(article.published_at);
      meta.append(date);

      const keywords = document.createElement("div");
      keywords.className = "keyword-pills";
      const pills = article.tags.length > 0 ? article.tags : article.matched_keywords;
      for (const keyword of pills) {
        const pill = document.createElement("span");
        pill.className = "keyword-pill";
        pill.textContent = keyword;
        keywords.append(pill);
      }
      meta.append(keywords);

      const title = document.createElement("a");
      title.className = "bullet-title";
      title.href = article.link;
      title.target = "_blank";
      title.rel = "noreferrer noopener";
      title.textContent = article.title;

      const summary = document.createElement("p");
      summary.className = "bullet-summary";
      summary.textContent = article.summary
        ? `${article.summary}｜來源：${article.source}`
        : `來源：${article.source}`;

      item.append(meta, title, summary);
      list.append(item);
    }

    section.append(list);
    fragment.append(section);
  }

  elements.results.append(fragment);
}


function renderSummary(articles) {
  const sourceLabel = elements.sourceFilter.value === "all"
    ? "全部來源"
    : elements.sourceFilter.value;
  const tagLabel = state.activeTag === "all" ? "全部標籤" : state.activeTag;

  elements.resultsSummary.textContent =
    `顯示 ${articles.length} 筆結果 · ${sourceLabel} · ${tagLabel}`;
}


function updateView() {
  const filtered = filterArticles();
  renderSummary(filtered);
  renderArticles(filtered);
}


function bindEvents() {
  elements.searchToggle.addEventListener("click", () => {
    setSearchPanelOpen(!state.searchPanelOpen);
  });

  elements.searchInput.addEventListener("input", updateView);
  elements.sourceFilter.addEventListener("change", updateView);
  elements.sortSelect.addEventListener("change", updateView);

  elements.tagFilters.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-tag]");
    if (!button) {
      return;
    }

    state.activeTag = button.dataset.tag;
    for (const chip of elements.tagFilters.querySelectorAll(".tag-chip")) {
      chip.classList.toggle("is-active", chip === button);
    }
    updateView();
  });
}


function handleAuthPadClick(event) {
  const button = event.target.closest("button[data-key], button[data-action]");
  if (!button || button.disabled) {
    return;
  }

  if (button.dataset.key) {
    appendAuthDigit(button.dataset.key);
    return;
  }

  if (button.dataset.action === "backspace") {
    removeLastAuthDigit();
  }
}


function handleAuthInputKeydown(event) {
  if (/^\d$/.test(event.key)) {
    event.preventDefault();
    appendAuthDigit(event.key);
    return;
  }

  if (event.key === "Backspace") {
    event.preventDefault();
    removeLastAuthDigit();
    return;
  }

  if (event.key === "Enter") {
    event.preventDefault();
    elements.authForm.requestSubmit(elements.authSubmit);
  }
}


async function fetchStoredNews() {
  const response = await fetch(DATA_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load ${DATA_URL}`);
  }
  return response.json();
}


async function refreshNewsOnLogin(password) {
  try {
    const response = await fetch(REFRESH_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
      body: JSON.stringify({ password }),
    });

    if (response.ok) {
      return response.json();
    }

    if ([404, 405, 501].includes(response.status)) {
      return null;
    }

    const errorPayload = await response.json().catch(() => null);
    throw new Error(errorPayload?.error ?? `refresh failed (${response.status})`);
  } catch (error) {
    if (error instanceof TypeError) {
      return null;
    }
    throw error;
  }
}


async function loadNews(password = null) {
  let payload = null;

  if (password) {
    try {
      payload = await refreshNewsOnLogin(password);
    } catch (error) {
      console.warn("Latest refresh failed, falling back to stored news.", error);
    }
  }

  if (!payload) {
    payload = await fetchStoredNews();
  }

  applyPayload(payload);
}


function handleLoadFailure(error) {
  elements.resultsSummary.textContent = "資料載入失敗";

  const errorBox = document.createElement("div");
  errorBox.className = "empty-state card";
  errorBox.innerHTML = `
    <h3>讀取失敗</h3>
    <p>${error.message}</p>
  `;
  elements.results.replaceChildren(errorBox);
}


async function unlockApp(password) {
  setLocked(false);
  setAuthMessage("");
  await loadNews(password);
}


async function handleAuthSubmit(event) {
  event.preventDefault();

  if (syncGuardUi()) {
    startGuardTimer();
    return;
  }

  const password = elements.authPassword.value.trim();
  if (!password) {
    setAuthMessage("請輸入登入密碼。", "error");
    return;
  }

  setAuthBusy(true);

  try {
    const digest = await digestText(password);
    if (digest === SECURITY.passwordHash) {
      clearGuardState();
      setAuthMessage("");
      await unlockApp(password);
      return;
    }

    const guard = getGuardState();
    const nextAttempts = guard.attempts + 1;
    const remainingAttempts = Math.max(SECURITY.maxAttempts - nextAttempts, 0);
  const nextGuard = {
      attempts: nextAttempts,
      lockUntil: nextAttempts >= SECURITY.maxAttempts
        ? Date.now() + SECURITY.lockoutMs
        : 0,
    };
    saveGuardState(nextGuard);
    setAuthPasswordValue("");

    if (nextGuard.lockUntil > 0) {
      syncGuardUi();
      startGuardTimer();
      return;
    }

    setAuthMessage(`密碼錯誤，尚可再嘗試 ${remainingAttempts} 次。`, "error");
  } catch (error) {
    handleLoadFailure(error);
    setAuthMessage(`驗證失敗：${error.message}`, "error");
  } finally {
    if (!document.body.classList.contains("is-locked")) {
      setAuthBusy(false);
      return;
    }

    if (getRemainingLockMs() === 0) {
      setAuthBusy(false);
    }
  }
}


function protectInteractions() {
  document.addEventListener("contextmenu", (event) => {
    event.preventDefault();
  });

  document.addEventListener("dragstart", (event) => {
    event.preventDefault();
  });

  document.addEventListener("copy", (event) => {
    if (isEditableTarget(event.target)) {
      return;
    }
    event.preventDefault();
  });

  document.addEventListener("cut", (event) => {
    if (isEditableTarget(event.target)) {
      return;
    }
    event.preventDefault();
  });

  document.addEventListener("selectstart", (event) => {
    if (isEditableTarget(event.target)) {
      return;
    }
    event.preventDefault();
  });

  document.addEventListener("keydown", (event) => {
    const key = event.key.toLowerCase();
    const ctrlOrMeta = event.ctrlKey || event.metaKey;
    const editable = isEditableTarget(event.target);

    const blockedShortcuts = ctrlOrMeta && (
      key === "u" ||
      key === "s" ||
      key === "p" ||
      (!editable && (key === "a" || key === "c" || key === "x")) ||
      (event.shiftKey && ["i", "j", "c"].includes(key))
    );
    const blockedFunctionKey = event.key === "F12" || event.key === "ContextMenu";

    if (!blockedShortcuts && !blockedFunctionKey) {
      return;
    }

    event.preventDefault();
  });

  window.addEventListener("beforeprint", (event) => {
    event.preventDefault();
  });
}


function bindAuthEvents() {
  elements.authForm.addEventListener("click", handleAuthPadClick);
  elements.authPassword.addEventListener("keydown", handleAuthInputKeydown);
  elements.authForm.addEventListener("submit", (event) => {
    handleAuthSubmit(event).catch((error) => {
      setAuthMessage(`驗證失敗：${error.message}`, "error");
      setAuthBusy(false);
    });
  });
}


function bootstrap() {
  protectInteractions();
  bindAuthEvents();
  setSearchPanelOpen(false);
  setLocked(true);

  if (getRemainingLockMs() > 0) {
    syncGuardUi();
    startGuardTimer();
  }
}


bootstrap();
