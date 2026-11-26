"""Input rules that don't need a database or web framework."""

MAX_NAME_LENGTH = 80


def clean_passenger_name(value: str) -> str:
    """The name is copied into an email sent to a caller-chosen address, so it
    must not be usable to deliver links or markup."""
    if any(not ch.isprintable() and ch not in "\u200c\u200d" for ch in value):
        raise ValueError("Name contains characters that are not allowed.")
    name = " ".join(value.split())
    if not name:
        raise ValueError("Enter the passenger's name.")
    lowered = name.lower()
    if any(part in lowered for part in ("<", ">", "://", "www.")):
        raise ValueError("Name cannot contain links or < > characters.")
    return name
