import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react';

import { SearchSessionContext } from './session';

function SearchSessionProvider({ children }: { children: ReactNode }) {
  const [values, setValues] = useState<Record<string, unknown>>({});
  const latestSearch = useRef(0);

  const startSearch = useCallback(() => ++latestSearch.current, []);
  const isLatestSearch = useCallback((id: number) => id === latestSearch.current, []);

  const session = useMemo(
    () => ({ values, setValues, startSearch, isLatestSearch }),
    [values, startSearch, isLatestSearch],
  );

  return <SearchSessionContext.Provider value={session}>{children}</SearchSessionContext.Provider>;
}

export default SearchSessionProvider;
