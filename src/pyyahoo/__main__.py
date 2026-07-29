"""Run the pyyahoo CLI, so ``python -m pyyahoo`` matches the ``pyyahoo`` console script.

Importing this module runs the CLI and terminates the process via ``SystemExit``.
"""

from .cli import main

raise SystemExit(main())
