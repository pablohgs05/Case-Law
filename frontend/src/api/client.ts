const normalizeApiBaseUrl = (value: string | undefined) => {
  const trimmed = value?.trim();

  return trimmed ? trimmed.replace(/\/+$/, '') : '';
};

export const apiBaseUrl = normalizeApiBaseUrl(import.meta.env.VITE_API_URL as string | undefined);

export function assertApiConfiguration() {
  if (!apiBaseUrl) {
    throw new Error('Missing VITE_API_URL. Set it in .env using the value from .env.example.');
  }
}

export async function fetchHealth() {
  assertApiConfiguration();

  const response = await fetch(`${apiBaseUrl}/health`);

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  return response.json();
}
