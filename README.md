# Filechest

A simple file manager for Django with S3 support.

## Overview

FileChest is a TinyFileManager-like web-based file manager that can be:

- **Integrated as a Django app** - Add file management to your existing Django project
- **Run standalone (adhoc mode)** - Quickly browse any local directory or S3 bucket

## Quick Start (Adhoc Mode)

Run FileChest for any local directory without configuration:

```bash
uvx filechest /path/to/directory
```

Or for an S3 bucket:

```bash
uvx filechest s3://bucket-name/prefix
```

This starts a web server and opens your browser automatically.

### Features

- File/folder listing
- S3 bucket support
- Upload files (drag & drop supported)
- Download files
- Create, rename, delete files and folders
- Copy and move files between directories
- Preview images, videos, audio, PDF, and text files
- Access control (viewer/editor)


## Installation

```bash
git clone https://github.com/atsuoishimoto/filechest.git
cd filechest
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Open http://127.0.0.1:8000/admin/ and configure via Django admin:

- **Filechest > Volumes**: Add directories or S3 URLs to manage
- **Filechest > Volume permissions**: Assign users access to volumes

### Access Control

| User Type | Condition | Access Level |
|-----------|-----------|--------------|
| Superuser | Always | Editor |
| Authenticated | Has VolumePermission with role=editor | Editor |
| Authenticated | Has VolumePermission with role=viewer | Viewer |
| Authenticated | No permission, public_read=True | Viewer |
| Authenticated | No permission, public_read=False | No access |
| Anonymous | public_read=True | Viewer |
| Anonymous | public_read=False | No access |

## Configuration

### Volume Settings

| Field | Description |
|-------|-------------|
| `name` | URL-safe identifier (slug) |
| `verbose_name` | Display name shown in UI |
| `path` | Local filesystem path or S3 URL (`s3://bucket/prefix`) |
| `public_read` | Allow anonymous read access |
| `max_file_size` | Maximum upload size in bytes (default: 10MB) |
| `is_active` | Enable/disable the volume |

### S3 Configuration

For S3 volumes, configure AWS credentials via environment variables:

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_DEFAULT_REGION=us-east-1
```

Or use IAM roles when running on AWS infrastructure.

## License

MIT License

## Links

- GitHub: https://github.com/atsuoishimoto/filechest
- Issues: https://github.com/atsuoishimoto/filechest/issues

