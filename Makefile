# Makefile for CareRoute desktop app

PYTHON ?= python3
VENV_DIR := .venv

# OS-specific python path inside venv
# On Linux/macOS: .venv/bin/python
# On Windows (PowerShell): .venv/Scripts/python.exe
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

# If they are on Windows and 'bin' doesn't exist, they can override VENV_PYTHON manually
# e.g. make run VENV_PYTHON=.venv/Scripts/python.exe VENV_PIP=.venv/Scripts/pip.exe

.PHONY: build run clean package

# 1) build: create virtual env and install dependencies
build: $(VENV_PYTHON)

$(VENV_PYTHON): requirements.txt
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	@echo "Virtualenv ready at $(VENV_DIR)"

# 2) run: build (if needed) then run the app
run: build
	@echo "Starting CareRoute desktop app..."
	$(VENV_PYTHON) main.py

# 3) package (optional): build a standalone executable using PyInstaller
package: build
	$(VENV_PYTHON) -m pip install pyinstaller
	$(VENV_PYTHON) -m PyInstaller --noconfirm --onefile --name careroute main.py
	@echo "Executable built in dist/careroute (or careroute.exe on Windows)"

# 4) clean: remove venv and PyInstaller outputs
clean:
	rm -rf $(VENV_DIR) build dist __pycache__ *.spec
