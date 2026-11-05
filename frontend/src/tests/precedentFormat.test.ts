import { describe, expect, it } from 'vitest';

import {
  readAdherenceShare,
  readCitedPrecedent,
  readCitedPrecedents,
  readMostCited,
} from '../api/precedents';

/**
 * The client reads the answer field by field so that one field the screen
 * cannot use leaves the others standing. These feed it what a wrong answer
 * looks like — a missing block, a number as text, a category nobody defined —
 * and check that the screen still gets something it can render.
 */

describe('a cited precedent', () => {
  it('is dropped when it cannot be named', () => {
    expect(readCitedPrecedent({ number: 7, adherence: 'seguiu' })).toBeNull();
    expect(readCitedPrecedent({ court: 'STJ', number: 7 })).toBeNull();
  });

  it('survives a catalogue that carries no text for it', () => {
    const row = readCitedPrecedent({
      court: 'STJ',
      kind: 'sumula',
      number: 999,
      text: null,
      snippet: 'trecho da citacao',
      adherence: 'mencionou',
      resolved: false,
    });

    expect(row).not.toBeNull();
    expect(row?.text).toBeNull();
    expect(row?.snippet).toBe('trecho da citacao');
    expect(row?.resolved).toBe(false);
  });

  it('treats a category nobody defined as no category', () => {
    const row = readCitedPrecedent({
      court: 'STJ',
      kind: 'sumula',
      number: 7,
      adherence: 'aplicou parcialmente',
    });

    expect(row?.adherence).toBeNull();
  });

  it('counts resolved only when the answer says so', () => {
    const base = { court: 'STJ', kind: 'sumula', number: 7 };

    expect(readCitedPrecedent({ ...base, resolved: 'yes' })?.resolved).toBe(false);
    expect(readCitedPrecedent({ ...base, resolved: true })?.resolved).toBe(true);
  });

  it('answers an empty list when the block is missing or not a list', () => {
    expect(readCitedPrecedents(undefined)).toEqual([]);
    expect(readCitedPrecedents({ court: 'STJ' })).toEqual([]);
  });
});

describe('the adherence of a cut', () => {
  it('keeps the three denominators apart', () => {
    const share = readAdherenceShare({
      decisions: 1788,
      citing: 497,
      links: 1715,
      determined: 1301,
      undetermined: 414,
      adherences: [{ adherence: 'seguiu', links: 913, decisions: 870, share: 70.2 }],
    });

    expect(share.decisions).toBe(1788);
    expect(share.citing).toBe(497);
    expect(share.determined).toBe(1301);
    expect(share.undetermined).toBe(414);
  });

  it('reads a missing answer as nothing known, never as zero', () => {
    const share = readAdherenceShare(undefined);

    expect(share.decisions).toBeNull();
    expect(share.citing).toBeNull();
    expect(share.determined).toBeNull();
    expect(share.adherences).toEqual([]);
  });

  it('refuses a count that is not a count', () => {
    const share = readAdherenceShare({ decisions: '1788', citing: -4, links: Number.NaN });

    expect(share.decisions).toBeNull();
    expect(share.citing).toBeNull();
    expect(share.links).toBeNull();
  });

  it('drops a row whose category it does not know', () => {
    const share = readAdherenceShare({
      adherences: [
        { adherence: 'seguiu', links: 10 },
        { adherence: 'talvez', links: 4 },
        { links: 2 },
      ],
    });

    expect(share.adherences).toHaveLength(1);
    expect(share.adherences[0].adherence).toBe('seguiu');
  });

  it('accepts indeterminado as a value like any other', () => {
    const share = readAdherenceShare({
      adherences: [{ adherence: 'indeterminado', links: 414, decisions: 390, share: 0 }],
    });

    expect(share.adherences[0].adherence).toBe('indeterminado');
    expect(share.adherences[0].links).toBe(414);
  });
});

describe('the most cited precedents', () => {
  it('answers an empty list when the body is not one', () => {
    expect(readMostCited(undefined)).toEqual([]);
    expect(readMostCited({ court: 'STJ' })).toEqual([]);
  });

  it('keeps a precedent the catalogue never carried', () => {
    const ranked = readMostCited([
      { court: 'STJ', kind: 'sumula', number: 7, text: 'enunciado', citations: 612 },
      { court: 'STJ', kind: 'sumula', number: 999, text: null, citations: 3 },
    ]);

    expect(ranked).toHaveLength(2);
    expect(ranked[1].text).toBeNull();
    expect(ranked[1].citations).toBe(3);
  });

  it('keeps the order the API sent', () => {
    const ranked = readMostCited([
      { court: 'STJ', kind: 'sumula', number: 7, citations: 612 },
      { court: 'STF', kind: 'sumula', number: 284, citations: 300 },
    ]);

    expect(ranked.map((row) => row.number)).toEqual([7, 284]);
  });
});
