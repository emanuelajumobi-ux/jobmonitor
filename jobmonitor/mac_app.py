"""Erzeugt Job-Monitor.app: ein echtes macOS-App-Bundle mit Name und Icon, das die Oberfläche als App-Fenster
startet (`python -m jobmonitor desktop`).

Die App enthält den absoluten Pfad dieses Ordners und wird deshalb lokal erzeugt (`make app`), nicht committet.
Log: ~/Library/Logs/job-monitor.log. Das Icon (jobmonitor/assets/icon.png) erzeugt `render_icon()` einmalig.
"""
from __future__ import annotations

import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

APP_NAME = "Job-Monitor.app"
BUNDLE_ID = "de.local.jobmonitor"
ICON_PNG = Path(__file__).parent / "assets" / "icon.png"
# Von .github/workflows/icon.yml mit Xcode übersetzt; passt sich an hell/dunkel/getönt/transparent an.
ASSETS_CAR = Path(__file__).parent / "assets" / "compiled" / "Assets.car"
ICONSET_SIZES = [16, 32, 64, 128, 256, 512]
LAUNCHER_SWIFT = Path(__file__).parent / "assets" / "launcher.swift"   # Hauptprogramm, kann auch Mitteilungen


def launcher(root: Path) -> str:
    repo = str(root).replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    return f'''#!/bin/zsh
# Startet den Job-Monitor als App-Fenster. Pfad wird von `make app` eingetragen.
cd "{repo}" || exit 1
# Aus Finder/Dock gestartet gibt es nur /usr/bin:/bin:… – TeX (latexmk) und Homebrew (gh) ergänzen
export PATH="/Library/TeX/texbin:/opt/homebrew/bin:/usr/local/bin:$PATH"
exec ./.venv/bin/python -m jobmonitor desktop >> "$HOME/Library/Logs/job-monitor.log" 2>&1
'''


def info_plist(adaptive: bool = False) -> dict:
    info = {
        "CFBundleName": "Job-Monitor", "CFBundleDisplayName": "Job-Monitor", "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleExecutable": "Job-Monitor", "CFBundleIconFile": "AppIcon", "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0", "CFBundleVersion": "1", "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True, "LSApplicationCategoryType": "public.app-category.productivity",
    }
    if adaptive:
        info["CFBundleIconName"] = "AppIcon"   # Icon aus Assets.car; AppIcon.icns bleibt Rückfall
    return info


def _icns(png: Path, target: Path) -> bool:
    if not (png.exists() and shutil.which("sips") and shutil.which("iconutil")):
        return False
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "AppIcon.iconset"
        iconset.mkdir()
        for size in ICONSET_SIZES:
            for scale in (1, 2):
                name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
                subprocess.run(["sips", "-z", str(size * scale), str(size * scale), str(png), "--out",
                                str(iconset / name)], check=True, capture_output=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(target)], check=True, capture_output=True)
    return True


def create(root: Path) -> Path:
    target = root / APP_NAME
    if target.exists():
        shutil.rmtree(target)
    contents = target / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources").mkdir()
    adaptive = ASSETS_CAR.exists()
    if adaptive:
        shutil.copy2(ASSETS_CAR, contents / "Resources" / "Assets.car")
    with open(contents / "Info.plist", "wb") as fh:
        plistlib.dump(info_plist(adaptive), fh)
    exe = contents / "MacOS" / "Job-Monitor"
    start = contents / "Resources" / "start.sh"
    start.write_text(launcher(root), encoding="utf-8")
    start.chmod(0o755)
    if not _swift_launcher(exe):        # ohne Xcode-Werkzeuge: Skript direkt, Mitteilungen dann über AppleScript
        shutil.copy2(start, exe)
    _icns(ICON_PNG, contents / "Resources" / "AppIcon.icns")
    _sign(target)
    subprocess.run(["touch", str(target)], capture_output=True)   # Finder lädt das Icon neu
    return target


def _sign(app: Path, versuche: int = 4) -> bool:
    """Ad-hoc-Signatur (nur lokal), damit macOS Mitteilungen der App zuordnet. Dateiattribute stören codesign; in
    iCloud-Ordnern setzt der Dateianbieter sie kurz nach dem Anlegen erneut – daher mehrere Versuche mit Prüfung."""
    if not shutil.which("codesign"):
        return False
    for _ in range(versuche):
        subprocess.run(["xattr", "-cr", str(app)], capture_output=True)
        subprocess.run(["codesign", "--force", "--sign", "-", str(app)], capture_output=True)
        if subprocess.run(["codesign", "--verify", str(app)], capture_output=True).returncode == 0:
            return True
        time.sleep(0.5)
    return False


def _swift_launcher(target: Path) -> bool:
    """Hauptprogramm aus launcher.swift: startet start.sh oder sendet Mitteilungen (benachrichtigung.py)."""
    if not (sys.platform == "darwin" and LAUNCHER_SWIFT.exists() and shutil.which("swiftc")):   # braucht AppKit
        return False
    proc = subprocess.run(["swiftc", "-O", "-o", str(target), str(LAUNCHER_SWIFT)], capture_output=True)
    return proc.returncode == 0


LAYERS = ["rings", "center", "hit"]   # von hinten nach vorn
ICON_SOURCE = Path(__file__).parent / "assets" / "AppIcon.icon"
BG = (0x0E, 0x3B, 0x36)   # wie icon.json (hell); das adaptive Icon aus Assets.car hat Vorrang


def render_icon(path: Path = ICON_PNG, size: int = 1024) -> Path:
    """Klassisches Icon (PNG → icns) aus denselben Ebenen wie AppIcon.icon: Radar mit einem Treffer auf tiefem
    Türkis. Flach, ohne Verlauf; die Glas-Optik gibt es nur im adaptiven Icon. Nur macOS."""
    from AppKit import (NSBezierPath, NSBitmapImageFileTypePNG, NSBitmapImageRep, NSColor,
                        NSCompositingOperationSourceOver, NSGraphicsContext, NSImage, NSMakeRect, NSShadow,
                        NSZeroRect)

    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(  # noqa: E501
        None, size, size, 8, 4, True, False, "NSDeviceRGBColorSpace", 0, 0)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
    inset = size * 100 / 1024   # Apple-Raster: Körper 824 von 1024
    body = NSMakeRect(inset, inset, size - 2 * inset, size - 2 * inset)
    shape = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(body, size * 0.18, size * 0.18)

    NSGraphicsContext.saveGraphicsState()   # leichter Schlagschatten wie bei Systemicons
    shadow = NSShadow.alloc().init()
    shadow.setShadowColor_(NSColor.colorWithWhite_alpha_(0, 0.3))
    shadow.setShadowBlurRadius_(size * 0.02)
    shadow.setShadowOffset_((0, -size * 0.008))
    shadow.set()
    NSColor.colorWithSRGBRed_green_blue_alpha_(BG[0] / 255, BG[1] / 255, BG[2] / 255, 1).setFill()
    shape.fill()
    NSGraphicsContext.restoreGraphicsState()

    full = NSMakeRect(0, 0, size, size)   # Ebenen nutzen das ganze 1024er Raster
    for name in LAYERS:
        layer = NSImage.alloc().initWithContentsOfFile_(str(ICON_SOURCE / "Assets" / f"{name}.svg"))
        layer.drawInRect_fromRect_operation_fraction_(full, NSZeroRect, NSCompositingOperationSourceOver, 1.0)
    NSGraphicsContext.restoreGraphicsState()
    path.parent.mkdir(parents=True, exist_ok=True)
    rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, {}).writeToFile_atomically_(str(path), True)
    return path


if __name__ == "__main__":
    print(render_icon())
