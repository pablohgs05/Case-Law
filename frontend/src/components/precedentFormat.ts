import type {
  Adherence,
  AdherenceCount,
  AdherenceShare,
  CitedPrecedent,
  MostCited,
} from '../api/precedents';

export type AdherenceState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  | { status: 'loaded'; adherence: AdherenceShare };

export type MostCitedState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  | { status: 'loaded'; precedents: MostCited[] };

export const ADHERENCE_LABELS: Record<string, string> = {
  seguiu: 'Seguiu',
  afastou: 'Afastou',
  distinguiu: 'Distinguiu',
  mencionou: 'Apenas mencionou',
  indeterminado: 'Não foi possível determinar',
};

// What each label means, said once beside the chart rather than left to the
// reader to infer from the verb.
export const ADHERENCE_MEANINGS: Record<string, string> = {
  seguiu: 'a decisão aplicou o precedente ao caso',
  afastou: 'a decisão expressamente não o aplicou',
  distinguiu: 'a decisão reconheceu o precedente e o diferenciou do caso',
  mencionou: 'a citação é referência, sem juízo de aplicação',
  indeterminado: 'a redação não permitiu decidir',
};

export const adherenceLabel = (adherence: string) => ADHERENCE_LABELS[adherence] ?? adherence;

export const KIND_LABELS: Record<string, string> = {
  sumula: 'Súmula',
  tema: 'Tema',
};

// "Súmula 284 do STF", the way a petition would name it. Without a court in
// the ementa the name stops at the number: "Tema 793 do STJ" would be a claim
// the decision never made, and both courts have a Tema 793.
export function precedentName(precedent: {
  court: string;
  kind: string;
  number: number | null;
  court_stated?: boolean;
}): string {
  const kind = KIND_LABELS[precedent.kind] ?? precedent.kind;
  const number = precedent.number === null ? '' : ` ${precedent.number}`;
  const court = precedent.court_stated === false ? '' : ` do ${precedent.court}`;
  return `${kind}${number}${court}`;
}

// Three states, not two. A null status is "we do not know", which is why it
// never reads as "in force": presenting a cancelled precedent as current is
// the error this refuses to risk.
export type Standing = 'superseded' | 'current' | 'unknown';

export function standingOf(status: string | null): Standing {
  if (!status) {
    return 'unknown';
  }

  const folded = status.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

  if (/cancelad|superad|revogad|prejudicad/.test(folded)) {
    return 'superseded';
  }
  return 'current';
}

// The official portals, which hold the authoritative wording. The catalogue
// carries no link of its own, so these are built from the precedent's own
// numbering. The STJ's súmula search answers 403 to anything that is not a
// browser, which is why it cannot be checked from a script — it opens for a
// reader.
export function officialUrl(precedent: {
  court: string;
  kind: string;
  number: number | null;
}): string | null {
  if (precedent.number === null) {
    return null;
  }

  if (precedent.kind === 'tema' && precedent.court === 'STJ') {
    return (
      'https://processo.stj.jus.br/repetitivos/temas_repetitivos/pesquisa.jsp' +
      `?novaConsulta=true&tipo_pesquisa=T&cod_tema_inicial=${precedent.number}` +
      `&cod_tema_final=${precedent.number}`
    );
  }

  if (precedent.kind === 'sumula' && precedent.court === 'STF') {
    return (
      'https://jurisprudencia.stf.jus.br/pages/search?base=sumulas' +
      `&pesquisa_inteiro_teor=false&queryString=${precedent.number}`
    );
  }

  if (precedent.kind === 'sumula' && precedent.court === 'STJ') {
    return (
      'https://scon.stj.jus.br/SCON/pesquisar.jsp?b=SUMU' +
      `&livre=%40NUM%3D%22${precedent.number}%22`
    );
  }

  return null;
}

// One order for the bar and the list beside it, so the two cannot disagree.
export function rankAdherences(adherences: AdherenceCount[]): AdherenceCount[] {
  return [...adherences].sort((a, b) => {
    if (a.links !== b.links) {
      if (a.links === null) return 1;
      if (b.links === null) return -1;
      return b.links - a.links;
    }
    return a.adherence < b.adherence ? -1 : a.adherence > b.adherence ? 1 : 0;
  });
}

// The order a reader expects in the detail: what the court settled first, then
// by number, so two citations of the same kind sit together.
export function orderCited(precedents: CitedPrecedent[]): CitedPrecedent[] {
  return [...precedents].sort((a, b) => {
    // What the catalogue can explain comes first: a citation with no text
    // tells the reader less, and reading starts at the top.
    if (a.resolved !== b.resolved) return a.resolved ? -1 : 1;
    if (a.kind !== b.kind) return a.kind < b.kind ? -1 : 1;
    if (a.court !== b.court) return a.court < b.court ? -1 : 1;
    return (a.number ?? 0) - (b.number ?? 0);
  });
}

export const percent = (share: number) =>
  `${share.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;

export const isAdherence = (value: string): value is Adherence => value in ADHERENCE_LABELS;
