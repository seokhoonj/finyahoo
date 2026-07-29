"""Run the finyahoo CLI, so ``python -m finyahoo`` matches the ``finyahoo`` console script.

Importing this module runs the CLI and terminates the process via ``SystemExit``.
"""

from .cli import main

raise SystemExit(main())
