import subprocess

def get_git_version(default="0.0.0"):
    try:
        version = subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"])
        return version.decode("utf-8").strip()
    except Exception:
        return default
