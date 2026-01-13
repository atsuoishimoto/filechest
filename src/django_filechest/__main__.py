#!/usr/bin/env python
"""
Entry point for standalone django-filechest usage.

Usage:
    uvx django-filechest /path/to/directory
    uvx django-filechest s3://bucket/prefix
    uvx django-filechest s3://  # List all buckets
    python -m django_filechest /path/to/directory
"""

import argparse
import atexit
import os
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path


def is_s3_bucket_list_mode(path: str) -> bool:
    """Check if the path requests S3 bucket listing mode."""
    return path in ('s3://', 's3:', 's3')


def sanitize_bucket_name(bucket_name: str) -> str:
    """Convert bucket name to a valid Django slug (replace dots with dashes)."""
    return bucket_name.replace('.', '-')


def main():
    parser = argparse.ArgumentParser(
        description='Start a file manager for a directory or S3 bucket',
        prog='django-filechest',
    )
    parser.add_argument(
        'path',
        help='Path to directory, S3 URL (s3://bucket/prefix), or "s3://" to list all buckets',
    )
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=8000,
        help='Port to run the server on (default: 8000)',
    )
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not open browser automatically',
    )

    args = parser.parse_args()

    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix='.sqlite3', prefix='filechest_')
    os.close(db_fd)
    atexit.register(lambda: os.unlink(db_path) if os.path.exists(db_path) else None)

    # Set up Django
    os.environ['FILECHEST_DB_PATH'] = db_path
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_filechest.settings_adhoc')

    import django
    django.setup()

    # Create tables
    from django.core.management import call_command
    call_command('migrate', '--run-syncdb', verbosity=0)

    from filechest.models import Volume

    # Validate path and create volumes
    path = args.path
    if is_s3_bucket_list_mode(path):
        # S3 bucket listing mode - create a volume for each bucket
        from filechest.storage import list_s3_buckets
        try:
            buckets = list_s3_buckets()
        except Exception as e:
            print(f"Error listing S3 buckets: {e}", file=sys.stderr)
            sys.exit(1)

        if not buckets:
            print("No S3 buckets found", file=sys.stderr)
            sys.exit(1)

        for bucket_name in buckets:
            Volume.objects.create(
                name=sanitize_bucket_name(bucket_name),
                verbose_name=bucket_name,
                path=f's3://{bucket_name}',
                is_active=True,
                public_read=True,
            )

        url = f'http://127.0.0.1:{args.port}/'
        display_path = 'S3 (all buckets)'

    elif path.startswith('s3://'):
        # Single S3 bucket/prefix
        volume_name = 's3'
        verbose_name = path
        Volume.objects.create(
            name=volume_name,
            verbose_name=verbose_name,
            path=path,
            is_active=True,
            public_read=True,
        )
        url = f'http://127.0.0.1:{args.port}/{volume_name}/'
        display_path = path

    else:
        # Local path - resolve and validate
        path = str(Path(path).resolve())
        if not Path(path).is_dir():
            print(f"Error: '{path}' is not a directory", file=sys.stderr)
            sys.exit(1)
        volume_name = 'local'
        verbose_name = Path(path).name or path
        Volume.objects.create(
            name=volume_name,
            verbose_name=verbose_name,
            path=path,
            is_active=True,
            public_read=True,
        )
        url = f'http://127.0.0.1:{args.port}/{volume_name}/'
        display_path = path

    # Open browser after a short delay
    if not args.no_browser:
        def open_browser():
            time.sleep(1.0)
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    print(f'\nStarting FileChest for: {display_path}')
    print(f'Open your browser at: {url}')
    print('Press Ctrl+C to stop\n')

    # Run the development server
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', 'runserver', str(args.port), '--noreload'])


if __name__ == '__main__':
    main()
