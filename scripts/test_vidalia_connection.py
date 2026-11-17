#!/usr/bin/env python3
"""Compatibility entry point for the Vidalia gateway smoke test."""

from smoke_npc_gateway import main


if __name__ == "__main__":
    raise SystemExit(main("vidalia"))
