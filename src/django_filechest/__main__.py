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
from django.utils.text import slugify
from hashlib import sha256
from shutil import rmtree


def is_s3_bucket_list_mode(path: str) -> bool:
    """Check if the path requests S3 bucket listing mode."""
    return path in ("s3://", "s3:")


def sanitize_bucket_name(bucket_name: str) -> str:
    """Convert bucket name to a valid Django slug (replace dots with dashes)."""
    return slugify(bucket_name) + "_" + sha256(bucket_name.encode()).hexdigest()[:8]


parser = argparse.ArgumentParser(
    description="Start a file manager for a directory or S3 bucket",
    prog="filechest",
)
parser.add_argument(
    "path",
    help='Path to directory, S3 URL (s3://bucket/prefix), or "s3://" to list all buckets',
)
parser.add_argument(
    "-p",
    "--port",
    type=int,
    default=8000,
    help="Port to run the server on (default: 8000)",
)
parser.add_argument(
    "--no-browser",
    action="store_true",
    help="Do not open browser automatically",
)

parser.add_argument(
    "-g",
    "--gui",
    action="store_true",
    help="Open GUI window",
)


def main():
    args = parser.parse_args()

    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite3", prefix="filechest_")
    os.close(db_fd)
    atexit.register(lambda: os.unlink(db_path) if os.path.exists(db_path) else None)

    # Set up Django
    os.environ["FILECHEST_DB_PATH"] = db_path
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_filechest.settings_adhoc")

    import django

    django.setup()

    # Create tables
    from django.core.management import call_command

    call_command("migrate", "--run-syncdb", verbosity=0)

    from filechest.models import Volume

    # Validate path and create volumes
    path = args.path
    if is_s3_bucket_list_mode(path) or path.startswith("s3://"):
        # S3 mode - create volumes for all accessible buckets
        from filechest.storage import list_s3_buckets, parse_s3_path

        try:
            buckets = list_s3_buckets()
        except Exception as e:
            print(f"Error listing S3 buckets: {e}", file=sys.stderr)
            sys.exit(1)

        if not buckets:
            print("No S3 buckets found", file=sys.stderr)
            sys.exit(1)

        # Create a volume for each bucket
        for bucket_name in buckets:
            Volume.objects.create(
                name=sanitize_bucket_name(bucket_name),
                verbose_name=bucket_name,
                path=f"s3://{bucket_name}",
                is_active=True,
                public_read=True,
            )

        # Determine which page to open
        if is_s3_bucket_list_mode(path):
            # Open home page showing all buckets
            page = ""
            url = f"http://127.0.0.1:{args.port}/"
            display_path = "S3 (all buckets)"
        else:
            # Open the specified bucket (with optional prefix as subpath)
            target_bucket, prefix = parse_s3_path(path)
            volume_name = sanitize_bucket_name(target_bucket)

            if target_bucket not in buckets:
                print(
                    f"Error: Bucket '{target_bucket}' not found or not accessible",
                    file=sys.stderr,
                )
                sys.exit(1)

            if prefix:
                page = f"{volume_name}/browse/{prefix}/"
            else:
                page = f"{volume_name}/"
                url = f"http://127.0.0.1:{args.port}/{volume_name}/"
            display_path = path

    else:
        # Local path - resolve and validate
        path = str(Path(path).resolve())
        if not Path(path).is_dir():
            print(f"Error: '{path}' is not a directory", file=sys.stderr)
            sys.exit(1)
        volume_name = "local"
        verbose_name = Path(path).name or path
        Volume.objects.create(
            name=volume_name,
            verbose_name=verbose_name,
            path=path,
            is_active=True,
            public_read=True,
        )
        page = f"{volume_name}/"
        url = f"http://127.0.0.1:{args.port}/{volume_name}/"
        display_path = path

    if args.gui:
        import webview
        from django_filechest import wsgi

        cwd = Path(".").resolve()

        config = f"""
        XDG_DESKTOP_DIR="{cwd}"
        XDG_DOWNLOAD_DIR="{cwd}"
        XDG_DOCUMENTS_DIR="{cwd}"
        XDG_MUSIC_DIR="{cwd}"
        XDG_PICTURES_DIR="{cwd}"
        XDG_PUBLICSHARE_DIR="{cwd}"
        XDG_TEMPLATES_DIR="{cwd}"
        XDG_VIDEOS_DIR="{cwd}"
        """

        cfg = Path(tempfile.mkdtemp())
        try:
            (cfg / "user-dirs.dirs").write_text(config)
            os.environ["XDG_CONFIG_HOME"] = str(cfg)

            def on_start(window):
                window.load_url(f"/{page}")

            webview.settings["ALLOW_DOWNLOADS"] = True
            webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True

            window = webview.create_window(
                f"FileChest - {display_path}", wsgi.application, text_select=True
            )
            webview.start(on_start, window)
        finally:
            rmtree(cfg)

    else:
        # Open browser after a short delay
        url = f"http://127.0.0.1:{args.port}/{page}"
        if not args.no_browser:

            def open_browser():
                time.sleep(1.0)
                webbrowser.open(url)

            threading.Thread(target=open_browser, daemon=True).start()

        print(f"\nStarting FileChest for: {display_path}")
        print(f"Open your browser at: {url}")
        print("Press Ctrl+C to stop\n")

        # Run the development server
        from django.core.management import execute_from_command_line

        execute_from_command_line(
            ["manage.py", "runserver", str(args.port), "--noreload"]
        )


if __name__ == "__main__":
    main()
