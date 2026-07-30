import Breadcrumb from "../components/Breadcrumb";
import { clientSlug } from "../lib/format";

export const ACTIVE_REPORT_JOB_STATUSES = new Set([
  "queued",
  "running",
  "retrying",
  "cancel_requested",
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

export function reportJobStageLabel(stage) {
  return {
    queued: "Waiting for worker",
    analysis: "Analyzing data with Gemini",
    slides: "Generating Google Slides",
    cancel_requested: "Stopping at the next safe checkpoint",
    completed: "Report ready",
    failed: "Generation stopped",
    cancelled: "Generation cancelled",
  }[stage] || String(stage || "Waiting").replaceAll("_", " ");
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

function JobSummary({ job }) {
  return (
    <div className="report-job-summary">
      <span className={`report-job-status ${job.status}`}>
        {reportJobStatusLabel(job.status)}
      </span>
      <span>{reportJobStageLabel(job.current_stage)}</span>
      <span>
        Attempt {job.attempt_count || 0}/{job.max_attempts || 3}
      </span>
      <span>{formatJobTime(job.created_at || job.queued_at)}</span>
    </div>
  );
}

export default function ReportJobsPage({
  client,
  month,
  jobs,
  actionJobId,
  onNavigate,
  onGenerate,
  onCancel,
  onRetry,
  onRefresh,
  onOpenReport,
}) {
  const activeJob = jobs.find(isActiveReportJob);
  const isCreating = actionJobId === `create:${month.id}`;

  return (
    <section className="view active report-jobs-page">
      <Breadcrumb
        items={[
          { label: "Clients", path: "/clients" },
          {
            label: client.client_name,
            path: `/clients/${clientSlug(client)}`,
          },
          {
            label: month.label,
            path: `/clients/${clientSlug(client)}/${month.slug}`,
          },
          { label: "Generation history" },
        ]}
        onNavigate={onNavigate}
      />

      <div className="page-title-row">
        <div>
          <h1>Report generation</h1>
          <p>
            Queue status and generation history for {client.client_name}{" "}
            {month.label}.
          </p>
        </div>
        <div className="page-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={onRefresh}
          >
            Refresh
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={Boolean(activeJob) || isCreating}
            onClick={() => onGenerate(month)}
          >
            {isCreating
              ? "Adding to queue..."
              : activeJob
                ? reportJobStatusLabel(activeJob.status)
                : "Generate report"}
          </button>
        </div>
      </div>

      {activeJob && (
        <section className="report-active-job">
          <div>
            <p className="report-section-eyebrow">Active generation</p>
            <h2>{reportJobStageLabel(activeJob.current_stage)}</h2>
            <JobSummary job={activeJob} />
          </div>
          <JobActions
            job={activeJob}
            actionJobId={actionJobId}
            onCancel={onCancel}
            onRetry={onRetry}
            onOpenReport={onOpenReport}
          />
        </section>
      )}

      <section className="report-history-section">
        <div className="section-row">
          <div>
            <h2>Generation history</h2>
            <p>Newest attempts are shown first.</p>
          </div>
          <span className="report-history-count">{jobs.length} jobs</span>
        </div>

        {jobs.length ? (
          <div className="report-job-list">
            {jobs.map((job) => (
              <article className="report-job-row" key={job.id}>
                <div className="report-job-row-main">
                  <div>
                    <h3>
                      {job.report_name
                        || `${job.client_name_snapshot} - ${job.period_label_snapshot}`}
                    </h3>
                    <JobSummary job={job} />
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
            ))}
          </div>
        ) : (
          <div className="empty">
            No generation history yet. Click Generate report to create the
            first background job.
          </div>
        )}
      </section>
    </section>
  );
}
