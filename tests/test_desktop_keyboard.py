import unittest
from unittest.mock import Mock,patch
import types
from maintenance.desktop_keyboard import choose_parent,is_keyboard
from maintenance.install_desktop_keyboard import NEW


class KeyboardTests(unittest.TestCase):
    def test_keyboard_detection(self):
        for name in ['Steam 输入屏幕键盘','Steam Input On-screen Keyboard','Steam 螢幕鍵盤']:
            self.assertTrue(is_keyboard(name))
        self.assertFalse(is_keyboard('Forza Horizon 4'))

    def test_choose_topmost_game_dialog_without_selecting_keyboard(self):
        classes={1:b'steam_app_12',2:b'steam_app_12',3:b'steam'}
        names={1:'Game',2:'Sign in',3:'Steam Input On-screen Keyboard'}
        self.assertEqual(choose_parent([1,2,3],1,classes,names),2)

    def test_desktop_application_keeps_its_own_parent(self):
        self.assertEqual(choose_parent([1,2],1,{1:b'dolphin',2:b'steam'},{1:'Files',2:'Steam'}),1)

    def test_patch_only_redirects_desktop_open_requests(self):
        original,spawn,gamepad = Mock(return_value=True),Mock(),Mock(return_value=False)
        namespace={'is_steam_gamepad_running':gamepad,'subprocess':types.SimpleNamespace(Popen=spawn),
                   'run_steam_command':original}
        exec(NEW,namespace)
        with patch('pathlib.Path') as path:
            path.return_value.is_file.return_value=True
            self.assertTrue(namespace['open_steam_kbd'](True))
            spawn.assert_called_once()
            original.assert_not_called()
            namespace['open_steam_kbd'](False)
            original.assert_called_with('steam://close/keyboard')
            gamepad.return_value=True
            namespace['open_steam_kbd'](True)
            original.assert_called_with('steam://open/keyboard')
            self.assertEqual(spawn.call_count,1)
