# Was zur Zeit möglich ist:
### Der Hook user-prompt-bootblock.sh kann als Claude Code Hook konfiguriert werden:
```
// ~/.claude/hooks.json
{
  "hooks": {
    "user-prompt-submit": [
      {
        "command": "/home/user/polylog_public/_sys/bootblock/claude/user-prompt-bootblock.sh"
      }
    ]
  }
}
```
### Dann wird der Bootblock automatisch bei jedem User-Prompt in meinen Kontext injiziert.