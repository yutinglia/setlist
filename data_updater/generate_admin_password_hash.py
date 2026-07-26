"""Interactively generate an Argon2id password hash for ADMIN_PASSWORD_HASH."""

from getpass import getpass

from argon2 import PasswordHasher


def main() -> None:
    password = getpass("New administrator password: ")
    confirmation = getpass("Confirm administrator password: ")
    if len(password) < 12:
        raise SystemExit("Use a password with at least 12 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    print(PasswordHasher().hash(password))


if __name__ == "__main__":
    main()
