#!/usr/bin/env python3
"""
POLYLOG BRIDGE - Tool-Integration für lokale LLMs

Python-basierte Tool-Definitionen mit Dekoratoren statt JSON-Schema.
Nutzt Ollama's native Tool-Calling API.

Usage:
    python polylog_bridge.py                         # Interaktiv mit devstral-small-2:latest
    python polylog_bridge.py --model qwen2.5:3b      # Mit anderem Modell
    python polylog_bridge.py --test                  # Test-Modus (ohne Ollama)

Autor: Jan-Christoph Thieme (mit Vibe Coding)
Datum: 13.01.2026
"""

import json
import platform
import sys
import inspect
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, get_type_hints
from dataclasses import dataclass, field
from functools import wraps

# Platform
IS_WINDOWS = platform.system() == "Windows"

# Requests
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("Warning: pip install requests")


# =============================================================================
# Tool Registry - Dekorator-basierte Tool-Definitionen
# =============================================================================

class ToolRegistry:
    """Registry für Tool-Funktionen mit automatischer Schema-Generierung."""

    _tools: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def tool(cls, description: str):
        """
        Dekorator um eine Funktion als Tool zu registrieren.

        @ToolRegistry.tool("Liest den Inhalt einer Datei")
        def read_file(path: str) -> dict:
            ...
        """
        def decorator(func: Callable) -> Callable:
            # Schema aus Type Hints generieren
            hints = get_type_hints(func)
            sig = inspect.signature(func)

            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue

                param_type = hints.get(param_name, str)

                # Python Type → JSON Schema Type
                type_map = {
                    str: "string",
                    int: "integer",
                    float: "number",
                    bool: "boolean",
                    list: "array",
                    dict: "object"
                }

                json_type = type_map.get(param_type, "string")

                # Parameter-Beschreibung aus Docstring extrahieren
                param_desc = f"Parameter: {param_name}"
                if func.__doc__:
                    for line in func.__doc__.split('\n'):
                        if param_name in line and ':' in line:
                            param_desc = line.split(':', 1)[-1].strip()
                            break

                properties[param_name] = {
                    "type": json_type,
                    "description": param_desc
                }

                # Required wenn kein Default
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            # Tool registrieren
            cls._tools[func.__name__] = {
                "function": func,
                "schema": {
                    "type": "function",
                    "function": {
                        "name": func.__name__,
                        "description": description,
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required
                        }
                    }
                }
            }

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper

        return decorator

    @classmethod
    def get_schemas(cls) -> List[Dict]:
        """Gibt alle Tool-Schemas für Ollama zurück."""
        return [t["schema"] for t in cls._tools.values()]

    @classmethod
    def execute(cls, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Führt ein Tool aus."""
        if name not in cls._tools:
            return {"success": False, "error": f"Unknown tool: {name}"}

        try:
            func = cls._tools[name]["function"]
            result = func(**args)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def list_tools(cls) -> List[str]:
        """Listet alle registrierten Tools."""
        return list(cls._tools.keys())


# =============================================================================
# Tool-Konfiguration
# =============================================================================

@dataclass
class ToolConfig:
    """Konfiguration für Tools."""
    working_dir: Path = field(default_factory=lambda: Path(".").resolve())
    allow_write: bool = True


# Globale Config (wird von Tools verwendet)
_config = ToolConfig()


def set_config(config: ToolConfig):
    """Setzt die globale Tool-Konfiguration."""
    global _config
    _config = config


def _safe_path(path_str: str) -> Optional[Path]:
    """Validiert Pfad - muss im Working Directory sein."""
    try:
        path = Path(path_str)
        if not path.is_absolute():
            path = _config.working_dir / path
        path = path.resolve()

        # Sicherheitscheck
        try:
            path.relative_to(_config.working_dir)
            return path
        except ValueError:
            return None
    except Exception:
        return None


# =============================================================================
# Tools: read_file, write_file, webrecherche
# =============================================================================

@ToolRegistry.tool("Liest den Inhalt einer Datei")
def read_file(path: str) -> dict:
    """
    Liest eine Datei und gibt den Inhalt zurück.

    path: Pfad zur Datei (relativ zum Projekt)
    """
    safe_path = _safe_path(path)
    if not safe_path:
        return {"success": False, "error": f"Ungültiger Pfad: {path}"}

    if not safe_path.exists():
        return {"success": False, "error": f"Datei nicht gefunden: {path}"}

    if not safe_path.is_file():
        return {"success": False, "error": f"Kein File: {path}"}

    try:
        content = safe_path.read_text(encoding='utf-8', errors='ignore')
        # Limit für LLM Context
        if len(content) > 10000:
            content = content[:10000] + "\n... [truncated]"

        return {
            "success": True,
            "path": path,
            "content": content,
            "size": safe_path.stat().st_size
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@ToolRegistry.tool("Schreibt Inhalt in eine Datei")
def write_file(path: str, content: str) -> dict:
    """
    Schreibt eine Datei.

    path: Pfad zur Datei
    content: Inhalt der Datei
    """
    if not _config.allow_write:
        return {"success": False, "error": "write_file deaktiviert"}

    safe_path = _safe_path(path)
    if not safe_path:
        return {"success": False, "error": f"Ungültiger Pfad: {path}"}

    try:
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding='utf-8')
        return {
            "success": True,
            "path": path,
            "bytes_written": len(content.encode('utf-8'))
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@ToolRegistry.tool("Führt eine Web-Recherche durch")
def webrecherche(query: str, max_results: int = 5, lang: str = "de") -> dict:
    """
    Führt eine Web-Recherche durch.

    query: Suchbegriff(e)
    max_results: Maximale Anzahl Ergebnisse (default: 5)
    lang: Sprache für Suche (default: de)
    """
    import urllib.parse

    results = []
    errors = []

    # Wikipedia API (funktioniert zuverlässig)
    if REQUESTS_AVAILABLE:
        headers = {"User-Agent": "PolylogBridge/1.0"}
        try:
            wiki_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query.replace(' ', '_'))}"
            response = requests.get(wiki_url, timeout=10, headers=headers)

            if response.status_code == 200:
                data = response.json()
                if data.get("extract"):
                    results.append({
                        "title": data.get("title", query),
                        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                        "snippet": data.get("extract", "")[:400],
                        "source": "wikipedia"
                    })
        except Exception as e:
            errors.append(f"Wikipedia: {e}")

        # OpenSearch für mehr Ergebnisse
        try:
            search_url = f"https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit={max_results}&format=json"
            response = requests.get(search_url, timeout=10, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if len(data) >= 4:
                    for title, url in zip(data[1], data[3]):
                        if not any(r.get("title") == title for r in results):
                            results.append({
                                "title": title,
                                "url": url,
                                "snippet": f"Wikipedia: {title}",
                                "source": "wikipedia"
                            })
        except Exception:
            pass

    summary_parts = [f"🔍 Web-Recherche: '{query}'"]
    if results:
        for r in results[:max_results]:
            summary_parts.append(f"\n📚 {r['title']}")
            summary_parts.append(f"   {r['snippet'][:150]}")
            if r.get("url"):
                summary_parts.append(f"   → {r['url']}")
        summary_parts.append(f"\n✓ {len(results)} Ergebnisse")
    else:
        summary_parts.append(f"\n⚠ Keine Ergebnisse - versuche: https://duckduckgo.com/?q={urllib.parse.quote(query)}")

    return {
        "success": bool(results),
        "query": query,
        "summary": '\n'.join(summary_parts),
        "results_count": len(results),
        "results": results,
        "errors": errors
    }


# =============================================================================
# Ollama Client
# =============================================================================

@dataclass
class BridgeConfig:
    """Konfiguration für die Polylog Bridge."""
    model: str = "devstral-small-2:latest"
    ollama_host: str = "http://localhost:11434"
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 300
    working_dir: Path = field(default_factory=lambda: Path(".").resolve())


class OllamaClient:
    """Ollama Client mit Native Tool-Calling und automatischer API-Erkennung."""

    CHAT_ENDPOINTS = ["/api/chat", "/v1/chat/completions", "/chat"]
    GENERATE_ENDPOINTS = ["/api/generate", "/generate"]

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.base_url = config.ollama_host.rstrip("/")
        self._working_chat_endpoint: Optional[str] = None
        self._working_generate_endpoint: Optional[str] = None
        self._use_openai_format = False

    def _build_prompt_from_messages(self, messages: List[Dict]) -> str:
        """Konvertiert Messages zu einem einzelnen Prompt für /api/generate."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            else:
                parts.append(f"User: {content}")
        parts.append("Assistant:")
        return "\n\n".join(parts)

    def _try_request(self, endpoint: str, payload: Dict, headers: Dict) -> Optional[Any]:
        """Versucht einen Request an einen Endpunkt."""
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.post(url, json=payload, headers=headers, timeout=self.config.timeout)
            if response.status_code in (200, 201):
                return response
        except Exception:
            pass
        return None

    def _discover_endpoints(self):
        """Erkennt verfügbare API-Endpunkte."""
        if self._working_chat_endpoint or self._working_generate_endpoint:
            return

        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        for endpoint in self.CHAT_ENDPOINTS:
            if "/v1/" in endpoint:
                test_payload = {
                    "model": self.config.model,
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1
                }
            else:
                test_payload = {
                    "model": self.config.model,
                    "messages": [{"role": "user", "content": "test"}],
                    "stream": False,
                    "options": {"num_predict": 1}
                }

            resp = self._try_request(endpoint, test_payload, headers)
            if resp:
                self._working_chat_endpoint = endpoint
                self._use_openai_format = "/v1/" in endpoint
                return

        for endpoint in self.GENERATE_ENDPOINTS:
            test_payload = {
                "model": self.config.model,
                "prompt": "test",
                "stream": False,
                "options": {"num_predict": 1}
            }
            resp = self._try_request(endpoint, test_payload, headers)
            if resp:
                self._working_generate_endpoint = endpoint
                return

    def chat(self, messages: List[Dict], use_tools: bool = True) -> Dict[str, Any]:
        """Sendet Chat-Anfrage mit optionalem Tool-Calling."""
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests nicht verfügbar")

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        self._discover_endpoints()

        if self._working_chat_endpoint:
            return self._chat_via_endpoint(messages, headers, use_tools)

        if self._working_generate_endpoint:
            return self._chat_via_generate(messages, headers)

        raise RuntimeError(
            f"Kein funktionierender Ollama-Endpunkt gefunden.\n"
            f"Bitte prüfen:\n"
            f"  1. Läuft Ollama? (ollama serve)\n"
            f"  2. Ist das Modell '{self.config.model}' installiert? (ollama list)\n"
            f"  3. Ist der Host korrekt? ({self.base_url})"
        )

    def _chat_via_endpoint(self, messages: List[Dict], headers: Dict, use_tools: bool) -> Dict[str, Any]:
        """Chat über den erkannten Endpunkt."""
        endpoint = self._working_chat_endpoint

        if self._use_openai_format:
            payload = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            if use_tools and ToolRegistry.get_schemas():
                payload["tools"] = ToolRegistry.get_schemas()
        else:
            payload = {
                "model": self.config.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens
                }
            }
            if use_tools:
                payload["tools"] = ToolRegistry.get_schemas()

        try:
            response = requests.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                headers=headers,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            data = response.json()

            if self._use_openai_format:
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                return {
                    "content": message.get("content", ""),
                    "tool_calls": message.get("tool_calls", [])
                }
            else:
                message = data.get("message", {})
                return {
                    "content": message.get("content", ""),
                    "tool_calls": message.get("tool_calls", [])
                }
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Ollama nicht erreichbar ({self.base_url})")
        except requests.exceptions.HTTPError as e:
            self._working_chat_endpoint = None
            raise RuntimeError(f"Ollama HTTP Fehler: {e}")
        except Exception as e:
            raise RuntimeError(f"Ollama Fehler: {e}")

    def _chat_via_generate(self, messages: List[Dict], headers: Dict) -> Dict[str, Any]:
        """Fallback: Nutzt /api/generate statt /api/chat."""
        prompt = self._build_prompt_from_messages(messages)
        endpoint = self._working_generate_endpoint or "/api/generate"

        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens
            }
        }

        try:
            response = requests.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                headers=headers,
                timeout=self.config.timeout
            )
            response.raise_for_status()

            data = response.json()
            return {
                "content": data.get("response", ""),
                "tool_calls": []
            }
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Ollama nicht erreichbar ({self.base_url})")
        except Exception as e:
            raise RuntimeError(f"Ollama Fehler: {e}")

    def is_available(self) -> bool:
        """Prüft Ollama-Verbindung."""
        try:
            for endpoint in ["/api/tags", "/v1/models", "/api/version"]:
                try:
                    r = requests.get(
                        f"{self.base_url}{endpoint}",
                        headers={"Accept": "application/json"},
                        timeout=5
                    )
                    if r.status_code == 200:
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False


# =============================================================================
# Prompt Registry - Für Bootblock
# =============================================================================

class PromptRegistry:
    """Registry für Bootblock-Prompt."""

    _bootblock: Optional[str] = None
    _bootblock_loaded: bool = False

    @classmethod
    def get_bootblock(cls) -> Optional[str]:
        """Lädt den Bootblock aus bootblock.md."""
        if cls._bootblock_loaded:
            return cls._bootblock

        cls._bootblock_loaded = True

        search_paths = [
            _config.working_dir / "bootblock.md",
            Path(__file__).parent / "bootblock.md",
        ]

        for path in search_paths:
            if path.exists():
                try:
                    cls._bootblock = path.read_text(encoding='utf-8')
                    return cls._bootblock
                except Exception:
                    pass

        return None

    @classmethod
    def has_bootblock(cls) -> bool:
        """Prüft ob ein Bootblock verfügbar ist."""
        return cls.get_bootblock() is not None


# =============================================================================
# Polylog Bridge - Hauptklasse
# =============================================================================

def get_system_prompt(working_dir: str, include_bootblock: bool = True) -> str:
    """Generiert den System-Prompt."""
    parts = []

    # Bootblock als Werte-Layer voranstellen
    if include_bootblock:
        bootblock = PromptRegistry.get_bootblock()
        if bootblock:
            parts.append("Die folgenden Werte haben HÖCHSTE PRIORITÄT bei allen Entscheidungen:\n")
            parts.append(bootblock)

    # Tool-Beschreibungen
    tools_desc = "\n".join(
        f"- {name}: {t['schema']['function']['description']}"
        for name, t in ToolRegistry._tools.items()
    )

    standard_prompt = f"""=== POLYLOG CODING ASSISTANT ===

Du bist ein hilfreicher Coding-Assistent.
Du MUSST Tools aktiv nutzen um Aufgaben zu erledigen.

VERFÜGBARE TOOLS:
{tools_desc}

REGELN:
1. IMMER Tools nutzen wenn möglich - nie nur beschreiben was zu tun wäre
2. Lies ZUERST Dateien bevor du sie änderst
3. Antworte kurz und präzise
4. Bei Unsicherheit: fragen, nicht raten

KONTEXT:
- Arbeitsverzeichnis: {working_dir}
- Platform: {'Windows' if IS_WINDOWS else 'Unix/Linux'}
"""

    parts.append(standard_prompt)
    return "\n".join(parts)


class PolylogBridge:
    """
    Polylog Bridge - Verbindet lokale LLMs mit Tools.

    Workflow:
    1. User-Input → LLM (mit Tool-Definitionen)
    2. LLM antwortet mit Tool-Calls
    3. Bridge führt Tools aus
    4. Ergebnisse → LLM
    5. LLM gibt finale Antwort
    """

    def __init__(self, config: BridgeConfig = None):
        self.config = config or BridgeConfig()
        self.client = OllamaClient(self.config)
        self.messages: List[Dict] = []

        set_config(ToolConfig(
            working_dir=self.config.working_dir,
            allow_write=True
        ))

        self._init_messages()

    def _init_messages(self):
        """Initialisiert die Nachrichten mit System-Prompt."""
        self.messages = [{
            "role": "system",
            "content": get_system_prompt(str(self.config.working_dir))
        }]

    def process(self, user_input: str, verbose: bool = False) -> str:
        """
        Verarbeitet eine User-Anfrage.

        Args:
            user_input: Die Anfrage
            verbose: Zeigt Tool-Calls an

        Returns:
            Finale Antwort des LLM
        """
        self.messages.append({"role": "user", "content": user_input})

        max_iterations = 5
        content = ""

        for _ in range(max_iterations):
            try:
                response = self.client.chat(self.messages, use_tools=True)
            except Exception as e:
                return f"Fehler: {e}"

            content = response.get("content", "")
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                self.messages.append({"role": "assistant", "content": content})
                break

            assistant_msg = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            self.messages.append(assistant_msg)

            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", {})

                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                if verbose:
                    print(f"  → {name}({args})")

                result = ToolRegistry.execute(name, args)

                self.messages.append({
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False)
                })

        return content

    def reset(self):
        """Setzt Konversation zurück."""
        self._init_messages()

    def run_interactive(self):
        """Interaktiver Modus."""
        print("=" * 60)
        print("POLYLOG BRIDGE")
        print(f"Modell: {self.config.model}")
        print(f"Tools: {', '.join(ToolRegistry.list_tools())}")
        print("=" * 60)
        print("Befehle: /quit, /reset, /tools, /verbose, /bootblock, /help")
        print("=" * 60)

        if not self.client.is_available():
            print(f"\n⚠️  Ollama nicht erreichbar")
            return

        # Bootblock-Status anzeigen
        if PromptRegistry.has_bootblock():
            print("\n✓ Bootblock geladen (Werte-Layer aktiv)")
        else:
            print("\n" + "=" * 60)
            print("⚠️  WARNUNG: Kein Bootblock gefunden!")
            print("=" * 60)
            print()
            print("Der Bootblock definiert die Grundwerte für den KI-Assistenten.")
            print("Ohne Bootblock arbeitet der Assistent OHNE Werte-Layer.")
            print()
            print("Lösung: Erstelle eine Datei 'bootblock.md' im Projektverzeichnis")
            print(f"        Pfad: {_config.working_dir / 'bootblock.md'}")
            print()
            print("Vorlage: https://github.com/Jan-Christoph/polylog-public/blob/main/bootblock.md")
            print("=" * 60)

        print("✓ Bereit.\n")

        verbose = False
        multiline_mode = False
        multiline_buffer = []

        while True:
            try:
                if multiline_mode:
                    user_input = input("... ")
                else:
                    user_input = input("Du: ")
            except (EOFError, KeyboardInterrupt):
                print("\n\nAuf Wiedersehen!")
                break

            # Mehrzeilige Eingabe
            if multiline_mode:
                if user_input.strip() == "---":
                    multiline_mode = False
                    user_input = "\n".join(multiline_buffer).strip()
                    multiline_buffer = []
                    if not user_input:
                        continue
                else:
                    multiline_buffer.append(user_input)
                    continue

            if user_input.strip() == "---":
                multiline_mode = True
                multiline_buffer = []
                print("(Mehrzeilige Eingabe gestartet. Beende mit '---')")
                continue

            user_input = user_input.strip()

            if not user_input:
                continue

            # Befehle
            if user_input.lower() == "/quit":
                break
            elif user_input.lower() == "/reset":
                self.reset()
                print("✓ Reset\n")
                continue
            elif user_input.lower() == "/tools":
                print("Tools:")
                for name, t in ToolRegistry._tools.items():
                    desc = t['schema']['function']['description']
                    print(f"  - {name}: {desc}")
                continue
            elif user_input.lower() == "/verbose":
                verbose = not verbose
                print(f"Verbose: {'ON' if verbose else 'OFF'}\n")
                continue
            elif user_input.lower() == "/bootblock":
                bootblock = PromptRegistry.get_bootblock()
                if bootblock:
                    print(bootblock)
                else:
                    print("\n⚠️  KEIN BOOTBLOCK GEFUNDEN")
                    print(f"Erstelle: {_config.working_dir / 'bootblock.md'}\n")
                continue
            elif user_input.lower() == "/help":
                print("\n=== POLYLOG BRIDGE HILFE ===")
                print("\nTOOLS:")
                print("  read_file   - Liest eine Datei")
                print("  write_file  - Schreibt eine Datei")
                print("  webrecherche - Web-Recherche (Wikipedia)")
                print("\nBEFEHLE:")
                print("  /quit      - Beenden")
                print("  /reset     - Konversation zurücksetzen")
                print("  /tools     - Verfügbare Tools anzeigen")
                print("  /verbose   - Tool-Aufrufe anzeigen")
                print("  /bootblock - Werte-Layer anzeigen")
                print()
                continue

            # Verarbeiten
            print("\nAssistent: ", end="", flush=True)
            response = self.process(user_input, verbose=verbose)
            print(response)
            print()


# =============================================================================
# Test & Main
# =============================================================================

def test_mode():
    """Testet Tools ohne Ollama."""
    print("=" * 60)
    print("POLYLOG BRIDGE - Test")
    print(f"Platform: {platform.system()}")
    print(f"Tools: {ToolRegistry.list_tools()}")
    print("=" * 60)

    set_config(ToolConfig(working_dir=Path(".")))

    # Test read_file
    print("\n--- read_file ---")
    result = read_file("README.md")
    print(f"Success: {result.get('success')}, Size: {result.get('size', 'N/A')}")

    # Test webrecherche
    print("\n--- webrecherche ---")
    result = webrecherche("Python")
    print(f"Results: {result.get('results_count')}")

    # Schemas
    print("\n--- Tool Schemas ---")
    for schema in ToolRegistry.get_schemas():
        print(f"  - {schema['function']['name']}")

    print("\n✓ Tests abgeschlossen")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Polylog Bridge")
    parser.add_argument("--test", action="store_true", help="Test-Modus")
    parser.add_argument("--model", default="devstral-small-2:latest", help="Modell")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout")
    parser.add_argument("query", nargs="?", help="Einzel-Anfrage")

    args = parser.parse_args()

    if args.test:
        test_mode()
        return

    config = BridgeConfig(
        model=args.model,
        timeout=args.timeout,
        working_dir=Path(".").resolve()
    )

    bridge = PolylogBridge(config)

    if args.query:
        print(bridge.process(args.query, verbose=True))
    else:
        bridge.run_interactive()


if __name__ == "__main__":
    main()
