"""
Server connector stub.
The original server module used compiled .so files which are not available.
This module provides a no-op implementation to prevent import errors.
"""
import logging

logger = logging.getLogger(__name__)


def Connect_Server():
    """No-op server connection. Original logic was in compiled .so files."""
    logger.info("Server connection stub - no external server configured.")


Connect_Server()
