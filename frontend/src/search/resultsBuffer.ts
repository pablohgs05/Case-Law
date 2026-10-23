import { searchDecisions, type SearchDecisionResponse, type SearchParams } from '../api/search';
import { PAGE_SIZE } from './filters';

// Pages fetched together. The API charges for the search, not for the rows it
// sends back, so one request for two pages costs about what one page costs.
export const PAGES_PER_BLOCK = 2;

export const BLOCK_SIZE = PAGE_SIZE * PAGES_PER_BLOCK;

export type ResultsPage = {
  total: number;
  results: SearchDecisionResponse['results'];
  page: number;
  page_size: number;
  range_from: number | null;
  range_to: number | null;
};

const blockOf = (page: number) => Math.floor((page - 1) / PAGES_PER_BLOCK) + 1;

const cutOf = ({ page: _page, page_size: _size, ...cut }: SearchParams) => JSON.stringify(cut);

// Only the cut being read is held: a new expression, filter or order replaces
// it whole, so nothing from the previous one can be served by mistake.
let held = {
  cut: '',
  ready: new Map<number, SearchDecisionResponse>(),
  pending: new Map<number, Promise<SearchDecisionResponse>>(),
};

// A search asked for again is asked of the API again: what is held belongs to
// the list being paged through, not to the expression that produced it.
export function resetBuffer() {
  held = { cut: '', ready: new Map(), pending: new Map() };
}

function open(cut: string) {
  if (held.cut !== cut) {
    held = { cut, ready: new Map(), pending: new Map() };
  }
}

function blockFor(params: SearchParams): Promise<SearchDecisionResponse> {
  const cut = cutOf(params);
  open(cut);

  const block = blockOf(params.page ?? 1);
  const known = held.ready.get(block) ?? held.pending.get(block);

  if (known) {
    return Promise.resolve(known);
  }

  // Identity matters: resetting the same cut invalidates older responses too.
  const requestedBuffer = held;
  const pending = searchDecisions({ ...params, page: block, page_size: BLOCK_SIZE });
  requestedBuffer.pending.set(block, pending);

  return pending.then(
    (response) => {
      if (held === requestedBuffer) {
        held.ready.set(block, response);
        held.pending.delete(block);
      }
      return response;
    },
    (failure) => {
      if (held === requestedBuffer) {
        held.pending.delete(block);
      }
      throw failure;
    },
  );
}

function sliceFor(page: number, block: SearchDecisionResponse): ResultsPage {
  const start = ((page - 1) % PAGES_PER_BLOCK) * PAGE_SIZE;
  const results = block.results.slice(start, start + PAGE_SIZE);
  const from = (page - 1) * PAGE_SIZE + 1;

  return {
    total: block.total,
    results,
    page,
    page_size: PAGE_SIZE,
    range_from: results.length > 0 ? from : null,
    range_to: results.length > 0 ? from + results.length - 1 : null,
  };
}

// The page when its block is already in hand. Null means the API has to answer
// first, which is what tells the screen to show that it is loading.
export function heldPage(params: SearchParams): ResultsPage | null {
  if (cutOf(params) !== held.cut) {
    return null;
  }

  const page = params.page ?? 1;
  const block = held.ready.get(blockOf(page));

  return block ? sliceFor(page, block) : null;
}

export async function fetchPage(params: SearchParams): Promise<ResultsPage> {
  return sliceFor(params.page ?? 1, await blockFor(params));
}

// Asked for from the last page of a block only: the next block is what the
// reader turns to next, and the pages before it are already in hand. Nothing is
// asked for past the end of the list.
export function prefetchAfter(params: SearchParams, total: number): void {
  const page = params.page ?? 1;
  const next = page + 1;

  if (page % PAGES_PER_BLOCK !== 0 || (next - 1) * PAGE_SIZE >= total) {
    return;
  }

  void blockFor({ ...params, page: next }).catch(() => undefined);
}
