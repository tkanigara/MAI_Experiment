import { useEffect, useMemo, useState } from "react";
import Modal, { ModalHeader } from "./Modal";
import { api } from "../lib/api";

export default function MetricDisplaySettingsModal({ client, onClose, onSaved }) {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    api(`/api/ads/clients/${client.id}/metric-configurations`).then((data) => {
      setItems(data.configurations || []);
      const pageObjective = new URLSearchParams(window.location.search).get("objective");
      const first = data.configurations?.find((item) => item.scope === "meta" && item.objective === pageObjective) || data.configurations?.[0];
      if (first) setSelected(`${first.scope}:${first.objective}`);
    }).catch((err) => setError(err.message));
  }, [client.id]);
  const current = useMemo(() => items.find((item) => `${item.scope}:${item.objective}` === selected), [items, selected]);
  function update(keys) {
    setItems((all) => all.map((item) => item === current ? { ...item, metric_keys: keys } : item));
  }
  function move(index, offset) {
    const keys = [...current.metric_keys];
    const next = index + offset;
    if (next < 0 || next >= keys.length) return;
    [keys[index], keys[next]] = [keys[next], keys[index]];
    update(keys);
  }
  async function save() {
    setSaving(true); setError("");
    try {
      const saved = await api(`/api/ads/clients/${client.id}/metric-configurations/${current.scope}/${current.objective}`, { method: "PUT", body: JSON.stringify({ metric_keys: current.metric_keys }) });
      await onSaved?.(saved);
    } catch (err) { setError(err.message); } finally { setSaving(false); }
  }
  async function reset() {
    setSaving(true); setError("");
    try {
      const saved = await api(`/api/ads/clients/${client.id}/metric-configurations/${current.scope}/${current.objective}`, { method: "DELETE" });
      update(saved.metric_keys);
    } catch (err) { setError(err.message); } finally { setSaving(false); }
  }
  return <Modal onClose={onClose} wide>
    <ModalHeader title="Metric Display Settings" subtitle="Applies to every month and campaign for this client. Meta settings are shared by All Meta, Instagram, and Facebook." onClose={onClose} />
    <div className="modal-body metric-settings-body">
      {error && <div className="import-alert danger">{error}</div>}
      {!items.length && !error ? <div className="empty compact-empty">Loading metric catalog...</div> : <>
        <label className="field"><span>Platform and objective</span><select value={selected} onChange={(event) => setSelected(event.target.value)}>{items.map((item) => <option key={`${item.scope}:${item.objective}`} value={`${item.scope}:${item.objective}`}>{item.scope_label} · {item.objective_label}{!item.available ? " (Coming soon)" : ""}</option>)}</select></label>
        {current && <>
          <div className="settings-note"><strong>{current.available_metrics.length} metrics available.</strong> {current.default_metric_keys.length} are selected by default for {current.objective_label}. Your selection controls both the summary cards and detailed table columns. An empty selection is allowed.</div>
          <div className="metric-picker-grid">
            <div><h3>Available metrics</h3><div className="metric-check-list">{current.available_metrics.map((metric) => <label key={metric.key}><input type="checkbox" checked={current.metric_keys.includes(metric.key)} onChange={() => update(current.metric_keys.includes(metric.key) ? current.metric_keys.filter((key) => key !== metric.key) : [...current.metric_keys, metric.key])} /><span>{metric.label}</span><small>{current.default_metric_keys.includes(metric.key) ? `Default · ${metric.formula || metric.format}` : metric.formula || metric.format}</small></label>)}</div></div>
            <div><h3>Display order</h3><div className="metric-order-list">{current.metric_keys.length ? current.metric_keys.map((key, index) => { const metric = current.available_metrics.find((item) => item.key === key); return <div key={key}><span>{index + 1}. {metric?.label || key}</span><span><button type="button" aria-label={`Move ${metric?.label} up`} onClick={() => move(index, -1)}>↑</button><button type="button" aria-label={`Move ${metric?.label} down`} onClick={() => move(index, 1)}>↓</button></span></div>; }) : <div className="empty compact-empty">No metrics selected.</div>}</div></div>
          </div>
          <div className="modal-actions"><button type="button" className="secondary-button" onClick={reset} disabled={saving}>Reset to default</button><button type="button" className="secondary-button" onClick={onClose}>Close</button><button type="button" className="primary-button" onClick={save} disabled={saving}>{saving ? "Saving..." : "Save settings"}</button></div>
        </>}
      </>}
    </div>
  </Modal>;
}
