async function load() {
  const res = await fetch(`/api/status?t=${Date.now()}`, { cache: "no-store" });
  const data = await res.json();

  const updated = document.getElementById("updated");
  updated.textContent = `Updated: ${data.generated_at} (window: ${data.window_days}d)`;

  const list = document.getElementById("list");
  list.innerHTML = "";

  for (const s of data.sites) {
    const card = document.createElement("article");
    card.className = `site-card state-${(s.state || "UNKNOWN").toLowerCase()}`;

    // ---------- Screenshot / hero ----------
    const hero = document.createElement("div");
    hero.className = "card-hero";

    const heroMedia = document.createElement("div");
    heroMedia.className = "card-hero-media";

    const badge = document.createElement("span");
    badge.className = `status-badge ${s.state}`;
    badge.textContent = s.state || "UNKNOWN";
    heroMedia.appendChild(badge);

    if (s.last_event_screenshot_url) {
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
      img.addEventListener("click", () => {
        openLightbox(
          `${screenshotUrl}?t=${Date.now()}`,
          `${s.site_name} screenshot`
        );
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

    // ---------- Main content ----------
    const body = document.createElement("div");
    body.className = "card-body";

    const title = document.createElement("div");
    title.className = "card-title";
    title.textContent = s.site_name || "Unnamed site";
    body.appendChild(title);

    const url = document.createElement("div");
    url.className = "card-url";
    url.title = s.url || "";
    url.textContent = s.url || "-";
    body.appendChild(url);

    const consoleRow = document.createElement("div");
    consoleRow.className = "card-console-row";

    const consoleStatus = document.createElement("span");
    consoleStatus.className = `mini-console-badge ${s.console_status || "CLEAN"}`;
    consoleStatus.textContent = s.console_status || "CLEAN";

    const consoleText = document.createElement("span");
    consoleText.className = "card-console-text";
    const issueCount = s.console_issue_count ?? 0;
    const ignoredCount = s.console_ignored_count ?? 0;
    consoleText.textContent = `Issues: ${issueCount}${ignoredCount ? ` • Ignored: ${ignoredCount}` : ""}`;

    consoleRow.appendChild(consoleStatus);
    consoleRow.appendChild(consoleText);
    body.appendChild(consoleRow);

    // Optional compact meta
    const meta = document.createElement("div");
    meta.className = "card-meta";
    meta.textContent = `Endpoint ${s.endpoint_id} • ${s.last_checked || "-"}${s.uptime_7d_percent != null ? ` • ${s.uptime_7d_percent}% uptime` : ""}`;
    body.appendChild(meta);

    // Tiny timeline stripe
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

    // ---------- Details ----------
    const hasRecentIssues =
      Array.isArray(s.console_issues_recent) && s.console_issues_recent.length > 0;
    const hasDaily = !!s.daily_screenshot_url;
    const hasEvent = !!s.last_event_screenshot_url;

    if (hasRecentIssues || hasDaily || hasEvent) {
      const details = document.createElement("details");
      details.className = "card-details";

      const summary = document.createElement("summary");
      summary.className = "card-details-summary";
      summary.textContent = "Details";
      details.appendChild(summary);

      const detailsInner = document.createElement("div");
      detailsInner.className = "card-details-inner";

      if (hasRecentIssues) {
        const issuesBlock = document.createElement("div");
        issuesBlock.className = "details-block";

        const issuesTitle = document.createElement("div");
        issuesTitle.className = "details-title";
        issuesTitle.textContent = "Recent console issues";
        issuesBlock.appendChild(issuesTitle);

        const issuesList = document.createElement("div");
        issuesList.className = "details-issues-list";

        for (const issue of s.console_issues_recent) {
          const item = document.createElement("div");
          item.className = "details-issue-item";

          const level = issue.level || "-";
          const ts = issue.ts || "-";
          const msg = issue.message || "-";
          const src = issue.source_url || "";

          item.innerHTML = `
            <div class="details-issue-top">
              <span class="details-issue-level">${level}</span>
              <span class="details-issue-ts">${ts}</span>
            </div>
            <div class="details-issue-message">${msg}</div>
            ${src ? `<div class="details-issue-source">${src}</div>` : ""}
          `;

          issuesList.appendChild(item);
        }

        issuesBlock.appendChild(issuesList);
        detailsInner.appendChild(issuesBlock);
      }

      if (hasDaily || hasEvent) {
        const shotsBlock = document.createElement("div");
        shotsBlock.className = "details-block";

        const shotsTitle = document.createElement("div");
        shotsTitle.className = "details-title";
        shotsTitle.textContent = "Screenshots";
        shotsBlock.appendChild(shotsTitle);

        const shotsGrid = document.createElement("div");
        shotsGrid.className = "details-shots-grid";

        if (hasDaily) {
          shotsGrid.appendChild(
            makeDetailShotCard(
              "Daily",
              s.daily_screenshot_url,
              s.site_name,
              s.endpoint_id
            )
          );
        }

        if (hasEvent) {
          shotsGrid.appendChild(
            makeDetailShotCard(
              s.last_state_change_at
                ? `Last state change • ${s.last_state_change_at}`
                : "Last state change",
              s.last_event_screenshot_url,
              s.site_name,
              s.endpoint_id
            )
          );
        }

        shotsBlock.appendChild(shotsGrid);
        detailsInner.appendChild(shotsBlock);
      }

      details.appendChild(detailsInner);
      body.appendChild(details);
    }

    card.appendChild(body);
    list.appendChild(card);
  }
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
setInterval(load, 1_800_000);