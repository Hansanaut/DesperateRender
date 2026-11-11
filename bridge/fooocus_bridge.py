from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def configure_fooocus(root: Path) -> None:
    """Make a local Fooocus checkout importable without OS-specific paths."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Fooocus directory not found: {root}")
    sys.path.insert(0, str(root))


def main() -> None:
    parser = argparse.ArgumentParser(description="DESPERATE RENDER Fooocus bridge diagnostic")
    parser.add_argument("fooocus_root", type=Path, help="Path to the Fooocus checkout")
    args = parser.parse_args()

    configure_fooocus(args.fooocus_root)

    import modules.async_worker as worker
    import modules.promptlab_api as promptlab_api

    print("=" * 80)
    print("DESPERATE RENDER Bridge")
    print("=" * 80)
    print("Bridge OK")
    print(worker.AsyncTask)
    print()
    print(promptlab_api.ping())
    task = promptlab_api.enqueue_empty()
    print("\nReturned:")
    print(task)
    print("\nQueue status:")
    print(promptlab_api.ping())
    print("\nWaiting 60 seconds...")
    for i in range(60):
        time.sleep(1)
        print(f"{i + 1:02d}s  {promptlab_api.ping()}")


if __name__ == "__main__":
    main()
