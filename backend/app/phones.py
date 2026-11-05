"""
A Brazilian phone number, kept in one shape.

Digits only, and always the same ten or eleven of them: two for the area code,
then eight for a landline or nine for a mobile. The screen formats while
someone types, and this is what the API accepts regardless — a request that
skips the screen is still a request.

Stored formatted, because that is how it is read back on every screen and
nobody wants to format it four times.
"""

import re

DIGITS = re.compile(r"\D+")

# What a phone number may carry besides its digits. Anything else is refused
# rather than stripped: dropping a stray letter turns `1299999000a` into a
# ten-digit landline that looks right and is not the number anyone meant.
SEPARATORS = re.compile(r"^[0-9()\-.\s+]*$")

REFUSAL = (
    "O telefone precisa do DDD e do número, só com algarismos: "
    "10 dígitos para fixo ou 11 para celular."
)


def digits_of(phone: str) -> str:
    return DIGITS.sub("", phone or "")


def formatted(phone: str | None) -> str | None:
    """
    `(12) 99999-0000`, or None when nothing was given.

    Raises `ValueError` when there is something that is not a phone number,
    so a caller can turn it into the one refusal above.
    """
    if phone is None or not phone.strip():
        return None

    if not SEPARATORS.match(phone):
        raise ValueError(REFUSAL)

    numbers = digits_of(phone)

    # A number written with the country code is the same number: nobody typing
    # +55 means a different line, and refusing it would read as a bug.
    if len(numbers) in (12, 13) and numbers.startswith("55"):
        numbers = numbers[2:]

    if len(numbers) not in (10, 11):
        raise ValueError(REFUSAL)

    # Area codes start at 11; a leading zero or a 0800 is not an area code.
    if numbers[0] == "0":
        raise ValueError(REFUSAL)

    area, rest = numbers[:2], numbers[2:]

    return f"({area}) {rest[:-4]}-{rest[-4:]}"
