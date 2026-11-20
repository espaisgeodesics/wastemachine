"""Separate installed program resources from persistent user projects."""
import os
from pathlib import Path
import sys


def data_directory():
    if getattr(sys,'frozen',False):
        base=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'ATMO ESFERA FX'
    else:
        base=Path(__file__).resolve().parent
    for name in ('PROJECTES','GRAVACIONS'):(base/name).mkdir(parents=True,exist_ok=True)
    return base
