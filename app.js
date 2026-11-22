(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const state = {
    mode: "sources",
    result: null,
    busy: false,
  };

  const elements = {
    status: $("#engine-status"),
    statusText: $("#engine-status span"),
    outputState: $("#output-state"),
    sourceForm: $("#source-form"),
    draftForm: $("#draft-form"),
    sourceSubmit: $("#source-submit"),
    draftSubmit: $("#draft-submit"),
    inputTitle: $("#input-title"),
    inputStep: $("#input-step"),
    empty: $("#empty-state"),
    results: $("#results-view"),
    errors: $("#error-state"),
    errorMessage: $("#error-message"),
    summary: $("#summary-grid"),
    resultItems: $("#result-items"),
    markdown: $("#markdown-output"),
    disclaimer: $("#result-disclaimer"),
    resultsTitle: $("#results-title"),
    copy: $("#copy-output"),
    download: $("#download-output"),
  };

  const labels = {
    approved: "تأییدشده",
    pending: "در انتظار",
    rejected: "ردشده",
    errors: "خطا",
  };

  const escapeText = (value) => String(value ?? "");
  const statusText = (value) => {
    if (value === true) return ["approved", "✓", "تأیید"];
    if (value === false) return ["rejected", "✕", "رد"];
    return ["pending", "?", "در انتظار"];
  };

  function setOnline(online, message) {
    elements.status.classList.toggle("is-online", online);
    elements.statusText.textContent = message;
  }

  function setBusy(busy) {
    state.busy = busy;
    const button = state.mode === "sources" ? elements.sourceSubmit : elements.draftSubmit;
    button.disabled = busy;
    button.querySelector("span").textContent = busy
      ? "در حال پردازش…"
      : (state.mode === "sources" ? "اجرای اعتبارسنجی" : "بررسی پیش‌نویس");

    elements.outputState.classList.toggle("is-busy", busy);
    elements.outputState.querySelector("i").textContent = "";
    if (busy) {
      elements.outputState.classList.remove("is-done");
      elements.outputState.lastChild.textContent = " در حال پردازش";
    } else if (!elements.errors.classList.contains("is-hidden")) {
      elements.outputState.classList.remove("is-done");
      elements.outputState.lastChild.textContent = " خطا";
    } else if (!elements.results.classList.contains("is-hidden")) {
      elements.outputState.classList.add("is-done");
      elements.outputState.lastChild.textContent = " گزارش آماده است";
    } else {
      elements.outputState.classList.remove("is-done");
      elements.outputState.lastChild.textContent = " آماده اجرا";
    }
  }

  function showError(message) {
    elements.empty.classList.add("is-hidden");
    elements.results.classList.add("is-hidden");
    elements.errors.classList.remove("is-hidden");
    elements.errorMessage.textContent = escapeText(message || "خطای نامشخص.");
    elements.outputState.classList.remove("is-busy", "is-done");
    elements.outputState.lastChild.textContent = " خطا";
  }

  function showEmpty() {
    elements.empty.classList.remove("is-hidden");
    elements.results.classList.add("is-hidden");
    elements.errors.classList.add("is-hidden");
    elements.outputState.classList.remove("is-busy", "is-done");
    elements.outputState.lastChild.textContent = " آماده اجرا";
  }

  function makeNode(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = escapeText(text);
    return node;
  }

  function addSummaryCard(key, value) {
    const card = makeNode("div", "summary-card " + key);
    card.append(
      makeNode("strong", "", Number.isFinite(Number(value)) ? String(value) : "—"),
      makeNode("span", "", labels[key] || key)
    );
    elements.summary.append(card);
  }

  function renderSummary(summary, mode) {
    elements.summary.replaceChildren();
    if (mode === "sources") {
      addSummaryCard("approved", summary.approved ?? 0);
      addSummaryCard("pending", summary.pending ?? 0);
      addSummaryCard("rejected", summary.rejected ?? 0);
      addSummaryCard("errors", summary.errors ?? 0);
    } else {
      addSummaryCard("approved", summary.approved_sections ?? 0);
      addSummaryCard("pending", summary.pending ?? 0);
      addSummaryCard("rejected", summary.failed ?? 0);
      addSummaryCard("errors", summary.total_checks ?? 0);
      elements.summary.lastElementChild.querySelector("span").textContent = "کل قواعد";
      elements.summary.firstElementChild.querySelector("span").textContent = "بخش تأییدشده";
    }
  }

  function safeDoiLink(article) {
    const link = makeNode("a", "", article.doi || article.url || "بدون DOI");
    const url = typeof article.url === "string" ? article.url : "";
    if (/^https:\/\/doi\.org\/\S+$/i.test(url) && !/\s/.test(url)) {
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    } else {
      link.removeAttribute("href");
    }
    return link;
  }

  function renderGates(steps) {
    const wrap = makeNode("div", "gate-grid");
    for (let index = 1; index <= 11; index += 1) {
      const id = "S" + index;
      const [kind, symbol] = statusText(steps?.[id]);
      const pill = makeNode("span", "gate-pill " + kind, id.replace("S", "") + " " + symbol);
      pill.title = id + ": " + (steps?.[id] === true ? "approved" : steps?.[id] === false ? "rejected" : "pending");
      wrap.append(pill);
    }
    return wrap;
  }

  function renderSourceResult(entry) {
    const article = entry.article || {};
    const verdict = entry.verdict || "pending";
    const card = makeNode("article", "source-result");
    const top = makeNode("div", "source-top");
    const meta = makeNode("div", "");
    meta.append(
      makeNode("h3", "source-title", article.title || "عنوان در فراداده پیدا نشد"),
      makeNode("p", "source-meta")
    );
    meta.lastElementChild.append(
      makeNode("span", "", [article.type, article.year, article.tier ? "Tier " + article.tier : ""].filter(Boolean).join(" · ") + " · "),
      safeDoiLink(article)
    );
    const badge = makeNode("span", "verdict-badge " + verdict, labels[verdict] || verdict);
    top.append(meta, badge);
    card.append(top);

    const passed = Number(entry.verified_steps || 0);
    const total = Number(entry.total_steps || 11);
    const progress = makeNode("div", "source-progress");
    const track = makeNode("div", "progress-track");
    const bar = makeNode("i", "");
    const progressPercent = Math.round(Math.max(0, Math.min(100, total ? passed / total * 100 : 0)) / 10) * 10;
    bar.className = "progress-fill progress-pct-" + progressPercent;
    track.append(bar);
    progress.append(track, makeNode("span", "", passed + " / " + total));
    card.append(progress, renderGates(entry.steps));

    const notes = article.notes?.fa || article.notes?.en || "";
    if (notes) {
      const details = makeNode("details", "source-notes");
      details.append(makeNode("summary", "", "جزئیات و موارد نیازمند بررسی"));
      details.append(makeNode("p", "", notes));
      card.append(details);
    }
    return card;
  }

  function renderErrors(errors) {
    if (!Array.isArray(errors) || errors.length === 0) return null;
    const container = makeNode("div", "error-list");
    container.append(makeNode("strong", "", "مواردی که از سرویس فراداده پاسخ نگرفتند"));
    for (const error of errors) {
      container.append(makeNode("p", "", (error.doi || "DOI نامشخص") + " — " + (error.message || "خطا")));
    }
    return container;
  }

  function renderDraftSections(sections, checks) {
    const wrap = makeNode("div", "draft-sections");
    const bySection = new Map();
    for (const check of checks || []) {
      if (!bySection.has(check.section)) bySection.set(check.section, []);
      bySection.get(check.section).push(check);
    }
    for (const section of sections || []) {
      const details = makeNode("details", "section-result");
      const summary = makeNode("summary", "");
      const name = makeNode("span", "section-name", section.title);
      const count = makeNode("span", "section-counts",
        [section.passed || 0, section.failed || 0, section.pending || 0].join(" / "));
      const badge = makeNode("span", "verdict-badge " + section.verdict,
        labels[section.verdict] || section.verdict);
      summary.append(name, count, badge);
      details.append(summary);
      const list = makeNode("div", "section-checks");
      for (const check of bySection.get(section.id) || []) {
        const row = makeNode("div", "check-row");
        const id = makeNode("span", "check-id", check.id + " · " + check.step);
        const text = makeNode("div", "check-label");
        text.append(makeNode("div", "", check.label || check.id));
        if (check.detail) text.append(makeNode("p", "check-detail", check.detail));
        const [kind, symbol] = statusText(check.ok);
        row.append(id, text, makeNode("span", "check-status " + kind, symbol));
        list.append(row);
      }
      details.append(list);
      wrap.append(details);
    }
    return wrap;
  }

  function renderResult(data) {
    state.result = data;
    elements.empty.classList.add("is-hidden");
    elements.errors.classList.add("is-hidden");
    elements.results.classList.remove("is-hidden");
    elements.outputState.classList.remove("is-busy");
    elements.outputState.classList.add("is-done");
    elements.outputState.lastChild.textContent = " گزارش آماده است";
    renderSummary(data.summary || {}, data.mode);

    elements.resultItems.replaceChildren();
    if (data.mode === "sources") {
      for (const entry of data.results || []) {
        elements.resultItems.append(renderSourceResult(entry));
      }
      const errorList = renderErrors(data.errors);
      if (errorList) elements.resultItems.append(errorList);
      elements.resultsTitle.textContent = "نتیجهٔ اعتبارسنجی منابع";
    } else {
      elements.resultItems.append(renderDraftSections(data.sections, data.checks));
      elements.resultsTitle.textContent = "نتیجهٔ بررسی پیش‌نویس";
    }
    elements.markdown.textContent = data.table_markdown || "خروجی متنی در دسترس نیست.";
    elements.disclaimer.textContent = data.disclaimer || "";
    elements.copy.disabled = !data.table_markdown;
    elements.download.disabled = false;
  }


  async function discoverSources() {
    const button = $("#discover-submit");
    const results = $("#discovery-results");
    const keyword = $("#discovery-keyword").value.trim();
    if (!keyword) {
      results.classList.remove("is-hidden");
      results.textContent = "عبارت جست‌وجو را وارد کن.";
      return;
    }
    button.disabled = true;
    button.querySelector("span").textContent = "در حال جست‌وجو…";
    results.classList.remove("is-hidden");
    results.replaceChildren();
    results.append(makeNode("p", "", "در حال دریافت نتایج واقعی از Crossref…"));
    try {
      const response = await fetch("/api", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        cache: "no-store",
        body: JSON.stringify({
          action: "discover_sources",
          keyword,
          category: $("#source-category").value,
          area: $("#source-area").value.trim(),
          subject: $("#source-area").value.trim(),
          limit: 4,
        }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || ("خطای جست‌وجو: HTTP " + response.status));
      }
      results.replaceChildren();
      const candidates = Array.isArray(data.candidates) ? data.candidates : [];
      if (!candidates.length) {
        results.append(makeNode("p", "", "نتیجه‌ای با DOI معتبر در پاسخ Crossref پیدا نشد."));
        return;
      }
      results.append(makeNode("p", "discovery-footnote", candidates.length + " نتیجه از Crossref دریافت شد. موارد دلخواه را انتخاب کن."));
      candidates.forEach((candidate, index) => {
        const label = makeNode("label", "discovery-result");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = String(index);
        checkbox.checked = true;
        checkbox.setAttribute("aria-label", "انتخاب " + (candidate.title || candidate.doi));
        const copy = makeNode("div", "");
        copy.append(
          makeNode("h4", "", candidate.title || "بدون عنوان"),
          makeNode("p", "", [
            (candidate.authors || []).slice(0, 3).join(", "),
            candidate.year || "سال نامشخص",
            candidate.venue || candidate.publisher || "",
          ].filter(Boolean).join(" · "))
        );
        const link = makeNode("a", "", candidate.doi);
        link.href = candidate.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        const meta = makeNode("p", "");
        meta.append(link);
        copy.append(meta);
        label.append(checkbox, copy);
        results.append(label);
      });
      const actions = makeNode("div", "discovery-actions");
      const count = makeNode("small", "", "حداکثر ۴ منبع؛ تأیید نهایی با ۱۱ دروازه انجام می‌شود.");
      const use = makeNode("button", "secondary-button", "افزودن انتخاب‌ها به طرح شواهد");
      use.type = "button";
      use.addEventListener("click", () => {
        const selected = Array.from(results.querySelectorAll(".discovery-result input:checked"))
          .map(input => data.plan[Number(input.value)])
          .filter(Boolean);
        if (!selected.length) {
          results.append(makeNode("p", "discovery-error", "حداقل یک نتیجه انتخاب کن."));
          return;
        }
        $("#source-plan").value = JSON.stringify(selected, null, 2);
        $("#source-dois").value = selected.map(item => item.doi).join("\n");
        results.append(makeNode("p", "discovery-footnote", selected.length + " منبع به طرح شواهد اضافه شد. حالا «اجرای اعتبارسنجی» را بزن."));
      });
      actions.append(count, use);
      results.append(actions);
    } catch (error) {
      results.replaceChildren(makeNode("p", "discovery-error", error?.message || "جست‌وجو ناموفق بود."));
    } finally {
      button.disabled = false;
      button.querySelector("span").textContent = "جست‌وجوی منابع در Crossref";
    }
  }

  function parseJsonField(value, label) {
    if (!value.trim()) return null;
    try {
      return JSON.parse(value);
    } catch {
      throw new Error("JSON بخش «" + label + "» معتبر نیست.");
    }
  }

  function sourcePayload() {
    const planText = $("#source-plan").value.trim();
    const language = document.documentElement.lang || "fa";
    let payload;
    if (planText) {
      const parsed = parseJsonField(planText, "طرح کامل شواهد");
      payload = Array.isArray(parsed) ? { entries: parsed } : parsed;
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("طرح کامل باید آرایه یا شیء JSON باشد.");
      }
    } else {
      const dois = $("#source-dois").value.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
      if (!dois.length) throw new Error("حداقل یک DOI وارد کن.");
      if (dois.length > 4) throw new Error("در هر اجرا حداکثر ۴ DOI مجاز است.");
      const keyword = $("#source-keyword").value.trim();
      if (!keyword) throw new Error("فرمول کلیدواژه الزامی است.");
      const area = $("#source-area").value.trim();
      payload = {
        entries: dois.map(doi => ({
          doi,
          category: $("#source-category").value,
          keyword,
          area,
          subject: area,
        })),
        cutoff: $("#source-cutoff").value,
        language,
      };
    }
    payload.action = "verify_sources";
    payload.language = "fa";
    if (!payload.cutoff) payload.cutoff = $("#source-cutoff").value;
    return payload;
  }

  function draftPayload() {
    const draft = $("#draft-text").value;
    if (!draft.trim()) throw new Error("متن پیش‌نویس را وارد کن.");
    const manual = parseJsonField($("#draft-manual").value, "قضاوت دستی");
    if (manual !== null && (!manual || typeof manual !== "object" || Array.isArray(manual))) {
      throw new Error("قضاوت دستی باید یک شیء JSON باشد.");
    }
    return {
      action: "check_draft",
      draft,
      language: $("#draft-language").value,
      manual,
    };
  }

  async function run(payload, key) {
    setBusy(true);
    elements.errors.classList.add("is-hidden");
    elements.empty.classList.add("is-hidden");
    elements.results.classList.add("is-hidden");
    try {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 85_000);
      let response;
      try {
        response = await fetch("/api", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(key ? { Authorization: "Bearer " + key } : {}),
          },
          body: JSON.stringify(payload),
          credentials: "same-origin",
          cache: "no-store",
          signal: controller.signal,
        });
      } finally {
        window.clearTimeout(timeout);
      }
      const body = await response.json().catch(() => null);
      if (!response.ok || !body?.ok) {
        throw new Error(body?.error || ("سرور با وضعیت HTTP " + response.status + " پاسخ داد."));
      }
      renderResult(body);
    } catch (error) {
      const message = error?.name === "AbortError"
        ? "زمان پردازش تمام شد. تعداد منابع را کمتر کن یا دوباره تلاش کن."
        : (error?.message || "اتصال به API برقرار نشد.");
      showError(message);
    } finally {
      setBusy(false);
    }
  }

  async function checkHealth() {
    try {
      const response = await fetch("/api", {
        method: "GET",
        cache: "no-store",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok || !data?.ok) throw new Error("API health check failed");
      setOnline(true, "موتور API متصل است");
    } catch {
      setOnline(false, "API پس از استقرار فعال می‌شود");
    }
  }

  function setMode(mode) {
    if (state.busy || !["sources", "draft"].includes(mode)) return;
    state.mode = mode;
    $$(".mode-tab").forEach(button => {
      const active = button.dataset.mode === mode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", String(active));
    });
    elements.sourceForm.classList.toggle("is-hidden", mode !== "sources");
    elements.draftForm.classList.toggle("is-hidden", mode !== "draft");
    elements.inputTitle.textContent = mode === "sources" ? "رکوردهای منبع" : "متن پیش‌نویس";
    elements.inputStep.textContent = mode === "sources" ? "01 / 02" : "02 / 02";
    if (elements.results.classList.contains("is-hidden")) {
      showEmpty();
    } else {
      elements.results.classList.add("is-hidden");
      showEmpty();
    }
  }

  function getKey() {
    return state.mode === "sources"
      ? $("#access-key").value.trim()
      : $("#draft-access-key").value.trim();
  }

  $("#discover-submit").addEventListener("click", discoverSources);

  elements.sourceForm.addEventListener("submit", event => {
    event.preventDefault();
    if (state.busy) return;
    try {
      run(sourcePayload(), getKey());
    } catch (error) {
      showError(error.message);
    }
  });

  elements.draftForm.addEventListener("submit", event => {
    event.preventDefault();
    if (state.busy) return;
    try {
      run(draftPayload(), getKey());
    } catch (error) {
      showError(error.message);
    }
  });

  $$(".mode-tab").forEach(button => {
    button.addEventListener("click", () => setMode(button.dataset.mode));
  });

  $("#dismiss-error").addEventListener("click", showEmpty);

  elements.copy.addEventListener("click", async () => {
    if (!state.result?.table_markdown) return;
    const text = state.result.table_markdown;
    try {
      await navigator.clipboard.writeText(text);
      elements.copy.textContent = "کپی شد";
      window.setTimeout(() => { elements.copy.textContent = "کپی گزارش"; }, 1600);
    } catch {
      const helper = document.createElement("textarea");
      helper.value = text;
      helper.setAttribute("readonly", "");
      helper.className = "clipboard-fallback";
      document.body.append(helper);
      helper.select();
      const copied = document.execCommand("copy");
      helper.remove();
      elements.copy.textContent = copied ? "کپی شد" : "کپی نشد";
      window.setTimeout(() => { elements.copy.textContent = "کپی گزارش"; }, 1600);
    }
  });

  elements.download.addEventListener("click", () => {
    if (!state.result) return;
    const file = new Blob([JSON.stringify(state.result, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(file);
    const anchor = makeNode("a", "");
    anchor.href = url;
    anchor.download = "article-finder-report.json";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  });

  checkHealth();
})();
