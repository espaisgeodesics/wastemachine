import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

PATH = Path(__file__).resolve().parents[1] / 'wasteland_4_5_15_pas_15_editor_musical_desplegable.py'
spec = importlib.util.spec_from_file_location('wasteland', PATH)
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)

class CameraTests(unittest.TestCase):
    def make_app(self):
        app = app_module.App.__new__(app_module.App)
        app.camera = None
        app.cam_index = Mock()
        app.cam_index.get.return_value = 2
        app.status = Mock()
        return app

    def test_camera_backend_and_selected_index(self):
        for platform, backend in [('win32', app_module.cv2.CAP_DSHOW), ('linux', app_module.cv2.CAP_ANY)]:
            with self.subTest(platform=platform), patch.object(app_module.sys, 'platform', platform), patch.object(app_module.cv2, 'VideoCapture') as capture:
                app = self.make_app()
                app.toggle_cam()
                capture.assert_called_once_with(2, backend)

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

    def test_failed_open_releases_camera(self):
        app = self.make_app()
        with patch.object(app_module.cv2, 'VideoCapture') as capture, patch.object(app_module.messagebox, 'showwarning') as warning:
            capture.return_value.isOpened.return_value = False
            app.toggle_cam()
            capture.return_value.release.assert_called_once()
            self.assertIsNone(app.camera)
            warning.assert_called_once()

if __name__ == '__main__':
    unittest.main()
