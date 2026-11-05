"""Test helpers for running the suite on macOS and Windows."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import vivarc  # noqa: E402

MAC = sys.platform == "darwin"
WIN = os.name == "nt"

mac_only = unittest.skipUnless(MAC, "needs macOS (osacompile, launchd, bash)")
posix_only = unittest.skipIf(WIN, "POSIX file permissions and users")
windows_only = unittest.skipUnless(WIN, "needs Windows")

FAKE_WIN_VERSION = "9.9.9.9"


def use_keys(test, name):
    """Run one test with the given platform's shortcut table."""
    vivarc.use_keys(name)
    test.addCleanup(vivarc.use_keys, vivarc.PLATFORM)


def fake_app(root):
    """A Vivaldi install laid out like the real one on this OS. Returns (app, resources)."""
    if WIN:
        app = os.path.join(root, "Vivaldi", "Application")
        resources = os.path.join(app, FAKE_WIN_VERSION, "resources", "vivaldi")
    else:
        app = os.path.join(root, "Vivaldi.app")
        resources = os.path.join(app, vivarc.RESOURCES)
    os.makedirs(resources)
    return app, resources
