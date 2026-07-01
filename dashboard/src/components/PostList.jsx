import { captionText, formatNumber } from "../lib/format";

export default function PostList({ posts }) {
  if (!posts.length) return <div className="empty">No content data available.</div>;
  return (
    <div className="post-list">
      {posts.slice(0, 3).map((post, index) => (
        <article className="post-card" key={post.post_id || index}>
          <div className="post-thumb">view</div>
          <div>
            <div className="post-title">{captionText(post)}</div>
            <div className="post-meta">
              {formatNumber(post.likes)} likes · {formatNumber(post.comments)} comments ·{" "}
              {formatNumber(post.shares)} shares
            </div>
          </div>
          <div className="post-score">
            <span>Engagement</span>
            <strong>{formatNumber(post.total_engagement)}</strong>
          </div>
        </article>
      ))}
    </div>
  );
}
