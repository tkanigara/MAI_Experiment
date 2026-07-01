import { PlatformBadges } from "./Badges";
import { platformFlags } from "../lib/format";

export default function ClientCard({ client, onOpen, onDelete }) {
  const platforms = platformFlags(client);
  return (
    <article className="client-card" onClick={() => onOpen(client.id)}>
      <div className="card-main">
        <div className="client-head">
          <div>
            <div className="client-title">{client.client_name}</div>
            <div className="client-code">{client.client_code || client.id}</div>
          </div>
          {client.industry && <span className="badge">{client.industry}</span>}
        </div>
        <PlatformBadges platforms={platforms} />
        <div className="client-meta">
          <span>{platforms.length || client.connected_profiles || 0} connected profiles</span>
          <span>{client.industry || "No industry"}</span>
        </div>
      </div>
      <div className="card-footer">
        <button className="text-link" type="button">Open client</button>
        <button
          className="danger-link"
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onDelete(client);
          }}
        >
          Delete
        </button>
      </div>
    </article>
  );
}
