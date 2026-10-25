"""End-to-end: trace.sqlite — stdlib sqlite3 query-shape and write-footprint
diffing through the real CLI."""

import json

from regression_firewall import cli

JOB = """\\
import sqlite3

conn = sqlite3.connect("app.db")
conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
conn.execute("INSERT INTO users(name) VALUES (?)", ("alice",))
conn.execute("INSERT INTO users(name) VALUES (?)", ("bob",))
conn.commit()
print("ok")
"""


def _project(tmp_path, trace_config):
    (tmp_path / "job.py").write_text(JOB, encoding="utf-8")
    (tmp_path / ".regression-firewall.yml").write_text(
        "version: 1\n"
        "surfaces:\n"
        "  http: {enabled: false}\n"
        "  public_api: {enabled: false}\n"
        "  js_api: {enabled: false}\n"
        "  cli:\n"
        "    probes:\n"
        "      - id: job\n"
        "        command: ['python', 'job.py']\n"
        "        trace:\n" + trace_config + "\n",
        encoding="utf-8",
    )


def test_query_shapes_are_parameter_insensitive(tmp_path):
    # two INSERTs with different literals -> ONE shape with count 2
    _project(tmp_path, "          sqlite: true")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    snapshot = json.loads(
        (tmp_path / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    data = snapshot["surfaces"]["cli"][0]["data"]
    queries = data["db_queries"]
    assert len(queries) == 2  # CREATE TABLE + INSERT
    insert = next(s for s in queries if s.startswith("INSERT"))
    assert queries[insert] == 2
    assert data["db_tables_written"] == ["users"]
    # the literal values must not appear anywhere in the snapshot
    assert "alice" not in json.dumps(snapshot)


def test_new_query_and_table_detected(tmp_path):
    _project(tmp_path, "          sqlite: true")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    job = tmp_path / "job.py"
    job.write_text(
        JOB.replace('print("ok")',
                    'conn.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER, uid INTEGER)")\n'
                    'conn.execute("INSERT INTO orders(uid) VALUES (?)", (1,))\n'
                    'print("ok")'),
        encoding="utf-8",
    )
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_REVIEW
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    by_cat = {}
    for c in report["changes"]:
        by_cat.setdefault(c["category"], []).append(c)
    assert len(by_cat["db_query_added"]) == 2
    added_tables = {c["path"] for c in by_cat["db_table_written_added"]}
    assert added_tables == {"orders"}
    for c in report["changes"]:
        assert c["classification"] == "uncertain"
        assert c["severity"] == "medium"


def test_query_count_change_is_low_uncertain(tmp_path):
    _project(tmp_path, "          sqlite: true")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    job = tmp_path / "job.py"
    job.write_text(
        JOB.replace('conn.execute("INSERT INTO users(name) VALUES (?)", ("bob",))\n', "")
            .replace('print("ok")',
                     'for name in ("bob", "carol", "dave"):\n'
                     '    conn.execute("INSERT INTO users(name) VALUES (?)", (name,))\n'
                     'print("ok")'),
        encoding="utf-8",
    )
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_REVIEW
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    counts = [c for c in report["changes"] if c["category"] == "db_query_count_changed"]
    assert len(counts) == 1
    assert counts[0]["before"] == 2 and counts[0]["after"] == 4
    assert counts[0]["severity"] == "low"


def test_identical_database_behavior_traces_clean(tmp_path):
    _project(tmp_path, "          sqlite: true")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_OK


def test_query_removed_detected(tmp_path):
    _project(tmp_path, "          sqlite: true")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    job = tmp_path / "job.py"
    job.write_text(JOB.replace(
        'conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")\n',
        ""), encoding="utf-8")
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_REVIEW
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    assert any(c["category"] == "db_query_removed" for c in report["changes"])
