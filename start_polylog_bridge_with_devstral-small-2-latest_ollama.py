#!/usr/bin/env python3
"""
POLYLOG: Ollama + devstral-small-2:latest

===================================

Startet Ollama und lädt devstral-small-2:latest
 (Mistrals Coding-LLM).

Usage:
    python start_ollama.py              # Startet Ollama + prüft devstral-small-2:latest
    python start_ollama.py --pull       # Lädt devstral-small-2:latest herunter
    python start_ollama.py --chat       # Startet interaktiven Chat
    python start_ollama.py --status     # Zeigt Status

Autor: Jan-Christoph Thieme (mit Vibe Coding)
Datum: 13.01.2026
Licensed under EUPL 1.2
"""

import subprocess
import sys
import time
import platform
import argparse
from pathlib import Path

# Optional: requests für API-Checks
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def ensure_requests_installed() -> bool:
    """Installiert requests automatisch falls nicht vorhanden."""
    global REQUESTS_AVAILABLE
    if REQUESTS_AVAILABLE:
        return True

    print("requests-Library nicht gefunden. Installiere automatisch...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "requests"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("✓ requests installiert")
        # Neu importieren
        import requests
        REQUESTS_AVAILABLE = True
        return True
    except Exception as e:
        print(f"✗ Installation fehlgeschlagen: {e}")
        print("  Manuell: pip install requests")
        return False


# =============================================================================
# Konfiguration
# =============================================================================

MODEL = "devstral-small-2:latest"  # devstral-small-2:latest (optimiert für Code)
OLLAMA_HOST = "http://localhost:11434"
PULL_TIMEOUT = 1800  # 30 Minuten für Download


# =============================================================================
# Hilfsfunktionen
# =============================================================================

def print_header():
    """Zeigt Header."""
    print("=" * 60)
    print("POLYLOG: Ollama + devstral-small-2:latest")
    print("=" * 60)
    print(f"Modell: {MODEL}")
    print(f"Host: {OLLAMA_HOST}")
    print(f"Platform: {platform.system()}")
    print("=" * 60)
    print()


def is_ollama_installed() -> bool:
    """Prüft ob Ollama installiert ist."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_ollama_running() -> bool:
    """Prüft ob Ollama Server läuft."""
    if not REQUESTS_AVAILABLE:
        # Fallback ohne requests
        try:
            import urllib.request
            urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2)
            return True
        except Exception:
            return False

    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def is_model_available(model: str) -> bool:
    """Prüft ob Modell verfügbar ist."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return model in result.stdout
    except Exception:
        return False


def start_ollama_server() -> bool:
    """Startet Ollama Server im Hintergrund."""
    print("Starte Ollama Server...")

    try:
        if platform.system() == "Windows":
            # Windows: Start im Hintergrund
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            # Linux/Mac: Start im Hintergrund
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

        # Warten bis Server bereit ist
        for i in range(10):
            time.sleep(1)
            if is_ollama_running():
                print("✓ Ollama Server gestartet")
                return True
            print(f"  Warte... ({i+1}/10)")

        print("✗ Timeout beim Starten von Ollama")
        return False

    except Exception as e:
        print(f"✗ Fehler beim Starten: {e}")
        return False


def pull_model(model: str) -> bool:
    """Lädt Modell herunter."""
    print(f"Lade {model} herunter...")
    print("(Dies kann einige Minuten dauern, ca. 14GB)")
    print()

    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            timeout=PULL_TIMEOUT
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("✗ Timeout beim Download")
        return False
    except Exception as e:
        print(f"✗ Fehler: {e}")
        return False


def run_chat(model: str):
    """Startet interaktiven Chat."""
    print(f"Starte Chat mit {model}...")
    print("(Beenden mit /bye oder Ctrl+C)")
    print()

    try:
        subprocess.run(["ollama", "run", model])
    except KeyboardInterrupt:
        print("\n\nChat beendet.")


def show_status():
    """Zeigt aktuellen Status."""
    print("Status:")
    print()

    # Ollama installiert?
    if is_ollama_installed():
        print("  ✓ Ollama installiert")
    else:
        print("  ✗ Ollama nicht gefunden")
        print("    Installation: https://ollama.ai")
        return

    # Server läuft?
    if is_ollama_running():
        print("  ✓ Ollama Server läuft")
    else:
        print("  ○ Ollama Server nicht aktiv")

    # Modell verfügbar?
    if is_model_available(MODEL):
        print(f"  ✓ {MODEL} verfügbar")
    else:
        print(f"  ○ {MODEL} nicht heruntergeladen")
        print(f"    Herunterladen: python {Path(__file__).name} --pull")


def show_usage():
    """Zeigt Verwendungshinweise."""
    print()
    print("Verwendung:")
    print(f"  ollama run {MODEL}                    # Interaktiver Chat")
    print(f"  python polylog_bridge.py              # Mit Polylog Bridge")
    print(f"  python polylog_bridge.py --model {MODEL}")
    print()
    print("Python-Integration:")
    print("  from polylog_bridge import PolylogBridge")
    print("  bridge = PolylogBridge()")
    print("  response = bridge.process('Erkläre diesen Code...')")
    print()


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Polylog: Ollama + Devstral Starter"
    )
    parser.add_argument(
        "--pull", action="store_true",
        help="Lädt Devstral herunter"
    )
    parser.add_argument(
        "--chat", action="store_true",
        help="Startet interaktiven Chat"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Zeigt Status"
    )
    parser.add_argument(
        "--model", default=MODEL,
        help=f"Modell-Name (default: {MODEL})"
    )

    args = parser.parse_args()
    model = args.model

    print_header()

    # Status anzeigen
    if args.status:
        show_status()
        return

    # Prüfen ob Ollama installiert ist
    if not is_ollama_installed():
        print("✗ Ollama nicht gefunden.")
        print()
        print("Installation:")
        print("  Linux:   curl -fsSL https://ollama.ai/install.sh | sh")
        print("  Windows: https://ollama.ai/download")
        print("  Mac:     brew install ollama")
        sys.exit(1)

    print("✓ Ollama installiert")

    # Nur Pull
    if args.pull:
        if not is_ollama_running():
            if not start_ollama_server():
                sys.exit(1)

        if pull_model(model):
            print(f"✓ {model} erfolgreich heruntergeladen")
        else:
            print(f"✗ Fehler beim Herunterladen von {model}")
            sys.exit(1)
        return

    # Nur Chat
    if args.chat:
        if not is_ollama_running():
            if not start_ollama_server():
                sys.exit(1)

        if not is_model_available(model):
            print(f"{model} nicht gefunden. Lade herunter...")
            if not pull_model(model):
                sys.exit(1)

        run_chat(model)
        return

    # Standard: Server starten und Status prüfen
    if is_ollama_running():
        print("✓ Ollama Server läuft bereits")
    else:
        if not start_ollama_server():
            sys.exit(1)

    # Modell prüfen
    print()
    if is_model_available(model):
        print(f"✓ {model} ist verfügbar")
    else:
        print(f"○ {model} nicht gefunden")
        response = input(f"  Jetzt herunterladen? (ca. 14GB) [j/N]: ")
        if response.lower() in ['j', 'y', 'ja', 'yes']:
            if not pull_model(model):
                sys.exit(1)
            print(f"✓ {model} erfolgreich heruntergeladen")
        else:
            print(f"  Später: python {Path(__file__).name} --pull")

    print()
    print("=" * 60)
    print("Bereit!")
    print("=" * 60)

    # Sicherstellen dass requests installiert ist
    if not ensure_requests_installed():
        sys.exit(1)

    # Bridge laden und interaktiven Modus starten
    try:
        from polylog_bridge import PolylogBridge, BridgeConfig

        config = BridgeConfig(model=model, temperature=0.3)
        bridge = PolylogBridge(config)

        # Direkt in interaktiven Modus
        bridge.run_interactive()

    except ImportError as e:
        print(f"\nFehler beim Import der Bridge: {e}")
        print("Stelle sicher, dass polylog_bridge.py im gleichen Verzeichnis liegt.")
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\nFehler: {e}")
        sys.exit(1)

    print("\nAuf Wiedersehen!")


if __name__ == "__main__":
    main()
