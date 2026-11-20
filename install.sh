#!/usr/bin/env bash
# Install aula-f75 for the current user.
#
#   ./install.sh              install (builds the interface if it isn't built yet)
#   ./install.sh --build      rebuild the interface from app/web first
#   ./install.sh --no-udev    skip the udev rule (no sudo)
#   ./install.sh --no-battery-log  don't install the background battery logger
#   ./install.sh --uninstall  remove everything this script installed
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_DIR/applications"
ICON_DIR="$DATA_DIR/icons/hicolor/scalable/apps"
UDEV_RULE=/etc/udev/rules.d/70-aula-f75.rules

BUILD=0 UDEV=1 UNINSTALL=0 BATLOG=1
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
for arg in "$@"; do
  case "$arg" in
    --build) BUILD=1 ;;
    --no-udev) UDEV=0 ;;
    --no-battery-log) BATLOG=0 ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (see --help)" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m! %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31mx %s\033[0m\n' "$*" >&2; exit 1; }

refresh_menus() {
  command -v update-desktop-database >/dev/null && update-desktop-database "$APP_DIR" 2>/dev/null || true
  command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || \
    { command -v kbuildsycoca5 >/dev/null && kbuildsycoca5 >/dev/null 2>&1; } || true
}

if [ "$UNINSTALL" = 1 ]; then
  say "Removing aula-f75"
  if command -v systemctl >/dev/null; then
    systemctl --user disable --now aula-f75-battery.service 2>/dev/null || true
  fi
  rm -f "$UNIT_DIR/aula-f75-battery.service"
  rm -f "$BIN_DIR/aula-f75" "$BIN_DIR/aula-f75-app" "$APP_DIR/aula-f75.desktop" "$ICON_DIR/aula-f75.svg"
  refresh_menus
  if [ -f "$UDEV_RULE" ] && [ "$UDEV" = 1 ]; then
    sudo rm -f "$UDEV_RULE" && sudo udevadm control --reload-rules || warn "Could not remove $UDEV_RULE"
  fi
  say "Done. Your backups in $ROOT/backups were left in place."
  exit 0
fi

# 1. Python ------------------------------------------------------------------
command -v python3 >/dev/null || die "python3 not found. Install Python 3.8 or newer."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 8))' || die "Python 3.8 or newer is required."
say "Python: $(python3 --version)"

# 2. Interface ---------------------------------------------------------------
if [ "$BUILD" = 1 ] || [ ! -f "$ROOT/app/static/index.html" ]; then
  say "Building the interface (app/web)"
  command -v node >/dev/null || die "Node.js 20+ is needed to build the interface. Install it, or download a release that includes app/static."
  node -e 'process.exit(parseInt(process.versions.node) < 20 ? 1 : 0)' || die "Node.js 20 or newer is required (found $(node --version))."
  cd "$ROOT/app/web"
  if command -v pnpm >/dev/null; then
    pnpm install --frozen-lockfile && pnpm build
  else
    npm install && npm run build
  fi
  cd "$ROOT"
else
  say "Interface: already built (use --build to rebuild)"
fi

# 3. Device access -------------------------------------------------------------
if [ "$UDEV" = 1 ]; then
  if cmp -s "$ROOT/70-aula-f75.rules" "$UDEV_RULE" 2>/dev/null; then
    say "udev rule: already installed"
  else
    say "Installing udev rule so you can talk to the keyboard without root (needs sudo)"
    sudo install -m 644 "$ROOT/70-aula-f75.rules" "$UDEV_RULE"
    sudo udevadm control --reload-rules
    sudo udevadm trigger --subsystem-match=hidraw
    warn "Unplug and replug the receiver or cable if the keyboard is not found."
  fi
else
  warn "Skipped the udev rule; without it you may need sudo to reach the keyboard."
fi

# 4. Commands, icon and menu entry -----------------------------------------------
mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"
chmod +x "$ROOT/aula_f75.py" "$ROOT/app/aula-f75-app"
ln -sf "$ROOT/aula_f75.py" "$BIN_DIR/aula-f75"
ln -sf "$ROOT/app/aula-f75-app" "$BIN_DIR/aula-f75-app"
install -m 644 "$ROOT/app/web/public/icon.svg" "$ICON_DIR/aula-f75.svg"
cat > "$APP_DIR/aula-f75.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=AULA F75
GenericName=Keyboard settings
Comment=Lighting, key remapping and macros for the AULA F75 keyboard
Exec=$ROOT/app/aula-f75-app
Icon=aula-f75
Terminal=false
Categories=Settings;HardwareSettings;
Keywords=keyboard;rgb;lighting;macro;remap;aula;
StartupNotify=false
EOF
refresh_menus
say "Installed: aula-f75 (command line), aula-f75-app and the AULA F75 menu entry"

case ":$PATH:" in *":$BIN_DIR:"*) ;; *) warn "$BIN_DIR is not on your PATH; add it to use the commands from a terminal." ;; esac

# 5. Battery logger (feeds the battery health estimate) ---------------------------------
if [ "$BATLOG" = 1 ] && command -v systemctl >/dev/null; then
  mkdir -p "$UNIT_DIR"
  install -m 644 "$ROOT/aula-f75-battery.service" "$UNIT_DIR/aula-f75-battery.service"
  sed -i "s|%h/aula-f75|$ROOT|" "$UNIT_DIR/aula-f75-battery.service"
  systemctl --user daemon-reload
  systemctl --user enable --now aula-f75-battery.service && say "Battery logger: running (user service aula-f75-battery)"
else
  warn "Battery logger not installed; the battery health estimate won't collect data."
fi

# 6. Browser for the app window ------------------------------------------------------
if python3 -c "
import importlib.machinery as m, importlib.util as u, sys
l = m.SourceFileLoader('launcher', '$ROOT/app/aula-f75-app')
mod = u.module_from_spec(u.spec_from_loader('launcher', l)); l.exec_module(mod)
sys.exit(mod.browser() is None)"; then
  say "Browser for the app window: found"
else
  warn "No Chromium-based browser found (Chromium, Chrome, Edge, Brave, Vivaldi)."
  warn "The app will open in your default browser instead of its own window."
fi

say "All set. Check the connection with: aula-f75 info"
