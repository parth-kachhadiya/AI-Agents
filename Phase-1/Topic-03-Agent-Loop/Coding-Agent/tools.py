"""
Coding-agent tools. All file access is confined to WORKSPACE.

Layout:
    main.py
    tools.py
    Coding-Agent/
        Playground/      <- the only place the LLM can touch
"""

import os
import sys
import platform
import subprocess
from pathlib import Path
from importlib import metadata

# ----------------------------------------------------------
#                        Config
# ----------------------------------------------------------

WORKSPACE = (Path(__file__).resolve().parent / "Playground")
WORKSPACE.mkdir(parents=True, exist_ok=True)

MAX_OUTPUT_CHARS  = 4000      # cap for stdout / stderr / read_file
MAX_WRITE_CHARS   = 100_000   # cap for write_file content
DEFAULT_TIMEOUT_S = 10
MAX_TIMEOUT_S     = 60
MAX_PACKAGES      = 150
REQUIRE_APPROVAL  = True      # human y/n before running code or overwriting


# ----------------------------------------------------------
#                        Helpers
# ----------------------------------------------------------

def _fail(error: str, **extra) -> dict:
    return {"ok": False, "error": error, **extra}


def _safe_path(user_path: str) -> Path:
    """Resolve a model-supplied path inside WORKSPACE or raise ValueError."""
    if user_path is None or not str(user_path).strip():
        raise ValueError("path must be a non-empty string, e.g. 'hello.py'.")

    root = WORKSPACE.resolve()
    candidate = (root / str(user_path).strip()).resolve()   # collapses ../ and follows symlinks

    if not candidate.is_relative_to(root):
        raise ValueError(
            f"Path '{user_path}' is outside the workspace. "
            f"Use a path relative to the workspace root, e.g. 'script.py' or 'sub/script.py'."
        )
    return candidate


def _rel(path: Path) -> str:
    return path.relative_to(WORKSPACE.resolve()).as_posix()


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS):
    """Return (text, truncated_flag)."""
    if text is None:
        return "", False
    if len(text) <= limit:
        return text, False
    return text[:limit] + f"\n...[truncated, {len(text) - limit} more characters]", True


def _to_text(value) -> str:
    """subprocess gives bytes (not str) on TimeoutExpired even with text=True."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _approve(action: str) -> bool:
    if not REQUIRE_APPROVAL:
        return True
    print("\n  ---- APPROVAL REQUIRED ----")
    for line in action.splitlines():
        print(f"    {line}")
    answer = input("  Allow? [y/N]: ").strip().lower()
    return answer in ("y", "yes")


# ----------------------------------------------------------
#                        Tools
# ----------------------------------------------------------

def get_environment_info() -> dict:
    try:
        packages = sorted(
            {d.metadata["Name"] for d in metadata.distributions() if d.metadata["Name"]},
            key=str.lower,
        )
        return {
            "ok": True,
            "python_version": sys.version.split()[0],
            "python_executable": sys.executable,
            "os": f"{platform.system()} {platform.release()}",
            "workspace": str(WORKSPACE.resolve()),
            "installed_packages": packages[:MAX_PACKAGES],
            "packages_truncated": len(packages) > MAX_PACKAGES,
        }
    except Exception as e:
        return _fail(f"could not collect environment info: {e}")


def list_files(path: str = ".") -> dict:
    try:
        target = _safe_path(path)
    except ValueError as e:
        return _fail(str(e))

    if not target.exists():
        return _fail(f"Directory '{path}' does not exist.")
    if not target.is_dir():
        return _fail(f"'{path}' is a file, not a directory. Use read_file to view it.")

    entries = []
    for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if item.name == "__pycache__":
            continue
        entries.append({
            "name": item.name,
            "type": "dir" if item.is_dir() else "file",
            "size_bytes": item.stat().st_size if item.is_file() else None,
        })
        if len(entries) >= 200:
            break

    return {"ok": True, "path": _rel(target) if target != WORKSPACE.resolve() else ".", "entries": entries}


def read_file(path: str, start_line: int = 1, end_line: int = None) -> dict:
    try:
        target = _safe_path(path)
    except ValueError as e:
        return _fail(str(e))

    if not target.exists():
        return _fail(f"File '{path}' not found. Use list_files to see available files.")
    if not target.is_file():
        return _fail(f"'{path}' is a directory. Use list_files to view it.")

    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return _fail(f"'{path}' is not a UTF-8 text file.")
    except OSError as e:
        return _fail(f"could not read '{path}': {e}")

    total = len(lines)
    start = max(1, start_line or 1)
    end = min(total, end_line) if end_line else total

    if total and start > total:
        return _fail(f"start_line {start} is past the end of the file ({total} lines).")

    numbered = "\n".join(f"{n:>4} | {lines[n - 1]}" for n in range(start, end + 1))
    content, truncated = _truncate(numbered)

    return {
        "ok": True,
        "path": _rel(target),
        "total_lines": total,
        "shown_lines": [start, end],
        "content": content,
        "truncated": truncated,
    }


def write_file(path: str, content: str, overwrite: bool = False) -> dict:
    try:
        target = _safe_path(path)
    except ValueError as e:
        return _fail(str(e))

    if not isinstance(content, str):
        return _fail("content must be a string.")
    if len(content) > MAX_WRITE_CHARS:
        return _fail(f"content too large ({len(content)} chars, max {MAX_WRITE_CHARS}). Split it into several files.")
    if target.is_dir():
        return _fail(f"'{path}' is a directory.")

    existed = target.exists()
    if existed and not overwrite:
        return _fail(f"File '{path}' already exists. Set overwrite=true to replace it, or use edit_file for small changes.")

    if existed and not _approve(f"Overwrite existing file: {_rel(target)}"):
        return _fail("User denied the overwrite.")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as e:
        return _fail(f"could not write '{path}': {e}")

    return {"ok": True, "path": _rel(target), "bytes_written": len(content.encode("utf-8")), "overwritten": existed}


def edit_file(path: str, old_str: str, new_str: str) -> dict:
    try:
        target = _safe_path(path)
    except ValueError as e:
        return _fail(str(e))

    if not target.is_file():
        return _fail(f"File '{path}' not found. Use list_files to see available files.")
    if not old_str:
        return _fail("old_str must be a non-empty string.")

    try:
        text = target.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        return _fail(f"could not read '{path}': {e}")

    count = text.count(old_str)
    if count == 0:
        return _fail("old_str not found. Use read_file to copy the exact text, including whitespace.")
    if count > 1:
        return _fail(f"old_str appears {count} times. Include more surrounding lines so it matches exactly once.")

    try:
        target.write_text(text.replace(old_str, new_str, 1), encoding="utf-8")
    except OSError as e:
        return _fail(f"could not write '{path}': {e}")

    return {"ok": True, "path": _rel(target), "replacements": 1}


def run_python_file(path: str, args: list = None, timeout_s: int = DEFAULT_TIMEOUT_S) -> dict:
    try:
        target = _safe_path(path)
    except ValueError as e:
        return _fail(str(e))

    if not target.is_file():
        return _fail(f"File '{path}' not found. Use list_files to see available files.")
    if target.suffix != ".py":
        return _fail(f"'{path}' is not a .py file; only Python files can be run.")

    args = [str(a) for a in (args or [])]
    try:
        timeout_s = max(1, min(int(timeout_s), MAX_TIMEOUT_S))
    except (TypeError, ValueError):
        timeout_s = DEFAULT_TIMEOUT_S

    if not _approve(f"Run: python {_rel(target)} {' '.join(args)}\n\n{target.read_text(encoding='utf-8', errors='replace')}"):
        return _fail("User denied execution.")

    # Minimal environment: do NOT leak OPENROUTER_API_KEY etc. to generated code.
    env = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    for key in ("PATH", "SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG"):
        if key in os.environ:
            env[key] = os.environ[key]

    try:
        proc = subprocess.run(
            [sys.executable, str(target), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            cwd=WORKSPACE,
            env=env,
        )
        stdout, out_cut = _truncate(proc.stdout)
        stderr, err_cut = _truncate(proc.stderr)
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
            "truncated": out_cut or err_cut,
            **({} if proc.returncode == 0 else {"error": "Script exited with a non-zero code. Read stderr, fix the file, and run again."}),
        }

    except subprocess.TimeoutExpired as e:
        stdout, out_cut = _truncate(_to_text(e.stdout))
        stderr, err_cut = _truncate(_to_text(e.stderr))
        return {
            "ok": False,
            "exit_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
            "truncated": out_cut or err_cut,
            "error": f"Script exceeded {timeout_s}s and was killed. Check for infinite loops or reduce the work.",
        }
    except Exception as e:
        return _fail(f"could not run '{path}': {e}")



CODING_TOOLS = [
    {
        "type"     : "function",
        "function" : {
            "name"        : "get_environment_info",
            "description" : "Get the Python version, interpreter path, OS, workspace path and installed packages. Call this before writting code that needs third-party libraries."
        }
    },
    {
        "type"     : "function",
        "function" : {
            "name"        : "list_files",
            "description" : "List files and folders inside the workspace directory.",
            "parameters"  : {
                "type"       : "object",
                "properties" : {
                    "path" : {
                        "type"        : "string",
                        "description" : "Directory relative to workspace root. Default '.'"
                    }
                }
            }
        }
    },
    {
        "type"     : "function",
        "function" : {
            "name"        : "read_file",
            "description" : "Read a text file from the workspace. Output has line numbers (not part of the file). Long files are truncated; use start_line/end_line to page through.",
            "parameters"  : {
                "type"       : "object",
                "properties" : {
                    "path" : {
                        "type"        : "string",
                        "description" : "e.g. 'hello.py'"
                    },
                    "start_line" : {
                        "type"        : "integer",
                        "description" : "First line to show (1-based)."
                    },
                    "end_line" : {
                        "type"        : "integer",
                        "description" : "Last line to show."
                    }
                },
                "required" : ["path"]
            }
        }
    },
    {
        "type"     : "function",
        "function" : {
            "name"        : "write_file",
            "description" : "Create a new file in the workspace with the given content. Fails if the file exists unless overwrite=true. Prefer edit_file for small changes to existing files.",
            "parameters"  : {
                "type"       : "object",
                "properties" : {
                    "path" : {
                        "type"        : "string",
                        "description" : "e.g. 'fib.py'"
                    },
                    "content" : {
                        "type"        : "string",
                        "description" : "Full file content."
                    },
                    "overwrite" : {
                        "type"        : "boolean",
                        "description" : "Replace the file if it exists. Default false."
                    }
                },
                "required" : ["path", "content"]
            }
        }
    },
    {
        "type"     : "function",
        "function" : {
            "name"        : "edit_file",
            "description" : "Replace one exact occurrence of old_str with new_str in an existing file. old_str must match exactly once; copy it from read_file (without line numbers).",
            "parameters"  : {
                "type"       : "object",
                "properties" : {
                    "path" : {
                        "type"        : "string"
                    },
                    "old_str" : {
                        "type"        : "string",
                        "description" : "Exact text to replace."
                    },
                    "new_str" : {
                        "type"        : "string",
                        "description" : "Replacement text."
                    }
                },
                "required" : ["path", "old_str", "new_str"]
            }
        }
    },
    {
        "type"     : "function",
        "function" : {
            "name"        : "run_python_file",
            "description" : "Run a .py file from the workspace and return exit code, stdout and stderr. If it fails, read stderr, fix the file, and run again.",
            "parameters"  : {
                "type"       : "object",
                "properties" : {
                    "path" : {
                        "type"        : "string",
                        "description" : "e.g. 'fib.py'"
                    },
                    "args" : {
                        "type"        : "array",
                        "items"       : {
                            "type" : "string"
                        },
                        "description" : "Command-line arguments."
                    },
                    "timeout_s" : {
                        "type"        : "integer",
                        "description" : f"Seconds before the script is killed. Default {DEFAULT_TIMEOUT_S}, max {MAX_TIMEOUT_S}."
                    }
                },
                "required" : ["path"]
            }
        }
    }
]

CODING_TOOL_KIT = {
    "get_environment_info": get_environment_info,
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "run_python_file": run_python_file,
}


'''
# ----------------------------------------------------------
#          Quick self-test:  python tools.py
# ----------------------------------------------------------

if __name__ == "__main__":
    REQUIRE_APPROVAL = False
    print(write_file("hello.py", "print('hello')\n", overwrite=True))
    print(read_file("hello.py"))
    print(run_python_file("hello.py"))
    print(list_files("../../"))          # should be rejected
    print(read_file("/etc/passwd"))      # should be rejected
'''