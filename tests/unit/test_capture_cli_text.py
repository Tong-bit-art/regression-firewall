from pathlib import Path

from regression_firewall.capture.cli import _relativize_text


def test_relativize_text_rewrites_cwd_prefixes():
    cwd = Path(r"C:\build\repo-base")
    text = (
        "Traceback (most recent call last):\n"
        f'  File "{cwd}\\deploy.py", line 3, in <module>\n'
        "ValueError: boom\n"
    )
    out = _relativize_text(text, cwd)
    assert str(cwd) not in out
    assert "./deploy.py" in out
    assert out.startswith("Traceback")


def test_relativize_text_forward_slashes():
    cwd = Path("/home/runner/work/repo-base")
    text = f"reading {cwd}/src/app.py done\n"
    out = _relativize_text(text, cwd)
    assert str(cwd) not in out
    assert "./src/app.py" in out


def test_relativize_text_untouched_when_cwd_absent():
    text = "no paths here\n"
    assert _relativize_text(text, Path(r"C:\elsewhere")) == text
