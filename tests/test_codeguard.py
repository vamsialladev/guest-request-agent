"""After an in-place update (a push to Streamlit Cloud), old and new modules must never be mixed."""

import codeguard


def make_package(root, files):
    for name, text in files.items():
        path = root / "src" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_stamp_changes_when_code_changes(tmp_path):
    make_package(tmp_path, {"a.py": "x = 1"})
    first = codeguard.code_stamp(tmp_path)
    assert first == codeguard.code_stamp(tmp_path)
    make_package(tmp_path, {"a.py": "x = 22"})  # edited (size changes)
    assert codeguard.code_stamp(tmp_path) != first
    second = codeguard.code_stamp(tmp_path)
    make_package(tmp_path, {"b.py": ""})  # added
    assert codeguard.code_stamp(tmp_path) != second


def test_refresh_drops_project_modules_only_after_a_change(tmp_path):
    make_package(tmp_path, {"retrieve.py": "old"})
    env = {}
    assert codeguard.refresh(tmp_path, env, {"streamlit": 5}) == []  # fresh process: nothing loaded yet
    modules = {"src": 1, "src.retrieve": 2, "views.assistant": 3, "eval.metrics": 4, "streamlit": 5, "srcx": 6}
    assert codeguard.refresh(tmp_path, env, modules) == []  # unchanged
    make_package(tmp_path, {"retrieve.py": "new code"})
    dropped = codeguard.refresh(tmp_path, env, modules)
    assert sorted(dropped) == ["eval.metrics", "src", "src.retrieve", "views.assistant"]
    assert set(modules) == {"streamlit", "srcx"}  # third-party modules are kept


def test_first_check_in_a_process_that_already_loaded_old_code_drops_it(tmp_path):
    """The live app ran the old code before this guard existed: its modules must not survive."""
    make_package(tmp_path, {"retrieve.py": "x"})
    modules = {"src.retrieve": 1, "streamlit": 2}
    assert codeguard.refresh(tmp_path, {}, modules) == ["src.retrieve"] and set(modules) == {"streamlit"}
