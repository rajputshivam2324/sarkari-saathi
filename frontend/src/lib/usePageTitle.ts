import { useEffect } from "react";

const SUFFIX = "Sarkari Saathi";

/** Sets document.title for the current page. */
export function usePageTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} | ${SUFFIX}` : `${SUFFIX} | Find government schemes by voice`;
  }, [title]);
}
