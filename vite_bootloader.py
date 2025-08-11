#!/usr/bin/env python3
"""
Vite/React & Proxy Installer — NO-OP STUB
Always exits 0. Accepts any flags. Prints a brief success message.
"""

from __future__ import annotations
import sys, os, argparse

def main() -> int:
    # Accept/ignore any flags so callers don't break
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--frontend-dir")
    ap.add_argument("--proxy-port")
    ap.add_argument("--config")
    _, _unknown = ap.parse_known_args()

    print(f"[FRONTEND-STUB] pid={os.getpid()} cwd={os.getcwd()}", flush=True)
    print("[FRONTEND-STUB] Vite/React install & proxy setup: NO-OP (success)", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
