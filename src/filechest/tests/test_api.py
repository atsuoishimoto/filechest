import json
from io import BytesIO
from pathlib import Path


# =============================================================================
# api_list Tests
# =============================================================================


def test_list_public_volume(client, public_volume):
    """Can list public volume contents."""
    response = client.get(f"/api/{public_volume.name}/list/")
    assert response.status_code == 200
    data = response.json()
    assert data["volume"]["name"] == public_volume.name


def test_list_private_volume_forbidden(client, volume):
    """Cannot list private volume without permission."""
    response = client.get(f"/api/{volume.name}/list/")
    assert response.status_code == 403


# =============================================================================
# api_mkdir Tests
# =============================================================================


def test_mkdir_as_editor(client, volume, editor_user):
    """Editor can create folders."""
    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/mkdir/",
        data=json.dumps({"path": "", "name": "newfolder"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert (Path(volume.path) / "newfolder").is_dir()


def test_mkdir_as_viewer_forbidden(client, volume, viewer_user):
    """Viewer cannot create folders."""
    client.login(username="viewer", password="viewerpass")
    response = client.post(
        f"/api/{volume.name}/mkdir/",
        data=json.dumps({"path": "", "name": "newfolder"}),
        content_type="application/json",
    )
    assert response.status_code == 403


def test_mkdir_invalid_name(client, volume, editor_user):
    """Cannot create folder with invalid name."""
    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/mkdir/",
        data=json.dumps({"path": "", "name": "../escape"}),
        content_type="application/json",
    )
    assert response.status_code == 400


# =============================================================================
# api_delete Tests
# =============================================================================


def test_delete_file(client, volume, editor_user):
    """Editor can delete files."""
    test_file = Path(volume.path) / "testfile.txt"
    test_file.write_text("test content")

    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/delete/",
        data=json.dumps({"items": ["testfile.txt"]}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "testfile.txt" in data["deleted"]
    assert not test_file.exists()


def test_delete_folder(client, volume, editor_user):
    """Editor can delete folders."""
    test_folder = Path(volume.path) / "testfolder"
    test_folder.mkdir()
    (test_folder / "file.txt").write_text("content")

    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/delete/",
        data=json.dumps({"items": ["testfolder"]}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert not test_folder.exists()


def test_delete_as_viewer_forbidden(client, volume, viewer_user):
    """Viewer cannot delete files."""
    client.login(username="viewer", password="viewerpass")
    response = client.post(
        f"/api/{volume.name}/delete/",
        data=json.dumps({"items": ["anyfile"]}),
        content_type="application/json",
    )
    assert response.status_code == 403


# =============================================================================
# api_rename Tests
# =============================================================================


def test_rename_file(client, volume, editor_user):
    """Editor can rename files."""
    test_file = Path(volume.path) / "oldname.txt"
    test_file.write_text("content")

    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/rename/",
        data=json.dumps({"path": "oldname.txt", "new_name": "newname.txt"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert not test_file.exists()
    assert (Path(volume.path) / "newname.txt").exists()


# =============================================================================
# api_upload Tests
# =============================================================================


def test_upload_file(client, volume, editor_user):
    """Editor can upload files."""
    client.login(username="editor", password="editorpass")

    file_content = b"test file content"
    file = BytesIO(file_content)
    file.name = "uploaded.txt"

    response = client.post(
        f"/api/{volume.name}/upload/",
        data={"path": "", "files": file},
    )
    assert response.status_code == 200
    data = response.json()
    assert "uploaded.txt" in data["uploaded"]
    assert (Path(volume.path) / "uploaded.txt").read_bytes() == file_content


def test_upload_as_viewer_forbidden(client, volume, viewer_user):
    """Viewer cannot upload files."""
    client.login(username="viewer", password="viewerpass")

    file = BytesIO(b"content")
    file.name = "test.txt"

    response = client.post(
        f"/api/{volume.name}/upload/",
        data={"path": "", "files": file},
    )
    assert response.status_code == 403


def test_upload_file_size_limit(client, volume, editor_user):
    """Files exceeding max_file_size should be rejected."""
    volume.max_file_size = 100  # 100 bytes
    volume.save()

    client.login(username="editor", password="editorpass")

    file_content = b"x" * 200  # 200 bytes
    file = BytesIO(file_content)
    file.name = "large.txt"

    response = client.post(
        f"/api/{volume.name}/upload/",
        data={"path": "", "files": file},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["uploaded"]) == 0
    assert len(data["errors"]) == 1
    assert "exceeds limit" in data["errors"][0]["error"]
    assert not (Path(volume.path) / "large.txt").exists()


def test_upload_directory_with_relative_paths(client, volume, editor_user):
    """Upload files with relative paths (directory upload)."""
    client.login(username="editor", password="editorpass")

    file1 = BytesIO(b"content1")
    file1.name = "file1.txt"
    file2 = BytesIO(b"content2")
    file2.name = "file2.txt"

    relative_paths = json.dumps(["mydir/file1.txt", "mydir/subdir/file2.txt"])

    response = client.post(
        f"/api/{volume.name}/upload/",
        data={
            "path": "",
            "files": [file1, file2],
            "relative_paths": relative_paths,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "mydir/file1.txt" in data["uploaded"]
    assert "mydir/subdir/file2.txt" in data["uploaded"]

    assert (Path(volume.path) / "mydir" / "file1.txt").read_bytes() == b"content1"
    assert (
        Path(volume.path) / "mydir" / "subdir" / "file2.txt"
    ).read_bytes() == b"content2"


# =============================================================================
# api_copy Tests
# =============================================================================


def test_copy_file(client, volume, editor_user):
    """Editor can copy files."""
    (Path(volume.path) / "source.txt").write_text("content")
    (Path(volume.path) / "dest").mkdir()

    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/copy/",
        data=json.dumps({"items": ["source.txt"], "destination": "dest"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "source.txt" in data["copied"]
    assert (Path(volume.path) / "source.txt").exists()
    assert (Path(volume.path) / "dest" / "source.txt").exists()


# =============================================================================
# api_move Tests
# =============================================================================


def test_move_file(client, volume, editor_user):
    """Editor can move files."""
    (Path(volume.path) / "tomove.txt").write_text("content")
    (Path(volume.path) / "dest").mkdir()

    client.login(username="editor", password="editorpass")
    response = client.post(
        f"/api/{volume.name}/move/",
        data=json.dumps({"items": ["tomove.txt"], "destination": "dest"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "tomove.txt" in data["moved"]
    assert not (Path(volume.path) / "tomove.txt").exists()
    assert (Path(volume.path) / "dest" / "tomove.txt").exists()


# =============================================================================
# api_raw Tests
# =============================================================================


def test_raw_text_file(client, public_volume):
    """Can get raw text file content."""
    test_file = Path(public_volume.path) / "test.txt"
    test_file.write_text("raw content")

    response = client.get(f"/api/{public_volume.name}/raw/test.txt/")
    assert response.status_code == 200
    assert b"raw content" in b"".join(response.streaming_content)


def test_raw_private_forbidden(client, volume):
    """Cannot get raw content without permission."""
    test_file = Path(volume.path) / "secret.txt"
    test_file.write_text("secret")

    response = client.get(f"/api/{volume.name}/raw/secret.txt/")
    assert response.status_code == 403
