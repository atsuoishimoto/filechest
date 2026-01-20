import tempfile
import shutil

import boto3
import pytest
from django.test import Client
from django.contrib.auth import get_user_model
from moto import mock_aws

from filechest.models import Volume, VolumePermission, Role
from filechest.storage import LocalStorage, S3Storage

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
        name="test-volume",
        verbose_name="Test Volume",
        path=temp_volume_path,
        public_read=False,
        is_active=True,
    )


@pytest.fixture
def public_volume(db, temp_volume_path):
    """Create a public test volume."""
    path = tempfile.mkdtemp()
    vol = Volume.objects.create(
        name="public-volume",
        verbose_name="Public Volume",
        path=path,
        public_read=True,
        is_active=True,
    )
    yield vol
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def user(db):
    """Create a regular user."""
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def superuser(db):
    """Create a superuser."""
    return User.objects.create_superuser(username="admin", password="adminpass")


@pytest.fixture
def editor_user(db, volume):
    """Create a user with editor permission."""
    user = User.objects.create_user(username="editor", password="editorpass")
    VolumePermission.objects.create(user=user, volume=volume, role=Role.EDITOR)
    return user


@pytest.fixture
def viewer_user(db, volume):
    """Create a user with viewer permission."""
    user = User.objects.create_user(username="viewer", password="viewerpass")
    VolumePermission.objects.create(user=user, volume=volume, role=Role.VIEWER)
    return user


@pytest.fixture
def client():
    """Create a test client."""
    return Client()


@pytest.fixture
def local_storage():
    """Create a LocalStorage instance with a temporary directory."""
    path = tempfile.mkdtemp()
    storage = LocalStorage(path)
    yield storage
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def s3_storage():
    """Create an S3Storage instance with mocked AWS."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        yield S3Storage("test-bucket", s3_client=s3)


@pytest.fixture
def s3_storage_with_prefix():
    """Create an S3Storage instance with a prefix."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        yield S3Storage("test-bucket", prefix="myprefix", s3_client=s3)
