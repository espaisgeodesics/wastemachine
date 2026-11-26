import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

PATH = Path(__file__).resolve().parents[1] / 'atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable.py'
spec = importlib.util.spec_from_file_location('atmo_esfera_fx', PATH)
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)

class CameraTests(unittest.TestCase):
    def make_app(self):
        app = app_module.App.__new__(app_module.App)
        app.camera = None
        app.cam_index = Mock()
        app.cam_index.get.return_value = 2
        app.status = Mock()
        app.simulation = Mock()
        app.simulation.get.return_value = False
        return app

    def test_camera_backend_and_selected_index(self):
        for platform,backend in [('win32',app_module.cv2.CAP_DSHOW),('linux',app_module.cv2.CAP_ANY)]:
            app=self.make_app()
            with patch('atmo_windows.sys.platform',platform),patch.object(app_module,'CameraStream') as reader:
                app.toggle_cam()
                reader.assert_called_once_with(2,backend)
                reader.return_value.start.assert_called_once()
                self.assertIs(app.camera,reader.return_value.start.return_value)

    def test_camera_close_releases_active_notes(self):
        app = self.make_app()
        camera = app.camera = Mock()
        app.active = {0: True, 3: True}
        app.deactivate = Mock()
        app.all_notes_off = Mock()
        app.cam_label = Mock()
        app.toggle_cam()
        camera.release.assert_called_once()
        self.assertIsNone(app.camera)
        self.assertEqual([c.args[0] for c in app.deactivate.call_args_list], [0, 3])
        app.all_notes_off.assert_called_once()
        app.cam_label.config.assert_called_once_with(image='', text='Càmera desconnectada')

    def test_still_closing_worker_prevents_second_connection(self):
        app=self.make_app();app.camera_retiring=Mock(is_running=True)
        with patch.object(app_module,'CameraStream') as reader:
            app.toggle_cam();reader.assert_not_called()
        self.assertIn('segona connexió',app.status.set.call_args.args[0])

if __name__ == '__main__':
    unittest.main()
