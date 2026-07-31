"""Allow `python -m deepstream ...` to reach the CLI."""

from deepstream.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
