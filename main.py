import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib
import os
import secretstorage
import requests
import json
import threading
import subprocess

def apply_css(file):
    css_provider = Gtk.CssProvider()
    css_file_path = os.path.join(os.path.dirname(__file__), file)
    css_provider.load_from_path(css_file_path)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    
def save_model_preference(key, value):
    preference_file = '.gpt_search_app_preference.json'
    data = get_all_preferences()
    data[key] = value

    with open(preference_file, 'w') as file:
        json.dump(data, file)
        show_alert(f"{key} Saved to {preference_file}")

def get_model_preference(key, default_value):
    data = get_all_preferences()
    return data.get(key, default_value)

def get_all_preferences():
    preference_file = '.gpt_search_app_preference.json'
    try:
        with open(preference_file, 'r') as file:
            data = json.load(file)
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_api_key(api_key):
    bus = secretstorage.dbus_init()
    collection = secretstorage.get_default_collection(bus)
    attributes = {'application': 'gpt4-app'}

    collection.create_item('GPT-4 API Key', attributes, api_key, replace=True)
    show_alert("Key Saved")
    
def get_api_key():
    bus = secretstorage.dbus_init()
    collection = secretstorage.get_default_collection(bus)
    for item in collection.get_all_items():
        if item.get_label() == 'GPT-4 API Key':
            return item.get_secret().decode()
    return None

def show_alert(message):
    subprocess.run(["/usr/bin/notify-send", "--icon=error", message])

def query_gpt4_stream(query, response_window, model_preference, custom_temperature, current_custom_freq_penalty):
    api_key = get_api_key()
    if not api_key:
        show_alert("API Key Not Set")
        return

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "model": model_preference,
        "messages": [{"role": "user", "content": query}],
        "stream": True,
        "temperature": custom_temperature,
        "frequency_penalty": current_custom_freq_penalty
    }).encode()

    with requests.post(url, data=data, headers=headers, stream=True) as response:
        try:
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        json_str = line_str[6:]  # Strip 'data: ' prefix

                        if json_str == '[DONE]':
                            response_window.append_response('\n==========================\n')
                            break  # End of stream

                        try:
                            decoded_line = json.loads(json_str)
                            content = decoded_line.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            # Append each chunk of content to the response window
                            response_window.append_response(content)
                        except json.JSONDecodeError:
                            show_alert(f"Invalid JSON after 'data: ' prefix: {json_str}")
                    else:
                        show_alert(f"Non-data line received: {line_str}")
        except Exception as e:
            show_alert(f"Error in GPT-4 API request: {e}")

class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="Settings", transient_for=parent)
        self.set_default_size(400, 100)  # Set a larger size for the dialog

        # Create a vertical box to hold the widgets
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Enter your GPT-4 API Key")
        self.entry.set_visibility(False)
        box.append(self.entry)

        # Add the box to the dialog's content area and show it
        content_area = self.get_content_area()
        content_area.append(box)

        # Add buttons after adding the entry field
        self.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
        self.present()  # Make sure the box and its children are visible

class ModelSettingsDialog(Gtk.Dialog):

    def __init__(self, parent, current_model, current_custom_temperature, current_custom_freq_penalty):
        super().__init__(title="Model Settings", transient_for=parent)
        self.set_default_size(250, 100)

        self.model_combo = Gtk.ComboBoxText()
        self.model_combo.append("gpt-4", 'GPT-4')
        self.model_combo.append("gpt-4-1106-preview", 'GPT-4-1106-Preview')
        self.model_combo.set_active_id(current_model)
        
        self.temperature_label = Gtk.Label(label="Temperature (0-2)")
        self.custom_temperature_entry = Gtk.Entry()
        self.custom_temperature_entry.set_text(str(current_custom_temperature))
        
        self.custom_freq_label = Gtk.Label(label="Frequency Penalty (-2 to 2):")
        self.custom_freq_penalty_entry = Gtk.Entry()
        self.custom_freq_penalty_entry.set_text(str(current_custom_freq_penalty))

        box = self.get_content_area()
        box.append(self.model_combo)
        box.append(self.temperature_label)
        box.append(self.custom_temperature_entry)
        box.append(self.custom_freq_label)
        box.append(self.custom_freq_penalty_entry)

        self.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)        

        self.present()
        
class ResponseWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Response")
        self.set_default_size(400, 300)

        self.response_view = Gtk.TextView()
        self.response_view.set_editable(False)
        self.response_view.set_wrap_mode(Gtk.WrapMode.WORD)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_child(self.response_view)

        self.set_child(scrolled_window)

    def append_response(self, text):
        def update_text_buffer():
            text_buffer = self.response_view.get_buffer()
            end_iter = text_buffer.get_end_iter()
            text_buffer.insert(end_iter, text)
            return False

        GLib.idle_add(update_text_buffer)

class MyApp(Gtk.Application):
    def __init__(self):
        super().__init__()
        self.window = None
        self.response_window = ResponseWindow()

    def on_main_window_close(self, window):
        self.save_window_size(window, "main_window")
        if self.response_window:
            self.save_window_size(self.response_window, "response_window")

    def on_response_window_close(self, window):
        self.save_window_size(window, "response_window")

    def save_window_size(self, window, window_key):
        width = window.get_width()
        height = window.get_height()

        size_data = {}
        if os.path.exists(".gpt_search_app_window_sizes.json"):
            with open(".gpt_search_app_window_sizes.json", "r") as f:
                size_data = json.load(f)

        size_data[window_key] = {"width": width, "height": height}

        with open(".gpt_search_app_window_sizes.json", "w") as f:
            json.dump(size_data, f)

    def restore_window_size(self, window, window_key):
        if os.path.exists(".gpt_search_app_window_sizes.json"):
            with open(".gpt_search_app_window_sizes.json", "r") as f:
                size_data = json.load(f)
                if window_key in size_data:
                    width = size_data[window_key]["width"]
                    height = size_data[window_key]["height"]
                    window.set_default_size(width, height)

    def on_window_size_change(self, window, param):
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor()
        workarea = monitor.get_workarea()
        max_width = workarea.width
        max_height = workarea.height

        current_width = window.get_property("default-width")
        current_height = window.get_property("default-height")

        if current_width > max_width or current_height > max_height:
            new_width = min(current_width, max_width)
            new_height = min(current_height, max_height)
            window.set_default_size(new_width, new_height)

    def show_settings_dialog(self, button):
        dialog = SettingsDialog(self.window)
        dialog.present()  # Show the dialog
        dialog.connect("response", self.dialog_response)

    def dialog_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            api_key = dialog.entry.get_text()
            save_api_key(api_key)
        dialog.destroy()
        
    def show_model_settings_dialog(self, button):
        current_model = get_model_preference('model_preference', 'gpt-4')
        current_custom_temperature = get_model_preference('custom_temperature', 1)
        custom_freq_penalty_entry = get_model_preference('custom_freq_penalty_entry', 0)
        dialog = ModelSettingsDialog(self.window, current_model, current_custom_temperature, custom_freq_penalty_entry)
        dialog.present()
        dialog.connect("response", self.model_dialog_response)

    def model_dialog_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            selected_model = dialog.model_combo.get_active_text()
            model_preference = "gpt-4"
            if 'Preview' in selected_model:
                model_preference = "gpt-4-1106-preview"
            save_model_preference('model_preference', model_preference)

        # Retrieve and save the decimal number
            try:
                custom_temperature = float(dialog.custom_temperature_entry.get_text())
                save_model_preference('custom_temperature', custom_temperature)
            except ValueError:
                show_alert("Invalid decimal number entered")

            try:
                custom_freq_penalty_entry = float(dialog.custom_freq_penalty_entry.get_text())
                save_model_preference('custom_freq_penalty_entry', custom_freq_penalty_entry)
            except ValueError:
                show_alert("Invalid decimal number entered")

        dialog.destroy()
    
    def on_search_button_clicked(self, button, search_entry):
        model_preference = get_model_preference('model_preference', 'gpt-4')
        custom_temperature = get_model_preference('custom_temperature', 1)
        current_custom_freq_penalty = get_model_preference('current_custom_freq_penalty', 0.0)
        buffer = search_entry.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        query = buffer.get_text(start_iter, end_iter, True)

        if not self.response_window.is_visible():
            self.response_window.present()

        query_thread = threading.Thread(target=query_gpt4_stream, args=(query, self.response_window, model_preference, custom_temperature, current_custom_freq_penalty))
        query_thread.start()

    def do_activate(self):
        if not self.response_window.is_visible():
            self.restore_window_size(self.response_window, "response_window")
            self.response_window.connect("close-request", self.on_response_window_close)

            self.response_window.set_size_request(666, 666)
            self.response_window.present()
            
        if not self.window:
            self.window = Gtk.ApplicationWindow(application=self)
            apply_css("style.css")
            self.window.set_title("GPT-4 Search App")

            self.restore_window_size(self.window, "main_window")
            self.window.connect("close-request", self.on_main_window_close)
            self.window.connect("notify::default-width", self.on_window_size_change)
            self.window.connect("notify::default-height", self.on_window_size_change)

            self.window.set_size_request(666, 333)
            self.response_view = Gtk.TextView()
            self.response_view.set_editable(False)

            pointer_cursor = Gdk.Cursor.new_from_name("pointer")
            icon = Gtk.Image.new_from_icon_name("dialog-password")
            model_settings_icon = Gtk.Image.new_from_icon_name("preferences-system")
            model_settings_button = Gtk.Button(label="")
            model_settings_button.set_child(model_settings_icon)
            model_settings_button.add_css_class("settings-button")
            model_settings_button.set_halign(Gtk.Align.START)
            model_settings_button.set_valign(Gtk.Align.CENTER)
            model_settings_button.set_cursor(pointer_cursor)
            model_settings_button.connect("clicked", self.show_model_settings_dialog)

            scrollable = Gtk.ScrolledWindow()  
            scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)  
            search_entry = Gtk.TextView()  
            search_entry.set_wrap_mode(Gtk.WrapMode.WORD) 
            buffer = search_entry.get_buffer()  
            buffer.set_text("Enter your query")
            scrollable.set_min_content_height(333)
            scrollable.set_child(search_entry)

            search_button = Gtk.Button(label="Search")
            search_button.connect("clicked", self.on_search_button_clicked, search_entry)
            search_button.set_cursor(pointer_cursor)

            settings_button = Gtk.Button(label="")
            settings_button.set_child(icon)
            settings_button.add_css_class("settings-button")
            settings_button.set_halign(Gtk.Align.START)
            settings_button.set_valign(Gtk.Align.CENTER)
            settings_button.set_cursor(pointer_cursor)
            settings_button.connect("clicked", self.show_settings_dialog)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            inline_button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            inline_button_box.set_spacing(6)
            inline_button_box.append(settings_button)
            inline_button_box.append(model_settings_button)

            box.set_spacing(6)
            box.append(inline_button_box)
            box.append(scrollable)
            box.append(search_button)

            self.window.set_child(box)

            self.window.present()      

app = MyApp()
app.run(None)
