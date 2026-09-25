import { describe, expect, it } from 'vitest';

import { formatDate, normalizeOfficialUrl } from '../components/decisionFormat';

describe('a date that is only a day', () => {
  it('keeps its day, whatever the local time zone', () => {
    expect(formatDate('2026-01-01')).toBe('01/01/2026');
    expect(formatDate('2026-12-31')).toBe('31/12/2026');
  });

  it('is refused rather than rolled over when it cannot exist', () => {
    expect(formatDate('2026-13-45')).toBeNull();
    expect(formatDate('2026-02-30')).toBeNull();
  });

  it('is left out when empty or unreadable', () => {
    expect(formatDate(null)).toBeNull();
    expect(formatDate('')).toBeNull();
    expect(formatDate('ontem')).toBeNull();
  });
});

describe('the official address', () => {
  it('is kept when it is a web address', () => {
    expect(normalizeOfficialUrl(' https://jurisdf.tjdft.jus.br/detalhes/1 ')).toBe(
      'https://jurisdf.tjdft.jus.br/detalhes/1',
    );
  });

  it('is dropped when it is anything else', () => {
    expect(normalizeOfficialUrl('javascript:alert(1)')).toBeNull();
    expect(normalizeOfficialUrl('detalhes/1')).toBeNull();
    expect(normalizeOfficialUrl(null)).toBeNull();
  });
});
