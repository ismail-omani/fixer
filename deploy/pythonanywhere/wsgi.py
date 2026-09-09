import os
import sys

path = "/home/<your-login>/fixer"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault("FIXER_HTTPS", "1")

from app import app as application