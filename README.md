# FileChest

A zero-configuration file browser for local directories and Amazon S3, built with Python/Django.

```bash
uvx filechest /path/to/directory
uvx filechest s3://bucket-name/prefix
```

No setup required. Just run the command and start browsing.

## Features

- Browse local directories and S3 buckets
- Upload files (drag & drop supported)
- Download files
- Create, rename, delete files and folders
- Copy and move files between directories
- Preview images, videos, audio, PDF, and text files
- List/Grid view toggle

## Installation

We recommend using [uv](https://docs.astral.sh/uv/) for the best experience. See [Installing uv](https://docs.astral.sh/uv/getting-started/installation/) for setup instructions.

```bash
# Using uvx (recommended, no installation needed)
uvx filechest /path/to/directory

# Or install globally with pipx
pipx install filechest
```

## Usage

Browse a local directory:

```bash
filechest /path/to/directory
```

Browse an S3 bucket:

```bash
filechest s3://bucket-name/prefix
```

List all accessible S3 buckets:

```bash
filechest s3://
```

The command starts a web server and opens your browser automatically.

### Command Line Options

```
usage: filechest [-h] [-p PORT] [--no-browser] [-g] [-a AWS_PROFILE] path

Start a file manager for a directory or S3 bucket

positional arguments:
  path                  Path to directory, S3 URL (s3://bucket/prefix), or "s3://" to list all buckets

options:
  -h, --help            show this help message and exit
  -p, --port PORT       Port to run the server on (default: 8000)
  --no-browser          Do not open browser automatically
  -g, --gui             Open GUI window (Experimental)
  -a, --aws-profile AWS_PROFILE
                        AWS profile name to use (sets AWS_PROFILE environment variable)
```

### S3 Configuration

FileChest uses your existing AWS credentials. Configure them using the AWS CLI:

```bash
# Standard credentials
aws configure

# SSO authentication
aws sso configure
```

Or set environment variables directly:

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_DEFAULT_REGION=us-east-1
```

Use the `-a` option to specify a named profile:

```bash
filechest -a my-profile s3://bucket-name
```

---

## Using as a Django Application

FileChest is also available as a reusable Django app for building web-based file management systems. When used as a Django app, you can:

- Register multiple directories and S3 buckets as "Volumes"
- Control user access with role-based permissions (viewer/editor)
- Enable public read access for specific volumes

### Setup

```bash
git clone https://github.com/atsuoishimoto/django-filechest.git
cd django-filechest
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Open http://127.0.0.1:8000/admin/ and configure via Django admin:

- **Filechest > Volumes**: Add directories or S3 URLs to manage
- **Filechest > Volume permissions**: Assign users access to volumes

### Volume Settings

| Field | Description |
|-------|-------------|
| `name` | URL-safe identifier (slug) |
| `verbose_name` | Display name shown in UI |
| `path` | Local filesystem path or S3 URL (`s3://bucket/prefix`) |
| `public_read` | Allow anonymous read access |
| `max_file_size` | Maximum upload size in bytes (default: 10MB) |
| `is_active` | Enable/disable the volume |

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

---

## License

MIT License

## Links

- GitHub: https://github.com/atsuoishimoto/django-filechest
- Issues: https://github.com/atsuoishimoto/django-filechest/issues
