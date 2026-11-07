#!/bin/sh
# Installs Halo Cursors for the current user and applies the theme when the desktop is recognized.
set -e
here=$(cd "$(dirname "$0")" && pwd)
dest="${XDG_DATA_HOME:-$HOME/.local/share}/icons"

case "$1" in
    Light|light) base=Light ;;
    Dark|dark) base=Dark ;;
    *)
        echo "Usage: ./install.sh Light|Dark [Color]"
        echo "Colors: Red Cyan Green Magenta Blue Yellow Violet Orange"
        exit 1 ;;
esac

if [ -n "$2" ]; then
    color=$(printf '%s' "$2" | awk '{print toupper(substr($0,1,1)) tolower(substr($0,2))}')
    theme="Halo-$color-$base"
    src="$here/Colors/$theme"
else
    theme="Halo-$base"
    src="$here/$theme"
fi
[ -d "$src" ] || { echo "Theme not found: $theme"; exit 1; }

mkdir -p "$dest"
rm -rf "$dest/$theme"
cp -a "$src" "$dest/$theme"
mkdir -p "$HOME/.icons/default"
printf '[Icon Theme]\nInherits=%s\n' "$theme" > "$HOME/.icons/default/index.theme"

have() { command -v "$1" >/dev/null 2>&1; }
desktop=$(printf '%s' "${XDG_CURRENT_DESKTOP:-}" | tr 'A-Z' 'a-z')

case "$desktop" in
    *kde*)
        if have plasma-apply-cursortheme; then plasma-apply-cursortheme "$theme"; fi ;;
    *cinnamon*)
        if have gsettings; then gsettings set org.cinnamon.desktop.interface cursor-theme "$theme"; fi ;;
    *xfce*)
        if have xfconf-query; then xfconf-query -c xsettings -p /Gtk/CursorThemeName -n -t string -s "$theme"; fi ;;
    *)
        if have gsettings; then gsettings set org.gnome.desktop.interface cursor-theme "$theme"; fi ;;
esac

echo "Installed $theme in $dest."
echo "If the cursor does not change right away, log out and back in."
case "$desktop" in *cosmic*) echo "COSMIC: if it still shows the old cursor, pick Halo in Settings > Desktop > Appearance." ;; esac
