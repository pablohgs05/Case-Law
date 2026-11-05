import { useEffect, useState } from 'react';
import { listFilterOptions, type FilterOptions } from '../api/filters';

type FilterOptionsState =
  { status: 'loading' } | { status: 'loaded'; options: FilterOptions } | { status: 'failed' };

export type FilterOptionsList = { state: FilterOptionsState; retry: () => void };

// Lives beside useCourts in the page: moving the panel through its portal
// must not repeat the request or discard loaded options.
export function useFilterOptions(): FilterOptionsList {
  const [state, setState] = useState<FilterOptionsState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    listFilterOptions().then(
      (options) => {
        if (active) setState({ status: 'loaded', options });
      },
      () => {
        if (active) setState({ status: 'failed' });
      },
    );
    return () => {
      active = false;
    };
  }, [attempt]);
  return {
    state,
    retry: () => {
      setState({ status: 'loading' });
      setAttempt((current) => current + 1);
    },
  };
}
