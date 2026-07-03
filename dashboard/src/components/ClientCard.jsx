import { PlatformBadges } from "./Badges";
import { platformFlags } from "../lib/format";
import OpenIconButton from "./OpenIconButton";

export default function ClientCard({ client, onOpen, onEdit, onDelete }) {
  const platforms = platformFlags(client);
  return (
    <article className="client-card">
      <div className="card-main">
        <div className="client-head">
          <div>
            <div className="client-title">{client.client_name}</div>
            <div className="client-code">{client.client_code || client.id}</div>
          </div>
          <OpenIconButton label={`Open ${client.client_name}`} onClick={() => onOpen(client.id)} />
        </div>
        <PlatformBadges platforms={platforms} />
        <div className="client-meta">
          <span>{platforms.length || client.connected_profiles || 0} connected profiles</span>
          <span>{client.industry || "No industry"}</span>
        </div>
      </div>
      <div className="card-footer">
        <button className="text-link client-footer-link" type="button" onClick={() => onEdit(client)}>
          Edit
        </button>
        <button
          className="danger-link"
          type="button"
          onClick={() => onDelete(client)}
        >
          Delete
        </button>
      </div>
    </article>
  );
}
