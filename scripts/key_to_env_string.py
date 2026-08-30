#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

def key_file_to_single_line(file_path: str) -> str:
    """Reads an RSA key file and converts it into a single-line string with literal '\\n'."""
    path = Path(file_path)
    
    if not path.is_file():
        raise FileNotFoundError(f"Error: The file '{file_path}' was not found.")

    # 1. Read the contents of the key file
    key_content = path.read_text(encoding="utf-8")

    # 2. Split lines and join them with literal \n text
    single_line_key = "\\n".join(key_content.strip().splitlines())

    return single_line_key

def main():
    parser = argparse.ArgumentParser(
        description="Convert a multi-line RSA PEM key file into a single-line string for use in .env files."
    )
    parser.add_argument(
        "key_file",
        type=str,
        help="Path to the private key file (e.g., id_rsa or key.txt)"
    )
    
    args = parser.parse_args()
    
    try:
        single_line_result = key_file_to_single_line(args.key_file)
        print("--- Single-Line Key String (Copy below this line) ---")
        print(single_line_result)
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
