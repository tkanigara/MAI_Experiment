import { formatNumber } from "../lib/format";

export default function CompetitorTable({ rows }) {
  return (
    <div className="table-card">
      <table>
        <thead>
          <tr>
            <th>Profile</th>
            <th>Followers</th>
            <th>Growth Rate</th>
            <th>Total Posts</th>
            <th>Engagement Rate</th>
            <th>Total Engagements</th>
          </tr>
        </thead>
        <tbody>
          {!rows.length ? (
            <tr><td colSpan="6" className="muted">No competitor data imported for this period.</td></tr>
          ) : rows.map((row) => (
            <tr key={row.profile_name}>
              <td>{row.profile_name}</td>
              <td>{formatNumber(row.total_followers)}</td>
              <td className="status-good">{row.follower_growth_rate ? `${row.follower_growth_rate}%` : "-"}</td>
              <td>{formatNumber(row.total_posts)}</td>
              <td>{row.engagement_rate ? `${row.engagement_rate}%` : "-"}</td>
              <td>{formatNumber(row.total_engagement)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
