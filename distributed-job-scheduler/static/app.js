let token = localStorage.getItem("scheduler_token") || "";
let projectId = Number(localStorage.getItem("scheduler_project_id") || 0);
let queues = [];

const $ = (id) => document.getElementById(id);

function startAiBackground() {
  const canvas = $("aiCanvas");
  if (!canvas || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const context = canvas.getContext("2d");
  const nodes = [];
  let width = 0;
  let height = 0;
  let animationFrame = 0;

  function resize() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(height * ratio);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    nodes.length = 0;
    const count = Math.max(34, Math.min(82, Math.floor((width * height) / 22000)));
    for (let index = 0; index < count; index += 1) {
      nodes.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        radius: 1.4 + Math.random() * 2.2,
        phase: Math.random() * Math.PI * 2
      });
    }
  }

  function draw(time) {
    context.clearRect(0, 0, width, height);
    context.lineWidth = 1;

    nodes.forEach(node => {
      node.x += node.vx;
      node.y += node.vy;
      if (node.x < -20) node.x = width + 20;
      if (node.x > width + 20) node.x = -20;
      if (node.y < -20) node.y = height + 20;
      if (node.y > height + 20) node.y = -20;
    });

    for (let a = 0; a < nodes.length; a += 1) {
      for (let b = a + 1; b < nodes.length; b += 1) {
        const first = nodes[a];
        const second = nodes[b];
        const dx = first.x - second.x;
        const dy = first.y - second.y;
        const distance = Math.hypot(dx, dy);
        if (distance < 150) {
          const alpha = (1 - distance / 150) * 0.20;
          context.strokeStyle = `rgba(37, 99, 235, ${alpha})`;
          context.beginPath();
          context.moveTo(first.x, first.y);
          context.lineTo(second.x, second.y);
          context.stroke();
        }
      }
    }

    nodes.forEach(node => {
      const glow = 0.45 + Math.sin(time / 900 + node.phase) * 0.22;
      context.fillStyle = `rgba(8, 145, 178, ${glow})`;
      context.beginPath();
      context.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      context.fill();
    });

    animationFrame = requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize);
  resize();
  animationFrame = requestAnimationFrame(draw);

  window.addEventListener("beforeunload", () => {
    cancelAnimationFrame(animationFrame);
  });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error?.message || "request failed");
  return body;
}

function showNotice(message, type = "success") {
  $("notice").textContent = message;
  $("notice").className = `notice ${type}`;
}

function clearNotice() {
  $("notice").textContent = "";
  $("notice").className = "notice hidden";
}

async function login(event) {
  event.preventDefault();
  clearNotice();
  try {
    const mode = $("authMode").value;
    const credentials = {
      email: $("email").value.trim(),
      password: $("password").value
    };
    let data;

    if (mode === "signup") {
      data = await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          ...credentials,
          display_name: $("displayName").value.trim(),
          organization_name: $("organizationName").value.trim()
        })
      });
      token = data.token;
      localStorage.setItem("scheduler_token", token);
      const project = await api("/api/projects", {
        method: "POST",
        body: JSON.stringify({
          organization_id: data.organization.id,
          name: "Scheduler Demo",
          slug: `scheduler-demo-${Date.now()}`
        })
      });
      await api(`/api/projects/${project.project.id}/queues`, {
        method: "POST",
        body: JSON.stringify({
          name: "emails",
          priority: 10,
          concurrency_limit: 3,
          retry_policy_id: project.retry_policy.id
        })
      });
      showNotice("Account created. You are signed in and a default project/queue was created.");
    } else {
      data = await api("/api/auth/login", { method: "POST", body: JSON.stringify(credentials) });
      token = data.token;
      localStorage.setItem("scheduler_token", token);
      showNotice("Signed in successfully.");
    }

    await bootstrap();
  } catch (error) {
    showNotice(error.message, "error");
  }
}

async function bootstrap() {
  if (!token) return;
  const me = await api("/api/me");
  if (!me.projects.length) {
    showNotice("Signed in, but this account has no project yet. Use Sign up to create a demo project automatically.", "error");
    return;
  }
  projectId = me.projects[0].id;
  localStorage.setItem("scheduler_project_id", projectId);
  $("projectLabel").textContent = `${me.projects[0].name} - polling every 2s`;
  await refresh();
}

async function refresh() {
  if (!projectId) return;
  try {
    const [health, jobData] = await Promise.all([
      api(`/api/projects/${projectId}/health`),
      api(`/api/projects/${projectId}/jobs?limit=50&status=${$("statusFilter").value}`)
    ]);
    queues = health.queues;
    $("queuedCount").textContent = health.jobs.queued || 0;
    $("runningCount").textContent = health.jobs.running || 0;
    $("completedCount").textContent = health.jobs.completed || 0;
    $("deadCount").textContent = health.jobs.dead_letter || 0;
    renderQueues(health.queues);
    renderWorkers(health.workers);
    renderJobs(jobData.jobs);
  } catch (error) {
    showNotice(error.message, "error");
  }
}

function renderQueues(rows) {
  $("queueSelect").innerHTML = rows.map(q => `<option value="${q.id}">${escapeHtml(q.name)}</option>`).join("");
  $("queues").innerHTML = rows.map(q => `
    <article class="item">
      <div class="item-head">
        <strong>${escapeHtml(q.name)}</strong>
        <button class="secondary" onclick="toggleQueue(${q.id}, ${q.is_paused})">${q.is_paused ? "Resume" : "Pause"}</button>
      </div>
      <div class="chips">
        <span class="chip">priority ${q.priority}</span>
        <span class="chip">concurrency ${q.concurrency_limit}</span>
        <span class="chip">queued ${q.queued || 0}</span>
        <span class="chip success">completed ${q.completed || 0}</span>
        <span class="chip danger">DLQ ${q.dead_letter || 0}</span>
      </div>
    </article>
  `).join("");
}

async function toggleQueue(id, paused) {
  try {
    await api(`/api/projects/${projectId}/queues/${id}/${paused ? "resume" : "pause"}`, { method: "POST" });
    await refresh();
  } catch (error) {
    showNotice(error.message, "error");
  }
}

function renderWorkers(rows) {
  $("workers").innerHTML = rows.length ? rows.map(worker => `
    <article class="item">
      <div class="item-head">
        <strong>${escapeHtml(worker.name)}</strong>
        <span class="chip ${worker.status === "online" ? "success" : "warn"}">${worker.status}</span>
      </div>
      <div class="chips">
        <span class="chip">concurrency ${worker.concurrency}</span>
        <span class="chip">heartbeat ${worker.last_heartbeat_at}</span>
      </div>
    </article>
  `).join("") : `<p>No workers have registered yet.</p>`;
}

function renderJobs(rows) {
  if (!rows.length) {
    const filter = $("statusFilter").value || "all";
    const hint = filter === "queued"
      ? "No queued jobs right now. If a worker is online, jobs may move to Completed very quickly."
      : `No ${filter} jobs found.`;
    $("jobs").innerHTML = `
      <table>
        <thead><tr><th>ID</th><th>Type</th><th>Status</th><th>Attempts</th><th>Queue</th><th>Updated</th><th></th></tr></thead>
        <tbody>
          <tr><td colspan="7" class="empty-cell">${hint}</td></tr>
        </tbody>
      </table>
    `;
    return;
  }
  $("jobs").innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>Type</th><th>Status</th><th>Attempts</th><th>Queue</th><th>Updated</th><th></th></tr></thead>
      <tbody>
        ${rows.map(job => `
          <tr>
            <td>${job.id}</td>
            <td>${escapeHtml(job.type)}</td>
            <td><span class="chip ${statusClass(job.status)}">${job.status}</span></td>
            <td>${job.attempt_count}/${job.max_attempts || "policy"}</td>
            <td>${queueName(job.queue_id)}</td>
            <td>${job.updated_at}</td>
            <td>
              <button class="secondary" onclick="loadLogs(${job.id})">Logs</button>
              ${job.status === "dead_letter" ? `<button onclick="retryJob(${job.id})">Retry</button>` : ""}
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function queueName(id) {
  return escapeHtml((queues.find(q => q.id === id) || {}).name || id);
}

function statusClass(status) {
  if (status === "completed") return "success";
  if (status === "dead_letter" || status === "failed") return "danger";
  if (status === "running" || status === "scheduled") return "warn";
  return "";
}

async function loadLogs(jobId) {
  try {
    const data = await api(`/api/projects/${projectId}/jobs/${jobId}/logs`);
    $("logs").innerHTML = data.logs.map(log => `
      <div class="log-line">[${log.created_at}] ${log.level.toUpperCase()} job=${log.job_id} ${escapeHtml(log.message)} ${escapeHtml(log.context_json || "")}</div>
    `).join("");
  } catch (error) {
    showNotice(error.message, "error");
  }
}

async function retryJob(jobId) {
  try {
    await api(`/api/projects/${projectId}/jobs/${jobId}/retry`, { method: "POST" });
    await refresh();
  } catch (error) {
    showNotice(error.message, "error");
  }
}

async function createJob(event) {
  event.preventDefault();
  clearNotice();
  try {
    const scheduledAt = $("scheduledAt").value.trim();
    if (scheduledAt && !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(scheduledAt)) {
      throw new Error("Schedule At must be blank or a full date like 2026-07-04T12:30:00+05:30. Do not type only 12.");
    }

    const body = {
      queue_id: Number($("queueSelect").value),
      type: $("jobType").value.trim(),
      priority: Number($("priority").value || 100),
      payload: JSON.parse($("payload").value)
    };
    if (!body.queue_id) throw new Error("Select a queue first.");
    if (!body.type) throw new Error("Type is required.");
    if (scheduledAt) body.scheduled_at = scheduledAt;

    await api(`/api/projects/${projectId}/jobs`, { method: "POST", body: JSON.stringify(body) });
    $("scheduledAt").value = "";
    $("statusFilter").value = "";
    showNotice("Job created successfully. If a worker is running, it may complete quickly.");
    await refresh();
  } catch (error) {
    showNotice(error.message, "error");
  }
}

function syncAuthMode() {
  const signup = $("authMode").value === "signup";
  document.querySelectorAll(".signup-only").forEach(item => item.classList.toggle("hidden", !signup));
  $("authSubmit").textContent = signup ? "Sign up" : "Sign in";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

$("loginForm").addEventListener("submit", login);
$("jobForm").addEventListener("submit", createJob);
$("refreshBtn").addEventListener("click", refresh);
$("statusFilter").addEventListener("change", refresh);
$("authMode").addEventListener("change", syncAuthMode);

startAiBackground();
syncAuthMode();
bootstrap().catch(error => showNotice(error.message, "error"));
setInterval(() => refresh().catch(error => showNotice(error.message, "error")), 2000);
