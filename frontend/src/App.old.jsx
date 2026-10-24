import { useState } from "react";
import "./App.css";

const initialJobs = [
  {
    id: "#1042",
    repo: "codeWithNarayan07/pr-review-assistant-test",
    pr: 1,
    title: "Update API error handling",
    status: "done",
    time: "Just now",
    risk: "Low",
  },
  {
    id: "#1041",
    repo: "acme/backend-service",
    pr: 28,
    title: "Add authentication middleware",
    status: "processing",
    time: "2 min ago",
    risk: "Medium",
  },
  {
    id: "#1040",
    repo: "acme/payment-api",
    pr: 16,
    title: "Update payment validation",
    status: "failed",
    time: "8 min ago",
    risk: "High",
  },
  {
    id: "#1039",
    repo: "demo/frontend",
    pr: 9,
    title: "Improve loading states",
    status: "done",
    time: "15 min ago",
    risk: "Low",
  },
];

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
  const [jobs, setJobs] = useState(initialJobs);
  const [notice, setNotice] = useState("");

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch = `${job.repo} ${job.title} ${job.id}`
      .toLowerCase()
      .includes(search.toLowerCase());
    return matchesSearch && (filter === "all" || job.status === filter);
  });

  const completed = jobs.filter((job) => job.status === "done").length;
  const processing = jobs.filter((job) => job.status === "processing").length;
  const failed = jobs.filter((job) => job.status === "failed").length;

  function refreshDemo() {
    setNotice("Demo view refreshed. Live API integration comes next.");
    window.setTimeout(() => setNotice(""), 3000);
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
              <i /> Demo data
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
            <button className="primary-button" onClick={refreshDemo}>
              <span>↻</span> Refresh view
            </button>
          </section>

          {notice && <div className="notice">{notice}</div>}

          <section className="metrics-grid">
            <Metric
              title="Total review jobs"
              value={jobs.length}
              change="Demo records"
              icon="↗"
              tone="violet"
            />
            <Metric
              title="Completed"
              value={completed}
              change="Successfully processed"
              icon="✓"
              tone="green"
            />
            <Metric
              title="In progress"
              value={processing}
              change="Currently processing"
              icon="◷"
              tone="blue"
            />
            <Metric
              title="Failed jobs"
              value={failed}
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
                        <span className={`risk risk-${job.risk.toLowerCase()}`}>
                          {job.risk}
                        </span>
                      </td>
                      <td className="time-cell">{job.time}</td>
                      <td>
                        <button
                          className="more-button"
                          onClick={() =>
                            setNotice(
                              `${job.id}: ${job.title} — ${job.status}. These are sample records until API integration.`,
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
                Showing {filteredJobs.length} of {jobs.length} demo jobs
              </span>
              <span>Sample data · Live API connection comes next</span>
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
