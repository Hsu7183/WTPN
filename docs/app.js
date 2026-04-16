const DATA_URL = new URL("./data/news.json", window.location.href);

const elements = {
  count: document.querySelector("#article-count"),
  lastUpdated: document.querySelector("#last-updated"),
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


function buildSourceOptions(sources) {
  for (const source of sources) {
    const option = document.createElement("option");
    option.value = source;
    option.textContent = source;
    elements.sourceFilter.append(option);
  }
}


function buildTagButtons(tags) {
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


async function loadNews() {
  const response = await fetch(DATA_URL);
  if (!response.ok) {
    throw new Error(`Failed to load ${DATA_URL}`);
  }

  const payload = await response.json();
  state.articles = payload.articles ?? [];
  state.sources = payload.available_sources ?? [];
  state.tags = payload.available_tags ?? [];

  elements.count.textContent = String(payload.total_articles ?? state.articles.length);
  elements.lastUpdated.textContent = payload.generated_at
    ? formatUpdatedAt(payload.generated_at)
    : "未知";

  buildSourceOptions(state.sources);
  buildTagButtons(state.tags);
  bindEvents();
  updateView();
}


loadNews().catch((error) => {
  elements.resultsSummary.textContent = "資料載入失敗";

  const errorBox = document.createElement("div");
  errorBox.className = "empty-state card";
  errorBox.innerHTML = `
    <h3>讀取失敗</h3>
    <p>${error.message}</p>
  `;
  elements.results.replaceChildren(errorBox);
});
