"""Storage backend tests."""

import shutil
import tempfile
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from django_filechest.__main__ import is_s3_bucket_list_mode, sanitize_bucket_name
from filechest.storage import (
    LocalStorage,
    S3Storage,
    PathNotFoundError,
    PathExistsError,
    InvalidPathError,
    NotADirectoryError,
    parse_s3_path,
    list_s3_buckets,
)


# =============================================================================
# LocalStorage Tests
# =============================================================================


def test_local_list_empty_dir(local_storage):
    """List empty root directory."""
    items = local_storage.list_dir("")
    assert items == []


def test_local_list_dir_with_files(local_storage):
    """List directory with files and folders."""
    (Path(local_storage.root) / "file.txt").write_text("content")
    (Path(local_storage.root) / "folder").mkdir()

    items = local_storage.list_dir("")
    assert len(items) == 2

    names = {item.name for item in items}
    assert names == {"file.txt", "folder"}


def test_local_get_info_file(local_storage):
    """Get info for a file."""
    (Path(local_storage.root) / "test.txt").write_text("hello")

    info = local_storage.get_info("test.txt")
    assert info.name == "test.txt"
    assert info.is_dir is False
    assert info.size == 5


def test_local_get_info_dir(local_storage):
    """Get info for a directory."""
    (Path(local_storage.root) / "mydir").mkdir()

    info = local_storage.get_info("mydir")
    assert info.name == "mydir"
    assert info.is_dir is True
    assert info.size is None


def test_local_exists(local_storage):
    """Test exists method."""
    (Path(local_storage.root) / "exists.txt").write_text("x")

    assert local_storage.exists("exists.txt") is True
    assert local_storage.exists("notexists.txt") is False


def test_local_is_dir(local_storage):
    """Test is_dir method."""
    (Path(local_storage.root) / "folder").mkdir()
    (Path(local_storage.root) / "file.txt").write_text("x")

    assert local_storage.is_dir("folder") is True
    assert local_storage.is_dir("file.txt") is False
    assert local_storage.is_dir("notexists") is False


def test_local_is_file(local_storage):
    """Test is_file method."""
    (Path(local_storage.root) / "folder").mkdir()
    (Path(local_storage.root) / "file.txt").write_text("x")

    assert local_storage.is_file("file.txt") is True
    assert local_storage.is_file("folder") is False
    assert local_storage.is_file("notexists") is False


def test_local_open_file(local_storage):
    """Test open_file method."""
    (Path(local_storage.root) / "data.txt").write_bytes(b"binary data")

    file_obj, etag, size = local_storage.open_file("data.txt")
    with file_obj as f:
        content = f.read()
    assert content == b"binary data"
    assert etag is not None  # LocalStorage returns SHA256-based ETag
    assert etag.startswith('"') and etag.endswith('"')  # ETag format
    assert size == 11


def test_local_open_file_not_found(local_storage):
    """Opening non-existent file raises error."""
    with pytest.raises(PathNotFoundError):
        local_storage.open_file("notexists.txt")


def test_local_write_file(local_storage):
    """Test write_file method."""
    chunks = [b"hello ", b"world"]
    local_storage.write_file("output.txt", iter(chunks))

    content = (Path(local_storage.root) / "output.txt").read_bytes()
    assert content == b"hello world"


def test_local_write_file_creates_parents(local_storage):
    """write_file creates parent directories."""
    chunks = [b"data"]
    local_storage.write_file("a/b/c/file.txt", iter(chunks))

    assert (Path(local_storage.root) / "a" / "b" / "c" / "file.txt").exists()


def test_local_mkdir(local_storage):
    """Test mkdir method."""
    local_storage.mkdir("newdir")
    assert (Path(local_storage.root) / "newdir").is_dir()


def test_local_mkdir_already_exists(local_storage):
    """mkdir raises error if path exists."""
    (Path(local_storage.root) / "existing").mkdir()

    with pytest.raises(PathExistsError):
        local_storage.mkdir("existing")


def test_local_delete_file(local_storage):
    """Test delete file."""
    (Path(local_storage.root) / "todelete.txt").write_text("x")

    local_storage.delete("todelete.txt")
    assert not (Path(local_storage.root) / "todelete.txt").exists()


def test_local_delete_dir(local_storage):
    """Test delete directory recursively."""
    (Path(local_storage.root) / "dir" / "subdir").mkdir(parents=True)
    (Path(local_storage.root) / "dir" / "file.txt").write_text("x")

    local_storage.delete("dir")
    assert not (Path(local_storage.root) / "dir").exists()


def test_local_delete_root_fails(local_storage):
    """Cannot delete root."""
    with pytest.raises(InvalidPathError):
        local_storage.delete("")


def test_local_rename(local_storage):
    """Test rename method."""
    (Path(local_storage.root) / "old.txt").write_text("x")

    local_storage.rename("old.txt", "new.txt")
    assert not (Path(local_storage.root) / "old.txt").exists()
    assert (Path(local_storage.root) / "new.txt").exists()


def test_local_copy_file(local_storage):
    """Test copy file."""
    (Path(local_storage.root) / "source.txt").write_text("content")
    (Path(local_storage.root) / "dest").mkdir()

    local_storage.copy("source.txt", "dest")
    assert (Path(local_storage.root) / "source.txt").exists()
    assert (Path(local_storage.root) / "dest" / "source.txt").read_text() == "content"


def test_local_copy_dir(local_storage):
    """Test copy directory."""
    (Path(local_storage.root) / "srcdir").mkdir()
    (Path(local_storage.root) / "srcdir" / "file.txt").write_text("x")
    (Path(local_storage.root) / "dest").mkdir()

    local_storage.copy("srcdir", "dest")
    assert (Path(local_storage.root) / "dest" / "srcdir" / "file.txt").exists()


def test_local_move_file(local_storage):
    """Test move file."""
    (Path(local_storage.root) / "tomove.txt").write_text("content")
    (Path(local_storage.root) / "dest").mkdir()

    local_storage.move("tomove.txt", "dest")
    assert not (Path(local_storage.root) / "tomove.txt").exists()
    assert (Path(local_storage.root) / "dest" / "tomove.txt").read_text() == "content"


def test_local_path_traversal_blocked(local_storage):
    """Path traversal attempts are blocked."""
    with pytest.raises(InvalidPathError):
        local_storage.list_dir("../..")

    with pytest.raises(InvalidPathError):
        local_storage.get_info("../../etc/passwd")

    with pytest.raises(InvalidPathError):
        local_storage.mkdir("../escape")


# =============================================================================
# S3Storage Tests
# =============================================================================


def test_s3_list_empty_dir(s3_storage):
    """List empty root directory."""
    items = s3_storage.list_dir("")
    assert items == []


def test_s3_list_dir_with_files(s3_storage):
    """List directory with files and folders."""
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="file.txt", Body=b"content")
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="folder/.dir", Body=b"")

    items = s3_storage.list_dir("")
    assert len(items) == 2

    names = {item.name for item in items}
    assert names == {"file.txt", "folder"}


def test_s3_get_info_file(s3_storage):
    """Get info for a file."""
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="test.txt", Body=b"hello")

    info = s3_storage.get_info("test.txt")
    assert info.name == "test.txt"
    assert info.is_dir is False
    assert info.size == 5


def test_s3_get_info_dir(s3_storage):
    """Get info for a directory (implicit via file)."""
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="mydir/file.txt", Body=b"x")

    info = s3_storage.get_info("mydir")
    assert info.name == "mydir"
    assert info.is_dir is True
    assert info.size is None


def test_s3_exists(s3_storage):
    """Test exists method."""
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="exists.txt", Body=b"x")

    assert s3_storage.exists("exists.txt") is True
    assert s3_storage.exists("notexists.txt") is False


def test_s3_is_dir(s3_storage):
    """Test is_dir method."""
    assert s3_storage.is_dir("folder") is True
    assert s3_storage.is_dir("file.txt") is True
    assert s3_storage.is_dir("notexists") is True
    assert s3_storage.is_dir("") is True
    assert s3_storage.is_dir("..") is True


def test_s3_is_file(s3_storage):
    """Test is_file method."""
    s3_storage.s3.put_object(
        Bucket=s3_storage.bucket, Key="folder/dummy.txt", Body=b"x"
    )
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="file.txt", Body=b"x")

    assert s3_storage.is_file("file.txt") is True
    assert s3_storage.is_file("folder") is False
    assert s3_storage.is_file("notexists") is False


def test_s3_open_file(s3_storage):
    """Test open_file method."""
    s3_storage.s3.put_object(
        Bucket=s3_storage.bucket, Key="data.txt", Body=b"binary data"
    )

    file_obj, etag, size = s3_storage.open_file("data.txt")
    content = file_obj.read()
    assert content == b"binary data"
    assert etag is not None
    assert size == 11


def test_s3_open_file_not_found(s3_storage):
    """Opening non-existent file raises error."""
    with pytest.raises(PathNotFoundError):
        s3_storage.open_file("notexists.txt")


def test_s3_write_file(s3_storage):
    """Test write_file method."""
    chunks = [b"hello ", b"world"]
    s3_storage.write_file("output.txt", iter(chunks))

    response = s3_storage.s3.get_object(Bucket=s3_storage.bucket, Key="output.txt")
    assert response["Body"].read() == b"hello world"


def test_s3_mkdir(s3_storage):
    """Test mkdir method (no-op for S3, directories are implicit)."""
    s3_storage.mkdir("newdir")
    assert s3_storage.is_dir("newdir") is True


def test_s3_mkdir_file_collision(s3_storage):
    """mkdir raises error if a file with that name exists."""
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="existing", Body=b"x")

    with pytest.raises(PathExistsError):
        s3_storage.mkdir("existing")


def test_s3_delete_file(s3_storage):
    """Test delete file."""
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="todelete.txt", Body=b"x")

    s3_storage.delete("todelete.txt")
    assert not s3_storage.exists("todelete.txt")


def test_s3_delete_dir(s3_storage):
    """Test delete directory recursively."""
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="dir/file.txt", Body=b"x")
    s3_storage.s3.put_object(
        Bucket=s3_storage.bucket, Key="dir/subdir/file2.txt", Body=b"y"
    )

    s3_storage.delete("dir")
    assert not s3_storage.exists("dir")
    assert not s3_storage.exists("dir/file.txt")


def test_s3_delete_root_fails(s3_storage):
    """Cannot delete root."""
    with pytest.raises(InvalidPathError):
        s3_storage.delete("")


def test_s3_rename_file(s3_storage):
    """Test rename file."""
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="old.txt", Body=b"content")

    s3_storage.rename("old.txt", "new.txt")
    assert not s3_storage.exists("old.txt")
    assert s3_storage.exists("new.txt")


def test_s3_rename_dir(s3_storage):
    """Test rename directory."""
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="olddir/file.txt", Body=b"x")

    s3_storage.rename("olddir", "newdir")
    assert not s3_storage.exists("olddir")
    assert s3_storage.exists("newdir")
    assert s3_storage.exists("newdir/file.txt")


def test_s3_copy_file(s3_storage):
    """Test copy file to non-existent directory."""
    s3_storage.s3.put_object(
        Bucket=s3_storage.bucket, Key="source.txt", Body=b"content"
    )

    s3_storage.copy("source.txt", "newdir")
    assert s3_storage.exists("source.txt")
    assert s3_storage.exists("newdir/source.txt")


def test_s3_copy_dir(s3_storage):
    """Test copy directory to non-existent directory."""
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="srcdir/file.txt", Body=b"x")

    s3_storage.copy("srcdir", "newdir")
    assert s3_storage.exists("srcdir/file.txt")
    assert s3_storage.exists("newdir/srcdir/file.txt")


def test_s3_move_file(s3_storage):
    """Test move file to non-existent directory."""
    s3_storage.s3.put_object(
        Bucket=s3_storage.bucket, Key="tomove.txt", Body=b"content"
    )

    s3_storage.move("tomove.txt", "newdir")
    assert not s3_storage.exists("tomove.txt")
    assert s3_storage.exists("newdir/tomove.txt")


def test_s3_copy_to_file_fails(s3_storage):
    """Cannot copy to a path that is a file."""
    s3_storage.s3.put_object(
        Bucket=s3_storage.bucket, Key="source.txt", Body=b"content"
    )
    s3_storage.s3.put_object(Bucket=s3_storage.bucket, Key="dest", Body=b"a file")

    with pytest.raises(NotADirectoryError):
        s3_storage.copy("source.txt", "dest")


def test_s3_with_prefix(s3_storage_with_prefix):
    """Test S3Storage with prefix."""
    storage = s3_storage_with_prefix

    storage.write_file("test.txt", iter([b"hello"]))

    response = storage.s3.get_object(Bucket=storage.bucket, Key="myprefix/test.txt")
    assert response["Body"].read() == b"hello"

    assert storage.exists("test.txt")
    assert storage.is_file("test.txt")


def test_s3_implicit_directory(s3_storage):
    """Directories are implicitly created when files are uploaded."""
    s3_storage.write_file("a/b/c/file.txt", iter([b"content"]))

    assert s3_storage.is_dir("a")
    assert s3_storage.is_dir("a/b")
    assert s3_storage.is_dir("a/b/c")
    assert s3_storage.is_file("a/b/c/file.txt")


def test_s3_file_and_directory_same_name(s3_storage):
    """S3 allows a file and directory to have the same name."""
    s3_storage.s3.put_object(
        Bucket=s3_storage.bucket, Key="aaa/a.txt", Body=b"file content"
    )
    s3_storage.s3.put_object(
        Bucket=s3_storage.bucket, Key="aaa/a.txt/bbb/c.txt", Body=b"nested content"
    )

    assert s3_storage.is_file("aaa/a.txt") is True
    assert s3_storage.is_dir("aaa/a.txt") is True
    assert s3_storage.exists("aaa/a.txt") is True

    items = s3_storage.list_dir("aaa")
    names_and_types = [(item.name, item.is_dir) for item in items]
    assert ("a.txt", False) in names_and_types
    assert ("a.txt", True) in names_and_types

    nested_items = s3_storage.list_dir("aaa/a.txt")
    nested_names = [item.name for item in nested_items]
    assert "bbb" in nested_names


# =============================================================================
# parse_s3_path Tests
# =============================================================================


def test_parse_bucket_only():
    bucket, prefix = parse_s3_path("s3://mybucket")
    assert bucket == "mybucket"
    assert prefix == ""


def test_parse_bucket_with_prefix():
    bucket, prefix = parse_s3_path("s3://mybucket/some/prefix")
    assert bucket == "mybucket"
    assert prefix == "some/prefix"


def test_parse_invalid_path():
    with pytest.raises(ValueError):
        parse_s3_path("/local/path")


# =============================================================================
# list_s3_buckets Tests
# =============================================================================


def test_list_buckets_empty():
    """List buckets when no buckets exist."""
    with mock_aws():
        s3_client = boto3.client("s3", region_name="us-east-1")
        buckets = list_s3_buckets(s3_client=s3_client)
        assert buckets == []


def test_list_buckets_single():
    """List buckets with a single bucket."""
    with mock_aws():
        s3_client = boto3.client("s3", region_name="us-east-1")
        s3_client.create_bucket(Bucket="my-bucket")

        buckets = list_s3_buckets(s3_client=s3_client)
        assert buckets == ["my-bucket"]


def test_list_buckets_multiple():
    """List buckets with multiple buckets."""
    with mock_aws():
        s3_client = boto3.client("s3", region_name="us-east-1")
        s3_client.create_bucket(Bucket="bucket-a")
        s3_client.create_bucket(Bucket="bucket-b")
        s3_client.create_bucket(Bucket="bucket-c")

        buckets = list_s3_buckets(s3_client=s3_client)
        assert set(buckets) == {"bucket-a", "bucket-b", "bucket-c"}


# =============================================================================
# Adhoc Mode Tests
# =============================================================================


def test_is_s3_bucket_list_mode():
    """Test S3 bucket list mode detection."""
    assert is_s3_bucket_list_mode("s3://") is True
    assert is_s3_bucket_list_mode("s3:") is True
    assert is_s3_bucket_list_mode("s3://bucket") is False
    assert is_s3_bucket_list_mode("s3://bucket/prefix") is False
    assert is_s3_bucket_list_mode("/local/path") is False


def test_sanitize_bucket_name():
    """Test bucket name sanitization for Django slug compatibility."""
    assert sanitize_bucket_name("my-bucket") == "my-bucket_a483e74c"
    assert sanitize_bucket_name("my.bucket.name") == "mybucketname_2c8b40a2"


# =============================================================================
# FILECHEST_MAX_DIR_ENTRIES Tests
# =============================================================================


def test_local_storage_respects_limit(settings):
    """LocalStorage.list_dir respects FILECHEST_MAX_DIR_ENTRIES."""
    settings.FILECHEST_MAX_DIR_ENTRIES = 5

    path = tempfile.mkdtemp()
    try:
        for i in range(10):
            (Path(path) / f"file{i:02d}.txt").write_text("x")

        storage = LocalStorage(path)
        items = storage.list_dir("")

        assert len(items) == 5
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_s3_storage_respects_limit(settings):
    """S3Storage.list_dir respects FILECHEST_MAX_DIR_ENTRIES."""
    settings.FILECHEST_MAX_DIR_ENTRIES = 5

    with mock_aws():
        s3_client = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket"
        s3_client.create_bucket(Bucket=bucket_name)

        for i in range(10):
            s3_client.put_object(Bucket=bucket_name, Key=f"file{i:02d}.txt", Body=b"x")

        storage = S3Storage(bucket_name, prefix="", s3_client=s3_client)
        items = storage.list_dir("")

        assert len(items) == 5


def test_s3_storage_limit_includes_dirs_and_files(settings):
    """S3Storage.list_dir limit applies to total of dirs and files."""
    settings.FILECHEST_MAX_DIR_ENTRIES = 5

    with mock_aws():
        s3_client = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket"
        s3_client.create_bucket(Bucket=bucket_name)

        for i in range(3):
            s3_client.put_object(Bucket=bucket_name, Key=f"dir{i}/.keep", Body=b"")
        for i in range(5):
            s3_client.put_object(Bucket=bucket_name, Key=f"file{i}.txt", Body=b"x")

        storage = S3Storage(bucket_name, prefix="", s3_client=s3_client)
        items = storage.list_dir("")

        assert len(items) == 5
