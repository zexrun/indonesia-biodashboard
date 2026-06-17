"""Cache configuration for province mask pre-computation."""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Cache on/off
CACHE_ENABLED = True
CACHE_DIR = os.path.join(PROJECT_ROOT, "cache", "masks")
CACHE_VALIDATION_ENABLED = True
AUTO_CLEAR_OLD_CACHE = True
MAX_CACHE_SIZE_MB = 2048

# Logging
LOG_CACHE_OPERATIONS = True
VERBOSE_CACHE_LOGGING = False

# Fallback behavior
ALLOW_COMPUTE_IF_CACHE_FAILS = True
SKIP_SAVE_IF_COMPUTE_FAILS = False
