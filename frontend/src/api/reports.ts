import { apiBaseUrl, assertApiConfiguration } from './client';
import { apiHeaders } from './token';

/**
 * A reader telling the tool one of its readings is wrong.
 *
 * Sending a report changes nothing on the screen but the receipt: the
 * classification stays as it was published until someone reviews it, and this
 * module never touches what the search returned.
 */

export type ContestedInformation = 'resultado' | 'deliberacao' | 'aderencia' | 'tese';

export const CONTESTED_LABELS: Record<ContestedInformation, string> = {
  resultado: 'Resultado do recurso',
  deliberacao: 'Deliberação',
  aderencia: 'Aderência ao precedente',
  tese: 'Tese',
};

export const MAX_REPORT_LENGTH = 2000;

export type ReportStatus = 'pendente' | 'aceito' | 'recusado';

export type Report = {
  id: string;
  source: string;
  identifier: string;
  information: ContestedInformation;
  publishedValue: string | null;
  description: string;
  status: ReportStatus;
  receivedAt: string;
};

export type Receipt = Report & { message: string };

export type ListedReport = Report & {
  reportedBy: { id: string; name: string; email: string };
};

export class ReportError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ReportError';
    this.status = status;
  }
}

const UNREACHABLE = 'Não foi possível falar com o servidor. Verifique a conexão.';
const RECEIVED =
  'Recebemos o seu reporte. A classificação publicada continua a mesma até que alguém o revise.';

const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : null);

const isInformation = (value: unknown): value is ContestedInformation =>
  typeof value === 'string' && value in CONTESTED_LABELS;

const isStatus = (value: unknown): value is ReportStatus =>
  value === 'pendente' || value === 'aceito' || value === 'recusado';

function readReport(value: unknown): Report | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const id = text(row.id);
  const source = text(row.source);
  const identifier = text(row.identifier);
  const receivedAt = text(row.received_at);

  if (!id || !source || !identifier || !receivedAt || !isInformation(row.information)) {
    return null;
  }

  return {
    id,
    source,
    identifier,
    information: row.information,
    publishedValue: text(row.published_value),
    description: typeof row.description === 'string' ? row.description : '',
    // Unknown reads as pending: a report is never shown as settled by accident.
    status: isStatus(row.status) ? row.status : 'pendente',
    receivedAt,
  };
}

export function readReports(body: unknown): ListedReport[] {
  const raw = (body ?? {}) as Record<string, unknown>;

  if (!Array.isArray(raw.reports)) {
    return [];
  }

  return raw.reports.flatMap((item: unknown) => {
    const report = readReport(item);
    const who = ((item as Record<string, unknown> | null)?.reported_by ?? {}) as Record<
      string,
      unknown
    >;

    if (!report) {
      return [];
    }

    return [
      {
        ...report,
        reportedBy: {
          id: text(who.id) ?? '',
          name: text(who.name) ?? 'Conta sem nome',
          email: text(who.email) ?? '',
        },
      },
    ];
  });
}

async function detailOf(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as Record<string, unknown>;
    // FastAPI answers a validation failure with a list, not a sentence; the
    // reader gets the fallback rather than a dump of field paths.
    return text(body.detail) ?? fallback;
  } catch {
    return fallback;
  }
}

async function call(path: string, init: RequestInit = {}): Promise<Response> {
  assertApiConfiguration();

  try {
    return await fetch(new URL(`${apiBaseUrl}${path}`, window.location.origin), {
      ...init,
      headers: apiHeaders(init.body ? { 'Content-Type': 'application/json' } : {}),
    });
  } catch {
    throw new ReportError(0, UNREACHABLE);
  }
}

export async function reportClassification(
  decision: { source: string; identifier: string },
  information: ContestedInformation,
  description: string,
): Promise<Receipt> {
  const response = await call(
    `/decisions/${encodeURIComponent(decision.source)}/${encodeURIComponent(decision.identifier)}/reports`,
    { method: 'POST', body: JSON.stringify({ information, description }) },
  );

  if (!response.ok) {
    throw new ReportError(
      response.status,
      response.status === 404
        ? 'Esta decisão não está mais na base publicada.'
        : await detailOf(response, 'Não foi possível enviar o reporte. Tente novamente.'),
    );
  }

  const body = (await response.json()) as Record<string, unknown>;
  const report = readReport(body);

  if (!report) {
    throw new ReportError(500, 'O servidor respondeu sem confirmar o reporte.');
  }

  return { ...report, message: text(body.message) ?? RECEIVED };
}

export async function listReports(options: { signal?: AbortSignal } = {}): Promise<ListedReport[]> {
  const response = await call('/reports', { signal: options.signal });

  if (!response.ok) {
    throw new ReportError(response.status, await detailOf(response, UNREACHABLE));
  }

  return readReports(await response.json());
}
