"""Test package for HADJ NO-TOUCH AI.

Adds the project root to sys.path so the tests can import ``hadj_no_touch``
whether they are run with pytest or unittest.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)