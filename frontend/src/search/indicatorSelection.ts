import type { Highlight, SearchParams } from '../api/search';
import { outcomeLabel } from '../components/outcomeFormat';

export type Granularity = 'month' | 'quarter' | 'year';
export type IndicatorPoint =
  | { kind: 'court'; court: string; count: number }
  | { kind: 'outcome'; outcome: string; count: number }
  | { kind: 'period'; period: string; granularity: Granularity; count: number };

export type IndicatorSelection = {
  label: string;
  count: number;
  // Null is an empty intersection, never an unrestricted search.
  params: SearchParams | null;
  expression: string;
  original: SearchParams;
  originalTotal: number;
  filterCount: number;
  contextLabel: string;
  contextActive: boolean;
};

export function formatPeriodLabel(period: string, granularity: Granularity = 'month'): string {
  const [year, month] = period.split('-').map(Number);
  if (granularity === 'year') return String(year);
  if (granularity === 'quarter') return `${Math.ceil(month / 3)}T/${year}`;
  const months = [
    'Jan',
    'Fev',
    'Mar',
    'Abr',
    'Mai',
    'Jun',
    'Jul',
    'Ago',
    'Set',
    'Out',
    'Nov',
    'Dez',
  ];
  return `${months[month - 1]}/${String(year).slice(-2)}`;
}

// Add one condition to the applied cut. In particular, choosing a year must
// never widen a date range that already restricts the search to part of it.
export function selectIndicator(
  original: SearchParams,
  point: IndicatorPoint,
  context = { total: 0, filterCount: 0 },
): IndicatorSelection {
  const params = { ...original, page: 1 };
  let label: string;
  let compatible: boolean;
  if (point.kind === 'court') {
    label = point.court;
    compatible = !params.tribunal?.length || params.tribunal.includes(point.court);
    params.tribunal = [point.court];
  } else if (point.kind === 'outcome') {
    label = outcomeLabel(point.outcome);
    compatible = !params.resultado?.length || params.resultado.includes(point.outcome);
    params.resultado = [point.outcome];
    // The classification was read from the dispositive, so that is where the
    // snippet is cut. Court and period are copied fields: no passage to point
    // at, and the reader's own terms stay the right thing to highlight.
    params.highlight = 'resultado' satisfies Highlight;
  } else {
    label = formatPeriodLabel(point.period, point.granularity);
    const [year, month] = point.period.split('-').map(Number);
    const startMonth =
      point.granularity === 'year'
        ? 1
        : point.granularity === 'quarter'
          ? Math.floor((month - 1) / 3) * 3 + 1
          : month;
    const months = point.granularity === 'year' ? 12 : point.granularity === 'quarter' ? 3 : 1;
    const start = `${year}-${String(startMonth).padStart(2, '0')}-01`;
    // UTC keeps leap days and inclusive period ends independent of local time.
    const end = new Date(Date.UTC(year, startMonth - 1 + months, 0)).toISOString().slice(0, 10);
    params.date_from = params.date_from && params.date_from > start ? params.date_from : start;
    params.date_to = params.date_to && params.date_to < end ? params.date_to : end;
    compatible = params.date_from <= params.date_to;
  }
  const category =
    point.kind === 'court' ? 'Tribunal' : point.kind === 'outcome' ? 'Resultado' : 'Período';
  return {
    label,
    count: point.count,
    params: compatible ? params : null,
    expression: original.q,
    original: { ...original, page: 1 },
    originalTotal: context.total,
    filterCount: context.filterCount,
    contextLabel: `${category}: ${label}`,
    contextActive: true,
  };
}
