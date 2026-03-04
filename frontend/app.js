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
    left.innerHTML = `<div class="name">${s.site_name} • ${s.url}</div>
                      <div class="meta">endpoint ${s.endpoint_id} • last: ${s.last_checked || "-"} • uptime: ${s.uptime_7d_percent ?? "-"}%</div>`;

    const right = document.createElement("div");
    right.innerHTML = `<span class="badge ${s.state}">${s.state}</span>`;

    top.appendChild(left);
    top.appendChild(right);
    row.appendChild(top);

    // Stripe
    if (Array.isArray(s.timeline_7d) && s.timeline_7d.length > 0) {
      const stripe = document.createElement("div");
      stripe.className = "stripe";

      const totalSeconds = 7 * 24 * 3600;
      for (const seg of s.timeline_7d) {
        const w = Math.max(0, Math.min(1, (seg.duration_seconds || 0) / totalSeconds));
        const div = document.createElement("div");
        div.className = `seg ${seg.state}`;
        div.style.width = `${w * 100}%`;
        stripe.appendChild(div);
      }
      row.appendChild(stripe);
    }

    list.appendChild(row);
  }
}

load();
setInterval(load, 10_000); // refresh every 10s while testing