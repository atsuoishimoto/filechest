"""
Storage backends for FileChest.

This module provides an abstraction layer for file operations,
allowing different storage backends (local filesystem, S3, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO, Iterator
import hashlib
import shutil


@lru_cache(maxsize=1000)
def _compute_file_sha256(path: str, mtime: float) -> str:
    """
    Compute SHA256 hash of a file. Cached by path and mtime.

    Args:
        path: Absolute file path
        mtime: File modification time (used for cache invalidation)

    Returns:
        ETag string in the format '"<sha256>"'
    """
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return f'"{sha256.hexdigest()}"'


@dataclass
class FileInfo:
    """Information about a file or directory."""

    name: str
    is_dir: bool
    size: int | None  # None for directories
    modified: float  # Unix timestamp


class StorageError(Exception):
    """Base exception for storage operations."""

    def __init__(self, message: str, path: str = ""):
        super().__init__(message)
        self.path = path
        self.message = message

    def __str__(self):
        if self.path:
            return f"{self.message}: {self.path}"
        return self.message


class PathNotFoundError(StorageError):
    """Raised when a path does not exist."""

    pass


class PathExistsError(StorageError):
    """Raised when a path already exists."""

    pass


class PermissionDeniedError(StorageError):
    """Raised when permission is denied."""

    pass


class InvalidPathError(StorageError):
    """Raised when a path is invalid (e.g., path traversal attempt)."""

    pass


class NotADirectoryError(StorageError):
    """Raised when a directory operation is attempted on a file."""

    pass


class NotAFileError(StorageError):
    """Raised when a file operation is attempted on a directory."""

    pass


class BaseStorage(ABC):
    """Abstract base class for storage backends."""

    def normalize_path(self, path: str) -> str:
        """
        Normalize path for this storage backend.

        Default implementation returns the path unchanged.
        Subclasses may override to handle platform-specific path separators.
        """
        return path

    def validate_name(self, name: str) -> str | None:
        """
        Validate file/folder name.

        Returns error message if invalid, None if valid.
        """
        if not name:
            return "Name is required"
        if "/" in name or "\\" in name:
            return "Name cannot contain slashes"
        if name in (".", ".."):
            return "Invalid name"
        if name.startswith("."):
            return "Name cannot start with a dot"
        return None

    @abstractmethod
    def list_dir(self, path: str) -> list[FileInfo]:
        """
        List contents of a directory.

        Args:
            path: Path relative to storage root (empty string for root)

        Returns:
            List of FileInfo objects for each item in the directory

        Raises:
            PathNotFoundError: If path does not exist
            NotADirectoryError: If path is not a directory
            PermissionDeniedError: If permission is denied
        """
        pass

    @abstractmethod
    def get_info(self, path: str) -> FileInfo:
        """
        Get information about a file or directory.

        Args:
            path: Path relative to storage root

        Returns:
            FileInfo object

        Raises:
            PathNotFoundError: If path does not exist
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a path exists."""
        pass

    @abstractmethod
    def is_dir(self, path: str) -> bool:
        """Check if path is a directory. Returns False if path doesn't exist."""
        pass

    @abstractmethod
    def is_file(self, path: str) -> bool:
        """Check if path is a file. Returns False if path doesn't exist."""
        pass

    @abstractmethod
    def get_etag(self, path: str) -> str | None:
        """
        Get ETag for a file.

        Args:
            path: Path relative to storage root

        Returns:
            ETag string or None if not supported
        """
        pass

    @abstractmethod
    def open_file(self, path: str) -> tuple[BinaryIO, str | None, int]:
        """
        Open a file for reading.

        Args:
            path: Path relative to storage root

        Returns:
            Tuple of (file-like object, etag or None, file size in bytes)

        Raises:
            PathNotFoundError: If path does not exist
            NotAFileError: If path is not a file
            PermissionDeniedError: If permission is denied
        """
        pass

    @abstractmethod
    def write_file(self, path: str, content: Iterator[bytes]) -> None:
        """
        Write content to a file.

        Args:
            path: Path relative to storage root
            content: Iterator of bytes (chunks)

        Raises:
            PermissionDeniedError: If permission is denied
            InvalidPathError: If path is invalid
        """
        pass

    @abstractmethod
    def mkdir(self, path: str, parents: bool = False, exists_ok: bool = False) -> None:
        """
        Create a directory.

        Args:
            path: Path relative to storage root
            parents: If True, create parent directories as needed
            exists_ok: If True, don't raise error if directory already exists

        Raises:
            PathNotFoundError: If parent doesn't exist and parents=False
            PathExistsError: If path already exists and exists_ok=False
            PermissionDeniedError: If permission is denied
        """
        pass

    @abstractmethod
    def delete(self, path: str) -> None:
        """
        Delete a file or directory (recursively).

        Args:
            path: Path relative to storage root

        Raises:
            PathNotFoundError: If path does not exist
            PermissionDeniedError: If permission is denied
            InvalidPathError: If trying to delete root
        """
        pass

    @abstractmethod
    def rename(self, path: str, new_name: str) -> None:
        """
        Rename a file or directory.

        Args:
            path: Current path relative to storage root
            new_name: New name (not a path, just the name)

        Raises:
            PathNotFoundError: If path does not exist
            PathExistsError: If destination already exists
            PermissionDeniedError: If permission is denied
            InvalidPathError: If trying to rename root
        """
        pass

    @abstractmethod
    def copy(self, src_path: str, dest_dir: str) -> None:
        """
        Copy a file or directory to a destination directory.

        Args:
            src_path: Source path relative to storage root
            dest_dir: Destination directory path

        Raises:
            PathNotFoundError: If source or destination doesn't exist
            PathExistsError: If destination file/folder already exists
            NotADirectoryError: If dest_dir is not a directory
            PermissionDeniedError: If permission is denied
        """
        pass

    @abstractmethod
    def move(self, src_path: str, dest_dir: str) -> None:
        """
        Move a file or directory to a destination directory.

        Args:
            src_path: Source path relative to storage root
            dest_dir: Destination directory path

        Raises:
            PathNotFoundError: If source or destination doesn't exist
            PathExistsError: If destination file/folder already exists
            NotADirectoryError: If dest_dir is not a directory
            PermissionDeniedError: If permission is denied
            InvalidPathError: If trying to move root or move into itself
        """
        pass


class LocalStorage(BaseStorage):
    """Local filesystem storage backend."""

    def __init__(self, root_path: str):
        """
        Initialize local storage.

        Args:
            root_path: Absolute path to the storage root directory
        """
        self.root = Path(root_path).resolve()
        if not self.root.is_dir():
            raise ValueError(f"Root path is not a directory: {root_path}")

    def normalize_path(self, path: str) -> str:
        """Normalize path by converting backslashes to forward slashes."""
        return path.replace("\\", "/")

    def _resolve(self, path: str) -> Path:
        """
        Resolve a relative path to an absolute path within the root.

        Raises:
            InvalidPathError: If path contains path traversal attempts
        """
        if not path:
            return self.root

        # Check for path traversal attempts
        if ".." in path.split("/"):
            raise InvalidPathError("Invalid path", path)

        return self.root / path

    def list_dir(self, path: str) -> list[FileInfo]:
        from django.conf import settings

        max_entries = getattr(settings, "FILECHEST_MAX_DIR_ENTRIES", 1000)

        target = self._resolve(path)

        if not target.exists():
            raise PathNotFoundError("Path not found", path)

        if not target.is_dir():
            raise NotADirectoryError("Not a directory", path)

        items = []
        try:
            for entry in target.iterdir():
                if len(items) >= max_entries:
                    break
                stat = entry.stat()
                items.append(
                    FileInfo(
                        name=entry.name,
                        is_dir=entry.is_dir(),
                        size=stat.st_size if entry.is_file() else None,
                        modified=stat.st_mtime,
                    )
                )
        except PermissionError:
            raise PermissionDeniedError("Permission denied", path)

        return items

    def get_info(self, path: str) -> FileInfo:
        target = self._resolve(path)

        if not target.exists():
            raise PathNotFoundError("Path not found", path)

        stat = target.stat()
        return FileInfo(
            name=target.name,
            is_dir=target.is_dir(),
            size=stat.st_size if target.is_file() else None,
            modified=stat.st_mtime,
        )

    def exists(self, path: str) -> bool:
        try:
            return self._resolve(path).exists()
        except InvalidPathError:
            return False

    def is_dir(self, path: str) -> bool:
        try:
            return self._resolve(path).is_dir()
        except InvalidPathError:
            return False

    def is_file(self, path: str) -> bool:
        try:
            return self._resolve(path).is_file()
        except InvalidPathError:
            return False

    def get_etag(self, path: str) -> str | None:
        """Get ETag for a file using SHA256 hash."""
        target = self._resolve(path)

        if not target.is_file():
            return None

        try:
            mtime = target.stat().st_mtime
            return _compute_file_sha256(str(target), mtime)
        except (OSError, PermissionError):
            return None

    def open_file(self, path: str) -> tuple[BinaryIO, str | None, int]:
        target = self._resolve(path)

        if not target.exists():
            raise PathNotFoundError("Path not found", path)

        if not target.is_file():
            raise NotAFileError("Not a file", path)

        try:
            stat = target.stat()
            size = stat.st_size
            etag = _compute_file_sha256(str(target), stat.st_mtime)
            return open(target, "rb"), etag, size
        except PermissionError:
            raise PermissionDeniedError("Permission denied", path)

    def write_file(self, path: str, content: Iterator[bytes]) -> None:
        target = self._resolve(path)

        # Check if file already exists
        if target.exists():
            raise PathExistsError("File already exists", path)

        # Create parent directories if needed
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise PermissionDeniedError("Permission denied creating directory", path)

        try:
            with open(target, "wb") as f:
                for chunk in content:
                    f.write(chunk)
        except PermissionError:
            raise PermissionDeniedError("Permission denied", path)

    def mkdir(self, path: str, parents: bool = False, exists_ok: bool = False) -> None:
        target = self._resolve(path)

        if target.exists():
            if exists_ok and target.is_dir():
                return
            raise PathExistsError("Path already exists", path)

        try:
            target.mkdir(parents=parents, exist_ok=exists_ok)
        except FileNotFoundError:
            raise PathNotFoundError("Parent directory not found", path)
        except PermissionError:
            raise PermissionDeniedError("Permission denied", path)

    def delete(self, path: str) -> None:
        target = self._resolve(path)

        if target == self.root:
            raise InvalidPathError("Cannot delete root", "")

        if not target.exists():
            raise PathNotFoundError("Path not found", path)

        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        except PermissionError:
            raise PermissionDeniedError("Permission denied", path)

    def rename(self, path: str, new_name: str) -> None:
        target = self._resolve(path)

        if target == self.root:
            raise InvalidPathError("Cannot rename root", "")

        if not target.exists():
            raise PathNotFoundError("Path not found", path)

        dest = target.parent / new_name

        if dest.exists():
            raise PathExistsError("Destination already exists", new_name)

        try:
            target.rename(dest)
        except PermissionError:
            raise PermissionDeniedError("Permission denied", path)

    def copy(self, src_path: str, dest_dir: str) -> None:
        source = self._resolve(src_path)
        dest_parent = self._resolve(dest_dir)

        if not source.exists():
            raise PathNotFoundError("Source not found", src_path)

        if not dest_parent.exists():
            raise PathNotFoundError("Destination not found", dest_dir)

        if not dest_parent.is_dir():
            raise NotADirectoryError("Destination is not a directory", dest_dir)

        dest = dest_parent / source.name

        if dest.exists():
            raise PathExistsError("Destination already exists", source.name)

        try:
            if source.is_dir():
                shutil.copytree(source, dest)
            else:
                shutil.copy2(source, dest)
        except PermissionError:
            raise PermissionDeniedError("Permission denied", "")

    def move(self, src_path: str, dest_dir: str) -> None:
        source = self._resolve(src_path)
        dest_parent = self._resolve(dest_dir)

        if source == self.root:
            raise InvalidPathError("Cannot move root", "")

        if not source.exists():
            raise PathNotFoundError("Source not found", src_path)

        if not dest_parent.exists():
            raise PathNotFoundError("Destination not found", dest_dir)

        if not dest_parent.is_dir():
            raise NotADirectoryError("Destination is not a directory", dest_dir)

        dest = dest_parent / source.name

        if dest.exists():
            raise PathExistsError("Destination already exists", source.name)

        # Prevent moving a folder into itself
        if source.is_dir():
            try:
                dest_parent.relative_to(source)
                raise InvalidPathError("Cannot move folder into itself", src_path)
            except ValueError:
                pass  # Not a subdirectory, OK

        try:
            shutil.move(str(source), str(dest))
        except PermissionError:
            raise PermissionDeniedError("Permission denied", "")


class S3Storage(BaseStorage):
    """Amazon S3 storage backend.

    Directories are implicit - they exist when files exist under them.
    Empty directories are not supported.
    """

    def __init__(self, bucket: str, prefix: str = "", s3_client=None):
        """
        Initialize S3 storage.

        Args:
            bucket: S3 bucket name
            prefix: Optional prefix (folder) within the bucket
            s3_client: Optional boto3 S3 client (for testing with moto)
        """
        import boto3

        self.bucket = bucket
        self.prefix = prefix.strip("/") if prefix else ""
        self.s3 = s3_client or boto3.client("s3")

    def validate_name(self, name: str) -> str | None:
        """S3 allows any characters in object keys."""
        return None

    def _full_key(self, path: str) -> str:
        """Get full S3 key from relative path."""
        path = path.strip("/")
        if self.prefix:
            return f"{self.prefix}/{path}" if path else self.prefix
        return path

    def _list_objects(self, prefix: str, delimiter: str = "/") -> tuple[list, list]:
        """
        List objects with given prefix.
        Returns (files, directories) as lists of keys.
        """
        full_prefix = prefix
        if full_prefix and not full_prefix.endswith("/"):
            full_prefix += "/"

        paginator = self.s3.get_paginator("list_objects_v2")
        files = []
        dirs = []

        for page in paginator.paginate(
            Bucket=self.bucket, Prefix=full_prefix, Delimiter=delimiter
        ):
            # Files (objects)
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Skip the prefix itself
                if key == full_prefix:
                    continue
                files.append(obj)

            # Directories (common prefixes)
            for prefix_info in page.get("CommonPrefixes", []):
                dirs.append(prefix_info["Prefix"].rstrip("/"))

        return files, dirs

    def _object_exists(self, key: str) -> bool:
        """Check if an object exists in S3."""
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.s3.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def _dir_exists(self, path: str) -> bool:
        """Check if a directory exists (has any objects with this prefix)."""
        if not path:
            return True  # Root always exists

        key = self._full_key(path)
        prefix = key + "/" if not key.endswith("/") else key

        # Check if any objects exist with this prefix
        response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix, MaxKeys=1)
        return response.get("KeyCount", 0) > 0

    def list_dir(self, path: str) -> list[FileInfo]:
        from django.conf import settings

        max_entries = getattr(settings, "FILECHEST_MAX_DIR_ENTRIES", 1000)

        full_prefix = self._full_key(path)

        # Check if directory exists
        if path and not self._dir_exists(path):
            raise PathNotFoundError("Path not found", path)

        files, dirs = self._list_objects(full_prefix)

        items = []

        # Add directories
        for dir_key in dirs:
            if len(items) >= max_entries:
                break
            name = dir_key.split("/")[-1]
            if name:
                items.append(
                    FileInfo(
                        name=name,
                        is_dir=True,
                        size=None,
                        modified=0,  # S3 doesn't have directory timestamps
                    )
                )

        # Add files
        prefix_to_strip = full_prefix + "/" if full_prefix else ""
        for obj in files:
            if len(items) >= max_entries:
                break
            key = obj["Key"]
            name = key[len(prefix_to_strip) :] if prefix_to_strip else key
            # Skip nested files (should be handled by delimiter)
            if "/" in name:
                continue
            items.append(
                FileInfo(
                    name=name,
                    is_dir=False,
                    size=obj["Size"],
                    modified=obj["LastModified"].timestamp(),
                )
            )

        return items

    def get_info(self, path: str) -> FileInfo:
        if not path:
            raise PathNotFoundError("Cannot get info for root", "")

        key = self._full_key(path)
        name = path.split("/")[-1]

        # Check if it's a file
        try:
            response = self.s3.head_object(Bucket=self.bucket, Key=key)
            return FileInfo(
                name=name,
                is_dir=False,
                size=response["ContentLength"],
                modified=response["LastModified"].timestamp(),
            )
        except self.s3.exceptions.ClientError as e:
            if e.response["Error"]["Code"] != "404":
                raise

        # Check if it's a directory
        if self._dir_exists(path):
            return FileInfo(
                name=name,
                is_dir=True,
                size=None,
                modified=0,
            )

        raise PathNotFoundError("Path not found", path)

    def exists(self, path: str) -> bool:
        if not path:
            return True  # Root always exists

        key = self._full_key(path)

        # Check as file
        if self._object_exists(key):
            return True

        # Check as directory
        return self._dir_exists(path)

    def is_dir(self, path: str) -> bool:
        # In S3, directories are implicit and don't need to exist beforehand.
        # Files can be uploaded to any path, creating the directory structure.
        return True

    def is_file(self, path: str) -> bool:
        if not path:
            return False  # Root is not a file

        key = self._full_key(path)
        return self._object_exists(key)

    def get_etag(self, path: str) -> str | None:
        """Get ETag for a file using head_object."""
        if not path:
            return None
        key = self._full_key(path)
        try:
            response = self.s3.head_object(Bucket=self.bucket, Key=key)
            return response.get("ETag")
        except self.s3.exceptions.ClientError:
            return None

    def open_file(self, path: str) -> tuple[BinaryIO, str | None, int]:
        if not path:
            raise NotAFileError("Root is not a file", "")

        key = self._full_key(path)

        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            etag = response.get("ETag")
            size = response.get("ContentLength", 0)
            return response["Body"], etag, size
        except self.s3.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise PathNotFoundError("Path not found", path)
            raise

    def write_file(self, path: str, content: Iterator[bytes]) -> None:
        if not path:
            raise InvalidPathError("Cannot write to root", "")

        key = self._full_key(path)

        # Check if file already exists
        if self._object_exists(key):
            raise PathExistsError("File already exists", path)

        # Collect content into bytes
        data = b"".join(content)

        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)

    def mkdir(self, path: str, parents: bool = False, exists_ok: bool = False) -> None:
        """Create a directory (no-op for S3, directories are implicit)."""

        if not path:
            raise InvalidPathError("Cannot create root directory", "")

        # Check if a file with this exact name exists
        key = self._full_key(path)
        if self._object_exists(key):
            raise PathExistsError("Path already exists", path)

        # Check if directory already exists (only if exists_ok is False)
        if not exists_ok and self._dir_exists(path):
            raise PathExistsError("Path already exists", path)

        # For S3, directories are implicit - no action needed
        # The directory will "exist" once files are uploaded to it

    def delete(self, path: str) -> None:
        if not path:
            raise InvalidPathError("Cannot delete root", "")

        key = self._full_key(path)

        # Check if it's a file
        if self._object_exists(key):
            self.s3.delete_object(Bucket=self.bucket, Key=key)
            return

        # Check if it's a directory
        if not self._dir_exists(path):
            raise PathNotFoundError("Path not found", path)

        # Delete all objects with this prefix
        prefix = key + "/"
        paginator = self.s3.get_paginator("list_objects_v2")
        objects_to_delete = []

        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                objects_to_delete.append({"Key": obj["Key"]})

        if objects_to_delete:
            # Delete in batches of 1000 (S3 limit)
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i : i + 1000]
                self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": batch})

    def rename(self, path: str, new_name: str) -> None:
        if not path:
            raise InvalidPathError("Cannot rename root", "")

        if "/" in new_name:
            raise InvalidPathError("New name cannot contain slashes", new_name)

        # Build new path
        parts = path.split("/")
        parts[-1] = new_name
        new_path = "/".join(parts)

        if self.exists(new_path):
            raise PathExistsError("Destination already exists", new_name)

        old_key = self._full_key(path)
        new_key = self._full_key(new_path)

        # Check if it's a file
        if self._object_exists(old_key):
            # Copy then delete
            self.s3.copy_object(
                Bucket=self.bucket,
                CopySource={"Bucket": self.bucket, "Key": old_key},
                Key=new_key,
            )
            self.s3.delete_object(Bucket=self.bucket, Key=old_key)
            return

        # Check if it's a directory
        if not self._dir_exists(path):
            raise PathNotFoundError("Path not found", path)

        # Rename directory: copy all objects with new prefix, then delete old
        old_prefix = old_key + "/"
        new_prefix = new_key + "/"

        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=old_prefix):
            for obj in page.get("Contents", []):
                old_obj_key = obj["Key"]
                new_obj_key = new_prefix + old_obj_key[len(old_prefix) :]

                self.s3.copy_object(
                    Bucket=self.bucket,
                    CopySource={"Bucket": self.bucket, "Key": old_obj_key},
                    Key=new_obj_key,
                )
                self.s3.delete_object(Bucket=self.bucket, Key=old_obj_key)

    def copy(self, src_path: str, dest_dir: str) -> None:
        if not src_path:
            raise InvalidPathError("Cannot copy root", "")

        src_key = self._full_key(src_path)
        src_name = src_path.split("/")[-1]

        # Check destination is not a file (directories are implicit in S3)
        if self.is_file(dest_dir):
            raise NotADirectoryError("Destination is not a directory", dest_dir)

        dest_path = f"{dest_dir}/{src_name}".strip("/")
        dest_key = self._full_key(dest_path)

        if self.exists(dest_path):
            raise PathExistsError("Destination already exists", src_name)

        # Copy file
        if self._object_exists(src_key):
            self.s3.copy_object(
                Bucket=self.bucket,
                CopySource={"Bucket": self.bucket, "Key": src_key},
                Key=dest_key,
            )
            return

        # Copy directory
        if not self._dir_exists(src_path):
            raise PathNotFoundError("Source not found", src_path)

        src_prefix = src_key + "/"
        dest_prefix = dest_key + "/"

        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=src_prefix):
            for obj in page.get("Contents", []):
                old_obj_key = obj["Key"]
                new_obj_key = dest_prefix + old_obj_key[len(src_prefix) :]

                self.s3.copy_object(
                    Bucket=self.bucket,
                    CopySource={"Bucket": self.bucket, "Key": old_obj_key},
                    Key=new_obj_key,
                )

    def move(self, src_path: str, dest_dir: str) -> None:
        if not src_path:
            raise InvalidPathError("Cannot move root", "")

        # Check for moving into itself
        if dest_dir.startswith(src_path + "/"):
            raise InvalidPathError("Cannot move folder into itself", src_path)

        src_name = src_path.split("/")[-1]
        dest_path = f"{dest_dir}/{src_name}".strip("/")

        # Check destination is not a file (directories are implicit in S3)
        if self.is_file(dest_dir):
            raise NotADirectoryError("Destination is not a directory", dest_dir)

        if self.exists(dest_path):
            raise PathExistsError("Destination already exists", src_name)

        # Copy then delete
        self.copy(src_path, dest_dir)
        self.delete(src_path)


def parse_s3_path(path: str) -> tuple[str, str]:
    """
    Parse an S3 path into bucket and prefix.

    Args:
        path: S3 path in format "s3://bucket/prefix"

    Returns:
        Tuple of (bucket, prefix)
    """
    if not path.startswith("s3://"):
        raise ValueError(f"Invalid S3 path: {path}")

    path = path[5:]  # Remove "s3://"
    parts = path.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    return bucket, prefix


def list_s3_buckets(s3_client=None) -> list[str]:
    """
    List all S3 buckets accessible to the current user.

    Args:
        s3_client: Optional boto3 S3 client (for testing)

    Returns:
        List of bucket names
    """
    import boto3

    if s3_client is None:
        s3_client = boto3.client("s3")

    response = s3_client.list_buckets()
    return [bucket["Name"] for bucket in response.get("Buckets", [])]


def get_storage(volume) -> BaseStorage:
    """
    Get the appropriate storage backend for a volume.

    Args:
        volume: Volume model instance

    Returns:
        Storage backend instance
    """
    if volume.path.startswith("s3://"):
        bucket, prefix = parse_s3_path(volume.path)
        return S3Storage(bucket, prefix)
    else:
        return LocalStorage(volume.path)
