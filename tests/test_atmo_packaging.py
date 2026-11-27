import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

import atmo_paths

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_clean',ROOT/'packaging'/'build_clean.py')
build_clean=importlib.util.module_from_spec(spec);spec.loader.exec_module(build_clean)


class DesktopPackageTests(unittest.TestCase):
    def test_clean_package_keeps_current_runtime_and_excludes_old_versions_and_user_data(self):
        with TemporaryDirectory() as folder:
            dest=Path(folder)/'clean'
            modules=build_clean.build(dest)
            self.assertIn('atmo_entry_ui',modules)
            self.assertIn('atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable',modules)
            self.assertEqual([p.stem for p in dest.glob('atmo_esfera_fx_integracio_*.py')],['atmo_esfera_fx_integracio_19'])
            self.assertFalse((dest/'tests').exists())
            self.assertFalse((dest/'PROJECTES').exists())
            self.assertFalse((dest/'atmo_esfera_fx_integracio_12.py').exists())
            with zipfile.ZipFile(Path(folder)/'ATMO_ESFERA_FX_Codi_net.zip') as archive:
                self.assertTrue(any(name.endswith('atmo.ico') for name in archive.namelist()))
                self.assertFalse(any('__pycache__' in name for name in archive.namelist()))

    def test_installed_data_survives_repeated_starts_outside_program_resources(self):
        with TemporaryDirectory() as folder,patch.object(atmo_paths.sys,'frozen',True,create=True),patch.dict(os.environ,{'LOCALAPPDATA':folder}):
            path=atmo_paths.data_directory()
            self.assertEqual(path,Path(folder)/'ATMO ESFERA FX')
            saved=path/'PROJECTES'/'distribucio_finestres.json'
            saved.write_text('{"panels":{}}')
            self.assertEqual(atmo_paths.data_directory(),path)
            self.assertEqual(json.loads(saved.read_text()),{'panels':{}})
            self.assertTrue((path/'GRAVACIONS').is_dir())


if __name__=='__main__':unittest.main()
