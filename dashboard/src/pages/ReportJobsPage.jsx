import Breadcrumb from "../components/Breadcrumb";
import { StatusBadge } from "../components/Badges";
import { clientSlug } from "../lib/format";

export const ACTIVE_REPORT_JOB_STATUSES = new Set([
  "queued",
  "running",
  "retrying",
  "cancel_requested",
]);

const TERMINAL_REPORT_JOB_STATUSES = new Set([
  "completed",
  "failed",
  "cancelled",
]);

export function isActiveReportJob(job) {
  return ACTIVE_REPORT_JOB_STATUSES.has(job?.status);
}

export function reportJobStatusLabel(status) {
  return {
    queued: "Queued",
    running: "Running",
    retrying: "Waiting to retry",
    cancel_requested: "Cancelling",
    completed: "Completed",
    failed: "Failed",
    cancelled: "Cancelled",
  }[status] || status || "Unknown";
}

export function reportJobStatusState(status) {
  if (["queued", "running", "retrying", "cancel_requested"].includes(status)) {
    return "info";
  }
  if (status === "completed") return "success";
  if (["failed", "cancelled"].includes(status)) return "danger";
  return "neutral";
}

export function reportJobStageLabel(stage) {
  return {
    queued: "Waiting for worker",
    analysis: "Analyzing data with Gemini",
    slides: "Generating Google Slides",
    cancel_requested: "Stopping report worker",
    completed: "Report ready",
    failed: "Generation stopped",
    cancelled: "Generation cancelled",
  }[stage] || String(stage || "Waiting").replaceAll("_", " ");
}

function jobTimestamp(job) {
  return (
    job.finished_at
    || job.started_at
    || job.queued_at
    || job.created_at
  );
}

function formatJobTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function queueStatusOrder(status) {
  return {
    running: 0,
    cancel_requested: 1,
    retrying: 2,
    queued: 3,
  }[status] ?? 4;
}

function sortCurrentQueue(jobs) {
  return [...jobs].sort((left, right) => {
    const statusDifference = (
      queueStatusOrder(left.status) - queueStatusOrder(right.status)
    );
    if (statusDifference) return statusDifference;
    const leftTime = new Date(left.queued_at || left.created_at || 0).getTime();
    const rightTime = new Date(
      right.queued_at || right.created_at || 0,
    ).getTime();
    return leftTime - rightTime;
  });
}

function JobActions({
  job,
  actionJobId,
  onCancel,
  onRetry,
  onOpenReport,
}) {
  const isPending = actionJobId === job.id;
  const canCancel = ["queued", "running", "retrying"].includes(job.status);
  const canRetry = ["failed", "cancelled"].includes(job.status);

  return (
    <div className="report-job-actions">
      {job.presentation_url && (
        <button
          type="button"
          className="secondary-button"
          onClick={() => onOpenReport(job.presentation_url)}
        >
          Open Slides
        </button>
      )}
      {canRetry && (
        <button
          type="button"
          className="secondary-button"
          disabled={isPending}
          onClick={() => onRetry(job)}
        >
          {isPending ? "Retrying..." : "Retry"}
        </button>
      )}
      {canCancel && (
        <button
          type="button"
          className="report-job-cancel"
          disabled={isPending}
          onClick={() => onCancel(job)}
        >
          {isPending ? "Cancelling..." : "Cancel"}
        </button>
      )}
    </div>
  );
}

function JobSummary({ job, queuePosition }) {
  return (
    <div className="report-job-summary">
      <StatusBadge
        text={reportJobStatusLabel(job.status)}
        state={reportJobStatusState(job.status)}
      />
      {queuePosition && (
        <span className="report-queue-position">
          Queue #{queuePosition}
        </span>
      )}
      <span>{reportJobStageLabel(job.current_stage)}</span>
      <span>
        Attempt {job.attempt_count || 0}/{job.max_attempts || 3}
      </span>
      <span>{formatJobTime(jobTimestamp(job))}</span>
    </div>
  );
}

function JobRow({
  job,
  queuePosition,
  actionJobId,
  onCancel,
  onRetry,
  onOpenReport,
}) {
  return (
    <article className="report-job-row">
      <div className="report-job-row-main">
        <div>
          <h3>
            {job.client_name_snapshot} - {job.period_label_snapshot}
          </h3>
          <JobSummary job={job} queuePosition={queuePosition} />
        </div>
        <JobActions
          job={job}
          actionJobId={actionJobId}
          onCancel={onCancel}
          onRetry={onRetry}
          onOpenReport={onOpenReport}
        />
      </div>
      {job.error_message && (
        <p className="report-job-error">{job.error_message}</p>
      )}
    </article>
  );
}

export default function ReportJobsPage({
  client,
  jobs,
  pagination,
  actionJobId,
  onNavigate,
  onCancel,
  onRetry,
  onRefresh,
  onPageChange,
  onOpenReport,
}) {
  const isGlobal = !client;
  const currentQueue = sortCurrentQueue(jobs.filter(isActiveReportJob));
  const waitingJobs = currentQueue.filter(
    (job) => ["queued", "retrying"].includes(job.status),
  );
  const recentHistory = jobs.filter(
    (job) => TERMINAL_REPORT_JOB_STATUSES.has(job.status),
  );
  const currentPage = pagination?.page || 1;
  const pageSize = pagination?.page_size || 20;
  const totalHistory = pagination?.total ?? recentHistory.length;
  const totalPages = pagination?.total_pages || 1;
  const historyStart = totalHistory ? ((currentPage - 1) * pageSize) + 1 : 0;
  const historyEnd = Math.min(currentPage * pageSize, totalHistory);

  function queuePosition(job) {
    const index = waitingJobs.findIndex((item) => item.id === job.id);
    return index >= 0 ? index + 1 : null;
  }

  return (
    <section className="view active report-jobs-page">
      <Breadcrumb
        items={isGlobal
          ? [{ label: "Report Queue" }]
          : [
            { label: "Clients", path: "/clients" },
            {
              label: client.client_name,
              path: `/clients/${clientSlug(client)}`,
            },
            { label: "Report history" },
          ]}
        onNavigate={onNavigate}
      />

      <div className="page-title-row report-jobs-title">
        <div>
          <h1>{isGlobal ? "Report Queue" : "Report generation history"}</h1>
          <p>
            {isGlobal
              ? "Monitor report generation across every client. One report is processed at a time."
              : `All report generation attempts for ${client.client_name}, across every report month.`}
          </p>
        </div>
        <button
          type="button"
          className="secondary-button"
          onClick={onRefresh}
        >
          Refresh
        </button>
      </div>

      <section className="report-queue-section">
        <div className="section-row">
          <div>
            <h2>Current queue</h2>
            <p>Running report first, followed by reports waiting in line.</p>
          </div>
          <span className="report-history-count">
            {currentQueue.length} active
          </span>
        </div>

        {currentQueue.length ? (
          <div className="report-job-list report-current-queue">
            {currentQueue.map((job) => (
              <JobRow
                key={job.id}
                job={job}
                queuePosition={queuePosition(job)}
                actionJobId={actionJobId}
                onCancel={onCancel}
                onRetry={onRetry}
                onOpenReport={onOpenReport}
              />
            ))}
          </div>
        ) : (
          <div className="empty">
            No report is running or waiting in the queue.
          </div>
        )}
      </section>

      <section className="report-history-section">
        <div className="section-row">
          <div>
            <h2>Recent history</h2>
            <p>Completed, failed, and cancelled attempts, newest first.</p>
          </div>
          <span className="report-history-count">
            {historyStart}-{historyEnd} of {totalHistory} jobs
          </span>
        </div>

        {recentHistory.length ? (
          <div className="report-job-list">
            {recentHistory.map((job) => (
              <JobRow
                key={job.id}
                job={job}
                actionJobId={actionJobId}
                onCancel={onCancel}
                onRetry={onRetry}
                onOpenReport={onOpenReport}
              />
            ))}
          </div>
        ) : (
          <div className="empty">
            No completed report generation history yet.
          </div>
        )}

        {totalPages > 1 && (
          <nav className="report-pagination" aria-label="Report history pages">
            <button
              type="button"
              className="secondary-button"
              disabled={currentPage <= 1}
              onClick={() => onPageChange(currentPage - 1)}
            >
              Previous
            </button>
            <span aria-live="polite">
              Page {currentPage} of {totalPages}
            </span>
            <button
              type="button"
              className="secondary-button"
              disabled={currentPage >= totalPages}
              onClick={() => onPageChange(currentPage + 1)}
            >
              Next
            </button>
          </nav>
        )}
      </section>
    </section>
  );
}
