from pathlib import Path


# =============================================================================
# Index View Tests
# =============================================================================


def test_index_public_volume(client, public_volume):
    """Anonymous user can access public volume."""
    response = client.get(f"/{public_volume.name}/")
    assert response.status_code == 200
    assert public_volume.verbose_name in response.content.decode()


def test_index_private_volume_forbidden(client, volume):
    """Anonymous user cannot access private volume."""
    response = client.get(f"/{volume.name}/")
    assert response.status_code == 403


def test_index_with_editor(client, volume, editor_user):
    """Editor can access volume and see toolbar."""
    client.login(username="editor", password="editorpass")
    response = client.get(f"/{volume.name}/")
    assert response.status_code == 200
    assert "toolbar" in response.content.decode()


def test_index_with_viewer(client, volume, viewer_user):
    """Viewer can access volume but not see toolbar."""
    client.login(username="viewer", password="viewerpass")
    response = client.get(f"/{volume.name}/")
    assert response.status_code == 200
    # Viewer should not see the toolbar
    content = response.content.decode()
    assert "New Folder" not in content


# =============================================================================
# Preview View Tests
# =============================================================================


def test_preview_public_volume(client, public_volume):
    """Can access preview page for public volume."""
    test_file = Path(public_volume.path) / "test.txt"
    test_file.write_text("test content")

    response = client.get(f"/{public_volume.name}/preview/test.txt/")
    assert response.status_code == 200
    assert "test.txt" in response.content.decode()
    assert "Download" in response.content.decode()


def test_preview_private_forbidden(client, volume):
    """Cannot access preview page without permission."""
    test_file = Path(volume.path) / "secret.txt"
    test_file.write_text("secret")

    response = client.get(f"/{volume.name}/preview/secret.txt/")
    assert response.status_code == 403


def test_preview_with_permission(client, volume, viewer_user):
    """Viewer can access preview page."""
    test_file = Path(volume.path) / "test.txt"
    test_file.write_text("test content")

    client.login(username="viewer", password="viewerpass")
    response = client.get(f"/{volume.name}/preview/test.txt/")
    assert response.status_code == 200
    assert "test.txt" in response.content.decode()


def test_preview_directory_404(client, public_volume):
    """Preview of directory should return 404."""
    (Path(public_volume.path) / "subdir").mkdir()

    response = client.get(f"/{public_volume.name}/preview/subdir/")
    assert response.status_code == 404
