#!/usr/bin/env python3
"""check_config_drift.py

Compares an existing site configuration file (tide_constants.json or
tide.env) against its corresponding template, reporting parameter
NAMES that are missing (present in the template, absent from the
existing file) or obsolete (present in the existing file, absent from
the template). Used by install.sh to detect configuration drift on an
existing station without touching the file itself.

Comparison is by parameter name only, as an unordered set -- parameter
order never matters. For tide_constants.json specifically, only the
(unencrypted) key names are read via plain JSON parsing; the encrypted
values themselves are never touched, read, or decrypted -- this script
needs no encryption key at all.

Usage:
    python3 check_config_drift.py <existing_file> <template_file> <format>

    <format> is either "json" (for tide_constants.json) or "env"
    (for tide.env).

Exit code: 0 if the key sets are identical (no drift). 1 if there are
missing and/or obsolete parameters. 2 on a usage or file-reading error.
"""
import sys
import json
import re


def json_keys(path):
    with open(path, 'r') as f:
        data = json.load(f)
    return set(data.keys())


def env_keys(path):
    keys = set()
    pattern = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=')
    with open(path, 'r') as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            match = pattern.match(line)
            if match:
                keys.add(match.group(1))
    return keys


def main():
    if len(sys.argv) != 4:
        print("Usage: check_config_drift.py <existing_file> <template_file> <json|env>")
        sys.exit(2)

    existing_path, template_path, fmt = sys.argv[1], sys.argv[2], sys.argv[3]

    if fmt == 'json':
        parser = json_keys
    elif fmt == 'env':
        parser = env_keys
    else:
        print(f"Unknown format '{fmt}' -- must be 'json' or 'env'")
        sys.exit(2)

    try:
        existing = parser(existing_path)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Could not read existing file '{existing_path}': {e}")
        sys.exit(2)

    try:
        template = parser(template_path)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Could not read template file '{template_path}': {e}")
        sys.exit(2)

    missing = template - existing
    obsolete = existing - template

    if not missing and not obsolete:
        print(f"{existing_path} is up to date with {template_path} -- "
              f"no missing or obsolete parameters.")
        sys.exit(0)

    if missing:
        print(f"Missing parameters (in the template, not in {existing_path}):")
        for key in sorted(missing):
            print(f"  {key}")
    if obsolete:
        print(f"Obsolete parameters (in {existing_path}, not in the template):")
        for key in sorted(obsolete):
            print(f"  {key}")

    sys.exit(1)


if __name__ == '__main__':
    main()