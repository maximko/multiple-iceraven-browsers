# Agents.md

## git
Use git. If no repository is present in working dir root, init one. After finishing every job commit changes with short commit message with list of changes. Create gitignore. Include AGENTS.md to git.

## python
If you need to install packages (to inspect it for example) create venv in '.venv' dir and use it.

## rust esp32
Flashing will happen on other host, write build script to build firmware and to merge partition files to a singe binary I can flash with esptool.py at address 0x0.

## Docker
Create docker ignore for pycache etc.

## Web apps
If the code will be a web app create dev script to start backend and automatically reload it on code changes. Use TailwindCSS. For icons use FontAwesome Free, do not recreate icons and use original font. Use websockets for data streaming. Use localstorage for keeping things like sorting options etc between page reloads. Dialogs should be closed by pressing Escape on keyboard.
