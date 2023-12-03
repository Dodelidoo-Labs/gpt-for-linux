#!/bin/bash
# Check if the script is being run as root or with sudo
if [ "$UID" -eq 0 ]; then
    echo "Ugly! Do not run as sudo!"
    exit 1
fi

# Define paths
install_path="$HOME/.local/share/gpt4-search-app"
desktop_file_path="$HOME/.local/share/applications/gpt4-search-app.desktop"
icon_path="$install_path/icon.png"
script_path="$install_path/main.py"

check_dependencies() {
    dependencies=("python" "wget" "gtk4" "python-gobject" "python-requests" "python-secretstorage")
    missing_dependencies=()

    for pkg in "${dependencies[@]}"; do
        if ! pacman -Qs "$pkg" > /dev/null; then
            missing_dependencies+=("$pkg")
        fi
    done

    if [ ${#missing_dependencies[@]} -eq 0 ]; then
        echo "All necessary dependencies are already installed."
    else
        echo "The following packages are missing and need to be installed: ${missing_dependencies[*]}"
        read -p "Do you want to proceed with installation? (y/N) " response
        case $response in
            [yY][eE][sS]|[yY]) 
                for pkg in "${missing_dependencies[@]}"; do
                    echo "Installing $pkg..."
                    sudo pacman -S $pkg
                done
                ;;
            *)
                echo "Installation cancelled by user."
                exit 1
                ;;
        esac
    fi
}

# Run the function
check_dependencies

# Create install directory
echo "Creating installation directory..."
mkdir -p "$install_path"
echo "Downloading scripts..."
# Download script, CSS, and icon
wget -O "$script_path" "https://raw.githubusercontent.com/TukuToi/gpt-for-linux/main/main.py"
wget -O "$icon_path" "https://raw.githubusercontent.com/TukuToi/gpt-for-linux/main/icon.png"
wget -O "$install_path/style.css" "https://raw.githubusercontent.com/TukuToi/gpt-for-linux/main/style.css"

echo "Creating Desktop file..."
# Create .desktop file
echo "[Desktop Entry]
Type=Application
Name=GPT-4 Search App
Exec=python3 $script_path
Icon=$icon_path
Terminal=false
Categories=Utility;
" > "$desktop_file_path"

echo "Making scripts executable..."
# Make the script executable
chmod +x "$script_path"

# Make the .desktop file executable
chmod +x "$desktop_file_path"

echo "GPT-4 Search App installed successfully."