import {
  createContext,
  useCallback,
  useContext,
  useRef,
  type Dispatch,
  type SetStateAction,
} from 'react';

// The search as the reader left it — expression, filters, order, results,
// total — held above the routes, so it outlives the screen that shows it. A
// decision opened and closed again, or a list that unmounts and comes back,
// finds it as it was, with no new request. It lives as long as the tab does:
// nothing is written anywhere between sessions.
export type SearchSession = {
  values: Record<string, unknown>;
  setValues: Dispatch<SetStateAction<Record<string, unknown>>>;
  // Which search may still write to the screen. Kept here, not in the screen,
  // so an answer to a search started before a remount cannot overwrite one
  // started after it. `startSearch` names a new search; `isLatestSearch` says
  // whether an answer still belongs on screen.
  startSearch: () => number;
  isLatestSearch: (id: number) => boolean;
};

export const SearchSessionContext = createContext<SearchSession | null>(null);

export function useSearchSession(): SearchSession {
  const session = useContext(SearchSessionContext);
  if (!session) {
    throw new Error('useSearchSession must be used inside SearchSessionProvider.');
  }
  return session;
}

// Like useState, but the value belongs to the session instead of the
// component, so it survives the component being unmounted.
export function useSessionState<T>(key: string, initial: T): [T, Dispatch<SetStateAction<T>>] {
  const { values, setValues } = useSearchSession();
  const initialValue = useRef(initial);

  const value = (key in values ? values[key] : initial) as T;

  const setValue = useCallback<Dispatch<SetStateAction<T>>>(
    (next) =>
      setValues((current) => {
        const previous = (key in current ? current[key] : initialValue.current) as T;
        const resolved = typeof next === 'function' ? (next as (value: T) => T)(previous) : next;
        return { ...current, [key]: resolved };
      }),
    [key, setValues],
  );

  return [value, setValue];
}
