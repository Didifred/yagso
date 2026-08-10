# yagso
Yet Another Git Submodule Orchestrator

yagso is a CLI tool that manages Git submodule hierarchies via a YAML manifest.

Instead of manually tracking which branch each submodule should be on, you declare it once, 
and yagso handles `configure`, `commit`, and `push` recursively — including nested submodules.

## Building the Package

To build the Python package, ensure you have Python 3.8+ installed and follow these steps:

1. Clone the repository and navigate to the project directory.

2. Create a virtual environment:
   ```bash
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

## Development

1. Clone the repository and open worspace in VS Code.

2. Create a virtual environment (once):
   ```bash
   python -m venv .venv
   ```
3. Install dependencies in editable mode for development:
   ```bash
   pip install -e .
   ```


## Commands

- **`yagso generate`**: Generates the hierarchy of submodules from a Git root repository and produces a manifest file called `yagso.yaml` at the root of the Git repository.

- **`yagso generate --BOM --files <regex>`**: Generates in addition of the maniest, a bill of material BOM.yaml with files matching regex expression.

- **`yagso configure`**: Applies the manifest configuration to the repository.

- **`yagso commit`**: Commits changes recursively, including `.gitmodules`, index changes, and the manifest file itself.


These latest commands are simple git cli wrapper on a repo and its submodules (--recursive) :

- **`yagso update`**: Updates the submodules without initializing new ones.

- **`yagso update --init`**: After initial cloning of the root repository, clones all submodules recursively.

- **`yagso update --init --remote`**: Updates submodules to the latest commit on their tracking branch.

- **`yagso push`**: Pushes all commits of the submodules to the remote repository.

## Miscs

Line count :

**`pygount --format=summary .\yagso\`**