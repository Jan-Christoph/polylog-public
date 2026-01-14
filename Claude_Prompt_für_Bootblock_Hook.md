# Was zur Zeit möglich ist:
### Der Hook user-prompt-bootblock.sh kann als Claude Code Hook konfiguriert werden:
Wie user-prompt-submit Hooks funktionieren:
User schreibt Prompt
    ↓
Hook wird ausgeführt (_sys/bootblock/claude/user-prompt-bootblock.sh)
    ↓
Hook-Output wird an Claude übergeben (unsichtbar für User)
    ↓
Claude verarbeitet: Bootblock + User-Prompt zusammen
    ↓
Claude antwortet

# Dies in den Prompt geben:
```
// Write /home/user/polylog_privat_server/.claude/settings.json
{
  "hooks": {
    "user-prompt-submit": [
      {
        "type": "command",
        "command": "_sys/bootblock/claude/user-prompt-bootblock.sh"
      }
    ]
  }
}
```
### Bei jedem User-Prompt wird das Bootblock-Script automatisch ausgeführt und lädt:

Den Polylog Bootblock (Grundwerte)
Direkt vor deinem Prompt
🔄 Aktivierung:
Der Hook wird bei der nächsten Session oder beim nächsten Prompt aktiv.