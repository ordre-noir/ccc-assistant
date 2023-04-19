# CCC Assistant

[![Publish Packages](https://github.com/ordre-noir/ccc-assistant/actions/workflows/when_tagged.yaml/badge.svg)](https://github.com/ordre-noir/ccc-assistant/actions/workflows/when_tagged.yaml)

```bash
python -m nuitka --onefile --show-progress --follow-imports --output-dir=build --remove-output --static-libpython=no --include-package=discord ccc_assistant/bot.py
```

```bash
dpkg-deb -Sextreme --build ccc-assistant ccc-assistant-bot.deb
```
