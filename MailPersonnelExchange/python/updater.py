from __future__ import annotations

import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

# ← Remplacer par "username/nom-du-repo" après création du dépôt GitHub
GITHUB_REPO = "Asmodeus2006/ProMailPersonnelExchange"


def _parse_ver(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0,)


def is_newer(latest: str, current: str) -> bool:
    return _parse_ver(latest) > _parse_ver(current)


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

class UpdateCheckerSignals(QObject):
    found = pyqtSignal(str, str)   # (new_version, download_url)


class UpdateDownloaderSignals(QObject):
    progress = pyqtSignal(int)   # 0-100
    done     = pyqtSignal(str)   # chemin local vers l'installateur
    error    = pyqtSignal(str)


# ---------------------------------------------------------------------------
# Workers (s'exécutent dans QThreadPool)
# ---------------------------------------------------------------------------

class UpdateChecker(QRunnable):
    def __init__(self, current_version: str) -> None:
        super().__init__()
        self._version = current_version
        self.signals = UpdateCheckerSignals()

    def run(self) -> None:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "PromedMessagerie"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())

            tag = data.get("tag_name", "")
            if not is_newer(tag, self._version):
                return

            for asset in data.get("assets", []):
                if asset["name"].lower().endswith(".exe"):
                    self.signals.found.emit(tag.lstrip("v"), asset["browser_download_url"])
                    return
        except Exception:
            pass  # Erreur réseau silencieuse — ne pas déranger l'utilisateur


class UpdateDownloader(QRunnable):
    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url
        self.signals = UpdateDownloaderSignals()

    def run(self) -> None:
        try:
            tmp = Path(tempfile.mkdtemp()) / "PromedMessagerie_Setup.exe"
            req = urllib.request.Request(self._url, headers={"User-Agent": "PromedMessagerie"})
            with urllib.request.urlopen(req, timeout=120) as r:
                total = int(r.headers.get("Content-Length", 0) or 0)
                downloaded = 0
                with open(tmp, "wb") as f:
                    while True:
                        buf = r.read(65536)
                        if not buf:
                            break
                        f.write(buf)
                        downloaded += len(buf)
                        if total:
                            self.signals.progress.emit(int(downloaded * 100 / total))
            self.signals.done.emit(str(tmp))
        except Exception as exc:
            self.signals.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Lancement de l'installateur (tests)
# ---------------------------------------------------------------------------

def run_installer_and_quit(installer_path: str, quit_fn) -> None:
    """Lance l'installateur en mode silencieux puis ferme l'application."""
    subprocess.Popen(
        [installer_path, "/verysilent", "/norestart", "/closeapplications"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    quit_fn()

