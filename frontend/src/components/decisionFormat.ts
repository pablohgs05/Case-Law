// Shared by the result card and the decision detail, so a field reads the same
// way in both.

export const NOT_INFORMED = 'Não informado';

export function normalizeText(value: string | null | undefined): string {
  if (typeof value !== 'string') {
    return '';
  }

  return value.trim();
}

export function getDisplayValue(value: string | null | undefined): string {
  const normalized = normalizeText(value);
  return normalized || NOT_INFORMED;
}

// The court's page, only when it is a real web address. Anything else — empty,
// malformed, `javascript:` — is no link at all, never a link to nowhere.
export function normalizeOfficialUrl(value: string | null | undefined): string | null {
  const normalized = normalizeText(value);

  if (!normalized) {
    return null;
  }

  try {
    const parsedUrl = new URL(normalized);
    if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
      return null;
    }

    return normalized;
  } catch {
    return null;
  }
}

// A `YYYY-MM-DD` day is formatted in UTC: read in the local zone, midnight in
// Brasília would already be the previous day. Anything unreadable is null, so
// the screen can leave it out rather than print "Invalid Date".
export function formatDate(value: string | null | undefined): string | null {
  const normalized = normalizeText(value);

  if (!normalized) {
    return null;
  }

  const isoDateMatch = normalized.match(/^(\d{4})-(\d{2})-(\d{2})$/);

  if (isoDateMatch) {
    const [, year, month, day] = isoDateMatch.map(Number);
    const date = new Date(Date.UTC(year, month - 1, day));

    // Date.UTC rolls an impossible day over instead of refusing it:
    // 2026-13-45 would come back as a real day in 2027.
    if (
      Number.isNaN(date.getTime()) ||
      date.getUTCFullYear() !== year ||
      date.getUTCMonth() !== month - 1 ||
      date.getUTCDate() !== day
    ) {
      return null;
    }

    return date.toLocaleDateString('pt-BR', { timeZone: 'UTC' });
  }

  const parsedDate = new Date(normalized);

  if (Number.isNaN(parsedDate.getTime())) {
    return null;
  }

  return parsedDate.toLocaleDateString('pt-BR', { timeZone: 'UTC' });
}
