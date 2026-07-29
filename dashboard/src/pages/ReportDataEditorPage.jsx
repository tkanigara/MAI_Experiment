import { useEffect, useMemo, useState } from "react";
import Breadcrumb from "../components/Breadcrumb";
import { api } from "../lib/api";
import { clientSlug } from "../lib/format";

const TABS = [
  ["general", "General & Overview"],
  ["instagram", "Instagram"],
  ["facebook", "Facebook"],
  ["tiktok", "TikTok"],
  ["youtube", "YouTube"],
  ["kpi", "KPI"],
  ["competitor", "Competitor"],
  ["content", "Content & Evidence"],
  ["demographics", "Demographics"],
  ["website_ads", "Website & Ads"],
  ["advanced", "Advanced"],
];

const ACTOR_STORAGE_KEY = "mai-report-editor-name";

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function inputValue(field, draft) {
  const value = Object.prototype.hasOwnProperty.call(draft, field.id)
    ? draft[field.id]
    : field.value;
  if (value === null || value === undefined) return "";
  if (field.value_type === "json") {
    return typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }
  if (field.value_type === "datetime") {
    return String(value).replace("Z", "").slice(0, 16);
  }
  return String(value);
}

function fieldSearchText(field) {
  return [
    field.label,
    field.field_key,
    field.platform,
    field.post_id,
    field.profile_name,
    field.caption,
    ...(field.placeholders || []),
  ].filter(Boolean).join(" ").toLowerCase();
}

function AffectedPlaceholders({ placeholders = [] }) {
  if (!placeholders.length) return <span className="editor-muted">No direct alias</span>;
  return (
    <div className="editor-aliases">
      {placeholders.slice(0, 4).map((placeholder) => (
        <code key={placeholder}>{placeholder}</code>
      ))}
      {placeholders.length > 4 ? <span>+{placeholders.length - 4}</span> : null}
    </div>
  );
}

function FieldInput({
  field,
  draft,
  onChange,
  onUpload,
  actor,
  uploading,
  manualEnabled = true,
}) {
  const value = inputValue(field, draft);
  const commonProps = {
    value,
    disabled: field.override_scope === "derived" && !manualEnabled,
    onChange: (event) => onChange(field.id, event.target.value),
  };
  let control;
  if (field.value_type === "json") {
    control = <textarea rows="5" {...commonProps} />;
  } else if (field.value_type === "datetime") {
    control = <input type="datetime-local" {...commonProps} />;
  } else {
    control = (
      <input
        type={field.value_type === "number" || field.value_type === "percent" ? "number" : "text"}
        step="any"
        {...commonProps}
      />
    );
  }

  return (
    <div className="editor-input-stack">
      {control}
      {field.value_type === "url" ? (
        <label className={`editor-upload-button ${!actor || uploading ? "disabled" : ""}`}>
          {uploading ? "Uploading..." : "Upload image"}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            disabled={!actor || uploading}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload(field, file);
              event.target.value = "";
            }}
          />
        </label>
      ) : null}
    </div>
  );
}

function FriendlyFieldRow(props) {
  const {
    field,
    draft,
    onChange,
    onRestore,
    restoring,
    manualEnabled,
    onManualEnabled,
  } = props;
  return (
    <div className="editor-field-row">
      <div className="editor-field-heading">
        <div>
          <strong>{field.label}</strong>
          <code>{field.field_key}</code>
        </div>
        <span className={`editor-status ${field.status}`}>{field.status}</span>
      </div>
      {field.override_scope === "derived" && field.status !== "edited" ? (
        <label className="editor-manual-toggle">
          <input
            type="checkbox"
            checked={manualEnabled}
            onChange={(event) => onManualEnabled(field.id, event.target.checked)}
          />
          Enable manual override for this calculated value
        </label>
      ) : null}
      <div className="editor-field-grid">
        <div>
          <span className="editor-label">Source value</span>
          <div className="editor-source">{displayValue(field.source_value)}</div>
        </div>
        <div>
          <span className="editor-label">Effective value</span>
          <FieldInput {...props} manualEnabled={field.status === "edited" || manualEnabled} />
        </div>
        <div>
          <span className="editor-label">Affected placeholders</span>
          <AffectedPlaceholders placeholders={field.placeholders} />
        </div>
      </div>
      <div className="editor-field-footer">
        <span className={field.warning ? "editor-warning" : ""}>
          {field.warning || (field.edited_by ? `Last edited by ${field.edited_by}` : "No manual correction")}
        </span>
        {field.override_id ? (
          <button
            type="button"
            className="text-link"
            disabled={restoring === field.override_id}
            onClick={() => onRestore(field)}
          >
            {restoring === field.override_id ? "Restoring..." : "Restore"}
          </button>
        ) : null}
      </div>
    </div>
  );
}

function ContentTable({ fields, draft, onChange, onUpload, actor, uploading }) {
  const groups = useMemo(() => {
    const result = new Map();
    fields.forEach((field) => {
      const parts = field.id.split("|");
      const key = `${parts[1]}|${parts[2]}`;
      if (!result.has(key)) result.set(key, {});
      result.get(key)[field.field_key] = field;
    });
    return [...result.entries()].map(([id, values]) => ({ id, values }));
  }, [fields]);

  const getField = (group, key) => group.values[key];
  const renderInput = (group, key) => {
    const field = getField(group, key);
    if (!field) return null;
    return (
      <FieldInput
        field={field}
        draft={draft}
        onChange={onChange}
        onUpload={onUpload}
        actor={actor}
        uploading={uploading === field.id}
      />
    );
  };

  return (
    <div className="editor-content-table-wrap">
      <table className="editor-content-table">
        <thead>
          <tr>
            <th>Content</th>
            <th>Caption & Date</th>
            <th>Type & Links</th>
            <th>Metrics</th>
            <th>Bucket</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => {
            const sample = Object.values(group.values)[0] || {};
            return (
              <tr key={group.id}>
                <td>
                  <strong>{sample.profile_name || sample.platform || "Content"}</strong>
                  <span>{sample.post_id || "No post ID"}</span>
                </td>
                <td>
                  {renderInput(group, "caption")}
                  {renderInput(group, "published_at")}
                </td>
                <td>
                  {renderInput(group, "content_type")}
                  {renderInput(group, "permalink")}
                  {renderInput(group, "image_url")}
                </td>
                <td>
                  <div className="editor-metric-inputs">
                    {["likes", "comments", "shares", "saves", "reposts", "views", "reach", "total_engagement", "engagement_rate"].map((key) => {
                      const field = getField(group, key);
                      return field ? (
                        <label key={key}>
                          <span>{field.label}</span>
                          {renderInput(group, key)}
                        </label>
                      ) : null;
                    })}
                  </div>
                </td>
                <td>
                  {renderInput(group, "performance_bucket")}
                  {renderInput(group, "content_rank")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function ReportDataEditorPage({
  client,
  month,
  onNavigate,
  onSaved,
}) {
  const [editor, setEditor] = useState(null);
  const [section, setSection] = useState("general");
  const [draft, setDraft] = useState({});
  const [actor, setActor] = useState(() => localStorage.getItem(ACTOR_STORAGE_KEY) || "");
  const [query, setQuery] = useState("");
  const [missingOnly, setMissingOnly] = useState(false);
  const [editedOnly, setEditedOnly] = useState(false);
  const [limit, setLimit] = useState(200);
  const [saving, setSaving] = useState(false);
  const [restoring, setRestoring] = useState("");
  const [uploading, setUploading] = useState("");
  const [history, setHistory] = useState(null);
  const [manualOverrides, setManualOverrides] = useState({});
  const [error, setError] = useState("");
  const basePath = `/api/clients/${client.id}/report-periods/${month.id}`;

  async function loadEditor() {
    const payload = await api(`${basePath}/editor`);
    setEditor(payload);
  }

  useEffect(() => {
    loadEditor().catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client.id, month.id]);

  useEffect(() => {
    setLimit(200);
  }, [section, query, missingOnly, editedOnly]);

  const sectionFields = editor?.sections?.[section] || [];
  const filteredFields = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return sectionFields.filter((field) => {
      if (missingOnly && field.status !== "missing") return false;
      if (editedOnly && field.status !== "edited" && !Object.prototype.hasOwnProperty.call(draft, field.id)) return false;
      return !normalizedQuery || fieldSearchText(field).includes(normalizedQuery);
    });
  }, [sectionFields, query, missingOnly, editedOnly, draft]);
  const visibleFields = filteredFields.slice(0, limit);
  const dirtyIds = Object.keys(draft).filter((id) => (
    sectionFields.some((field) => field.id === id)
  ));

  function updateDraft(id, value) {
    setDraft((current) => ({ ...current, [id]: value }));
  }

  async function saveSection() {
    if (actor.trim().length < 2) {
      setError("Enter your editor name before saving.");
      return;
    }
    if (!dirtyIds.length) return;
    setSaving(true);
    setError("");
    localStorage.setItem(ACTOR_STORAGE_KEY, actor.trim());
    try {
      await api(`${basePath}/editor/sections/${section}`, {
        method: "PATCH",
        body: JSON.stringify({
          actor: actor.trim(),
          version: editor.versions[section] || 0,
          changes: dirtyIds.map((id) => ({ id, value: draft[id] })),
        }),
      });
      setDraft((current) => {
        const next = { ...current };
        dirtyIds.forEach((id) => delete next[id]);
        return next;
      });
      await loadEditor();
      await onSaved?.();
    } catch (err) {
      setError(err.message);
      if (err.message.toLowerCase().includes("changed after")) {
        await loadEditor();
      }
    } finally {
      setSaving(false);
    }
  }

  async function restoreField(field) {
    if (!actor.trim()) {
      setError("Enter your editor name before restoring a value.");
      return;
    }
    setRestoring(field.override_id);
    setError("");
    try {
      await api(`${basePath}/overrides/${field.override_id}/restore`, {
        method: "POST",
        body: JSON.stringify({ actor: actor.trim() }),
      });
      setDraft((current) => {
        const next = { ...current };
        delete next[field.id];
        return next;
      });
      await loadEditor();
      await onSaved?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setRestoring("");
    }
  }

  async function uploadAsset(field, file) {
    setUploading(field.id);
    setError("");
    const body = new FormData();
    body.append("actor", actor.trim());
    if (field.platform) body.append("platform", field.platform);
    body.append("file", file);
    try {
      const asset = await api(`${basePath}/assets`, { method: "POST", body });
      updateDraft(field.id, asset.public_url);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading("");
    }
  }

  async function toggleHistory() {
    if (history) {
      setHistory(null);
      return;
    }
    try {
      setHistory(await api(`${basePath}/edit-history`));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="view active report-editor">
      <Breadcrumb
        items={[
          { label: "Clients", path: "/clients" },
          { label: client.client_name, path: `/clients/${clientSlug(client)}` },
          { label: month.label, path: `/clients/${clientSlug(client)}/${month.slug}` },
          { label: "Edit Report Data" },
        ]}
        onNavigate={onNavigate}
      />
      <div className="page-title-row">
        <div>
          <h1>Edit Report Data</h1>
          <p>Correct imported values and placeholder output for {month.label}.</p>
        </div>
        <div className="page-actions">
          <button type="button" className="secondary-button" onClick={toggleHistory}>
            {history ? "Hide History" : `History (${editor?.history_count || 0})`}
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={saving || !dirtyIds.length}
            onClick={saveSection}
          >
            {saving ? "Saving..." : `Save ${dirtyIds.length || ""}`.trim()}
          </button>
        </div>
      </div>

      <div className="editor-identity">
        <label>
          Editor name
          <input
            value={actor}
            maxLength="80"
            placeholder="Your name"
            onChange={(event) => setActor(event.target.value)}
          />
        </label>
        <span>Saved locally for your next edit. Login and roles are not enabled yet.</span>
      </div>

      {error ? <div className="editor-error">{error}</div> : null}

      <div className="editor-tabs" role="tablist">
        {TABS.map(([key, label]) => (
          <button
            type="button"
            className={section === key ? "active" : ""}
            key={key}
            onClick={() => setSection(key)}
          >
            {label}
            <span>{editor?.sections?.[key]?.length || 0}</span>
          </button>
        ))}
      </div>

      <div className="editor-toolbar">
        <input
          className="search-input"
          value={query}
          placeholder="Search fields, post IDs, or placeholders"
          onChange={(event) => setQuery(event.target.value)}
        />
        <label>
          <input type="checkbox" checked={missingOnly} onChange={(event) => setMissingOnly(event.target.checked)} />
          Missing only
        </label>
        <label>
          <input type="checkbox" checked={editedOnly} onChange={(event) => setEditedOnly(event.target.checked)} />
          Edited only
        </label>
        <span>{filteredFields.length} fields</span>
      </div>

      {history ? (
        <section className="editor-history">
          <h2>Edit History</h2>
          {history.length ? history.slice(0, 100).map((item) => (
            <div key={item.id}>
              <strong>{item.field_key}</strong>
              <span>{item.action} by {item.edited_by}</span>
              <time>{new Date(item.created_at).toLocaleString()}</time>
            </div>
          )) : <p>No edits have been recorded.</p>}
        </section>
      ) : null}

      {!editor ? <div className="empty">Loading report data...</div> : null}
      {editor && section === "content" ? (
        <ContentTable
          fields={visibleFields}
          draft={draft}
          onChange={updateDraft}
          onUpload={uploadAsset}
          actor={actor}
          uploading={uploading}
        />
      ) : (
        <div className="editor-fields">
          {visibleFields.map((field) => (
            <FriendlyFieldRow
              key={field.id}
              field={field}
              draft={draft}
              onChange={updateDraft}
              onUpload={uploadAsset}
              actor={actor}
              uploading={uploading === field.id}
              onRestore={restoreField}
              restoring={restoring}
              manualEnabled={Boolean(manualOverrides[field.id])}
              onManualEnabled={(id, enabled) => setManualOverrides((current) => ({
                ...current,
                [id]: enabled,
              }))}
            />
          ))}
        </div>
      )}
      {editor && !filteredFields.length ? <div className="empty">No fields match this filter.</div> : null}
      {filteredFields.length > visibleFields.length ? (
        <button type="button" className="secondary-button editor-load-more" onClick={() => setLimit((value) => value + 200)}>
          Show 200 more
        </button>
      ) : null}
    </section>
  );
}
