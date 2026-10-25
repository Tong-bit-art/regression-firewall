from pathlib import Path

from regression_firewall.config.schema import (
    ApiProbeConfig,
    ApiSurfaceConfig,
    CliProbeConfig,
    CliSurfaceConfig,
    Config,
    HttpProbeConfig,
    HttpSurfaceConfig,
    JsApiProbeConfig,
    JsApiSurfaceConfig,
    ServerConfig,
)
from regression_firewall.selection import decide_probes, probe_dependencies


def _project(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def test_cli_probe_deps_from_command_and_watchlist(tmp_path):
    _project(tmp_path, {"jobs/build.py": "print('x')\n"})
    probe = CliProbeConfig(id="build", command=["python", "jobs/build.py"],
                           files=["out/receipt.json"])
    deps = probe_dependencies("cli", probe, Config(cli=CliSurfaceConfig(probes=[probe])), tmp_path)
    rel = sorted(str(d.relative_to(tmp_path)).replace("\\", "/") for d in deps)
    assert rel == ["jobs/build.py", "out/receipt.json"]


def test_cli_deps_dash_m_module_dir(tmp_path):
    _project(tmp_path, {"mypkg/__init__.py": ""})
    probe = CliProbeConfig(id="run", command=["python", "-m", "mypkg"])
    deps = probe_dependencies("cli", probe, Config(), tmp_path)
    assert next(iter(deps)).name == "mypkg"


def test_cli_deps_unknown_module_means_none(tmp_path):
    probe = CliProbeConfig(id="run", command=["python", "-m", "does_not_exist_pkg"])
    assert probe_dependencies("cli", probe, Config(), tmp_path) is None


def test_http_deps_requires_managed_server(tmp_path):
    probe = HttpProbeConfig(id="GET /", method="GET", path="/")
    assert probe_dependencies("http", probe, Config(http=HttpSurfaceConfig(probes=[probe])),
                              tmp_path) is None
    _project(tmp_path, {"serve.py": "pass\n"})
    managed = HttpSurfaceConfig(
        base_url="http://127.0.0.1:{port}",
        server=ServerConfig(command=["python", "serve.py"]),
        probes=[probe],
    )
    deps = probe_dependencies("http", probe, Config(http=managed), tmp_path)
    assert next(iter(deps)).name == "serve.py"


def test_api_deps_package_dir_with_src_layout(tmp_path):
    _project(tmp_path, {"src/mypkg/__init__.py": ""})
    probe = ApiProbeConfig(id="mypkg", module="mypkg")
    deps = probe_dependencies("public_api", probe, Config(), tmp_path)
    assert next(iter(deps)).name == "mypkg"


def test_api_deps_unknown_module_means_none(tmp_path):
    probe = ApiProbeConfig(id="ghost", module="ghost_pkg")
    assert probe_dependencies("public_api", probe, Config(), tmp_path) is None


def test_js_deps_include_reexport_origins(tmp_path):
    _project(tmp_path, {
        "src/index.ts": "export * from './core'\n",
        "src/core.ts": "export function alpha() {}\n",
    })
    probe = JsApiProbeConfig(id="pkg", file="src/index.ts")
    deps = probe_dependencies("js_api", probe, Config(), tmp_path)
    assert {d.name for d in deps} == {"index.ts", "core.ts"}


def test_decide_per_probe_skip_and_run(tmp_path):
    _project(tmp_path, {"a/one.py": "print(1)\n", "b/two.py": "print(2)\n"})
    cfg = Config(cli=CliSurfaceConfig(probes=[
        CliProbeConfig(id="one", command=["python", "a/one.py"]),
        CliProbeConfig(id="two", command=["python", "b/two.py"]),
    ]))
    decisions = decide_probes(cfg, tmp_path, ["b/two.py"])
    by_id = {d.probe_id: d for d in decisions}
    assert by_id["one"].run is False
    assert by_id["two"].run is True
    assert "b/two.py" in by_id["two"].reason


def test_decide_no_changed_files_runs_everything(tmp_path):
    _project(tmp_path, {"jobs/build.py": "print('x')\n"})
    cfg = Config(cli=CliSurfaceConfig(probes=[
        CliProbeConfig(id="build", command=["python", "jobs/build.py"])]))
    decisions = decide_probes(cfg, tmp_path, [])
    assert len(decisions) == 1 and decisions[0].run is True
    assert "unavailable" in decisions[0].reason


def test_decide_sibling_file_change_still_skips(tmp_path):
    """Dependency mapping is file-level: a sibling file changing does not
    touch the tracked file (conservative, documented)."""
    _project(tmp_path, {"jobs/build.py": "print('x')\n"})
    cfg = Config(cli=CliSurfaceConfig(probes=[
        CliProbeConfig(id="build", command=["python", "jobs/build.py"])]))
    decisions = decide_probes(cfg, tmp_path, ["jobs/helper.py"])
    assert decisions[0].run is False


def test_decide_unknown_deps_always_run(tmp_path):
    cfg = Config(cli=CliSurfaceConfig(probes=[
        CliProbeConfig(id="mystery", command=["python", "-m", "no_such_pkg"])]))
    decisions = decide_probes(cfg, tmp_path, ["anything.py"])
    assert decisions[0].run is True
    assert "could not be mapped" in decisions[0].reason


def test_venv_interpreter_token_is_not_a_dependency(tmp_path):
    """Holdout finding (datasette): {venv_python}-style absolute interpreter
    paths in probe commands are environment, not project dependencies — and
    they must never crash the selection with a relative_to error."""
    probe = CliProbeConfig(
        id="inspect",
        command=[r"C:\venvs\project\Scripts\python.exe", "-m", "mypkg", "inspect", "db.sqlite"],
    )
    _project(tmp_path, {"mypkg/__init__.py": ""})
    deps = probe_dependencies("cli", probe, Config(), tmp_path)
    assert deps is not None
    assert all(str(d).startswith(str(tmp_path)) for d in deps), deps
    decisions = decide_probes(Config(cli=CliSurfaceConfig(probes=[probe])), tmp_path, ["mypkg/app.py"])
    assert decisions[0].run is True  # the package dir was mapped and touched


def test_out_of_project_dep_labels_do_not_crash(tmp_path):
    probe = CliProbeConfig(id="j", command=["python", "app.py"])
    _project(tmp_path, {"app.py": "print(1)\n"})
    deps = probe_dependencies("cli", probe, Config(), tmp_path)
    deps.add(Path("C:") / "venvs" / "x" / "python.exe")  # environment path
    decisions = decide_probes(Config(cli=CliSurfaceConfig(probes=[probe])), tmp_path, ["app.py"])
    assert decisions[0].run is True
