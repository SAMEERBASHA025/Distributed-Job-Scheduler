const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const { chromium } = require("C:/Users/ASUA/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");

const root = path.resolve(__dirname, "..");
const workDir = __dirname;
const screenshotPath = path.join(workDir, "dashboard-screenshot.png");
const htmlPath = path.join(workDir, "distributed-job-scheduler-report.html");
const pdfPath = path.join(root, "Distributed_Job_Scheduler_Project_Report.pdf");
const dbPath = path.join(workDir, "pdf-scheduler.db");
const port = 8765;

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function waitForServer(url) {
  for (let i = 0; i < 40; i += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch (_) {
      await wait(250);
    }
  }
  throw new Error("Server did not start in time");
}

function buildReportHtml() {
  const imageData = fs.readFileSync(screenshotPath).toString("base64");
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Distributed Job Scheduler Project Report</title>
  <style>
    @page { size: A4; margin: 18mm 16mm; }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: #111827;
      background: #ffffff;
      line-height: 1.45;
      font-size: 11px;
    }
    h1, h2, h3 { margin: 0 0 8px; color: #0f172a; }
    h1 { font-size: 28px; }
    h2 {
      margin-top: 22px;
      font-size: 17px;
      border-bottom: 1px solid #dbe2ea;
      padding-bottom: 5px;
    }
    h3 { margin-top: 14px; font-size: 13px; }
    p { margin: 0 0 8px; }
    ul { margin: 6px 0 10px 18px; padding: 0; }
    li { margin: 3px 0; }
    code {
      background: #f1f5f9;
      padding: 2px 4px;
      border-radius: 4px;
      font-family: Consolas, monospace;
    }
    pre {
      white-space: pre-wrap;
      background: #f8fafc;
      border: 1px solid #dbe2ea;
      border-radius: 6px;
      padding: 10px;
      font-family: Consolas, monospace;
      font-size: 10px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 8px 0 12px;
      font-size: 10px;
    }
    th, td {
      border: 1px solid #dbe2ea;
      padding: 6px;
      text-align: left;
      vertical-align: top;
    }
    th { background: #eff6ff; color: #1d4ed8; }
    .cover {
      padding: 26px;
      border-radius: 12px;
      background: linear-gradient(135deg, #eff6ff, #f8fafc);
      border: 1px solid #dbe2ea;
      margin-bottom: 18px;
    }
    .subtitle { color: #475569; font-size: 13px; }
    .meta {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-top: 16px;
    }
    .meta div {
      background: #fff;
      border: 1px solid #dbe2ea;
      border-radius: 8px;
      padding: 10px;
    }
    .shot {
      width: 100%;
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      margin: 8px 0 6px;
    }
    .caption {
      color: #64748b;
      font-size: 10px;
      margin-bottom: 12px;
    }
    .page-break { page-break-before: always; }
    .badge {
      display: inline-block;
      border-radius: 999px;
      background: #ecfdf5;
      color: #15803d;
      padding: 3px 8px;
      font-weight: bold;
      font-size: 10px;
    }
    .diagram {
      display: grid;
      gap: 8px;
      margin: 10px 0 12px;
    }
    .flow {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .box {
      border: 1px solid #bfdbfe;
      background: #eff6ff;
      color: #1e3a8a;
      border-radius: 8px;
      padding: 8px 10px;
      font-weight: bold;
      min-width: 110px;
      text-align: center;
    }
    .arrow {
      color: #2563eb;
      font-weight: bold;
    }
    .deliverable {
      border-left: 4px solid #2563eb;
      background: #f8fafc;
      padding: 10px 12px;
      margin: 8px 0;
      border-radius: 0 8px 8px 0;
    }
  </style>
</head>
<body>
  <section class="cover">
    <h1>Distributed Job Scheduler</h1>
    <p class="subtitle">Production-inspired asynchronous job scheduling platform with REST APIs, worker execution, retry handling, dead letter queue support, observability, and dashboard UI.</p>
    <div class="meta">
      <div><strong>Backend</strong><br>Python REST API</div>
      <div><strong>Database</strong><br>SQLite relational schema</div>
      <div><strong>Status</strong><br><span class="badge">Tests Passing</span></div>
    </div>
  </section>

  <h2>Deliverables Included In This PDF</h2>
  <table>
    <tr><th>Deliverable</th><th>Included</th><th>Location / Summary</th></tr>
    <tr><td>Source code with setup instructions</td><td>Yes</td><td>Section 1 and project structure/setup commands.</td></tr>
    <tr><td>Architecture diagram</td><td>Yes</td><td>Section 2 with component flow diagram.</td></tr>
    <tr><td>ER diagram</td><td>Yes</td><td>Section 3 with relational entity mapping.</td></tr>
    <tr><td>API documentation</td><td>Yes</td><td>Section 4 with endpoint tables and examples.</td></tr>
    <tr><td>Design decisions document</td><td>Yes</td><td>Section 5 with major trade-offs.</td></tr>
    <tr><td>Automated tests</td><td>Yes</td><td>Section 6 with test coverage and command.</td></tr>
  </table>

  <h2>1. Source Code With Setup Instructions</h2>
  <div class="deliverable">
    <strong>Project folder:</strong><br>
    <code>C:\\Users\\ASUA\\Documents\\Codex\\2026-07-04\\intern-assignment-distributed-job-scheduler-objective\\outputs\\distributed-job-scheduler</code>
  </div>
  <pre>app/
  auth.py          Password hashing and bearer token authentication
  db.py            SQLite connection, schema, indexes, foreign keys
  main.py          REST API server and static dashboard server
  scheduler.py     Job creation, atomic claiming, retries, DLQ, metrics
  worker.py        Polling worker with heartbeats and graceful shutdown
static/
  index.html       Web dashboard
  styles.css       Modern UI and AI animated background
  app.js           Dashboard API calls and live polling
docs/
  architecture.md
  er-diagram.md
  api.md
  design-decisions.md
tests/
  test_api.py
  test_scheduler.py</pre>
  <h3>Run Project</h3>
  <pre>cd C:\\Users\\ASUA\\Documents\\Codex\\2026-07-04\\intern-assignment-distributed-job-scheduler-objective\\outputs\\distributed-job-scheduler
python -m app.main --init-db --seed
python -m app.main --serve</pre>
  <p>Open <code>http://127.0.0.1:8000</code>. Demo login: <code>demo@example.com</code> / <code>demo-password</code>.</p>
  <h3>Run Worker</h3>
  <pre>python -m app.worker --worker-name worker-a</pre>

  <h2>Dashboard Screenshot</h2>
  <img class="shot" src="data:image/png;base64,${imageData}" alt="Distributed Job Scheduler dashboard screenshot">
  <p class="caption">Dashboard showing authentication, queue health, job creation, worker status, logs, and live metrics with the AI animated background UI.</p>

  <h2>Objective</h2>
  <p>The project designs and builds a distributed job scheduling platform capable of reliably executing asynchronous background jobs across multiple workers. It evaluates backend engineering, database design, concurrency, reliability, API design, documentation, testing, and full-stack implementation.</p>

  <h2>Implemented Features</h2>
  <ul>
    <li>Authentication with sign in and sign up.</li>
    <li>Organizations, projects, and project-scoped queues.</li>
    <li>Queue priority, concurrency limit, retry policy, pause/resume, and statistics.</li>
    <li>Immediate, delayed, scheduled, recurring cron-like, and batch jobs through REST APIs.</li>
    <li>Worker service with polling, atomic claim, concurrent execution, heartbeat, and graceful shutdown.</li>
    <li>Full lifecycle: queued, scheduled, claimed, running, completed, retry, dead letter.</li>
    <li>Fixed, linear, and exponential retry strategies.</li>
    <li>Execution logs, retry history, worker assignment, timestamps, and duration metrics.</li>
    <li>Responsive web dashboard with modern AI-style animated UI.</li>
  </ul>

  <h2>2. Architecture Diagram</h2>
  <div class="diagram">
    <div class="flow">
      <div class="box">Web Dashboard</div><div class="arrow">-></div>
      <div class="box">REST API Server</div><div class="arrow">-></div>
      <div class="box">SQLite Database</div>
    </div>
    <div class="flow">
      <div class="box">Worker A</div><div class="arrow">-></div>
      <div class="box">Atomic Claiming</div><div class="arrow">-></div>
      <div class="box">Job Execution</div><div class="arrow">-></div>
      <div class="box">Logs / Metrics</div>
    </div>
    <div class="flow">
      <div class="box">Worker B</div><div class="arrow">-></div>
      <div class="box">Heartbeats</div><div class="arrow">-></div>
      <div class="box">Retry History</div><div class="arrow">-></div>
      <div class="box">Dead Letter Queue</div>
    </div>
  </div>
  <p>The REST API owns authentication, validation, project access checks, queue configuration, job APIs, and health APIs. Workers communicate through the database, claim jobs transactionally, update executions, and emit logs/heartbeats.</p>

  <h2>Job Lifecycle</h2>
  <pre>Queued -> Claimed -> Running -> Completed
Scheduled -> Queued when due
Running -> Scheduled when retryable failure occurs
Running -> Dead Letter when attempts are exhausted
Dead Letter -> Queued when manually retried</pre>

  <h2>Database Design</h2>
  <p>The schema is normalized around users, organizations, projects, queues, retry policies, jobs, executions, workers, heartbeats, logs, scheduled jobs, retry history, and dead letter entries.</p>
  <table>
    <tr><th>Table</th><th>Purpose</th></tr>
    <tr><td>users</td><td>Stores user accounts and password hashes.</td></tr>
    <tr><td>organizations</td><td>Groups users and projects.</td></tr>
    <tr><td>projects</td><td>Owns queues and retry policies.</td></tr>
    <tr><td>queues</td><td>Stores queue configuration and pause/resume state.</td></tr>
    <tr><td>jobs</td><td>Stores job payload, status, schedule, attempts, and worker assignment.</td></tr>
    <tr><td>job_executions</td><td>Stores each execution attempt and duration.</td></tr>
    <tr><td>retry_history</td><td>Stores retry attempts, strategy, delay, and next run time.</td></tr>
    <tr><td>workers</td><td>Stores worker identity, status, concurrency, and heartbeat time.</td></tr>
    <tr><td>job_logs</td><td>Stores lifecycle and execution logs.</td></tr>
    <tr><td>dead_letter_queue</td><td>Stores permanently failed jobs and reason.</td></tr>
  </table>

  <h2>3. ER Diagram</h2>
  <table>
    <tr><th>Entity</th><th>Relationship</th><th>Related Entity</th></tr>
    <tr><td>users</td><td>1 to many</td><td>auth_tokens</td></tr>
    <tr><td>users</td><td>many to many through organization_members</td><td>organizations</td></tr>
    <tr><td>organizations</td><td>1 to many</td><td>projects</td></tr>
    <tr><td>projects</td><td>1 to many</td><td>queues</td></tr>
    <tr><td>projects</td><td>1 to many</td><td>retry_policies</td></tr>
    <tr><td>retry_policies</td><td>1 to many</td><td>queues</td></tr>
    <tr><td>queues</td><td>1 to many</td><td>jobs</td></tr>
    <tr><td>jobs</td><td>1 to many</td><td>job_executions</td></tr>
    <tr><td>jobs</td><td>1 to many</td><td>retry_history</td></tr>
    <tr><td>jobs</td><td>1 to many</td><td>job_logs</td></tr>
    <tr><td>jobs</td><td>0 or 1 to 1</td><td>dead_letter_queue</td></tr>
    <tr><td>workers</td><td>1 to many</td><td>worker_heartbeats</td></tr>
    <tr><td>workers</td><td>1 to many</td><td>job_executions</td></tr>
  </table>
  <p>Foreign keys enforce ownership boundaries and cascading behavior. Operational fields such as status, priority, schedule time, and timestamps are indexed for worker polling and dashboard filtering.</p>

  <h2>Important Indexes</h2>
  <ul>
    <li><code>idx_jobs_claimable</code> supports worker polling and atomic claiming.</li>
    <li><code>idx_jobs_project_status</code> supports dashboard filtering.</li>
    <li><code>idx_jobs_worker</code> supports worker assignment queries.</li>
    <li><code>idx_executions_job</code> supports execution history.</li>
    <li><code>idx_logs_job_time</code> supports ordered job logs.</li>
    <li><code>idx_workers_status_heartbeat</code> supports worker health checks.</li>
  </ul>

  <h2>4. API Documentation</h2>
  <table>
    <tr><th>Area</th><th>Endpoints</th></tr>
    <tr><td>Auth</td><td>POST /api/auth/register, POST /api/auth/login, GET /api/me</td></tr>
    <tr><td>Projects</td><td>GET /api/projects, POST /api/projects, GET /api/projects/{id}</td></tr>
    <tr><td>Queues</td><td>GET/POST /api/projects/{id}/queues, PATCH queue, pause, resume</td></tr>
    <tr><td>Jobs</td><td>GET/POST jobs, POST batch, GET logs, POST retry</td></tr>
    <tr><td>Health</td><td>GET /api/projects/{id}/health, GET /api/workers</td></tr>
  </table>
  <h3>Example: Create Immediate Job</h3>
  <pre>POST /api/projects/{project_id}/jobs
{
  "queue_id": 1,
  "type": "send_email",
  "priority": 100,
  "payload": {
    "to": "customer@example.com",
    "duration_seconds": 0.5
  }
}</pre>
  <h3>Example: Create Scheduled Job</h3>
  <pre>POST /api/projects/{project_id}/jobs
{
  "queue_id": 1,
  "type": "scheduled_email",
  "scheduled_at": "2026-07-04T12:30:00+05:30",
  "payload": {
    "to": "scheduled@example.com"
  }
}</pre>

  <h2>Atomic Claiming And Reliability</h2>
  <p>Workers claim jobs inside a write transaction using <code>BEGIN IMMEDIATE</code>. The scheduler checks queue pause state, queue concurrency limit, job status, schedule time, and priority before updating the selected job to <code>claimed</code> and creating a job execution row. This prevents duplicate execution across workers.</p>

  <h2>Retry And Dead Letter Queue</h2>
  <p>Retry policies support fixed delay, linear backoff, and exponential backoff. Failed attempts are recorded in retry history. Jobs that exhaust attempts are moved to <code>dead_letter</code> and receive a dead letter queue entry containing the reason and payload snapshot.</p>

  <h2>Frontend Dashboard</h2>
  <p>The dashboard includes sign in, sign up, queue health, queue pause/resume, job creation, job explorer, worker monitor, logs viewer, retry controls, polling-based updates, and AI-style animated background UI.</p>

  <h2>5. Design Decisions And Major Trade-Offs</h2>
  <table>
    <tr><th>Decision</th><th>Reason</th><th>Production Upgrade</th></tr>
    <tr><td>SQLite database</td><td>Portable, dependency-free, supports relational schema and transactions.</td><td>Move to PostgreSQL with FOR UPDATE SKIP LOCKED.</td></tr>
    <tr><td>Polling workers</td><td>Simple, reliable, testable, works without external brokers.</td><td>Use Kafka, RabbitMQ, SQS, or PostgreSQL LISTEN/NOTIFY.</td></tr>
    <tr><td>JSON job payload</td><td>Different job types need flexible payload shapes.</td><td>Keep metadata relational; validate payload by job type.</td></tr>
    <tr><td>Bearer token auth</td><td>Simple API authentication for assignment scope.</td><td>Add refresh tokens, RBAC policies, and audit logs.</td></tr>
    <tr><td>Polling dashboard</td><td>Easy live updates without extra infrastructure.</td><td>Use WebSockets for real-time streaming.</td></tr>
  </table>

  <h2>6. Automated Tests For Critical Functionality</h2>
  <p>Automated tests cover atomic claim behavior, duplicate claim prevention, dead letter queue transition, queue statistics, signup, duplicate signup conflict, login, and job creation API flow.</p>
  <pre>python -m unittest discover -s tests
Ran 6 tests
OK</pre>

  <h2>Requirement Mapping</h2>
  <table>
    <tr><th>Requirement</th><th>Status</th></tr>
    <tr><td>Authentication and project management</td><td>Implemented</td></tr>
    <tr><td>Queue configuration</td><td>Implemented</td></tr>
    <tr><td>Immediate, delayed, scheduled, recurring, batch jobs</td><td>Implemented</td></tr>
    <tr><td>Worker polling, claiming, heartbeats, graceful shutdown</td><td>Implemented</td></tr>
    <tr><td>Retries and dead letter queue</td><td>Implemented</td></tr>
    <tr><td>Logs, retry history, metrics</td><td>Implemented</td></tr>
    <tr><td>Dashboard</td><td>Implemented</td></tr>
    <tr><td>Documentation and tests</td><td>Implemented</td></tr>
  </table>
</body>
</html>`;
}

(async () => {
  const server = spawn("python", ["-m", "app.main", "--db", dbPath, "--init-db", "--seed", "--serve", "--port", String(port)], {
    cwd: root,
    stdio: "ignore",
    windowsHide: true
  });

  try {
    await waitForServer(`http://127.0.0.1:${port}`);
    const browser = await chromium.launch({
      headless: true,
      executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
    });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, deviceScaleFactor: 1 });
    await page.goto(`http://127.0.0.1:${port}`, { waitUntil: "networkidle" });
    await page.fill("#email", "demo@example.com");
    await page.fill("#password", "demo-password");
    await page.click("#authSubmit");
    await page.waitForSelector("#queues .item", { timeout: 5000 });
    await page.screenshot({ path: screenshotPath, fullPage: true });

    fs.writeFileSync(htmlPath, buildReportHtml(), "utf8");
    await page.goto(`file:///${htmlPath.replace(/\\/g, "/")}`, { waitUntil: "networkidle" });
    await page.pdf({
      path: pdfPath,
      format: "A4",
      printBackground: true,
      margin: { top: "14mm", right: "12mm", bottom: "14mm", left: "12mm" }
    });
    await browser.close();
  } finally {
    server.kill();
  }
})();
