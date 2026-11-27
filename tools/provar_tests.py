"""Run the suite while keeping Tk garbage collection on the main thread.

Usage: python -m tools.provar_tests
Linux GUI tests additionally require DISPLAY (for example a virtual X server).
"""
import gc
import sys
import unittest
from pathlib import Path


class MainThreadGCResult(unittest.TextTestResult):
    def startTest(self, test):
        # Prior tests can leave unreachable Tk reference cycles. A background
        # MIDI/audio worker must not become the thread that finalizes those.
        gc.collect()
        super().startTest(test)


def main():
    automatic_gc = gc.isenabled()
    gc.disable()
    try:
        directory = Path(__file__).resolve().parent.parent / 'tests'
        suite = unittest.defaultTestLoader.discover(str(directory))
        result = unittest.TextTestRunner(verbosity=2, resultclass=MainThreadGCResult).run(suite)
        gc.collect()
        return 0 if result.wasSuccessful() else 1
    finally:
        if automatic_gc:gc.enable()


if __name__ == '__main__':
    sys.exit(main())
