import { useCallback, useEffect, useState } from "react";
import "./App.css";

const navItems = [
  { id: "Overview", icon: "◫" },
  { id: "Pull requests", icon: "⑂" },
  { id: "Review jobs", icon: "☷" },
  { id: "Repositories", icon: "▣" },
  { id: "Settings", icon: "⚙" },
];

function Icon({ children }) {
  return (
    <span className="nav-icon" aria-hidden="true">
      {children}
    </span>
  );
}

function App() {
  const [active, setActive] = useState("Overview");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadDashboard = useCallback(async ({ quiet = false } = {}) => {
    if (quiet) setRefreshing(true);
    else setLoading(true);
    setError("");

    try {
      const [statsResponse, jobsResponse] = await Promise.all([
        fetch("/api/admin/stats"),
        fetch("/api/admin/jobs"),
      ]);

      if (!statsResponse.ok || !jobsResponse.ok) {
        const response = !statsResponse.ok ? statsResponse : jobsResponse;
        throw new Error(`API request failed (${response.status}). Check the backend and Vite proxy configuration.`);
      }

      const statsData = await statsResponse.json();
      const jobsData = await jobsResponse.json();
      const rawJobs = Array.isArray(jobsData)
        ? jobsData
        : Array.isArray(jobsData.jobs)
          ? jobsData.jobs
          : Array.isArray(jobsData.items)
            ? jobsData.items
            : [];

      const normalizedJobs = rawJobs.map((job, index) => {
        const status = String(job.status || "pending").toLowerCase();
        const createdAt = job.created_at ? new Date(job.created_at) : null;
        const result = job.result;
        const resultTitle =
          (result && typeof result === "object" && (result.title || result.summary)) ||
          job.title ||
          (job.pr_number ? `Pull request #${job.pr_number}` : `Review job ${job.id ?? index + 1}`);

        return {
          id: String(job.id ?? index + 1),
          repo: job.repo || job.repository || "Unknown repository",
          pr: job.pr_number ?? job.pr ?? "—",
          title: String(resultTitle),
          status,
          time: createdAt && !Number.isNaN(createdAt.getTime())
            ? createdAt.toLocaleString()
            : "—",
          risk: "—",
          sha: job.sha || "",
          attempts: job.attempts ?? 0,
          error: job.error || "",
          result,
        };
      });

      setStats(statsData);
      setJobs(normalizedJobs);
      setNotice("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard data.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch = `${job.repo} ${job.title} ${job.id} ${job.pr} ${job.sha}`
      .toLowerCase()
      .includes(search.toLowerCase());
    return matchesSearch && (filter === "all" || job.status === filter);
  });

  const statusCounts = stats?.jobs_by_status || {};
  const completed = statusCounts.done ?? jobs.filter((job) => job.status === "done").length;
  const processing = statusCounts.processing ?? jobs.filter((job) => job.status === "processing").length;
  const failed = statusCounts.failed ?? jobs.filter((job) => job.status === "failed").length;
  const totalJobs = Object.values(statusCounts).reduce(
    (total, count) => total + (Number(count) || 0),
    0,
  );

  function refreshDemo() {
    loadDashboard({ quiet: true });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#overview"
          onClick={() => setActive("Overview")}
        >
          <span className="brand-mark">PR</span>
          <span className="brand-name">
            review<span>assistant</span>
          </span>
        </a>

        <div className="workspace-label">WORKSPACE</div>
        <button
          className="workspace-switch"
          onClick={() => setNotice("Workspace switching will be added later.")}
        >
          <span className="workspace-avatar">N</span>
          <span className="workspace-info">
            <strong>Narayan's workspace</strong>
            <small>Personal workspace</small>
          </span>
          <span>⌄</span>
        </button>

        <div className="nav-label">MENU</div>
        <nav className="main-nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${active === item.id ? "active" : ""}`}
              onClick={() => setActive(item.id)}
            >
              <Icon>{item.icon}</Icon>
              <span>{item.id}</span>
              {item.id === "Review jobs" && (
                <span className="nav-count">{jobs.length}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-icon">✳</div>
            <strong>Built for better reviews</strong>
            <p>Catch risky changes before they reach production.</p>
            <a
              href="https://github.com/codeWithNarayan07/pr-review-assistant"
              target="_blank"
              rel="noreferrer"
            >
              View on GitHub ↗
            </a>
          </div>
          <div className="profile">
            <div className="profile-avatar">N</div>
            <div>
              <strong>Developer</strong>
              <small>Local demo</small>
            </div>
            <span className="profile-menu">•••</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumbs">
            Workspace <span>/</span> <strong>{active}</strong>
          </div>
          <div className="topbar-actions">
            <span className="connection-pill">
              <i /> {error ? "Connection issue" : loading ? "Connecting…" : "Live API"}
            </span>
            <a
              className="github-button"
              href="https://github.com/codeWithNarayan07/pr-review-assistant"
              target="_blank"
              rel="noreferrer"
            >
              <span>↗</span> GitHub
            </a>
          </div>
        </header>

        <div className="page-content">
          <section className="welcome-row">
            <div>
              <div className="eyebrow">
                <span className="eyebrow-dot" /> DEVELOPER WORKSPACE
              </div>
              <h1>
                {active === "Overview" ? "Code review, at a glance." : active}
              </h1>
              <p className="page-subtitle">
                {active === "Overview"
                  ? "Monitor automated reviews, spot risks, and keep your pull requests moving."
                  : `Explore your ${active.toLowerCase()} in the PR Review Assistant workspace.`}
              </p>
            </div>
            <button className="primary-button" onClick={refreshDemo} disabled={refreshing}>
              <span>↻</span> {refreshing ? "Refreshing…" : "Refresh data"}
            </button>
          </section>

          {notice && <div className="notice">{notice}</div>}
          {error && (
            <div className="notice" role="alert">
              Could not load live data: {error}
              <button className="text-button" onClick={() => loadDashboard()} style={{ marginLeft: 12 }}>
                Try again
              </button>
            </div>
          )}

          <section className="metrics-grid">
            <Metric
              title="Total review jobs"
              value={loading ? "—" : (totalJobs || jobs.length)}
              change="From backend"
              icon="↗"
              tone="violet"
            />
            <Metric
              title="Completed"
              value={loading ? "—" : completed}
              change="Successfully processed"
              icon="✓"
              tone="green"
            />
            <Metric
              title="In progress"
              value={loading ? "—" : processing}
              change="Currently processing"
              icon="◷"
              tone="blue"
            />
            <Metric
              title="Failed jobs"
              value={loading ? "—" : failed}
              change="Need investigation"
              icon="!"
              tone="orange"
            />
          </section>

          <section className="hero-panel">
            <div className="hero-copy">
              <div className="hero-tag">
                <span /> AUTOMATED CODE INTELLIGENCE
              </div>
              <h2>
                Ship better code.
                <br />
                <span>Catch risks earlier.</span>
              </h2>
              <p>
                Review jobs, security checks, migration risks, and code changes
                — organized in one developer workspace.
              </p>
              <button
                className="hero-button"
                onClick={() => setActive("Review jobs")}
              >
                Explore review jobs <span>→</span>
              </button>
            </div>
            <div className="hero-art" aria-hidden="true">
              <div className="orbit orbit-one" />
              <div className="orbit orbit-two" />
              <div className="code-window">
                <div className="window-bar">
                  <i />
                  <i />
                  <i />
                  <span>review-summary.py</span>
                </div>
                <div className="code-lines">
                  <div>
                    <b>01</b>
                    <span className="code-purple">review</span>(pull_request)
                  </div>
                  <div>
                    <b>02</b>{" "}
                    <span className="code-muted"># inspect changed files</span>
                  </div>
                  <div>
                    <b>03</b> <span className="code-blue">check</span>(
                    <span className="code-green">"security"</span>)
                  </div>
                  <div>
                    <b>04</b> <span className="code-blue">check</span>(
                    <span className="code-green">"migrations"</span>)
                  </div>
                  <div>
                    <b>05</b> <span className="code-purple">post_review</span>()
                  </div>
                </div>
                <div className="code-success">
                  <span>✓</span> Review checklist generated
                </div>
              </div>
              <div className="floating-check">✓</div>
              <div className="floating-risk">
                <span>↗</span>
                <div>
                  <small>Risk checks</small>
                  <strong>Enabled</strong>
                </div>
              </div>
            </div>
          </section>

          <section className="jobs-section">
            <div className="section-heading">
              <div>
                <h2>
                  {active === "Repositories"
                    ? "Repository activity"
                    : active === "Pull requests"
                      ? "Pull request activity"
                      : "Recent review jobs"}
                </h2>
                <p>Track review activity and processing results.</p>
              </div>
              <button
                className="text-button"
                onClick={() => setActive("Review jobs")}
              >
                View all jobs <span>→</span>
              </button>
            </div>

            <div className="table-toolbar">
              <div className="search-box">
                <span>⌕</span>
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search jobs or repositories..."
                />
              </div>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                aria-label="Filter jobs by status"
              >
                <option value="all">All statuses</option>
                <option value="done">Completed</option>
                <option value="processing">Processing</option>
                <option value="failed">Failed</option>
              </select>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>REVIEW JOB</th>
                    <th>REPOSITORY</th>
                    <th>STATUS</th>
                    <th>RISK</th>
                    <th>UPDATED</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {filteredJobs.map((job) => (
                    <tr key={job.id}>
                      <td>
                        <div className="job-title">
                          <span className="pr-icon">⑂</span>
                          <div>
                            <strong>{job.title}</strong>
                            <small>
                              {job.id} · PR #{job.pr}
                            </small>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className="repo-name">{job.repo}</span>
                      </td>
                      <td>
                        <Status status={job.status} />
                      </td>
                      <td>
                        <span className="risk">{job.risk}</span>
                      </td>
                      <td className="time-cell">{job.time}</td>
                      <td>
                        <button
                          className="more-button"
                          onClick={() =>
                            setNotice(
                              `${job.id}: ${job.title} | Status: ${job.status} | Attempts: ${job.attempts}${job.error ? ` | Error: ${job.error}` : ""}${job.sha ? ` | Commit: ${job.sha}` : ""}`,
                            )
                          }
                          aria-label={`Details for ${job.id}`}
                        >
                          •••
                        </button>
                      </td>
                    </tr>
                  ))}
                  {filteredJobs.length === 0 && (
                    <tr>
                      <td colSpan="6" className="empty-state">
                        No jobs match your search.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <span>
                {loading ? "Loading review jobs…" : `Showing ${filteredJobs.length} of ${jobs.length} review jobs`}
              </span>
              <span>{error ? "Data may be out of date" : "Connected to backend API"}</span>
            </div>
          </section>

          <footer className="page-footer">
            <span>
              PR Review Assistant <span className="footer-dot">•</span> v1.0.0
            </span>
            <span>Built for developers, by developers.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}

function Metric({ title, value, change, icon, tone }) {
  return (
    <article className="metric-card">
      <div className="metric-top">
        <span>{title}</span>
        <span className={`metric-icon ${tone}`}>{icon}</span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-change">
        <span className={`metric-indicator ${tone}`} />
        {change}
      </div>
    </article>
  );
}

function Status({ status }) {
  const labels = {
    done: "Completed",
    processing: "Processing",
    pending: "Pending",
    skipped: "Skipped",
    failed: "Failed",
  };
  return (
    <span className={`status status-${status}`}>
      <i />
      {labels[status]}
    </span>
  );
}

export default App;
