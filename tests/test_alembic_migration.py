import importlib.util
from pathlib import Path


def test_initial_migration_loads() -> None:
    path = Path(__file__).parent.parent / "alembic" / "versions" / "0001_initial_schema.py"
    assert path.exists(), f"missing migration: {path}"

    spec = importlib.util.spec_from_file_location("initial_migration", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert callable(mod.upgrade)
    assert callable(mod.downgrade)
    assert mod.revision == "0001"
    assert mod.down_revision is None
