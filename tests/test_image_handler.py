"""
Tests for per-place image folders (PR #31).

Place ids contain ':' which Windows rejects in directory names, so folders
use '_' instead. Folders named after the raw id by older versions are
renamed once so their images are kept.
"""

import os

import pytest

from modules.image_handler import ImageHandler, place_image_dir

# Folders named after raw ids (with ':') can only exist off Windows.
skip_on_windows = pytest.mark.skipif(os.name == "nt", reason="':' is not allowed in Windows folder names")


@pytest.mark.parametrize("place_id, folder", [
    ("0x89accda1eff33585:0x8347540c3719d897", "0x89accda1eff33585_0x8347540c3719d897"),
    ("0x30e29edb0244829f:0", "0x30e29edb0244829f_0"),
    ("cid:12345678901234567", "cid_12345678901234567"),
    ("short:7EPKEs7rukXW2qVn7", "short_7EPKEs7rukXW2qVn7"),
    ("hash:3f2a9c0d1e4b5a67", "hash_3f2a9c0d1e4b5a67"),
    ("ChIJN1t_tDeuEmsRUsoyG83frY4", "ChIJN1t_tDeuEmsRUsoyG83frY4"),
])
def test_folder_name_has_no_windows_reserved_chars(tmp_path, place_id, folder):
    assert place_image_dir(tmp_path, place_id) == tmp_path / folder


@skip_on_windows
def test_legacy_folder_is_renamed(tmp_path):
    legacy = tmp_path / "0x30e29edb0244829f:0"
    (legacy / "profiles").mkdir(parents=True)
    (legacy / "profiles" / "a.jpg").write_bytes(b"x")

    base = place_image_dir(tmp_path, "0x30e29edb0244829f:0")

    assert base == tmp_path / "0x30e29edb0244829f_0"
    assert (base / "profiles" / "a.jpg").read_bytes() == b"x"
    assert not legacy.exists()


@skip_on_windows
def test_existing_new_folder_wins_over_legacy(tmp_path):
    legacy = tmp_path / "cid:1"
    legacy.mkdir()
    (tmp_path / "cid_1").mkdir()

    assert place_image_dir(tmp_path, "cid:1") == tmp_path / "cid_1"
    assert legacy.exists()


def test_set_place_id_uses_safe_folder(tmp_path):
    handler = ImageHandler({"image_dir": str(tmp_path)})
    handler.set_place_id("0x882b21e060e098b7:0")
    handler.ensure_directories()

    assert handler.profile_dir == tmp_path / "0x882b21e060e098b7_0" / "profiles"
    assert handler.review_dir == tmp_path / "0x882b21e060e098b7_0" / "reviews"
    assert handler.review_dir.is_dir()


@skip_on_windows
def test_traversal_in_place_id_stays_inside_image_dir(tmp_path):
    image_dir = tmp_path / "images"
    (image_dir / "cid:..").mkdir(parents=True)  # left behind by an older version
    outside = tmp_path / "outside"
    outside.mkdir()

    base = place_image_dir(image_dir, "cid:../../../outside")

    assert base.parent == image_dir
    assert outside.is_dir()  # not moved into the image folder
