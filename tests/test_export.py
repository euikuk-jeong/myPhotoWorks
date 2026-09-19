from pathlib import Path

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.processing.export import export_adopted


def item(tmp_path, name, adopted, content=b"x"):
    p = tmp_path / "src" / name
    p.parent.mkdir(exist_ok=True)
    p.write_bytes(content)
    it = PhotoItem(p)
    it.is_adopted = adopted
    return it


def test_copies_only_adopted(tmp_path):
    photos = [item(tmp_path, "a.jpg", True), item(tmp_path, "b.jpg", False)]
    out = tmp_path / "out"
    copied, errors = export_adopted(photos, out)
    assert copied == 1 and errors == []
    assert [f.name for f in out.iterdir()] == ["a.jpg"]


def test_never_overwrites_existing_file(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.jpg").write_bytes(b"keep")
    copied, _ = export_adopted([item(tmp_path, "a.jpg", True, b"new")], out)
    assert copied == 1
    assert (out / "a.jpg").read_bytes() == b"keep"
    assert (out / "a_1.jpg").read_bytes() == b"new"


def test_missing_source_reported_not_raised(tmp_path):
    it = item(tmp_path, "a.jpg", True)
    it.source_path = Path(tmp_path / "gone.jpg")
    copied, errors = export_adopted([it], tmp_path / "out")
    assert copied == 0 and len(errors) == 1
