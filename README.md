# yagso
Yet Another Git Submodule Orchestrator

## Building the Package

To build the Python package, ensure you have Python 3.8+ installed and follow these steps:

1. Clone the repository and navigate to the project directory.

2. Create a virtual environment (remove any existing `.venv` directory first if needed):
   ```bash
   # If .venv already exists and is active, deactivate first or remove it
   # deactivate  # if active
   # rm -rf .venv  # on Linux/macOS, or rmdir /s .venv on Windows
   
   python -m venv .venv
   ```

3. Activate the virtual environment:
   - On Windows: `.venv\Scripts\activate`
   - On macOS/Linux: `source .venv/bin/activate`

4. Install the build dependencies:
   ```bash
   pip install build
   ```

5. Build the package:
   ```bash
   python -m build
   ```

This will create distribution files in the `dist/` directory:
- `yagso-0.1.0.tar.gz` (source distribution)
- `yagso-0.1.0-py3-none-any.whl` (wheel)

## Installation

Install the package using pip:
```bash
pip install dist/yagso-0.1.0-py3-none-any.whl
```

Or install in editable mode for development:
```bash
pip install -e .
```
