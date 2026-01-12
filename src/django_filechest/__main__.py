#!/usr/bin/env python
"""
Entry point for standalone django-filechest usage.

Usage:
    uvx django-filechest /path/to/directory
    uvx django-filechest s3://bucket/prefix
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


def main():
    parser = argparse.ArgumentParser(
        description='Start a file manager for a directory or S3 bucket',
        prog='django-filechest',
    )
    parser.add_argument(
        'path',
        help='Path to directory or S3 URL (s3://bucket/prefix)',
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

    # Validate path
    path = args.path
    if path.startswith('s3://'):
        # S3 path - will be validated when accessed
        volume_name = 's3'
        verbose_name = path
    else:
        # Local path - resolve and validate
        path = str(Path(path).resolve())
        if not Path(path).is_dir():
            print(f"Error: '{path}' is not a directory", file=sys.stderr)
            sys.exit(1)
        volume_name = 'local'
        verbose_name = Path(path).name or path

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

    # Create temporary volume
    from filechest.models import Volume
    Volume.objects.create(
        name=volume_name,
        verbose_name=verbose_name,
        path=path,
        is_active=True,
        public_read=True,
    )

    url = f'http://127.0.0.1:{args.port}/{volume_name}/'

    # Open browser after a short delay
    if not args.no_browser:
        def open_browser():
            time.sleep(1.0)
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    print(f'\nStarting FileChest for: {path}')
    print(f'Open your browser at: {url}')
    print('Press Ctrl+C to stop\n')

    # Run the development server
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', 'runserver', str(args.port), '--noreload'])


if __name__ == '__main__':
    main()
