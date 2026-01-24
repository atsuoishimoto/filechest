"""Security tests for path traversal and backslash handling."""

import json
from io import BytesIO
from pathlib import Path


# =============================================================================
# api_mkdir - Path Traversal and Backslash Tests
# =============================================================================


def test_mkdir_path_traversal(client, volume, editor_user):
    """Cannot create folder outside volume with path traversal."""
    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/mkdir/",
        data=json.dumps({"path": "../..", "name": "escape"}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_mkdir_backslash_in_path(client, volume, editor_user):
    """Backslash in path is converted to forward slash (LocalStorage)."""
    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/mkdir/",
        data=json.dumps({"path": "", "name": "parent"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    response = client.post(
        f"/api/{volume.name}/mkdir/",
        data=json.dumps({"path": "parent\\subdir", "name": "child"}),
        content_type="application/json",
    )
    assert response.status_code == 404


# =============================================================================
# api_delete - Path Traversal and Backslash Tests
# =============================================================================


def test_delete_path_traversal(client, volume, editor_user):
    """Cannot delete outside volume with path traversal."""
    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/delete/",
        data=json.dumps({"items": ["../../etc/passwd"]}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["deleted"]) == 0
    assert len(data["errors"]) == 1


def test_delete_backslash_in_path(client, volume, editor_user):
    """Backslash in item path is converted to forward slash."""
    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/delete/",
        data=json.dumps({"items": ["folder\\file.txt"]}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["deleted"]) == 0
    assert len(data["errors"]) == 1


# =============================================================================
# api_list - Path Traversal and Backslash Tests
# =============================================================================


def test_list_path_traversal(client, volume, editor_user):
    """Cannot list outside volume with path traversal."""
    client.login(username="editor", password="editorpass")
    response = client.get(f"/api/{volume.name}/list/../../")
    assert response.status_code == 400


def test_list_backslash_in_path(client, volume, editor_user):
    """Backslash in list path is converted to forward slash."""
    client.login(username="editor", password="editorpass")
    response = client.get(f"/api/{volume.name}/list/folder%5Csubfolder/")
    assert response.status_code == 400


# =============================================================================
# api_raw - Path Traversal and Backslash Tests
# =============================================================================


def test_raw_path_traversal(client, volume, editor_user):
    """Cannot access files outside volume with path traversal."""
    client.login(username="editor", password="editorpass")
    response = client.get(f"/api/{volume.name}/raw/../../etc/passwd")
    assert response.status_code == 400


def test_raw_backslash_in_path(client, volume, editor_user):
    """Backslash in raw path is handled."""
    client.login(username="editor", password="editorpass")
    response = client.get(f"/api/{volume.name}/raw/folder%5Cfile.txt")
    assert response.status_code == 404


# =============================================================================
# api_rename - Path Traversal and Backslash Tests
# =============================================================================


def test_rename_path_traversal(client, volume, editor_user):
    """Cannot rename with path traversal in path."""
    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/rename/",
        data=json.dumps({"path": "../secret", "new_name": "exposed"}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_rename_backslash_in_path(client, volume, editor_user):
    """Backslash in rename path is converted to forward slash."""
    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/rename/",
        data=json.dumps({"path": "folder\\file.txt", "new_name": "new.txt"}),
        content_type="application/json",
    )
    assert response.status_code == 404


# =============================================================================
# api_upload - Path Traversal and Backslash Tests
# =============================================================================


def test_upload_path_traversal(client, volume, editor_user):
    """Cannot upload with path traversal in path."""
    client.login(username="editor", password="editorpass")

    file_content = BytesIO(b"test content")
    file_content.name = "test.txt"
    response = client.post(
        f"/api/{volume.name}/upload/",
        data={"path": "../..", "files": file_content},
    )
    assert response.status_code == 404


def test_upload_backslash_in_path(client, volume, editor_user):
    """Backslash in upload path is converted to forward slash."""
    client.login(username="editor", password="editorpass")

    file_content = BytesIO(b"test content")
    file_content.name = "test.txt"
    response = client.post(
        f"/api/{volume.name}/upload/",
        data={"path": "folder\\subfolder", "files": file_content},
    )
    assert response.status_code == 404


def test_upload_path_traversal_in_relative_paths(client, volume, editor_user):
    """Cannot upload with path traversal in relative_paths."""
    client.login(username="editor", password="editorpass")

    file_content = BytesIO(b"test content")
    file_content.name = "test.txt"
    response = client.post(
        f"/api/{volume.name}/upload/",
        data={
            "path": "",
            "files": file_content,
            "relative_paths": json.dumps(["../../../etc/passwd"]),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["errors"]) == 1
    assert ".." in data["errors"][0]["error"] or "Invalid" in data["errors"][0]["error"]


# =============================================================================
# api_copy - Path Traversal and Backslash Tests
# =============================================================================


def test_copy_path_traversal_in_items(client, volume, editor_user):
    """Cannot copy with path traversal in items."""
    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/copy/",
        data=json.dumps({"items": ["../../etc/passwd"], "destination": ""}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["copied"]) == 0
    assert len(data["errors"]) == 1


def test_copy_path_traversal_in_destination(client, volume, editor_user):
    """Cannot copy with path traversal in destination."""
    client.login(username="editor", password="editorpass")

    (Path(volume.path) / "source.txt").write_text("content")
    response = client.post(
        f"/api/{volume.name}/copy/",
        data=json.dumps({"items": ["source.txt"], "destination": "../.."}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_copy_backslash_in_paths(client, volume, editor_user):
    """Backslash in copy paths is converted to forward slash."""
    client.login(username="editor", password="editorpass")

    (Path(volume.path) / "dest").mkdir()
    response = client.post(
        f"/api/{volume.name}/copy/",
        data=json.dumps({"items": ["folder\\file.txt"], "destination": "dest"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["copied"]) == 0
    assert len(data["errors"]) == 1


# =============================================================================
# api_move - Path Traversal and Backslash Tests
# =============================================================================


def test_move_path_traversal_in_items(client, volume, editor_user):
    """Cannot move with path traversal in items."""
    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/move/",
        data=json.dumps({"items": ["../../etc/passwd"], "destination": ""}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["moved"]) == 0
    assert len(data["errors"]) == 1


def test_move_path_traversal_in_destination(client, volume, editor_user):
    """Cannot move with path traversal in destination."""
    client.login(username="editor", password="editorpass")

    (Path(volume.path) / "tomove.txt").write_text("content")
    response = client.post(
        f"/api/{volume.name}/move/",
        data=json.dumps({"items": ["tomove.txt"], "destination": "../.."}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_move_backslash_in_paths(client, volume, editor_user):
    """Backslash in move paths is converted to forward slash."""
    client.login(username="editor", password="editorpass")

    (Path(volume.path) / "dest").mkdir(exist_ok=True)
    response = client.post(
        f"/api/{volume.name}/move/",
        data=json.dumps({"items": ["folder\\file.txt"], "destination": "dest"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["moved"]) == 0
    assert len(data["errors"]) == 1
