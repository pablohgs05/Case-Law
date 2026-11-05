import type { Suggestion } from '../api/doctrine';

/**
 * Turning a match into something a reader can judge.
 *
 * The API answers stems, because stems are what actually matched and the
 * record of that belongs in the data. `litiganc` on a screen means nothing;
 * "Litigância de má-fé" means everything. The translation back is presentation
 * work, and it lives here.
 */

const strip = (value: string) => value.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

const WORDS = /[^\p{L}\p{N}-]+/u;

function words(value: string): string[] {
  return strip(value).split(WORDS).filter(Boolean);
}

// The stemmer truncates, so a stem is a prefix of the word it came from once
// the accents are gone: `litiganc` of *litigância*, `constituica` of
// *constituição*, `ma-f` of *má-fé*.
function carries(text: string, stems: string[]): boolean {
  const parts = words(text);
  return stems.some((stem) => parts.some((word) => word.startsWith(stem)));
}

export type CommonGround =
  { kind: 'subjects'; items: string[] } | { kind: 'words'; items: string[] } | { kind: 'none' };

/**
 * Why this work is being suggested, in the work's own words.
 *
 * The subjects first, because a cataloguer chose them and they read as
 * phrases. The title's own words when the record carries no subject, which is
 * 45% of the collection. Never the bare stems: a reader asked to judge
 * `interpretaca` cannot.
 */
export function commonGround(suggestion: Suggestion): CommonGround {
  const stems = suggestion.matched_on.filter(Boolean);

  if (stems.length === 0) {
    return { kind: 'none' };
  }

  const subjects = suggestion.subjects
    .filter((subject) => carries(subject, stems))
    // Not the authority records. 37 works carry subjects like "Brasil. [Lei
    // n. 11.340, de 7 de agosto de 2006]", which is a catalogue string rather
    // than a topic, and on screen it reads as noise where a reason should be.
    .filter((subject) => !subject.includes('['));

  if (subjects.length > 0) {
    return { kind: 'subjects', items: subjects };
  }

  // Back to the title, keeping the court's spelling rather than the stem's.
  const seen = new Set<string>();
  const items = suggestion.title
    .split(WORDS)
    .filter((word) => {
      const plain = strip(word);
      if (!stems.some((stem) => plain.startsWith(stem)) || seen.has(plain)) {
        return false;
      }
      seen.add(plain);
      return true;
    })
    .map((word) => word.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, ''))
    .filter(Boolean);

  return items.length > 0 ? { kind: 'words', items } : { kind: 'none' };
}

export const COMMON_GROUND_LABELS: Record<Exclude<CommonGround['kind'], 'none'>, string> = {
  subjects: 'Assuntos em comum',
  words: 'Termos em comum',
};

/**
 * "Artigo, 2014" — what kind of work it is and when it came out, when the
 * record says. Either part alone is still worth showing.
 */
export function workKind(suggestion: { type: string | null; date: string | null }): string | null {
  return [suggestion.type, suggestion.date].filter(Boolean).join(', ') || null;
}

// A middot, not a comma: a catalogued subject carries commas of its own —
// "Constitucionalidade das leis, Brasil." is one subject — and joining three
// of those with commas produces one run-on line nobody can parse.
export const GROUND_SEPARATOR = ' · ';

// At most three. A subject runs 25 characters on average, so three fit a line
// and a half beside the label; four wrapped to two full lines and the reason
// stopped being readable at a glance, which is the whole point of it.
export const MAX_COMMON_GROUND = 3;
