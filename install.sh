#!/bin/bash

# Define paths
install_path="$HOME/.local/share/gpt4-search-app"
desktop_file_path="$HOME/.local/share/applications/gpt4-search-app.desktop"
icon_path="$install_path/icon.png"
script_path="$install_path/main.py"

# Check and install dependencies
check_dependencies() {
    dependencies=("python" "wget" "gtk4" "python-gobject" "python-requests" "python-secretstorage")

    for pkg in "${dependencies[@]}"; do
        if ! pacman -Qs "$pkg" > /dev/null; then
            echo "Installing missing package: $pkg"
            sudo pacman -S --noconfirm $pkg
        fi
    done
}

# Run the function
check_dependencies

# Create install directory
mkdir -p "$install_path"

# Download script, CSS, and icon
# (Replace the URLs with actual URLs where your files are hosted)
wget -O "$script_path" "http://example.com/main.py"
wget -O "$icon_path" "http://example.com/icon.png"
wget -O "$install_path/style.css" "http://example.com/style.css"

# Create .desktop file
echo "[Desktop Entry]
Type=Application
Name=GPT-4 Search App
Exec=python3 $script_path
Icon=$icon_path
Terminal=false
Categories=Utility;
" > "$desktop_file_path"

# Make the script executable
chmod +x "$script_path"

# Make the .desktop file executable
chmod +x "$desktop_file_path"

echo "GPT-4 Search App installed successfully."