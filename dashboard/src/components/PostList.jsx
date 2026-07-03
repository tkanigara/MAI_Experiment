import { captionText, formatNumber } from "../lib/format";

const CONTENT_TYPE_LABELS = {
  post: "Feed post",
  story: "Story",
  video: "Video",
};

function contentTypeLabel(type) {
  return CONTENT_TYPE_LABELS[type] || String(type || "Content").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function proxiedImageUrl(url) {
  return url ? `/api/image-proxy?url=${encodeURIComponent(url)}` : "";
}

export default function PostList({ posts }) {
  if (!posts.length) return <div className="empty">No content data available.</div>;
  return (
    <div className="post-list">
      {posts.slice(0, 3).map((post, index) => (
        <article className="post-card" key={post.post_id || index}>
          <div className={`post-thumb ${post.image_url ? "" : "is-empty"}`}>
            {post.image_url && (
              <img
                src={proxiedImageUrl(post.image_url)}
                alt=""
                loading="lazy"
                referrerPolicy="no-referrer"
                onError={(event) => {
                  if (!event.currentTarget.dataset.usedFallback && post.image_url) {
                    event.currentTarget.dataset.usedFallback = "1";
                    event.currentTarget.src = post.image_url;
                    return;
                  }
                  event.currentTarget.closest(".post-thumb")?.classList.add("is-empty");
                }}
              />
            )}
            <span className="thumb-placeholder">{contentTypeLabel(post.content_type)}</span>
          </div>
          <div>
            <div className="post-title">{captionText(post)}</div>
            <div className="post-type">{contentTypeLabel(post.content_type)}</div>
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
