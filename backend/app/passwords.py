"""
Storing a password without being able to read it back.

Argon2id, which is what the Password Hashing Competition settled on and what
OWASP recommends today. The library picks the cost parameters and keeps them
inside the hash, so a stored hash stays verifiable after the cost is raised.

Nothing here ever logs, returns or compares a password in the clear.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

MIN_LENGTH = 8

RULES = (
    f"pelo menos {MIN_LENGTH} caracteres",
    "uma letra maiúscula",
    "um número",
)

REFUSAL = "A senha precisa de " + ", ".join(RULES[:-1]) + " e " + RULES[-1] + "."


def refuses(password: str) -> str | None:
    """
    Why this password is not accepted, or None when it is.

    One sentence naming every rule at once. Answering them one at a time turns
    choosing a password into a guessing game — the person fixes the length,
    is told about the capital, fixes that, and is told about the digit.
    """
    if (
        len(password) < MIN_LENGTH
        or not any(letter.isupper() for letter in password)
        or not any(letter.isdigit() for letter in password)
    ):
        return REFUSAL

    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def matches(stored: str, password: str) -> bool:
    """
    Whether the password matches. A stored hash that is corrupt or was written
    by some other scheme answers False rather than raising: the caller is a
    login attempt, and there is nothing it could do differently.
    """
    try:
        return _hasher.verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def stale(stored: str) -> bool:
    """
    Whether this hash was made with weaker parameters than today's. The hash
    carries its own cost, so raising the cost is answered on the next login
    rather than by asking everyone to change their password.
    """
    try:
        return _hasher.check_needs_rehash(stored)
    except InvalidHashError:
        return True
