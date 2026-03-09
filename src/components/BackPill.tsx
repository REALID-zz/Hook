import { useNavigate } from 'react-router-dom';

export function BackPill(props: { fallbackHref?: string }) {
  const nav = useNavigate();

  return (
    <button
      type="button"
      className="softBtn"
      onClick={() => {
        // Navigate back if possible; otherwise fall back to a safe route.
        try {
          nav(-1);
        } catch {
          nav(props.fallbackHref ?? '/');
        }
      }}
      aria-label="返回"
    >
      <span aria-hidden="true">←</span>
      <span>返回</span>
    </button>
  );
}

