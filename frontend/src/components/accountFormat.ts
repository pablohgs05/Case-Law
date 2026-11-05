/**
 * The two fields the screen has to get right before the API sees them.
 *
 * Both rules live on the API too: this is the help, not the guard. A screen
 * that only shows the rule after a refusal makes the person guess, and a
 * screen that enforces it alone protects nothing.
 */

/** `(12) 99999-0000` as the person types, dropping anything that is not a digit. */
export function asPhone(typed: string): string {
  const digits = typed.replace(/\D/g, '').slice(0, 11);

  if (digits.length <= 2) {
    return digits;
  }

  const area = digits.slice(0, 2);
  const rest = digits.slice(2);

  // The break moves at nine digits: a landline is 4+4, a mobile 5+4. Splitting
  // early would show `(12) 9999-90000` while a mobile is being typed.
  if (rest.length <= 4) {
    return `(${area}) ${rest}`;
  }

  const head = rest.length > 8 ? rest.slice(0, 5) : rest.slice(0, 4);

  return `(${area}) ${head}-${rest.slice(head.length)}`;
}

export function phoneIsComplete(typed: string): boolean {
  const digits = typed.replace(/\D/g, '').length;
  return digits === 0 || digits === 10 || digits === 11;
}

export const PHONE_HINT = 'DDD e número, só algarismos. Fixo tem 10, celular tem 11.';

export const PASSWORD_MIN = 8;

export const PASSWORD_HINT = 'Pelo menos 8 caracteres, com uma letra maiúscula e um número.';

/** The same three rules the API applies, said before the refusal. */
export function passwordIsStrong(password: string): boolean {
  return password.length >= PASSWORD_MIN && /[A-ZÀ-Þ]/.test(password) && /[0-9]/.test(password);
}
