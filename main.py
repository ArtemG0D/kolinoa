import os
import subprocess
import tempfile
import threading
import time

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, ListProperty, BooleanProperty
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.boxlayout import BoxLayout

Window.clearcolor = (0.07, 0.08, 0.10, 1)

# ---------------------------------------------------------------------------
# Mock catalogue of Python builds. In a real build these would map to actual
# prebuilt python-for-android / termux-packages archives you host somewhere.
# ---------------------------------------------------------------------------
PYTHON_VERSIONS = [
    "3.13.0", "3.12.4", "3.11.9", "3.10.14",
    "3.9.19", "3.8.19", "3.13.0-alpha (experimental)",
]

KV = """
#:import dp kivy.metrics.dp

<GradientButton@Button>:
    background_normal: ''
    background_down: ''
    background_color: 0,0,0,0
    canvas.before:
        Color:
            rgba: (0.18,0.55,0.85,1) if self.state=='normal' else (0.14,0.45,0.72,1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14,]
    color: 1,1,1,1
    font_size: '16sp'
    bold: True

<CardLabel@Label>:
    color: 0.85,0.87,0.9,1
    font_size: '14sp'

<MenuScreen>:
    name: 'menu'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(24)
        spacing: dp(16)

        Label:
            text: '[b]Kolinoa[/b]'
            markup: True
            font_size: '34sp'
            color: 0.95,0.95,1,1
            size_hint_y: None
            height: dp(60)

        CardLabel:
            text: 'Выбери версию Python для установки'
            size_hint_y: None
            height: dp(24)

        TextInput:
            id: search_box
            hint_text: 'Поиск версии (например 3.11)'
            size_hint_y: None
            height: dp(46)
            multiline: False
            background_color: 0.15,0.16,0.2,1
            foreground_color: 1,1,1,1
            padding: dp(12), dp(12)
            on_text: root.filter_versions(self.text)

        ScrollView:
            BoxLayout:
                id: version_list
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)

        BoxLayout:
            size_hint_y: None
            height: dp(10)

        ProgressBar:
            id: dl_progress
            max: 100
            value: root.progress
            size_hint_y: None
            height: dp(18)

        CardLabel:
            id: status_label
            text: root.status_text
            size_hint_y: None
            height: dp(22)

        GradientButton:
            text: 'Скачать и продолжить'
            size_hint_y: None
            height: dp(52)
            on_release: root.start_download()

<VersionRow@BoxLayout>:
    version: ''
    selected: False
    size_hint_y: None
    height: dp(44)
    canvas.before:
        Color:
            rgba: (0.20,0.45,0.65,1) if self.selected else (0.13,0.14,0.18,1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [10,]
    Label:
        text: root.version
        color: 1,1,1,1

<HubScreen>:
    name: 'hub'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(24)
        spacing: dp(18)

        Label:
            text: '[b]Kolinoa[/b] — Python ' + app.selected_version
            markup: True
            font_size: '22sp'
            size_hint_y: None
            height: dp(40)

        GradientButton:
            text: '📄  Новый файл'
            on_release: root.new_file()

        GradientButton:
            text: '📂  Открыть файл'
            on_release: root.open_file()

        GradientButton:
            text: '⌨  Терминал'
            on_release: root.open_terminal()

        Widget:

<TerminalScreen>:
    name: 'terminal'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(8)

        BoxLayout:
            size_hint_y: None
            height: dp(40)
            GradientButton:
                text: '← Назад'
                size_hint_x: None
                width: dp(110)
                on_release: root.manager.current = 'hub'
            Label:
                text: 'Terminal'
                bold: True

        ScrollView:
            id: term_scroll
            BoxLayout:
                id: term_output_box
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                Label:
                    id: term_output
                    text: root.output_text
                    markup: True
                    color: 0.4,1,0.5,1
                    font_name: 'RobotoMono-Regular' if False else 'Roboto'
                    size_hint_y: None
                    text_size: self.width, None
                    height: self.texture_size[1]
                    halign: 'left'
                    valign: 'top'

        TextInput:
            id: term_input
            hint_text: '$ введи команду и нажми Enter'
            multiline: False
            size_hint_y: None
            height: dp(46)
            background_color: 0.1,0.1,0.13,1
            foreground_color: 0.5,1,0.6,1
            on_text_validate: root.run_command(self.text)

<EditorScreen>:
    name: 'editor'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(8)

        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(6)
            GradientButton:
                text: '← Назад'
                size_hint_x: None
                width: dp(100)
                on_release: root.manager.current = 'hub'
            Label:
                text: root.file_label
            GradientButton:
                text: '▶ Run'
                size_hint_x: None
                width: dp(90)
                on_release: root.run_code()
            GradientButton:
                text: '■ Stop'
                size_hint_x: None
                width: dp(90)
                on_release: root.stop_code()
            GradientButton:
                text: '💾 Save'
                size_hint_x: None
                width: dp(90)
                on_release: root.save_file()

        TextInput:
            id: code_input
            text: root.code_text
            font_name: 'Roboto'
            background_color: 0.09,0.09,0.12,1
            foreground_color: 0.95,0.95,0.95,1
            size_hint_y: 0.6

        Label:
            text: 'Вывод:'
            size_hint_y: None
            height: dp(20)

        ScrollView:
            BoxLayout:
                id: out_box
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                Label:
                    text: root.output_text
                    color: 0.8,0.9,1,1
                    size_hint_y: None
                    text_size: self.width, None
                    height: self.texture_size[1]
                    halign: 'left'
                    valign: 'top'
"""


class MenuScreen(Screen):
    progress = NumericProperty(0)
    status_text = StringProperty("Выбери версию и нажми «Скачать»")
    all_versions = ListProperty(PYTHON_VERSIONS)
    chosen_version = StringProperty(PYTHON_VERSIONS[0])

    def on_pre_enter(self, *a):
        self.filter_versions("")

    def filter_versions(self, query):
        box = self.ids.version_list
        box.clear_widgets()
        q = query.strip().lower()
        for v in self.all_versions:
            if q in v.lower():
                row = Builder.template('VersionRow', version=v,
                                        selected=(v == self.chosen_version))
                row.bind(on_touch_down=self._make_picker(v))
                box.add_widget(row)

    def _make_picker(self, version):
        def _pick(instance, touch):
            if instance.collide_point(*touch.pos):
                self.chosen_version = version
                self.filter_versions(self.ids.search_box.text)
            return False
        return _pick

    def start_download(self):
        self.progress = 0
        self.status_text = f"Загрузка Python {self.chosen_version}..."
        Clock.unschedule(self._tick)
        Clock.schedule_interval(self._tick, 1 / 30)

    def _tick(self, dt):
        self.progress += 2.2
        if self.progress >= 100:
            self.progress = 100
            self.status_text = f"Python {self.chosen_version} готов ✔"
            Clock.unschedule(self._tick)
            App.get_running_app().selected_version = self.chosen_version
            Clock.schedule_once(lambda *_: setattr(self.manager, 'current', 'hub'), 0.5)
            return False


class HubScreen(Screen):
    def new_file(self):
        editor = self.manager.get_screen('editor')
        editor.load_blank()
        self.manager.current = 'editor'

    def open_file(self):
        content = BoxLayout(orientation='vertical', spacing=6, padding=6)
        chooser = FileChooserListView(path=os.path.expanduser('~'))
        content.add_widget(chooser)
        btns = BoxLayout(size_hint_y=None, height=44, spacing=6)
        popup = Popup(title='Открыть файл', content=content, size_hint=(0.9, 0.9))

        def do_open(*_):
            if chooser.selection:
                path = chooser.selection[0]
                editor = self.manager.get_screen('editor')
                editor.load_from_path(path)
                popup.dismiss()
                self.manager.current = 'editor'

        open_btn = GradientButtonHelper('Открыть', do_open)
        cancel_btn = GradientButtonHelper('Отмена', lambda *_: popup.dismiss())
        btns.add_widget(open_btn)
        btns.add_widget(cancel_btn)
        content.add_widget(btns)
        popup.open()

    def open_terminal(self):
        self.manager.current = 'terminal'


def GradientButtonHelper(text, on_release):
    from kivy.uix.button import Button
    b = Button(text=text)
    b.bind(on_release=on_release)
    return b


class TerminalScreen(Screen):
    output_text = StringProperty("Kolinoa terminal ready.\n")

    def on_pre_enter(self, *a):
        if not hasattr(self, 'proc') or self.proc is None:
            self._start_shell()

    def _start_shell(self):
        self.cwd = os.path.expanduser('~')
        self.proc = subprocess.Popen(
            ['/bin/sh'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, cwd=self.cwd, text=True, bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self):
        for line in iter(self.proc.stdout.readline, ''):
            self._append(line)

    @mainthread
    def _append(self, text):
        self.output_text += text
        Clock.schedule_once(lambda *_: setattr(
            self.ids.term_scroll, 'scroll_y', 0), 0.05)

    def run_command(self, cmd):
        if not cmd.strip():
            return
        self.ids.term_input.text = ''
        self.output_text += f"\n$ {cmd}\n"
        try:
            self.proc.stdin.write(cmd + "\n")
            self.proc.stdin.flush()
        except Exception as e:
            self.output_text += f"[error] {e}\n"


class EditorScreen(Screen):
    code_text = StringProperty("print('Привет от Kolinoa!')\n")
    output_text = StringProperty("")
    file_label = StringProperty("новый_файл.py")
    file_path = StringProperty("")
    running_proc = None

    def load_blank(self):
        self.file_path = ""
        self.file_label = "новый_файл.py"
        self.ids.code_input.text = "print('Привет от Kolinoa!')\n"
        self.output_text = ""

    def load_from_path(self, path):
        try:
            with open(path, 'r', errors='replace') as f:
                content = f.read()
        except Exception as e:
            content = f"# не удалось открыть файл: {e}"
        self.file_path = path
        self.file_label = os.path.basename(path)
        self.ids.code_input.text = content
        self.output_text = ""

    def save_file(self):
        path = self.file_path or os.path.join(
            os.path.expanduser('~'), self.file_label or 'untitled.py')
        try:
            with open(path, 'w') as f:
                f.write(self.ids.code_input.text)
            self.file_path = path
            self.output_text += f"\n[saved to {path}]\n"
        except Exception as e:
            self.output_text += f"\n[save error] {e}\n"

    def run_code(self):
        self.stop_code()
        code = self.ids.code_input.text
        self._tmp = tempfile.NamedTemporaryFile(
            suffix='.py', mode='w', delete=False)
        self._tmp.write(code)
        self._tmp.close()
        self.output_text = "▶ running...\n"
        self.running_proc = subprocess.Popen(
            ['python3', self._tmp.name], stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        threading.Thread(target=self._stream_output, daemon=True).start()

    def _stream_output(self):
        proc = self.running_proc
        if not proc:
            return
        for line in iter(proc.stdout.readline, ''):
            self._append(line)
        self._append(f"\n[process exited with code {proc.poll()}]\n")

    @mainthread
    def _append(self, text):
        self.output_text += text

    def stop_code(self):
        if self.running_proc and self.running_proc.poll() is None:
            self.running_proc.terminate()
            self.output_text += "\n[stopped]\n"
        self.running_proc = None


class KolinoaApp(App):
    selected_version = StringProperty(PYTHON_VERSIONS[0])

    def build(self):
        Builder.load_string(KV)
        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(MenuScreen())
        sm.add_widget(HubScreen())
        sm.add_widget(TerminalScreen())
        sm.add_widget(EditorScreen())
        return sm


if __name__ == '__main__':
    KolinoaApp().run()
