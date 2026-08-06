export default function TypedNumberInput({ onKeyDown, onWheel, ...props }) {
  function handleKeyDown(event) {
    if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      event.preventDefault();
    }
    onKeyDown?.(event);
  }

  function handleWheel(event) {
    event.currentTarget.blur();
    onWheel?.(event);
  }

  return (
    <input
      {...props}
      type="number"
      onKeyDown={handleKeyDown}
      onWheel={handleWheel}
    />
  );
}
