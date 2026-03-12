async function load() {
  const res = await fetch(`/api/status?t=${Date.now()}`, { cache: "no-store" });
  const data = await res.json();

  document.getElementById("updated").textContent =
    `Updated: ${data.generated_at} (window: ${data.window_days}d)`;

  const list = document.getElementById("list");
  list.innerHTML = "";

  for (const s of data.sites) {
    const row = document.createElement("div");
    row.className = "row";

    const top = document.createElement("div");
    top.className = "topline";

    const left = document.createElement("div");
    left.innerHTML = `
      <div class="name">${s.site_name} • ${s.url}</div>
      <div class="meta">
        endpoint ${s.endpoint_id} • last: ${s.last_checked || "-"} • uptime: ${s.uptime_7d_percent ?? "-"}%
      </div>
    `;

    const right = document.createElement("div");
    right.innerHTML = `<span class="badge ${s.state}">${s.state}</span>`;

    top.appendChild(left);
    top.appendChild(right);
    row.appendChild(top);

    // Existing 7-day stripe
    if (Array.isArray(s.timeline_7d) && s.timeline_7d.length > 0) {
      const stripe = document.createElement("div");
      stripe.className = "stripe";

      const totalSeconds = 7 * 24 * 3600;
      for (const seg of s.timeline_7d) {
        const w = Math.max(
          0,
          Math.min(1, (seg.duration_seconds || 0) / totalSeconds)
        );
        const div = document.createElement("div");
        div.className = `seg ${seg.state}`;
        div.style.width = `${w * 100}%`;
        stripe.appendChild(div);
      }

      row.appendChild(stripe);
    }

    // Console summary
    const consoleWrap = document.createElement("div");
    consoleWrap.className = "console-wrap";

    const consoleStatus = s.console_status || "CLEAN";
    const issueCount = s.console_issue_count ?? 0;
    const ignoredCount = s.console_ignored_count ?? 0;

    const consoleHeader = document.createElement("div");
    consoleHeader.className = "console-header";
    consoleHeader.innerHTML = `
      <span class="console-badge ${consoleStatus}">${consoleStatus}</span>
      <span class="console-meta">
        console issues: ${issueCount} • ignored: ${ignoredCount}
      </span>
    `;
    consoleWrap.appendChild(consoleHeader);

    if (Array.isArray(s.console_issues_recent) && s.console_issues_recent.length > 0) {
      const details = document.createElement("details");
      details.className = "console-details";

      const summary = document.createElement("summary");
      summary.textContent = "Recent console issues";
      details.appendChild(summary);

      const issues = document.createElement("div");
      issues.className = "console-issues";

      for (const issue of s.console_issues_recent) {
        const item = document.createElement("div");
        item.className = "console-issue";

        const ts = issue.ts || "-";
        const level = issue.level || "-";
        const msg = issue.message || "-";
        const src = issue.source_url || "";

        item.innerHTML = `
          <div class="console-issue-top">
            <span class="console-level">${level}</span>
            <span class="console-ts">${ts}</span>
          </div>
          <div class="console-message">${msg}</div>
          ${src ? `<div class="console-source">${src}</div>` : ""}
        `;

        issues.appendChild(item);
      }

      details.appendChild(issues);
      consoleWrap.appendChild(details);
    }

    row.appendChild(consoleWrap);

    // Screenshot section
    
    const hasDaily = !!s.daily_screenshot_url;
    const hasEvent = !!s.last_event_screenshot_url;

    if (hasDaily || hasEvent) {
      const shotsWrap = document.createElement("div");
      shotsWrap.className = "shots-wrap";

      const details = document.createElement("details");
      details.className = "shots-details";

      const summary = document.createElement("summary");
      summary.className = "shots-summary";

      const count = (hasDaily ? 1 : 0) + (hasEvent ? 1 : 0);
      summary.textContent = `Screenshots (${count})`;
      details.appendChild(summary);

      const gallery = document.createElement("div");
      gallery.className = "shots-gallery";

      if (hasDaily) {
        gallery.appendChild(
          makeShotCard(
            "Daily",
            s.daily_screenshot_url,
            s.site_name,
            s.endpoint_id
          )
        );
      }

      if (hasEvent) {
        gallery.appendChild(
          makeShotCard(
            "Last state change",
            s.last_event_screenshot_url,
            s.site_name,
            s.endpoint_id,
            s.last_state_change_at || ""
          )
        );
      }

      details.appendChild(gallery);
      shotsWrap.appendChild(details);
      row.appendChild(shotsWrap);
    }
    list.appendChild(row);
  }
}

function makeShotCard(label, url, siteName, endpointId, extra = "") {
  const wrap = document.createElement("div");
  wrap.className = "shot-card";

  const labelDiv = document.createElement("div");
  labelDiv.className = "shot-label";
  labelDiv.textContent = extra ? `${label} • ${extra}` : label;

  const img = document.createElement("img");
  img.className = "shot-thumb";
  img.src = `${url}?t=${Date.now()}`;
  img.alt = `${label} screenshot for ${siteName} endpoint ${endpointId}`;
  img.loading = "lazy";

  img.addEventListener("click", () => openLightbox(img.src, img.alt));

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
setInterval(load, 60_000); // refresh every 10s while testing