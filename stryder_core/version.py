import logging
import subprocess


logger = logging.getLogger(__name__)


def get_git_version(default="0.0.0"):
    """ Gets git version and returns it to the caller """
    try:
        version = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            stderr=subprocess.DEVNULL       # hide git error messages
        )

        return version.decode("utf-8").strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        logger.warning("⚠️ Could not determine git version: %s", e)
        return default
