import { useEffect, useMemo, useState } from "react";
import AdsPeriodNavigation from "../components/AdsPeriodNavigation";
import Breadcrumb from "../components/Breadcrumb";
import { api } from "../lib/api";
import { adsPeriodSlug, clientSlug, formatDateTime } from "../lib/format";

const ACTOR_STORAGE_KEY = "mai-ads-editor-name";
const TABS = ["campaign", "adset", "ad", "placement"];
const DEFAULT_METRICS = ["result_value", "reach", "impressions", "post_engagements", "link_clicks", "spend", "leads"];

const titleCase = (value) => String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const draftKey = (rowId, field) => `${rowId}:${field}`;

export default function AdsDataEditorPage({ client, period, onNavigate, onSaved, navigationActions }) {
  const [editor, setEditor] = useState(null);
  const [section, setSection] = useState("campaign");
  const [actor, setActor] = useState(() => localStorage.getItem(ACTOR_STORAGE_KEY) || "");
  const [query, setQuery] = useState("");
  const [visibleMetrics, setVisibleMetrics] = useState(DEFAULT_METRICS);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [restoring, setRestoring] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [error, setError] = useState("");
  const basePath = `/api/ads/clients/${client.id}/periods/${period.id}/editor`;
  const pageBase = `/ads/clients/${clientSlug(client)}/${adsPeriodSlug(period)}`;

  async function loadEditor() {
    const payload = await api(basePath);
    setEditor(payload);
    return payload;
  }

  useEffect(() => {
    setEditor(null); setError(""); setDraft({});
    loadEditor().catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client.id, period.id]);

  const rows = editor?.sections?.[section] || [];
  const fields = editor?.definitions?.[section]?.fields || [];
  const nameField = editor?.definitions?.[section]?.name_field;
  const metricFields = fields.filter((field) => field !== nameField);
  const displayedFields = [
    ...(nameField ? [nameField] : []),
    ...visibleMetrics.filter((field) => metricFields.includes(field)),
  ];
  const filteredRows = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return rows;
    return rows.filter((row) => [row.label, row.campaign_name, row.adset_name, row.ad_name, row.publisher_platform, row.placement]
      .some((value) => String(value || "").toLowerCase().includes(normalized)));
  }, [rows, query]);
  const dirtyEntries = Object.entries(draft).filter(([, item]) => item.entity_type === section);

  function updateDraft(row, field, value) {
    setDraft((current) => ({
      ...current,
      [draftKey(row.row_id, field)]: {
        row_id: row.row_id, field, value, entity_type: section,
        version: row.overrides?.[field]?.version ?? null,
      },
    }));
  }

  function effectiveValue(row, field) {
    const pending = draft[draftKey(row.row_id, field)];
    return pending ? pending.value : (row.values?.[field] ?? "");
  }

  async function save() {
    if (actor.trim().length < 2) { setError("Enter your editor name before saving."); return; }
    if (!dirtyEntries.length) return;
    setSaving(true); setError("");
    localStorage.setItem(ACTOR_STORAGE_KEY, actor.trim());
    try {
      const payload = await api(`${basePath}/${section}`, {
        method: "PATCH",
        body: JSON.stringify({ actor: actor.trim(), changes: dirtyEntries.map(([, item]) => item) }),
      });
      setEditor(payload);
      setDraft((current) => {
        const next = { ...current };
        dirtyEntries.forEach(([key]) => delete next[key]);
        return next;
      });
      await onSaved?.();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  async function restore(row, field) {
    const override = row.overrides?.[field];
    if (!override) return;
    if (actor.trim().length < 2) { setError("Enter your editor name before restoring."); return; }
    setRestoring(override.id); setError("");
    try {
      const payload = await api(`${basePath}/overrides/${override.id}/restore`, {
        method: "POST", body: JSON.stringify({ actor: actor.trim() }),
      });
      setEditor(payload);
      setDraft((current) => { const next = { ...current }; delete next[draftKey(row.row_id, field)]; return next; });
      await onSaved?.();
    } catch (err) { setError(err.message); }
    finally { setRestoring(""); }
  }

  return <section className="view active report-editor ads-data-editor">
    <Breadcrumb items={[
      { label: "Clients", path: "/ads/clients" },
      { label: client.client_name, path: `/ads/clients/${clientSlug(client)}` },
      { label: period.period_label, path: pageBase },
      { label: "Edit Ads Data" },
    ]} onNavigate={onNavigate} />
    <div className="page-title-row"><div><span className="eyebrow ads">Data correction</span><h1>Edit Ads Data</h1><p>Correct values in the active snapshot without changing the original Meta API or CSV data.</p></div><button type="button" className="secondary-button" onClick={() => onNavigate(pageBase)}>Back to overview</button></div>
    <AdsPeriodNavigation client={client} period={period} active="edit" onNavigate={onNavigate} {...navigationActions} />

    <div className="editor-identity">
      <label><span>Editor name</span><input value={actor} placeholder="Your name" onChange={(event) => setActor(event.target.value)} /></label>
      <span>Every saved correction is recorded in edit history.</span>
      <button type="button" className="secondary-button" onClick={() => setShowHistory((value) => !value)}>{showHistory ? "Hide history" : "View history"}</button>
    </div>
    {error && <div className="editor-error">{error}</div>}
    {!editor && !error && <div className="empty">Loading Ads data editor...</div>}

    {editor && <>
      <section className="ads-editor-sources content-card"><div><span className="eyebrow ads">Active snapshots</span><strong>{editor.snapshots.length ? `${editor.snapshots.length} platform sources` : "No active snapshot"}</strong></div>{editor.snapshots.map((snapshot) => <div key={snapshot.platform}><strong>{titleCase(snapshot.platform)}</strong><span>{titleCase(snapshot.source)} · {formatDateTime(snapshot.sync_completed_at || snapshot.imported_at)}</span></div>)}</section>
      {!editor.snapshots.length && <div className="empty"><h2>No editable data yet</h2><p>Sync from Meta or import a CSV, then return to this page.</p></div>}
      {!!editor.snapshots.length && <>
        <div className="editor-tabs" role="tablist">{TABS.map((key) => <button type="button" role="tab" aria-selected={section === key} className={section === key ? "active" : ""} key={key} onClick={() => { setSection(key); setQuery(""); }}>{editor.definitions[key].label}<span>{editor.sections[key].length}</span></button>)}</div>
        <div className="ads-editor-toolbar">
          <label className="ads-editor-search"><span>Search rows</span><input value={query} placeholder="Campaign, Ad Set, Ad, or placement" onChange={(event) => setQuery(event.target.value)} /></label>
          <label className="ads-editor-columns"><span>Metric columns</span><select multiple value={visibleMetrics} onChange={(event) => setVisibleMetrics([...event.target.selectedOptions].map((option) => option.value))}>{metricFields.map((field) => <option key={field} value={field}>{editor.metric_definitions[field]?.label || titleCase(field)}</option>)}</select><small>Ctrl/Cmd + click to select multiple.</small></label>
          <div className="ads-editor-save"><span>{dirtyEntries.length} unsaved changes</span><button type="button" className="primary-button" disabled={!dirtyEntries.length || saving} onClick={save}>{saving ? "Saving..." : "Save changes"}</button></div>
        </div>
        <div className="table-scroll ads-editor-table-wrap"><table className="ads-detail-table ads-editor-table"><thead><tr><th>Context</th>{displayedFields.map((field) => <th key={field}>{field === nameField ? titleCase(field) : (editor.metric_definitions[field]?.label || titleCase(field))}</th>)}</tr></thead><tbody>{filteredRows.map((row) => <tr key={row.row_id}><td className="ads-editor-context"><strong>{section === "campaign" ? row.label : (row.campaign_name || "—")}</strong>{section !== "campaign" && <span>{row.adset_name || "—"}</span>}{section === "campaign" && <small>{row.campaign_external_id || "CSV row"}</small>}{section === "placement" && <small>{titleCase(row.publisher_platform)} · {titleCase(row.placement)} · {titleCase(row.device_platform)}</small>}</td>{displayedFields.map((field) => { const override = row.overrides?.[field]; return <td key={field} className={override ? "is-edited" : ""}><div className="ads-editor-cell"><input type={field === nameField ? "text" : "number"} min={field === nameField ? undefined : "0"} step="any" value={effectiveValue(row, field)} aria-label={`${row.label} ${titleCase(field)}`} onChange={(event) => updateDraft(row, field, event.target.value)} />{override && <button type="button" className="inline-action" disabled={restoring === override.id} title={`Original: ${row.source_values?.[field] ?? "empty"}`} onClick={() => restore(row, field)}>{restoring === override.id ? "Restoring..." : "Restore"}</button>}</div></td>; })}</tr>)}</tbody></table>{!filteredRows.length && <div className="empty compact-empty">No rows match this search.</div>}</div>
      </>}
      {showHistory && <aside className="editor-history"><h2>Edit history</h2>{editor.history.length ? editor.history.map((item) => <div key={item.id}><strong>{item.edited_by}</strong><span>{titleCase(item.action)} · {titleCase(item.entity_type)} · {item.entity_label || item.entity_row_id}</span><span>{titleCase(item.field_key)}: {String(item.old_value ?? "—")} → {String(item.new_value ?? "—")}</span><time>{formatDateTime(item.created_at)}</time></div>) : <div>No edits have been saved for this period.</div>}</aside>}
    </>}
  </section>;
}
