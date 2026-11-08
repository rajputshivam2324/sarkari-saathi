import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/**
 * Restores expected browser scroll behaviour for a client-side router:
 * - navigating to a new path scrolls to the top
 * - navigating to a path with a #hash scrolls that element into view
 * Query-string-only changes (e.g. ?page=2) are handled by the page itself.
 */
export function ScrollManager() {
  const { pathname, hash } = useLocation();

  useEffect(() => {
    if (hash) {
      const id = decodeURIComponent(hash.slice(1));
      // Wait a frame so the target section has rendered.
      const raf = requestAnimationFrame(() => {
        document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      return () => cancelAnimationFrame(raf);
    }
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [pathname, hash]);

  return null;
}
