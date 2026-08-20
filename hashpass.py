#!/usr/bin/env python3

"""Generate an MD5 password hash for the OpenSprinkler API."""

import getpass
import hashlib


def main():
    """Prompt for an OpenSprinkler password and print its MD5 hash."""
    password = getpass.getpass("Enter your OpenSprinkler password: ")

    if not password:
        print("Error: Password cannot be empty.")
        return

    password_hash = hashlib.md5(
        password.encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()

    print()
    print("OpenSprinkler password hash:")
    print(password_hash)


if __name__ == "__main__":
    main()
