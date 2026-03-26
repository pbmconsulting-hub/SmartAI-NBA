# ============================================================
# FILE: utils/log_helper.py
# PURPOSE: Single-import logger factory with stdlib fallback.
#
#          Previously, 30 files repeated this 4–6 line pattern:
#
#              try:
#                  from utils.logger import get_logger
#                  _logger = get_logger(__name__)
#              except ImportError:
#                  import logging
#                  _logger = logging.getLogger(__name__)
#
#          Now each file just needs:
#
#              from utils.log_helper import get_logger
#              _logger = get_logger(__name__)
#
# CONCEPTS: Fail-safe import wrapper, DRY boilerplate reduction
# ============================================================

try:
    from utils.logger import get_logger
except ImportError:
    import logging

    get_logger = logging.getLogger
