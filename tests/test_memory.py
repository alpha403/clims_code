from pathlib import Path

from clims_core.memory import load_memory


def test_project_memory_loaded(tmp_path: Path):
    (tmp_path / "CLIMS.md").write_text("Project rule: always use tabs.", encoding="utf-8")
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    mem = load_memory(cwd=tmp_path, home=fake_home)
    assert "always use tabs" in mem


def test_memory_import(tmp_path: Path):
    (tmp_path / "extra.md").write_text("Imported guidance here.", encoding="utf-8")
    (tmp_path / "CLIMS.md").write_text("Main memory.\n@import extra.md\n", encoding="utf-8")
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    mem = load_memory(cwd=tmp_path, home=fake_home)
    assert "Main memory" in mem and "Imported guidance here" in mem


def test_nested_specificity(tmp_path: Path):
    (tmp_path / "CLIMS.md").write_text("ROOT", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "CLIMS.md").write_text("CHILD", encoding="utf-8")
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    mem = load_memory(cwd=sub, home=fake_home)
    # both present; child (most specific) appears after root
    assert "ROOT" in mem and "CHILD" in mem
    assert mem.index("ROOT") < mem.index("CHILD")


def test_no_memory_is_empty(tmp_path: Path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    assert load_memory(cwd=tmp_path, home=fake_home) == ""
