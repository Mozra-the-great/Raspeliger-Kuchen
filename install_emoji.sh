#!/bin/bash
# ============================================================
# Emoji-Font Installer für Raspberry Pi Touchscreen-Kiosk
# Zielsystem: Pi 2 (192.168.1.232) - Chromium Kiosk
# ============================================================
# Was er tut:
#   1. apt update
#   2. fonts-noto-color-emoji (Googles Standard-Emoji-Font)
#   3. fonts-symbola (Fallback für Unicode-Symbole)
#   4. Font-Cache refreshen
#   5. Chromium killen → Kiosk respawnt mit neuen Fonts
# ============================================================

set -e

echo "==> Aktualisiere Paketquellen"
sudo apt-get update -qq

echo "==> Installiere Emoji-Fonts"
sudo apt-get install -y fonts-noto-color-emoji fonts-symbola

echo "==> Refreshe Font-Cache"
sudo fc-cache -fv > /dev/null

echo "==> Verifiziere Installation"
if fc-list | grep -qi "noto color emoji"; then
    echo "    OK: Noto Color Emoji installiert"
else
    echo "    FEHLER: Font wurde nicht gefunden!"
    exit 1
fi

echo "==> Killing Chromium (Kiosk-Service startet automatisch neu)"
pkill chromium 2>/dev/null || true
sleep 1

echo ""
echo "============================================================"
echo "FERTIG. Emojis sollten jetzt auf dem Touchscreen sichtbar sein."
echo "Falls Chromium nicht automatisch wiederkommt:"
echo "   sudo systemctl restart kiosk.service"
echo "   (oder Pi neu starten: sudo reboot)"
echo "============================================================"
