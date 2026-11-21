"""Explicit Windows build self-check. Normal startup never executes this module."""
import json
from pathlib import Path
import traceback


def run(choose_experience,open_engine,report_path):
    import os
    import tkinter as tk
    from unittest.mock import patch
    from PIL import ImageGrab
    import atmo_primary
    report_path=Path(report_path);report_path.parent.mkdir(parents=True,exist_ok=True)
    result={'errors':[],'entry':False,'project':False,'engine':False,'returned_home':False,'audio':False}
    actual_tk=tk.Tk
    def save(root,name):
        root.update_idletasks()
        ImageGrab.grab().save(report_path.parent/(name+'.png'))
    try:
        def make_splash():
            root=actual_tk()
            root.report_callback_exception=lambda typ,value,tb:result['errors'].append(str(value))
            def select_mode():
                save(root,'01_inici')
                def children(widget):
                    for child in widget.winfo_children():yield child;yield from children(child)
                button=next(w for w in children(root) if isinstance(w,tk.Button) and w.cget('text')=='Entrar a Música')
                button.invoke()
                def select_new():
                    save(root,'02_projecte')
                    buttons=[w for w in children(root) if isinstance(w,tk.Button)]
                    assert not any('plantilla' in w.cget('text').lower() or 'sense carregar' in w.cget('text') for w in buttons)
                    next(w for w in buttons if 'Projecte nou' in w.cget('text')).invoke()
                root.after(350,select_new)
            root.after(800,select_mode)
            root.after(15000,root.destroy)
            return root
        with patch.object(tk,'Tk',side_effect=make_splash):
            choice=choose_experience()
        assert choice=={'mode':'Música','game_action':'new'},choice
        result['entry']=True;result['project']=True
        original=atmo_primary.primary_engine
        def checked_engine(module,mode):
            base=original(module,mode)
            class Checked(base):
                def __init__(self,root):
                    super().__init__(root)
                    root.report_callback_exception=lambda typ,value,tb:result['errors'].append(str(value))
                    def finish():
                        save(root,'03_motor')
                        result['engine']=True
                        assert getattr(root,'_atmo_app_icon',None) is not None
                        self.confirm_new_project=lambda:True
                        self.new_project()
                    root.after(1200,finish)
                    root.after(15000,lambda:self.close(confirmed=True))
            return Checked
        with patch.dict(open_engine.__globals__,{'primary_engine':checked_engine}):
            result['returned_home']=bool(open_engine(choice['mode'],choice['game_action']))
        assert result['returned_home']
        import cv2
        import mido
        import rtmidi
        assert hasattr(cv2.aruco,'ArucoDetector')
        mido.set_backend('mido.backends.rtmidi/WINDOWS_MM')
        mido.get_output_names()
        os.environ['SDL_AUDIODRIVER']='dummy'
        from local_audio import PygameAudioBackend
        backend=PygameAudioBackend()
        try:backend.check();result['audio']=True
        finally:backend.close()
    except Exception:
        result['errors'].append(traceback.format_exc())
    report_path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if not result['errors'] and all(result[k] for k in ('entry','project','engine','returned_home','audio')) else 1
