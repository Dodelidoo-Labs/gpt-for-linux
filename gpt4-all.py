from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget,
                             QTextEdit, QPushButton, QLabel, QLineEdit, QDialog,
                             QComboBox, QDesktopWidget)
from PyQt5.QtCore import QThread, pyqtSignal
import sys
import keyring
import requests
import json
from plyer import notification
import appdirs
import os

class QueryThread(QThread):
    response_signal = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, query, model_preference, custom_temperature, current_custom_freq_penalty):
        QThread.__init__(self)
        self.query = query
        self.model_preference = model_preference
        self.custom_temperature = custom_temperature
        self.current_custom_freq_penalty = current_custom_freq_penalty

    def run(self):
        api_key = get_api_key()
        if not api_key:
            self.response_signal.emit("API Key Not Set")
            return

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = json.dumps({
            "model": self.model_preference,
            "messages": [{"role": "user", "content": self.query}],
            "stream": True,
            "temperature": self.custom_temperature,
            "frequency_penalty": self.current_custom_freq_penalty
        }).encode()

        with requests.post(url, data=data, headers=headers, stream=True) as response:
            try:
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            json_str = line_str[6:]  # Strip 'data: ' prefix

                            if json_str == '[DONE]':
                                self.done_signal.emit()
                                break  # End of stream

                            try:
                                decoded_line = json.loads(json_str)
                                content = decoded_line.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                # Emit each chunk of content to the response window
                                self.response_signal.emit(content)
                            except json.JSONDecodeError:
                                self.response_signal.emit(f"Invalid JSON after 'data: ' prefix: {json_str}")
                        else:
                            self.response_signal.emit(f"Non-data line received: {line_str}")
            except Exception as e:
                self.response_signal.emit(f"Error in GPT-4 API request: {e}")

def get_preference_file_path(file_name):
    user_data_dir = appdirs.user_data_dir("GPT4-All", appauthor='Beda Schmid')
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
    return os.path.join(user_data_dir, file_name)

def save_model_preference(key, value):
    preference_file = get_preference_file_path('.gpt_search_app_preference.json')
    data = get_all_preferences()
    data[key] = value

    with open(preference_file, 'w') as file:
        json.dump(data, file)
        show_alert(f"{key} Saved to {preference_file}")

def get_model_preference(key, default_value):
    data = get_all_preferences()
    return data.get(key, default_value)

def get_all_preferences():
    preference_file = get_preference_file_path('.gpt_search_app_preference.json')
    try:
        with open(preference_file, 'r') as file:
            data = json.load(file)
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_api_key(api_key):
    keyring.set_password("gpt4-app", "api_key", api_key)
    show_alert("Key Saved")
    
def get_api_key():
    return keyring.get_password("gpt4-app", "api_key")

def show_alert(message):
    try:
        notification.notify( title='Notification', message=message, app_name='GPT4-All' )
    except Exception as e:
        print(f"Failed to show alert: {e}")

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setWindowTitle("Settings")
        self.setGeometry(100, 100, 400, 100)

        layout = QVBoxLayout()

        self.api_key_entry = QLineEdit(self)
        self.api_key_entry.setPlaceholderText("Enter your GPT-4 API Key")
        self.api_key_entry.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.api_key_entry)

        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.ok_pressed)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def ok_pressed(self):
        api_key = self.api_key_entry.text()
        save_api_key(api_key)
        self.accept()

class ModelSettingsDialog(QDialog):
    def __init__(self, parent=None, current_model='gpt-4', current_custom_temperature=1, current_custom_freq_penalty=0):
        super(ModelSettingsDialog, self).__init__(parent)
        self.setWindowTitle("Model Settings")
        self.setGeometry(100, 100, 250, 100)

        layout = QVBoxLayout()

        self.model_combo = QComboBox(self)
        self.model_combo.addItem('GPT-4', 'gpt-4')
        self.model_combo.addItem('GPT-4-1106-Preview', 'gpt-4-1106-preview')
        self.model_combo.setCurrentIndex(self.model_combo.findData(current_model))
        layout.addWidget(self.model_combo)

        self.temperature_label = QLabel("Temperature (0-2)", self)
        layout.addWidget(self.temperature_label)
        self.custom_temperature_entry = QLineEdit(str(current_custom_temperature), self)
        layout.addWidget(self.custom_temperature_entry)

        self.custom_freq_label = QLabel("Frequency Penalty (-2 to 2):", self)
        layout.addWidget(self.custom_freq_label)
        self.custom_freq_penalty_entry = QLineEdit(str(current_custom_freq_penalty), self)
        layout.addWidget(self.custom_freq_penalty_entry)

        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.ok_pressed)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def ok_pressed(self):
        model_preference = self.model_combo.currentData()
        save_model_preference('model_preference', model_preference)

        try:
            custom_temperature = float(self.custom_temperature_entry.text())
            save_model_preference('custom_temperature', custom_temperature)
        except ValueError:
            show_alert("Invalid decimal number entered")

        try:
            custom_freq_penalty_entry = float(self.custom_freq_penalty_entry.text())
            save_model_preference('custom_freq_penalty_entry', custom_freq_penalty_entry)
        except ValueError:
            show_alert("Invalid decimal number entered")
        
        self.accept()

class ResponseWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Response")
        self.setGeometry(100, 100, 800, 700)

        self.response_edit = QTextEdit(self)
        self.response_edit.setReadOnly(True)
        self.setCentralWidget(self.response_edit)
        self.restore_window_size_position("response_window")

    def append_response(self, text):
        cursor = self.response_edit.textCursor()  # Get the current text cursor from the QTextEdit
        cursor.movePosition(cursor.End)           # Move the cursor position to the end
        self.response_edit.setTextCursor(cursor)  # Set the text cursor in the QTextEdit
        self.response_edit.insertPlainText(text)  # Insert the text
        
    def save_window_size_position(self, window_key):
        size_position_data = {}
        window_file = get_preference_file_path('.window_sizes_positions.json')
        if os.path.exists(window_file):
            with open(window_file, "r") as f:
                size_position_data = json.load(f)

        size_position_data[window_key] = {
            "width": self.width(),
            "height": self.height(),
            "x": self.x(),
            "y": self.y()
        }

        with open(window_file, "w") as f:
            json.dump(size_position_data, f)

    def restore_window_size_position(self, window_key):
        window_sizes_file = get_preference_file_path('.window_sizes_positions.json')
        if os.path.exists(window_sizes_file):
            with open(window_sizes_file, "r") as f:
                size_position_data = json.load(f)
                if window_key in size_position_data:
                    width = size_position_data[window_key]["width"]
                    height = size_position_data[window_key]["height"]
                    x = size_position_data[window_key]["x"]
                    y = size_position_data[window_key]["y"]
                    self.setGeometry(x, y, width, height)

    def closeEvent(self, event):
        self.save_window_size_position("response_window")
        event.accept()

class MyApp(QApplication):
    def __init__(self, argv):
        super(MyApp, self).__init__(argv)
        self.response_window = ResponseWindow()
        self.main_window = QMainWindow()
        self.setup_ui()
        self.restore_window_size_position(self.main_window, "main_window")

    def setup_ui(self):
        
        self.main_window.setWindowTitle("GPT-4 Search App")
        self.center_window_on_screen(self.main_window)
        
        widget = QWidget(self.main_window)
        layout = QVBoxLayout(widget)

        self.search_entry = QTextEdit(widget)
        self.search_entry.setPlaceholderText("Enter your query")
        layout.addWidget(self.search_entry)

        self.search_button = QPushButton("Search", widget)
        self.search_button.clicked.connect(self.on_search_button_clicked)
        layout.addWidget(self.search_button)

        self.settings_button = QPushButton("Settings", widget)
        self.settings_button.clicked.connect(self.show_settings_dialog)
        layout.addWidget(self.settings_button)

        self.model_settings_button = QPushButton("Model Settings", widget)
        self.model_settings_button.clicked.connect(self.show_model_settings_dialog)
        layout.addWidget(self.model_settings_button)

        self.main_window.setCentralWidget(widget)
        self.main_window.show()
        self.main_window.closeEvent = self.on_main_window_close
        
    def center_window_on_screen(self, window):
        window.resize(800,800)  # Set desired size
        qRect = window.frameGeometry()
        centerPoint = QDesktopWidget().availableGeometry().center()
        qRect.moveCenter(centerPoint)
        window.move(qRect.topLeft())
        
    def save_window_size_position(self, window, window_key):
        size_position_data = {}
        window_file = get_preference_file_path('.window_sizes_positions.json')
        if os.path.exists(window_file):
            with open(window_file, "r") as f:
                size_position_data = json.load(f)

        size_position_data[window_key] = {
            "width": window.width(),
            "height": window.height(),
            "x": window.x(),
            "y": window.y()
        }

        with open(window_file, "w") as f:
            json.dump(size_position_data, f)

    def restore_window_size_position(self, window, window_key):
        window_sizes_file = get_preference_file_path('.window_sizes_positions.json')
        if os.path.exists(window_sizes_file):
            with open(window_sizes_file, "r") as f:
                size_position_data = json.load(f)
                if window_key in size_position_data:
                    width = size_position_data[window_key]["width"]
                    height = size_position_data[window_key]["height"]
                    x = size_position_data[window_key]["x"]
                    y = size_position_data[window_key]["y"]
                    window.setGeometry(x, y, width, height)

    def on_main_window_close(self, event):
        self.save_window_size_position(self.main_window, "main_window")
        event.accept()

    def show_settings_dialog(self):
        dialog = SettingsDialog(self.main_window)
        dialog.exec_()

    def show_model_settings_dialog(self):
        current_model = get_model_preference('model_preference', 'gpt-4')
        current_custom_temperature = get_model_preference('custom_temperature', 1)
        custom_freq_penalty_entry = get_model_preference('custom_freq_penalty_entry', 0)
        dialog = ModelSettingsDialog(self.main_window, current_model, current_custom_temperature, custom_freq_penalty_entry)
        dialog.exec_()

    def on_search_button_clicked(self):
        model_preference = get_model_preference('model_preference', 'gpt-4')
        custom_temperature = get_model_preference('custom_temperature', 1)
        current_custom_freq_penalty = get_model_preference('current_custom_freq_penalty', 0.0)
        query = self.search_entry.toPlainText()

        if not self.response_window.isVisible():
            self.response_window.show()

        self.query_thread = QueryThread(query, model_preference, custom_temperature, current_custom_freq_penalty)
        self.query_thread.response_signal.connect(self.response_window.append_response)
        #self.query_thread.done_signal.connect(lambda: QMessageBox.information(self.main_window, "Done", "Query completed."))
        self.query_thread.start()

if __name__ == "__main__":
    app = MyApp(sys.argv)
    sys.exit(app.exec_())