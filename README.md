# CCC Assistant

```bash
python -m nuitka --onefile --show-progress --follow-imports --output-dir=build --remove-output --static-libpython=no --include-package=discord ccc_assistant/bot.py
```

```bash
dpkg-deb -Sextreme --build ccc-assistant ccc-assistant-bot.deb
```
