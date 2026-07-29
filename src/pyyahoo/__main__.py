"""Enable ``python -m pyyahoo`` as an alias for the ``pyyahoo`` console script."""

from .cli import main

raise SystemExit(main())
