import ctypes
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from atmo_windows import ProjectionMonitor,projection_monitor,projection_dragging,install_projection_maximise

class Window:
 def __init__(self):self.current='normal';self.fullscreen=False;self.next=0;self.timers={};self.cancelled=[];self.bindings={};self.changes=[]
 def bind(self,event,callback,add=None):self.bindings[event]=callback
 def after(self,ms,callback):self.next+=1;self.timers[self.next]=callback;return self.next
 def after_cancel(self,token):self.cancelled.append(token);self.timers.pop(token,None)
 def winfo_exists(self):return True
 def state(self,value=None):
  if value is not None:self.current=value;self.changes.append(value)
  return self.current
 def attributes(self,key):return self.fullscreen

class ProjectionMonitorTests(unittest.TestCase):
 def setUp(self):
  self.window=Window();self.destination=1;self.held=False
  self.watch=ProjectionMonitor(self.window,lambda _:self.destination,lambda:self.held)
 def event(self,window=None):return SimpleNamespace(widget=window or self.window)
 def test_new_monitor_maximises_once_on_destination(self):
  self.destination=2;self.watch.check();self.assertEqual(self.window.changes,['zoomed'])
  self.watch.check();self.assertEqual(self.window.changes,['zoomed'])
 def test_resize_or_move_on_same_monitor_does_not_force_maximise(self):
  self.watch.configure(self.event());self.assertIsNotNone(self.watch.pending)
  self.watch.check();self.assertFalse(self.window.changes)
 def test_waits_for_mouse_release_then_maximises(self):
  self.destination=2;self.held=True;self.watch.check()
  self.assertFalse(self.window.changes);self.assertIsNotNone(self.watch.pending)
  self.held=False;self.watch.check();self.assertEqual(self.window.changes,['zoomed'])
 def test_configure_debounces_and_ignores_child_events(self):
  self.watch.configure(self.event(object()));self.assertIsNone(self.watch.pending)
  self.watch.configure(self.event());token=self.watch.pending
  self.watch.configure(self.event());self.assertIn(token,self.window.cancelled)
 def test_fullscreen_and_minimised_windows_keep_their_state(self):
  for state,fullscreen in [('normal',True),('iconic',False),('withdrawn',False),('zoomed',False)]:
   with self.subTest(state=state,fullscreen=fullscreen):
    self.window.current=state;self.window.fullscreen=fullscreen;self.destination+=1;self.watch.check()
    self.assertEqual(self.window.current,state);self.assertFalse(self.window.changes)
 def test_missing_monitor_does_not_pull_window_to_primary_screen(self):
  self.destination=None;self.watch.check();self.assertEqual(self.watch.monitor,1)
  self.assertFalse(self.window.changes)
 def test_destroy_cancels_pending_and_does_not_run_again(self):
  self.watch.configure(self.event());token=self.watch.pending
  self.watch.destroy(self.event());self.assertIn(token,self.window.cancelled)
  self.destination=2;self.watch.check();self.assertFalse(self.window.changes)
 def test_manual_restore_stays_normal_until_next_monitor_change(self):
  self.destination=2;self.watch.check();self.window.state('normal');self.window.changes.clear()
  self.watch.check();self.assertFalse(self.window.changes)
 def test_native_monitor_uses_pointer_sized_handle(self):
  user=Mock();user.GetAncestor.return_value=0x100000001;user.MonitorFromWindow.return_value=0x200000002
  window=Mock();window.winfo_id.return_value=42
  with patch('atmo_windows.sys.platform','win32'),patch.object(ctypes,'windll',SimpleNamespace(user32=user),create=True):
   self.assertEqual(projection_monitor(window),0x200000002)
  user.MonitorFromWindow.assert_called_once_with(0x100000001,2)
 def test_non_windows_is_noop(self):
  with patch('atmo_windows.sys.platform','linux'):
   self.assertIsNone(projection_monitor(self.window));self.assertFalse(projection_dragging())
   install_projection_maximise(self.window);self.assertFalse(hasattr(self.window,'_atmo_projection_monitor'))
