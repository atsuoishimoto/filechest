import json
import tempfile
import shutil
from pathlib import Path

import pytest
from django.test import Client
from django.contrib.auth import get_user_model

from filechest.models import Volume, VolumePermission, Role
from filechest.permissions import get_user_role, can_view, can_edit

User = get_user_model()


@pytest.fixture
def temp_volume_path():
    """Create a temporary directory for volume testing."""
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def volume(db, temp_volume_path):
    """Create a test volume."""
    return Volume.objects.create(
        name='test-volume',
        verbose_name='Test Volume',
        path=temp_volume_path,
        public_read=False,
        is_active=True,
    )


@pytest.fixture
def public_volume(db, temp_volume_path):
    """Create a public test volume."""
    path = tempfile.mkdtemp()
    vol = Volume.objects.create(
        name='public-volume',
        verbose_name='Public Volume',
        path=path,
        public_read=True,
        is_active=True,
    )
    yield vol
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def user(db):
    """Create a regular user."""
    return User.objects.create_user(username='testuser', password='testpass')


@pytest.fixture
def superuser(db):
    """Create a superuser."""
    return User.objects.create_superuser(username='admin', password='adminpass')


@pytest.fixture
def editor_user(db, volume):
    """Create a user with editor permission."""
    user = User.objects.create_user(username='editor', password='editorpass')
    VolumePermission.objects.create(user=user, volume=volume, role=Role.EDITOR)
    return user


@pytest.fixture
def viewer_user(db, volume):
    """Create a user with viewer permission."""
    user = User.objects.create_user(username='viewer', password='viewerpass')
    VolumePermission.objects.create(user=user, volume=volume, role=Role.VIEWER)
    return user


@pytest.fixture
def client():
    """Create a test client."""
    return Client()


# =============================================================================
# Permission Tests
# =============================================================================

class TestPermissions:
    """Test permission checking functions."""

    def test_superuser_always_editor(self, volume, superuser):
        """Superuser should always have editor role."""
        assert get_user_role(superuser, volume) == Role.EDITOR
        assert can_edit(superuser, volume) is True
        assert can_view(superuser, volume) is True

    def test_editor_permission(self, volume, editor_user):
        """User with editor permission should have editor role."""
        assert get_user_role(editor_user, volume) == Role.EDITOR
        assert can_edit(editor_user, volume) is True
        assert can_view(editor_user, volume) is True

    def test_viewer_permission(self, volume, viewer_user):
        """User with viewer permission should have viewer role."""
        assert get_user_role(viewer_user, volume) == Role.VIEWER
        assert can_edit(viewer_user, volume) is False
        assert can_view(viewer_user, volume) is True

    def test_no_permission(self, volume, user):
        """User without permission should have no access."""
        assert get_user_role(user, volume) is None
        assert can_edit(user, volume) is False
        assert can_view(user, volume) is False

    def test_public_read_anonymous(self, public_volume):
        """Anonymous user should have viewer access to public volume."""
        from django.contrib.auth.models import AnonymousUser
        anon = AnonymousUser()
        assert get_user_role(anon, public_volume) == Role.VIEWER
        assert can_view(anon, public_volume) is True
        assert can_edit(anon, public_volume) is False

    def test_public_read_authenticated_no_permission(self, public_volume, user):
        """Authenticated user without permission should have viewer access to public volume."""
        assert get_user_role(user, public_volume) == Role.VIEWER
        assert can_view(user, public_volume) is True

    def test_private_volume_anonymous(self, volume):
        """Anonymous user should have no access to private volume."""
        from django.contrib.auth.models import AnonymousUser
        anon = AnonymousUser()
        assert get_user_role(anon, volume) is None
        assert can_view(anon, volume) is False


# =============================================================================
# View Tests
# =============================================================================

class TestIndexView:
    """Test index view."""

    def test_index_public_volume(self, client, public_volume):
        """Anonymous user can access public volume."""
        response = client.get(f'/{public_volume.name}/')
        assert response.status_code == 200
        assert public_volume.verbose_name in response.content.decode()

    def test_index_private_volume_forbidden(self, client, volume):
        """Anonymous user cannot access private volume."""
        response = client.get(f'/{volume.name}/')
        assert response.status_code == 403

    def test_index_with_editor(self, client, volume, editor_user):
        """Editor can access volume and see toolbar."""
        client.login(username='editor', password='editorpass')
        response = client.get(f'/{volume.name}/')
        assert response.status_code == 200
        assert 'toolbar' in response.content.decode()

    def test_index_with_viewer(self, client, volume, viewer_user):
        """Viewer can access volume but not see toolbar."""
        client.login(username='viewer', password='viewerpass')
        response = client.get(f'/{volume.name}/')
        assert response.status_code == 200
        # Viewer should not see the toolbar
        content = response.content.decode()
        assert 'New Folder' not in content


# =============================================================================
# API Tests
# =============================================================================

class TestApiList:
    """Test api_list endpoint."""

    def test_list_public_volume(self, client, public_volume):
        """Can list public volume contents."""
        response = client.get(f'/api/{public_volume.name}/list/')
        assert response.status_code == 200
        data = response.json()
        assert data['volume']['name'] == public_volume.name

    def test_list_private_volume_forbidden(self, client, volume):
        """Cannot list private volume without permission."""
        response = client.get(f'/api/{volume.name}/list/')
        assert response.status_code == 403


class TestApiMkdir:
    """Test api_mkdir endpoint."""

    def test_mkdir_as_editor(self, client, volume, editor_user):
        """Editor can create folders."""
        client.login(username='editor', password='editorpass')
        response = client.post(
            f'/api/{volume.name}/mkdir/',
            data=json.dumps({'path': '', 'name': 'newfolder'}),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert (Path(volume.path) / 'newfolder').is_dir()

    def test_mkdir_as_viewer_forbidden(self, client, volume, viewer_user):
        """Viewer cannot create folders."""
        client.login(username='viewer', password='viewerpass')
        response = client.post(
            f'/api/{volume.name}/mkdir/',
            data=json.dumps({'path': '', 'name': 'newfolder'}),
            content_type='application/json',
        )
        assert response.status_code == 403

    def test_mkdir_invalid_name(self, client, volume, editor_user):
        """Cannot create folder with invalid name."""
        client.login(username='editor', password='editorpass')
        response = client.post(
            f'/api/{volume.name}/mkdir/',
            data=json.dumps({'path': '', 'name': '../escape'}),
            content_type='application/json',
        )
        assert response.status_code == 400


class TestApiDelete:
    """Test api_delete endpoint."""

    def test_delete_file(self, client, volume, editor_user):
        """Editor can delete files."""
        # Create a test file
        test_file = Path(volume.path) / 'testfile.txt'
        test_file.write_text('test content')

        client.login(username='editor', password='editorpass')
        response = client.post(
            f'/api/{volume.name}/delete/',
            data=json.dumps({'items': ['testfile.txt']}),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert 'testfile.txt' in data['deleted']
        assert not test_file.exists()

    def test_delete_folder(self, client, volume, editor_user):
        """Editor can delete folders."""
        # Create a test folder
        test_folder = Path(volume.path) / 'testfolder'
        test_folder.mkdir()
        (test_folder / 'file.txt').write_text('content')

        client.login(username='editor', password='editorpass')
        response = client.post(
            f'/api/{volume.name}/delete/',
            data=json.dumps({'items': ['testfolder']}),
            content_type='application/json',
        )
        assert response.status_code == 200
        assert not test_folder.exists()

    def test_delete_as_viewer_forbidden(self, client, volume, viewer_user):
        """Viewer cannot delete files."""
        client.login(username='viewer', password='viewerpass')
        response = client.post(
            f'/api/{volume.name}/delete/',
            data=json.dumps({'items': ['anyfile']}),
            content_type='application/json',
        )
        assert response.status_code == 403


class TestApiRename:
    """Test api_rename endpoint."""

    def test_rename_file(self, client, volume, editor_user):
        """Editor can rename files."""
        test_file = Path(volume.path) / 'oldname.txt'
        test_file.write_text('content')

        client.login(username='editor', password='editorpass')
        response = client.post(
            f'/api/{volume.name}/rename/',
            data=json.dumps({'path': 'oldname.txt', 'new_name': 'newname.txt'}),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert not test_file.exists()
        assert (Path(volume.path) / 'newname.txt').exists()


class TestApiUpload:
    """Test api_upload endpoint."""

    def test_upload_file(self, client, volume, editor_user):
        """Editor can upload files."""
        client.login(username='editor', password='editorpass')

        from io import BytesIO
        file_content = b'test file content'
        file = BytesIO(file_content)
        file.name = 'uploaded.txt'

        response = client.post(
            f'/api/{volume.name}/upload/',
            data={'path': '', 'files': file},
        )
        assert response.status_code == 200
        data = response.json()
        assert 'uploaded.txt' in data['uploaded']
        assert (Path(volume.path) / 'uploaded.txt').read_bytes() == file_content

    def test_upload_as_viewer_forbidden(self, client, volume, viewer_user):
        """Viewer cannot upload files."""
        client.login(username='viewer', password='viewerpass')

        from io import BytesIO
        file = BytesIO(b'content')
        file.name = 'test.txt'

        response = client.post(
            f'/api/{volume.name}/upload/',
            data={'path': '', 'files': file},
        )
        assert response.status_code == 403

    def test_upload_file_size_limit(self, client, volume, editor_user):
        """Files exceeding max_file_size should be rejected."""
        # Set a small limit for testing
        volume.max_file_size = 100  # 100 bytes
        volume.save()

        client.login(username='editor', password='editorpass')

        from io import BytesIO
        # Create a file larger than the limit
        file_content = b'x' * 200  # 200 bytes
        file = BytesIO(file_content)
        file.name = 'large.txt'

        response = client.post(
            f'/api/{volume.name}/upload/',
            data={'path': '', 'files': file},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data['uploaded']) == 0
        assert len(data['errors']) == 1
        assert 'exceeds limit' in data['errors'][0]['error']
        # File should not exist
        assert not (Path(volume.path) / 'large.txt').exists()

    def test_upload_directory_with_relative_paths(self, client, volume, editor_user):
        """Upload files with relative paths (directory upload)."""
        client.login(username='editor', password='editorpass')

        from io import BytesIO

        # Simulate uploading a directory structure: mydir/file1.txt, mydir/subdir/file2.txt
        file1 = BytesIO(b'content1')
        file1.name = 'file1.txt'
        file2 = BytesIO(b'content2')
        file2.name = 'file2.txt'

        relative_paths = json.dumps(['mydir/file1.txt', 'mydir/subdir/file2.txt'])

        response = client.post(
            f'/api/{volume.name}/upload/',
            data={
                'path': '',
                'files': [file1, file2],
                'relative_paths': relative_paths,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert 'mydir/file1.txt' in data['uploaded']
        assert 'mydir/subdir/file2.txt' in data['uploaded']

        # Check files were created with directory structure
        assert (Path(volume.path) / 'mydir' / 'file1.txt').read_bytes() == b'content1'
        assert (Path(volume.path) / 'mydir' / 'subdir' / 'file2.txt').read_bytes() == b'content2'


class TestApiCopy:
    """Test api_copy endpoint."""

    def test_copy_file(self, client, volume, editor_user):
        """Editor can copy files."""
        # Create source file and destination folder
        (Path(volume.path) / 'source.txt').write_text('content')
        (Path(volume.path) / 'dest').mkdir()

        client.login(username='editor', password='editorpass')
        response = client.post(
            f'/api/{volume.name}/copy/',
            data=json.dumps({'items': ['source.txt'], 'destination': 'dest'}),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert 'source.txt' in data['copied']
        # Original still exists
        assert (Path(volume.path) / 'source.txt').exists()
        # Copy exists
        assert (Path(volume.path) / 'dest' / 'source.txt').exists()


class TestApiMove:
    """Test api_move endpoint."""

    def test_move_file(self, client, volume, editor_user):
        """Editor can move files."""
        # Create source file and destination folder
        (Path(volume.path) / 'tomove.txt').write_text('content')
        (Path(volume.path) / 'dest').mkdir()

        client.login(username='editor', password='editorpass')
        response = client.post(
            f'/api/{volume.name}/move/',
            data=json.dumps({'items': ['tomove.txt'], 'destination': 'dest'}),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert 'tomove.txt' in data['moved']
        # Original no longer exists
        assert not (Path(volume.path) / 'tomove.txt').exists()
        # Moved file exists
        assert (Path(volume.path) / 'dest' / 'tomove.txt').exists()


class TestApiDownload:
    """Test api_download endpoint."""

    def test_download_file(self, client, public_volume):
        """Can download file from public volume."""
        test_file = Path(public_volume.path) / 'download.txt'
        test_file.write_text('download content')

        response = client.get(f'/api/{public_volume.name}/download/download.txt/')
        assert response.status_code == 200
        assert b'download content' in b''.join(response.streaming_content)

    def test_download_private_forbidden(self, client, volume):
        """Cannot download from private volume without permission."""
        test_file = Path(volume.path) / 'secret.txt'
        test_file.write_text('secret')

        response = client.get(f'/api/{volume.name}/download/secret.txt/')
        assert response.status_code == 403


class TestPreview:
    """Test preview page."""

    def test_preview_public_volume(self, client, public_volume):
        """Can access preview page for public volume."""
        test_file = Path(public_volume.path) / 'test.txt'
        test_file.write_text('test content')

        response = client.get(f'/{public_volume.name}/preview/test.txt/')
        assert response.status_code == 200
        assert 'test.txt' in response.content.decode()
        assert 'Download' in response.content.decode()

    def test_preview_private_forbidden(self, client, volume):
        """Cannot access preview page without permission."""
        test_file = Path(volume.path) / 'secret.txt'
        test_file.write_text('secret')

        response = client.get(f'/{volume.name}/preview/secret.txt/')
        assert response.status_code == 403

    def test_preview_with_permission(self, client, volume, viewer_user):
        """Viewer can access preview page."""
        test_file = Path(volume.path) / 'test.txt'
        test_file.write_text('test content')

        client.login(username='viewer', password='viewerpass')
        response = client.get(f'/{volume.name}/preview/test.txt/')
        assert response.status_code == 200
        assert 'test.txt' in response.content.decode()

    def test_preview_directory_404(self, client, public_volume):
        """Preview of directory should return 404."""
        (Path(public_volume.path) / 'subdir').mkdir()

        response = client.get(f'/{public_volume.name}/preview/subdir/')
        assert response.status_code == 404


class TestApiRaw:
    """Test api_raw endpoint (for inline preview)."""

    def test_raw_text_file(self, client, public_volume):
        """Can get raw text file content."""
        test_file = Path(public_volume.path) / 'test.txt'
        test_file.write_text('raw content')

        response = client.get(f'/api/{public_volume.name}/raw/test.txt/')
        assert response.status_code == 200
        assert b'raw content' in b''.join(response.streaming_content)

    def test_raw_private_forbidden(self, client, volume):
        """Cannot get raw content without permission."""
        test_file = Path(volume.path) / 'secret.txt'
        test_file.write_text('secret')

        response = client.get(f'/api/{volume.name}/raw/secret.txt/')
        assert response.status_code == 403


# =============================================================================
# Security Tests
# =============================================================================

class TestPathTraversal:
    """Test path traversal prevention."""

    def test_mkdir_path_traversal(self, client, volume, editor_user):
        """Cannot create folder outside volume with path traversal."""
        client.login(username='editor', password='editorpass')
        response = client.post(
            f'/api/{volume.name}/mkdir/',
            data=json.dumps({'path': '../..', 'name': 'escape'}),
            content_type='application/json',
        )
        assert response.status_code == 400  # Invalid path

    def test_delete_path_traversal(self, client, volume, editor_user):
        """Cannot delete outside volume with path traversal."""
        client.login(username='editor', password='editorpass')
        response = client.post(
            f'/api/{volume.name}/delete/',
            data=json.dumps({'items': ['../../etc/passwd']}),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data['deleted']) == 0
        assert len(data['errors']) == 1


# =============================================================================
# Storage Tests
# =============================================================================

from filechest.storage import (
    LocalStorage,
    PathNotFoundError,
    PathExistsError,
    InvalidPathError,
    NotAFileError,
    NotADirectoryError,
)


@pytest.fixture
def local_storage():
    """Create a LocalStorage instance with a temp directory."""
    path = tempfile.mkdtemp()
    storage = LocalStorage(path)
    yield storage
    shutil.rmtree(path, ignore_errors=True)


class TestLocalStorage:
    """Test LocalStorage backend."""

    def test_list_empty_dir(self, local_storage):
        """List empty root directory."""
        items = local_storage.list_dir('')
        assert items == []

    def test_list_dir_with_files(self, local_storage):
        """List directory with files and folders."""
        # Create test files and folders
        (Path(local_storage.root) / 'file.txt').write_text('content')
        (Path(local_storage.root) / 'folder').mkdir()

        items = local_storage.list_dir('')
        assert len(items) == 2

        names = {item.name for item in items}
        assert names == {'file.txt', 'folder'}

    def test_get_info_file(self, local_storage):
        """Get info for a file."""
        (Path(local_storage.root) / 'test.txt').write_text('hello')

        info = local_storage.get_info('test.txt')
        assert info.name == 'test.txt'
        assert info.is_dir is False
        assert info.size == 5

    def test_get_info_dir(self, local_storage):
        """Get info for a directory."""
        (Path(local_storage.root) / 'mydir').mkdir()

        info = local_storage.get_info('mydir')
        assert info.name == 'mydir'
        assert info.is_dir is True
        assert info.size is None

    def test_exists(self, local_storage):
        """Test exists method."""
        (Path(local_storage.root) / 'exists.txt').write_text('x')

        assert local_storage.exists('exists.txt') is True
        assert local_storage.exists('notexists.txt') is False

    def test_is_dir(self, local_storage):
        """Test is_dir method."""
        (Path(local_storage.root) / 'folder').mkdir()
        (Path(local_storage.root) / 'file.txt').write_text('x')

        assert local_storage.is_dir('folder') is True
        assert local_storage.is_dir('file.txt') is False
        assert local_storage.is_dir('notexists') is False

    def test_is_file(self, local_storage):
        """Test is_file method."""
        (Path(local_storage.root) / 'folder').mkdir()
        (Path(local_storage.root) / 'file.txt').write_text('x')

        assert local_storage.is_file('file.txt') is True
        assert local_storage.is_file('folder') is False
        assert local_storage.is_file('notexists') is False

    def test_open_file(self, local_storage):
        """Test open_file method."""
        (Path(local_storage.root) / 'data.txt').write_bytes(b'binary data')

        with local_storage.open_file('data.txt') as f:
            content = f.read()
        assert content == b'binary data'

    def test_open_file_not_found(self, local_storage):
        """Opening non-existent file raises error."""
        with pytest.raises(PathNotFoundError):
            local_storage.open_file('notexists.txt')

    def test_write_file(self, local_storage):
        """Test write_file method."""
        chunks = [b'hello ', b'world']
        local_storage.write_file('output.txt', iter(chunks))

        content = (Path(local_storage.root) / 'output.txt').read_bytes()
        assert content == b'hello world'

    def test_write_file_creates_parents(self, local_storage):
        """write_file creates parent directories."""
        chunks = [b'data']
        local_storage.write_file('a/b/c/file.txt', iter(chunks))

        assert (Path(local_storage.root) / 'a' / 'b' / 'c' / 'file.txt').exists()

    def test_mkdir(self, local_storage):
        """Test mkdir method."""
        local_storage.mkdir('newdir')
        assert (Path(local_storage.root) / 'newdir').is_dir()

    def test_mkdir_already_exists(self, local_storage):
        """mkdir raises error if path exists."""
        (Path(local_storage.root) / 'existing').mkdir()

        with pytest.raises(PathExistsError):
            local_storage.mkdir('existing')

    def test_delete_file(self, local_storage):
        """Test delete file."""
        (Path(local_storage.root) / 'todelete.txt').write_text('x')

        local_storage.delete('todelete.txt')
        assert not (Path(local_storage.root) / 'todelete.txt').exists()

    def test_delete_dir(self, local_storage):
        """Test delete directory recursively."""
        (Path(local_storage.root) / 'dir' / 'subdir').mkdir(parents=True)
        (Path(local_storage.root) / 'dir' / 'file.txt').write_text('x')

        local_storage.delete('dir')
        assert not (Path(local_storage.root) / 'dir').exists()

    def test_delete_root_fails(self, local_storage):
        """Cannot delete root."""
        with pytest.raises(InvalidPathError):
            local_storage.delete('')

    def test_rename(self, local_storage):
        """Test rename method."""
        (Path(local_storage.root) / 'old.txt').write_text('x')

        local_storage.rename('old.txt', 'new.txt')
        assert not (Path(local_storage.root) / 'old.txt').exists()
        assert (Path(local_storage.root) / 'new.txt').exists()

    def test_copy_file(self, local_storage):
        """Test copy file."""
        (Path(local_storage.root) / 'source.txt').write_text('content')
        (Path(local_storage.root) / 'dest').mkdir()

        local_storage.copy('source.txt', 'dest')
        assert (Path(local_storage.root) / 'source.txt').exists()
        assert (Path(local_storage.root) / 'dest' / 'source.txt').read_text() == 'content'

    def test_copy_dir(self, local_storage):
        """Test copy directory."""
        (Path(local_storage.root) / 'srcdir').mkdir()
        (Path(local_storage.root) / 'srcdir' / 'file.txt').write_text('x')
        (Path(local_storage.root) / 'dest').mkdir()

        local_storage.copy('srcdir', 'dest')
        assert (Path(local_storage.root) / 'dest' / 'srcdir' / 'file.txt').exists()

    def test_move_file(self, local_storage):
        """Test move file."""
        (Path(local_storage.root) / 'tomove.txt').write_text('content')
        (Path(local_storage.root) / 'dest').mkdir()

        local_storage.move('tomove.txt', 'dest')
        assert not (Path(local_storage.root) / 'tomove.txt').exists()
        assert (Path(local_storage.root) / 'dest' / 'tomove.txt').read_text() == 'content'

    def test_path_traversal_blocked(self, local_storage):
        """Path traversal attempts are blocked."""
        with pytest.raises(InvalidPathError):
            local_storage.list_dir('../..')

        with pytest.raises(InvalidPathError):
            local_storage.get_info('../../etc/passwd')

        with pytest.raises(InvalidPathError):
            local_storage.mkdir('../escape')


# =============================================================================
# S3 Storage Tests
# =============================================================================

import boto3
from moto import mock_aws
from filechest.storage import S3Storage, parse_s3_path


@pytest.fixture
def s3_storage():
    """Create an S3Storage instance with mocked S3."""
    with mock_aws():
        # Create a mock S3 client and bucket
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)

        storage = S3Storage(bucket_name, prefix='', s3_client=s3_client)
        yield storage


@pytest.fixture
def s3_storage_with_prefix():
    """Create an S3Storage instance with a prefix."""
    with mock_aws():
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)

        storage = S3Storage(bucket_name, prefix='myprefix', s3_client=s3_client)
        yield storage


class TestS3Storage:
    """Test S3Storage backend."""

    def test_list_empty_dir(self, s3_storage):
        """List empty root directory."""
        items = s3_storage.list_dir('')
        assert items == []

    def test_list_dir_with_files(self, s3_storage):
        """List directory with files and folders."""
        # Create test files
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='file.txt', Body=b'content')
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='folder/.dir', Body=b'')

        items = s3_storage.list_dir('')
        assert len(items) == 2

        names = {item.name for item in items}
        assert names == {'file.txt', 'folder'}

    def test_get_info_file(self, s3_storage):
        """Get info for a file."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='test.txt', Body=b'hello')

        info = s3_storage.get_info('test.txt')
        assert info.name == 'test.txt'
        assert info.is_dir is False
        assert info.size == 5

    def test_get_info_dir(self, s3_storage):
        """Get info for a directory (implicit via file)."""
        # In S3, directories are implicit - they exist when files exist under them
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='mydir/file.txt', Body=b'x')

        info = s3_storage.get_info('mydir')
        assert info.name == 'mydir'
        assert info.is_dir is True
        assert info.size is None

    def test_exists(self, s3_storage):
        """Test exists method."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='exists.txt', Body=b'x')

        assert s3_storage.exists('exists.txt') is True
        assert s3_storage.exists('notexists.txt') is False

    def test_is_dir(self, s3_storage):
        """Test is_dir method."""
        # In S3, directories are implicit - they exist when files exist under them
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='folder/dummy.txt', Body=b'x')
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='file.txt', Body=b'x')

        assert s3_storage.is_dir('folder') is True
        assert s3_storage.is_dir('file.txt') is False
        assert s3_storage.is_dir('notexists') is False
        assert s3_storage.is_dir('') is True  # Root is a directory

    def test_is_file(self, s3_storage):
        """Test is_file method."""
        # In S3, directories are implicit - they exist when files exist under them
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='folder/dummy.txt', Body=b'x')
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='file.txt', Body=b'x')

        assert s3_storage.is_file('file.txt') is True
        assert s3_storage.is_file('folder') is False
        assert s3_storage.is_file('notexists') is False

    def test_open_file(self, s3_storage):
        """Test open_file method."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='data.txt', Body=b'binary data')

        f = s3_storage.open_file('data.txt')
        content = f.read()
        assert content == b'binary data'

    def test_open_file_not_found(self, s3_storage):
        """Opening non-existent file raises error."""
        with pytest.raises(PathNotFoundError):
            s3_storage.open_file('notexists.txt')

    def test_write_file(self, s3_storage):
        """Test write_file method."""
        chunks = [b'hello ', b'world']
        s3_storage.write_file('output.txt', iter(chunks))

        response = s3_storage.s3.get_object(Bucket=s3_storage.bucket, Key='output.txt')
        assert response['Body'].read() == b'hello world'

    def test_mkdir(self, s3_storage):
        """Test mkdir method (no-op for S3, directories are implicit)."""
        # mkdir is a no-op for S3 - directories only exist when files exist under them
        s3_storage.mkdir('newdir')
        # Directory doesn't exist yet because no files are under it
        assert not s3_storage.is_dir('newdir')

        # After adding a file, the directory exists
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='newdir/file.txt', Body=b'x')
        assert s3_storage.is_dir('newdir')

    def test_mkdir_file_collision(self, s3_storage):
        """mkdir raises error if a file with that name exists."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='existing', Body=b'x')

        with pytest.raises(PathExistsError):
            s3_storage.mkdir('existing')

    def test_delete_file(self, s3_storage):
        """Test delete file."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='todelete.txt', Body=b'x')

        s3_storage.delete('todelete.txt')
        assert not s3_storage.exists('todelete.txt')

    def test_delete_dir(self, s3_storage):
        """Test delete directory recursively."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='dir/file.txt', Body=b'x')
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='dir/subdir/file2.txt', Body=b'y')

        s3_storage.delete('dir')
        assert not s3_storage.exists('dir')
        assert not s3_storage.exists('dir/file.txt')

    def test_delete_root_fails(self, s3_storage):
        """Cannot delete root."""
        with pytest.raises(InvalidPathError):
            s3_storage.delete('')

    def test_rename_file(self, s3_storage):
        """Test rename file."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='old.txt', Body=b'content')

        s3_storage.rename('old.txt', 'new.txt')
        assert not s3_storage.exists('old.txt')
        assert s3_storage.exists('new.txt')

    def test_rename_dir(self, s3_storage):
        """Test rename directory."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='olddir/file.txt', Body=b'x')

        s3_storage.rename('olddir', 'newdir')
        assert not s3_storage.exists('olddir')
        assert s3_storage.exists('newdir')
        assert s3_storage.exists('newdir/file.txt')

    def test_copy_file(self, s3_storage):
        """Test copy file to non-existent directory (directories are implicit in S3)."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='source.txt', Body=b'content')

        # Can copy to non-existent directory
        s3_storage.copy('source.txt', 'newdir')
        assert s3_storage.exists('source.txt')
        assert s3_storage.exists('newdir/source.txt')

    def test_copy_dir(self, s3_storage):
        """Test copy directory to non-existent directory."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='srcdir/file.txt', Body=b'x')

        # Can copy to non-existent directory
        s3_storage.copy('srcdir', 'newdir')
        assert s3_storage.exists('srcdir/file.txt')
        assert s3_storage.exists('newdir/srcdir/file.txt')

    def test_move_file(self, s3_storage):
        """Test move file to non-existent directory."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='tomove.txt', Body=b'content')

        # Can move to non-existent directory
        s3_storage.move('tomove.txt', 'newdir')
        assert not s3_storage.exists('tomove.txt')
        assert s3_storage.exists('newdir/tomove.txt')

    def test_copy_to_file_fails(self, s3_storage):
        """Cannot copy to a path that is a file."""
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='source.txt', Body=b'content')
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='dest', Body=b'a file')

        with pytest.raises(NotADirectoryError):
            s3_storage.copy('source.txt', 'dest')

    def test_path_traversal_blocked(self, s3_storage):
        """Path traversal attempts are blocked."""
        with pytest.raises(InvalidPathError):
            s3_storage.list_dir('../..')

        with pytest.raises(InvalidPathError):
            s3_storage.mkdir('../escape')

    def test_with_prefix(self, s3_storage_with_prefix):
        """Test S3Storage with prefix."""
        storage = s3_storage_with_prefix

        # Write a file
        storage.write_file('test.txt', iter([b'hello']))

        # Check it's stored with the prefix
        response = storage.s3.get_object(Bucket=storage.bucket, Key='myprefix/test.txt')
        assert response['Body'].read() == b'hello'

        # Can read it back
        assert storage.exists('test.txt')
        assert storage.is_file('test.txt')

    def test_implicit_directory(self, s3_storage):
        """Directories are implicitly created when files are uploaded."""
        # Upload a file in a nested path
        s3_storage.write_file('a/b/c/file.txt', iter([b'content']))

        # Parent directories should exist implicitly
        assert s3_storage.is_dir('a')
        assert s3_storage.is_dir('a/b')
        assert s3_storage.is_dir('a/b/c')
        assert s3_storage.is_file('a/b/c/file.txt')

    def test_file_and_directory_same_name(self, s3_storage):
        """S3 allows a file and directory to have the same name."""
        # Create a file
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='aaa/a.txt', Body=b'file content')
        # Create another file under the same "path" as a directory
        s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key='aaa/a.txt/bbb/c.txt', Body=b'nested content')

        # Both should be recognized
        assert s3_storage.is_file('aaa/a.txt') is True
        assert s3_storage.is_dir('aaa/a.txt') is True  # Because a.txt/bbb/c.txt exists
        assert s3_storage.exists('aaa/a.txt') is True

        # list_dir should show both as file and directory
        items = s3_storage.list_dir('aaa')
        names_and_types = [(item.name, item.is_dir) for item in items]
        assert ('a.txt', False) in names_and_types  # File
        assert ('a.txt', True) in names_and_types   # Directory

        # Can list the "directory" a.txt
        nested_items = s3_storage.list_dir('aaa/a.txt')
        nested_names = [item.name for item in nested_items]
        assert 'bbb' in nested_names


class TestParseS3Path:
    """Test parse_s3_path function."""

    def test_parse_bucket_only(self):
        bucket, prefix = parse_s3_path('s3://mybucket')
        assert bucket == 'mybucket'
        assert prefix == ''

    def test_parse_bucket_with_prefix(self):
        bucket, prefix = parse_s3_path('s3://mybucket/some/prefix')
        assert bucket == 'mybucket'
        assert prefix == 'some/prefix'

    def test_invalid_path(self):
        with pytest.raises(ValueError):
            parse_s3_path('/local/path')


# =============================================================================
# S3 Bucket Listing Tests
# =============================================================================

from filechest.storage import list_s3_buckets


class TestListS3Buckets:
    """Test list_s3_buckets function."""

    def test_list_buckets_empty(self):
        """List buckets when no buckets exist."""
        with mock_aws():
            s3_client = boto3.client('s3', region_name='us-east-1')
            buckets = list_s3_buckets(s3_client=s3_client)
            assert buckets == []

    def test_list_buckets_single(self):
        """List buckets with a single bucket."""
        with mock_aws():
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='my-bucket')

            buckets = list_s3_buckets(s3_client=s3_client)
            assert buckets == ['my-bucket']

    def test_list_buckets_multiple(self):
        """List buckets with multiple buckets."""
        with mock_aws():
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='bucket-a')
            s3_client.create_bucket(Bucket='bucket-b')
            s3_client.create_bucket(Bucket='bucket-c')

            buckets = list_s3_buckets(s3_client=s3_client)
            assert set(buckets) == {'bucket-a', 'bucket-b', 'bucket-c'}


# =============================================================================
# Adhoc Mode Tests
# =============================================================================

from django_filechest.__main__ import is_s3_bucket_list_mode, sanitize_bucket_name


class TestAdhocMode:
    """Test adhoc mode helper functions."""

    def test_is_s3_bucket_list_mode(self):
        """Test S3 bucket list mode detection."""
        assert is_s3_bucket_list_mode('s3://') is True
        assert is_s3_bucket_list_mode('s3:') is True
        assert is_s3_bucket_list_mode('s3') is True
        assert is_s3_bucket_list_mode('s3://bucket') is False
        assert is_s3_bucket_list_mode('s3://bucket/prefix') is False
        assert is_s3_bucket_list_mode('/local/path') is False

    def test_sanitize_bucket_name(self):
        """Test bucket name sanitization for Django slug compatibility."""
        assert sanitize_bucket_name('my-bucket') == 'my-bucket'
        assert sanitize_bucket_name('my.bucket.name') == 'my-bucket-name'
        assert sanitize_bucket_name('notemata.app') == 'notemata-app'
        assert sanitize_bucket_name('simple') == 'simple'
