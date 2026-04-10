const CHANGED_PILL_WINDOW_HOURS = 24;
const REFRESH_INTERVAL_MS = 1_800_000;

const FILTER_ALL = "all";
const FILTER_DOWN_24H = "down_24h";
const FILTER_ISSUES = "issues";

let snapshotData = { generated_at: null, sites: [] };
let currentFilter = FILTER_ALL;

async function load() {
  const res = await fetch(`/api/status?t=${Date.now()}`, { cache: "no-store" });
  const data = await res.json();

  snapshotData = data || { generated_at: null, sites: [] };
  render();
}

function render() {
  renderHeader();
  renderFilterBar();
  renderList();
}

function renderHeader() {
  const updated = document.getElementById("updated");
  updated.textContent = `Updated: ${snapshotData.generated_at || "-"}`;
}

function ensureFilterBar() {
  let bar = document.getElementById("filter-bar");
  if (bar) return bar;

  const list = document.getElementById("list");
  bar = document.createElement("div");
  bar.id = "filter-bar";
  bar.style.display = "flex";
  bar.style.gap = "10px";
  bar.style.flexWrap = "wrap";
  bar.style.margin = "0 0 18px 0";

  list.parentNode.insertBefore(bar, list);
  return bar;
}

function renderFilterBar() {
  const bar = ensureFilterBar();
  bar.innerHTML = "";

  const sites = Array.isArray(snapshotData.sites) ? snapshotData.sites : [];
  const down24Count = sites.filter((s) => !!s.was_down_last_24h).length;
  const issuesCount = sites.filter((s) => getIssueCountLastPing(s) > 0).length;

  const buttons = [
    {
      key: FILTER_ALL,
      label: `All (${sites.length})`,
    },
    {
      key: FILTER_DOWN_24H,
      label: `Down in last 24 hrs (${down24Count})`,
    },
    {
      key: FILTER_ISSUES,
      label: `Websites with issues (console issues) (${issuesCount})`,
    },
  ];

  for (const item of buttons) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = item.label;
    btn.style.border = "1px solid #dbe2ea";
    btn.style.background = item.key === currentFilter ? "#111827" : "#ffffff";
    btn.style.color = item.key === currentFilter ? "#ffffff" : "#1f2937";
    btn.style.padding = "8px 12px";
    btn.style.borderRadius = "999px";
    btn.style.cursor = "pointer";
    btn.style.fontSize = "13px";
    btn.style.fontWeight = "700";

    btn.addEventListener("click", () => {
      currentFilter = item.key;
      render();
    });

    bar.appendChild(btn);
  }
}

function renderList() {
  const list = document.getElementById("list");
  list.innerHTML = "";

  const filteredSites = getFilteredSites(Array.isArray(snapshotData.sites) ? snapshotData.sites : []);

  for (const site of filteredSites) {
    list.appendChild(buildSiteCard(site));
  }
}

function getFilteredSites(sites) {
  switch (currentFilter) {
    case FILTER_DOWN_24H:
      return sites.filter((s) => !!s.was_down_last_24h);
    case FILTER_ISSUES:
      return sites.filter((s) => getIssueCountLastPing(s) > 0);
    case FILTER_ALL:
    default:
      return sites;
  }
}

function buildSiteCard(s) {
  const card = document.createElement("article");
  card.className = `site-card state-${(s.state || "UNKNOWN").toLowerCase()}`;

  const hero = document.createElement("div");
  hero.className = "card-hero";

  const heroMedia = document.createElement("div");
  heroMedia.className = "card-hero-media";

  const badge = document.createElement("span");
  badge.className = `status-badge ${s.state}`;
  badge.textContent = s.state || "UNKNOWN";
  heroMedia.appendChild(badge);

  const showChangedPill = isRecentStatusChange(s.last_state_change_at_utc);
  if (showChangedPill) {
    const changed = document.createElement("span");
    changed.className = "change-pill";
    changed.textContent = "Changed";
    heroMedia.appendChild(changed);
  }

  const screenshotUrl = s.daily_screenshot_url || s.last_event_screenshot_url || "";
  if (screenshotUrl) {
    const img = document.createElement("img");
    img.className = "hero-shot";
    img.src = `${screenshotUrl}?t=${Date.now()}`;
    img.alt = `${s.site_name} screenshot`;
    img.loading = "lazy";
    img.style.objectPosition = "top center";
    img.addEventListener("click", () => {
      openLightbox(`${screenshotUrl}?t=${Date.now()}`, `${s.site_name} screenshot`);
    });
    heroMedia.appendChild(img);
  } else {
    const placeholder = document.createElement("div");
    placeholder.className = "hero-placeholder";
    placeholder.textContent = "No screenshot";
    heroMedia.appendChild(placeholder);
  }

  hero.appendChild(heroMedia);
  card.appendChild(hero);

  const body = document.createElement("div");
  body.className = "card-body";

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = s.site_name || "Unnamed site";
  body.appendChild(title);

  const urlLink = document.createElement("a");
  urlLink.className = "card-url";
  urlLink.href = s.url || "#";
  urlLink.target = "_blank";
  urlLink.rel = "noopener noreferrer";
  urlLink.title = s.url || "";
  urlLink.textContent = s.url || "-";
  body.appendChild(urlLink);

  const summaryRow = document.createElement("div");
  summaryRow.className = "card-console-row";

  const consoleStatus = document.createElement("span");
  consoleStatus.className = `mini-console-badge ${s.console_status || "CLEAN"}`;
  consoleStatus.textContent = s.console_status || "CLEAN";

  const consoleText = document.createElement("span");
  consoleText.className = "card-console-text";
  const issueCount = getIssueCountLastPing(s);
  const ignoredCount = getIgnoredCountLastPing(s);
  consoleText.textContent = `Issues: ${issueCount}${ignoredCount ? ` • Ignored: ${ignoredCount}` : ""}`;

  const statusCode = document.createElement("span");
  statusCode.className = "card-status-code";
  statusCode.textContent = `Code: ${formatStatusCode(s.status_code)}`;

  summaryRow.appendChild(consoleStatus);
  summaryRow.appendChild(consoleText);
  summaryRow.appendChild(statusCode);
  body.appendChild(summaryRow);

  const meta = document.createElement("div");
  meta.className = "card-meta";
  meta.textContent =
    `Endpoint ${s.endpoint_id}` +
    ` • Last checked: ${s.last_checked || "-"}` +
    (s.uptime_7d_percent != null ? ` • ${s.uptime_7d_percent}% uptime` : "");
  body.appendChild(meta);

  const trackingMeta = document.createElement("div");
  trackingMeta.className = "card-meta";
  trackingMeta.textContent = `Tracking since: ${s.tracking_since || "-"}`;
  body.appendChild(trackingMeta);

  if (Array.isArray(s.timeline_7d) && s.timeline_7d.length > 0) {
    const stripe = document.createElement("div");
    stripe.className = "mini-stripe";

    const totalSeconds = 7 * 24 * 3600;
    for (const seg of s.timeline_7d) {
      const segDiv = document.createElement("div");
      const w = Math.max(0, Math.min(1, (seg.duration_seconds || 0) / totalSeconds));
      segDiv.className = `mini-seg ${seg.state}`;
      segDiv.style.width = `${w * 100}%`;
      stripe.appendChild(segDiv);
    }

    body.appendChild(stripe);
  }

  if (hasDetails(s)) {
    const detailsBtn = document.createElement("button");
    detailsBtn.type = "button";
    detailsBtn.className = "card-details-summary";
    detailsBtn.style.marginTop = "12px";
    detailsBtn.textContent = "View details";
    detailsBtn.addEventListener("click", () => openDetailsModal(s));
    body.appendChild(detailsBtn);
  }

  card.appendChild(body);
  return card;
}

function getIssueCountLastPing(site) {
  return Number(site.console_issue_count_last_ping ?? 0);
}

function getIgnoredCountLastPing(site) {
  return Number(site.console_ignored_count_last_ping ?? 0);
}

function getIssuesLastPing(site) {
  return Array.isArray(site.console_issues_last_ping) ? site.console_issues_last_ping : [];
}

function hasStatusChangeRecord(site) {
  if (site.has_status_change_record === true) {
    return true;
  }

  return (
    !!site.change_from_state ||
    !!site.change_to_state ||
    site.change_from_status_code !== "" && site.change_from_status_code !== undefined && site.change_from_status_code !== null ||
    site.change_to_status_code !== "" && site.change_to_status_code !== undefined && site.change_to_status_code !== null ||
    !!site.last_state_change_at ||
    !!site.last_event_screenshot_url
  );
}

function hasDetails(site) {
  return (
    hasStatusChangeRecord(site) ||
    !!site.daily_screenshot_url ||
    !!site.last_event_screenshot_url ||
    getIssuesLastPing(site).length > 0
  );
}

function formatStatusCode(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function isRecentStatusChange(isoString) {
  if (!isoString) {
    return false;
  }

  const changedAt = new Date(isoString);
  if (Number.isNaN(changedAt.getTime())) {
    return false;
  }

  const ageMs = Date.now() - changedAt.getTime();
  const maxAgeMs = CHANGED_PILL_WINDOW_HOURS * 60 * 60 * 1000;

  return ageMs >= 0 && ageMs <= maxAgeMs;
}

function ensureDetailsModal() {
  let overlay = document.getElementById("details-modal");
  if (overlay) return overlay;

  overlay = document.createElement("div");
  overlay.id = "details-modal";
  overlay.setAttribute("aria-hidden", "true");
  overlay.style.position = "fixed";
  overlay.style.inset = "0";
  overlay.style.display = "none";
  overlay.style.zIndex = "10000";

  const backdrop = document.createElement("div");
  backdrop.style.position = "absolute";
  backdrop.style.inset = "0";
  backdrop.style.background = "rgba(2, 6, 23, 0.78)";

  const content = document.createElement("div");
  content.style.position = "relative";
  content.style.zIndex = "1";
  content.style.width = "min(94vw, 960px)";
  content.style.maxHeight = "88vh";
  content.style.margin = "6vh auto";
  content.style.background = "#ffffff";
  content.style.borderRadius = "16px";
  content.style.boxShadow = "0 20px 60px rgba(0, 0, 0, 0.25)";
  content.style.overflow = "hidden";
  content.style.display = "flex";
  content.style.flexDirection = "column";

  const header = document.createElement("div");
  header.style.display = "flex";
  header.style.justifyContent = "space-between";
  header.style.alignItems = "center";
  header.style.gap = "12px";
  header.style.padding = "16px 18px";
  header.style.borderBottom = "1px solid #e5e7eb";

  const title = document.createElement("div");
  title.id = "details-modal-title";
  title.style.fontSize = "20px";
  title.style.fontWeight = "700";
  title.style.lineHeight = "1.2";

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.textContent = "×";
  closeBtn.style.border = "none";
  closeBtn.style.background = "#f3f4f6";
  closeBtn.style.width = "36px";
  closeBtn.style.height = "36px";
  closeBtn.style.borderRadius = "999px";
  closeBtn.style.cursor = "pointer";
  closeBtn.style.fontSize = "24px";
  closeBtn.style.lineHeight = "1";

  const body = document.createElement("div");
  body.id = "details-modal-body";
  body.style.padding = "18px";
  body.style.overflow = "auto";
  body.style.display = "flex";
  body.style.flexDirection = "column";
  body.style.gap = "18px";

  header.appendChild(title);
  header.appendChild(closeBtn);
  content.appendChild(header);
  content.appendChild(body);
  overlay.appendChild(backdrop);
  overlay.appendChild(content);
  document.body.appendChild(overlay);

  backdrop.addEventListener("click", closeDetailsModal);
  closeBtn.addEventListener("click", closeDetailsModal);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDetailsModal();
    }
  });

  return overlay;
}

function openDetailsModal(site) {
  const overlay = ensureDetailsModal();
  const title = document.getElementById("details-modal-title");
  const body = document.getElementById("details-modal-body");

  title.textContent = site.site_name || "Site details";
  body.innerHTML = "";

  body.appendChild(makeDetailsSummarySection(site));

  if (hasStatusChangeRecord(site)) {
    body.appendChild(makeStatusChangeSection(site));
  }

  body.appendChild(makeIssuesSection(site));

  if (site.daily_screenshot_url || site.last_event_screenshot_url) {
    body.appendChild(makeScreenshotsSection(site));
  }

  overlay.style.display = "block";
  overlay.setAttribute("aria-hidden", "false");
}

function closeDetailsModal() {
  const overlay = document.getElementById("details-modal");
  if (!overlay) return;
  overlay.style.display = "none";
  overlay.setAttribute("aria-hidden", "true");
}

function makeSection(titleText) {
  const section = document.createElement("section");

  const title = document.createElement("div");
  title.className = "details-title";
  title.textContent = titleText;
  title.style.marginBottom = "10px";

  section.appendChild(title);
  return section;
}

function makeDetailsSummarySection(site) {
  const section = makeSection("Summary");

  const rows = [
    ["URL", site.url || "-"],
    ["State", site.state || "-"],
    ["Status code", formatStatusCode(site.status_code)],
    ["Last checked", site.last_checked || "-"],
    ["Tracking since", site.tracking_since || "-"],
    ["Console status", site.console_status || "CLEAN"],
    ["Issues in last ping", String(getIssueCountLastPing(site))],
    ["Ignored in last ping", String(getIgnoredCountLastPing(site))],
  ];

  if (site.console_last_ping_at) {
    rows.push(["Issue ping", site.console_last_ping_at]);
  }

  const card = document.createElement("div");
  card.className = "details-change-card";

  for (const [labelText, valueText] of rows) {
    const row = document.createElement("div");
    row.className = "details-change-row";

    const label = document.createElement("span");
    label.className = "details-change-label";
    label.textContent = labelText;

    const value = document.createElement("span");
    value.className = "details-change-value";
    value.textContent = valueText;

    row.appendChild(label);
    row.appendChild(value);
    card.appendChild(row);
  }

  section.appendChild(card);
  return section;
}

function makeStatusChangeSection(site) {
  const section = makeSection("Status change");

  const card = document.createElement("div");
  card.className = "details-change-card";

  const rows = [
    ["State", `${site.change_from_state || "-"} → ${site.change_to_state || "-"}`],
    [
      "Status code",
      `${formatStatusCode(site.change_from_status_code)} → ${formatStatusCode(site.change_to_status_code)}`,
    ],
    ["Recorded", site.last_state_change_at || "-"],
  ];

  for (const [labelText, valueText] of rows) {
    const row = document.createElement("div");
    row.className = "details-change-row";

    const label = document.createElement("span");
    label.className = "details-change-label";
    label.textContent = labelText;

    const value = document.createElement("span");
    value.className = "details-change-value";
    value.textContent = valueText;

    row.appendChild(label);
    row.appendChild(value);
    card.appendChild(row);
  }

  section.appendChild(card);
  return section;
}

function makeIssuesSection(site) {
  const issues = getIssuesLastPing(site);
  const titleText = site.console_last_ping_at
    ? `Last ping issues • ${site.console_last_ping_at}`
    : "Last ping issues";

  const section = makeSection(titleText);

  if (issues.length === 0) {
    const empty = document.createElement("div");
    empty.className = "details-issue-item";

    const msg = document.createElement("div");
    msg.className = "details-issue-message";
    msg.textContent = "No issues for the last ping.";

    empty.appendChild(msg);
    section.appendChild(empty);
    return section;
  }

  const list = document.createElement("div");
  list.className = "details-issues-list";

  for (const issue of issues) {
    list.appendChild(makeIssueItem(issue));
  }

  section.appendChild(list);
  return section;
}

function makeIssueItem(issue) {
  const item = document.createElement("div");
  item.className = "details-issue-item";

  const top = document.createElement("div");
  top.className = "details-issue-top";

  const level = document.createElement("span");
  level.className = "details-issue-level";
  level.textContent = issue.level || "-";

  const ts = document.createElement("span");
  ts.className = "details-issue-ts";
  ts.textContent = issue.ts || "-";

  top.appendChild(level);
  top.appendChild(ts);

  const message = document.createElement("div");
  message.className = "details-issue-message";
  message.textContent = issue.message || "-";

  item.appendChild(top);
  item.appendChild(message);

  if (issue.source_url) {
    const src = document.createElement("div");
    src.className = "details-issue-source";
    src.textContent = issue.source_url;
    item.appendChild(src);
  }

  return item;
}

function makeScreenshotsSection(site) {
  const section = makeSection("Screenshots");

  const grid = document.createElement("div");
  grid.className = "details-shots-grid";

  if (site.daily_screenshot_url) {
    grid.appendChild(
      makeDetailShotCard(
        "Daily",
        site.daily_screenshot_url,
        site.site_name,
        site.endpoint_id
      )
    );
  }

  if (site.last_event_screenshot_url) {
    grid.appendChild(
      makeDetailShotCard(
        site.last_state_change_at
          ? `Last state change • ${site.last_state_change_at}`
          : "Last state change",
        site.last_event_screenshot_url,
        site.site_name,
        site.endpoint_id
      )
    );
  }

  section.appendChild(grid);
  return section;
}

function makeDetailShotCard(label, url, siteName, endpointId) {
  const wrap = document.createElement("div");
  wrap.className = "details-shot-card";

  const labelDiv = document.createElement("div");
  labelDiv.className = "details-shot-label";
  labelDiv.textContent = label;

  const img = document.createElement("img");
  img.className = "details-shot-thumb";
  img.src = `${url}?t=${Date.now()}`;
  img.alt = `${label} screenshot for ${siteName} endpoint ${endpointId}`;
  img.loading = "lazy";
  img.style.objectPosition = "top center";
  img.addEventListener("click", () => {
    openLightbox(img.src, img.alt);
  });

  wrap.appendChild(labelDiv);
  wrap.appendChild(img);

  return wrap;
}

function openLightbox(src, alt) {
  let overlay = document.getElementById("lightbox");

  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "lightbox";
    overlay.className = "lightbox";
    overlay.innerHTML = `
      <div class="lightbox-backdrop"></div>
      <div class="lightbox-content">
        <button class="lightbox-close" type="button">×</button>
        <img class="lightbox-image" alt="">
      </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelector(".lightbox-backdrop").addEventListener("click", closeLightbox);
    overlay.querySelector(".lightbox-close").addEventListener("click", closeLightbox);

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        closeLightbox();
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeLightbox();
      }
    });
  }

  const img = overlay.querySelector(".lightbox-image");
  img.src = src;
  img.alt = alt || "Screenshot";

  overlay.classList.add("open");
}

function closeLightbox() {
  const overlay = document.getElementById("lightbox");
  if (!overlay) return;
  overlay.classList.remove("open");
}

load();
setInterval(load, REFRESH_INTERVAL_MS);