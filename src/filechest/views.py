import json
import mimetypes
import secrets
from pathlib import Path

from django.http import (
    JsonResponse,
    HttpResponse,
    HttpResponseNotModified,
    Http404,
    HttpResponseForbidden,
    StreamingHttpResponse,
)
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.contrib.auth import logout
from django.conf import settings as django_settings

from .models import Volume, Role
from .permissions import get_user_role, can_view, can_edit
from .storage import (
    get_storage,
    StorageError,
    PathNotFoundError,
    PathExistsError,
    PermissionDeniedError,
    InvalidPathError,
    NotAFileError,
)

# Session key generated at server startup for sessionStorage namespacing
SESSION_STORAGE_KEY = secrets.token_hex(8)


def get_volume_and_check_edit(
    request, volume_name: str
) -> tuple[Volume, None] | tuple[None, JsonResponse]:
    """Get volume and check edit permission. Returns (volume, None) or (None, error_response)."""
    volume = get_object_or_404(Volume, name=volume_name, is_active=True)
    if not can_edit(request.user, volume):
        return None, JsonResponse({"error": "Permission denied"}, status=403)
    return volume, None


# =============================================================================
# UI Views
# =============================================================================


@require_GET
@never_cache
def home(request):
    """Home page showing available volumes."""
    all_volumes = Volume.objects.filter(is_active=True)
    available_volumes = []

    for volume in all_volumes:
        role = get_user_role(request.user, volume)
        if role:
            available_volumes.append(
                {
                    "volume": volume,
                    "role": role,
                }
            )

    context = {
        "volumes": available_volumes,
        "adhoc_mode": getattr(django_settings, "FILECHEST_ADHOC_MODE", False),
    }
    return render(request, "filechest/home.html", context)


def logoutpage(request):
    logout(request)
    return redirect("filechest:home")


@require_GET
@ensure_csrf_cookie
@never_cache
def index(request, volume_name: str, subpath: str = ""):
    """Main file manager UI."""
    volume = get_object_or_404(Volume, name=volume_name, is_active=True)
    role = get_user_role(request.user, volume)

    if not role:
        return HttpResponseForbidden("Access denied")

    storage = get_storage(volume)

    try:
        if not storage.is_dir(subpath):
            raise Http404("Not a directory")

        file_list = storage.list_dir(subpath)
    except PathNotFoundError:
        raise Http404("Path not found")
    except PermissionDeniedError:
        return HttpResponseForbidden("Permission denied")

    # Convert to dict format for template
    items = [
        {
            "name": f.name,
            "is_dir": f.is_dir,
            "size": f.size,
            "modified": f.modified,
        }
        for f in file_list
    ]

    # Sort: directories first, then by name
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

    # Build breadcrumb
    breadcrumb = []
    if subpath:
        parts = subpath.strip("/").split("/")
        for i, part in enumerate(parts):
            breadcrumb.append(
                {
                    "name": part,
                    "path": "/".join(parts[: i + 1]),
                }
            )

    # Get available volumes for the user
    all_volumes = Volume.objects.filter(is_active=True)
    available_volumes = [v for v in all_volumes if get_user_role(request.user, v)]

    context = {
        "volume": volume,
        "subpath": subpath,
        "breadcrumb": breadcrumb,
        "items": items,
        "role": role,
        "can_edit": role == Role.EDITOR,
        "available_volumes": available_volumes,
        "adhoc_mode": getattr(django_settings, "FILECHEST_ADHOC_MODE", False),
        "session_storage_key": SESSION_STORAGE_KEY,
    }
    try:
        return render(request, "filechest/index.html", context)
    except Exception:
        import traceback

        traceback.print_exc()
        raise


@require_GET
@never_cache
def preview(request, volume_name: str, filepath: str):
    """File preview page."""
    volume = get_object_or_404(Volume, name=volume_name, is_active=True)
    role = get_user_role(request.user, volume)

    if not role:
        return HttpResponseForbidden("Access denied")

    storage = get_storage(volume)

    try:
        if not storage.is_file(filepath):
            raise Http404("Not a file")

        file_info = storage.get_info(filepath)
    except PathNotFoundError:
        raise Http404("Path not found")

    # Get file extension
    suffix = Path(filepath).suffix.lower()

    # Determine preview type
    preview_type = get_preview_type(suffix)

    # Build breadcrumb (directory path)
    breadcrumb = []
    parts = filepath.strip("/").split("/")
    dir_parts = parts[:-1]  # Exclude filename
    for i, part in enumerate(dir_parts):
        breadcrumb.append(
            {
                "name": part,
                "path": "/".join(dir_parts[: i + 1]),
            }
        )

    # Parent directory path for "back" button
    parent_path = "/".join(dir_parts) if dir_parts else ""

    from django.conf import settings as django_settings

    context = {
        "volume": volume,
        "filepath": filepath,
        "filename": file_info.name,
        "file_size": file_info.size,
        "file_modified": file_info.modified,
        "preview_type": preview_type,
        "mime_type": get_mime_type(suffix),
        "breadcrumb": breadcrumb,
        "parent_path": parent_path,
        "role": role,
        "can_edit": role == Role.EDITOR,
        "adhoc_mode": getattr(django_settings, "FILECHEST_ADHOC_MODE", False),
    }
    return render(request, "filechest/preview.html", context)


def get_preview_type(suffix: str) -> str:
    """Determine the preview type based on file extension."""
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"}
    video_exts = {".mp4", ".webm", ".ogg", ".mov", ".avi", ".mkv"}
    audio_exts = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"}
    text_exts = {
        ".txt",
        ".md",
        ".markdown",
        ".rst",
        ".log",
        ".csv",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".html",
        ".htm",
        ".css",
        ".scss",
        ".sass",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".ps1",
        ".bat",
        ".cmd",
        ".sql",
        ".graphql",
        ".vue",
        ".svelte",
        ".dockerfile",
        ".gitignore",
        ".env",
        ".editorconfig",
    }
    pdf_exts = {".pdf"}

    if suffix in image_exts:
        return "image"
    elif suffix in video_exts:
        return "video"
    elif suffix in audio_exts:
        return "audio"
    elif suffix in text_exts:
        return "text"
    elif suffix in pdf_exts:
        return "pdf"
    else:
        return "unknown"


def get_mime_type(suffix: str) -> str:
    """Get MIME type for common extensions."""
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".bmp": "image/bmp",
        ".ico": "image/x-icon",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".ogg": "video/ogg",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".aac": "audio/aac",
        ".m4a": "audio/mp4",
        ".pdf": "application/pdf",
        ".json": "application/json",
        ".xml": "application/xml",
    }
    return mime_types.get(suffix, "application/octet-stream")


# =============================================================================
# API Views - Read Operations
# =============================================================================


@require_GET
@never_cache
def api_list(request, volume_name: str, subpath: str = ""):
    """API: List directory contents."""
    volume = get_object_or_404(Volume, name=volume_name, is_active=True)

    if not can_view(request.user, volume):
        return JsonResponse({"error": "Access denied"}, status=403)

    storage = get_storage(volume)
    subpath = storage.normalize_path(subpath)

    try:
        if not storage.is_dir(subpath):
            return JsonResponse({"error": "Not a directory"}, status=400)

        file_list = storage.list_dir(subpath)
    except InvalidPathError:
        return JsonResponse({"error": "Invalid path"}, status=400)
    except PathNotFoundError:
        return JsonResponse({"error": "Path not found"}, status=404)
    except PermissionDeniedError:
        return JsonResponse({"error": "Permission denied"}, status=403)

    # Convert to dict format
    items = [
        {
            "name": f.name,
            "is_dir": f.is_dir,
            "size": f.size,
            "modified": f.modified,
        }
        for f in file_list
    ]

    # Sort: directories first, then by name
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

    # Build breadcrumb
    breadcrumb = []
    if subpath:
        parts = subpath.strip("/").split("/")
        for i, part in enumerate(parts):
            breadcrumb.append(
                {
                    "name": part,
                    "path": "/".join(parts[: i + 1]),
                }
            )

    return JsonResponse(
        {
            "volume": {
                "name": volume.name,
                "verbose_name": volume.verbose_name,
            },
            "path": subpath,
            "breadcrumb": breadcrumb,
            "items": items,
        }
    )


@require_GET
@xframe_options_sameorigin
def api_raw(request, volume_name: str, filepath: str):
    """API: Serve file content inline (for preview)."""
    volume = get_object_or_404(Volume, name=volume_name, is_active=True)

    if not can_view(request.user, volume):
        return HttpResponseForbidden("Access denied")

    storage = get_storage(volume)
    filepath = storage.normalize_path(filepath)

    try:
        # Check If-None-Match (get_etag only when header present)
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match:
            etag = storage.get_etag(filepath)
            if etag and if_none_match == etag:
                return HttpResponseNotModified()

        file_obj, etag, size = storage.open_file(filepath)

        response = StreamingHttpResponse(file_obj)
        response["Content-Length"] = size
        content_type, _ = mimetypes.guess_type(filepath)
        response["Content-Type"] = content_type

        if etag:
            response["ETag"] = etag
            response["Cache-Control"] = "private, max-age=0, must-revalidate"
        else:
            response["Cache-Control"] = "private"

        return response
    except InvalidPathError:
        return HttpResponse("Invalid path", status=400)
    except PathNotFoundError:
        raise Http404("File not found")
    except NotAFileError:
        return HttpResponse("Not a file", status=400)
    except PermissionDeniedError:
        return HttpResponseForbidden("Permission denied")


# =============================================================================
# API Views - Write Operations
# =============================================================================


@require_POST
def api_mkdir(request, volume_name: str):
    """API: Create a new folder."""
    volume, error = get_volume_and_check_edit(request, volume_name)
    if error:
        return error

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    storage = get_storage(volume)

    path = storage.normalize_path(data.get("path", ""))
    name = data.get("name", "")
    parents = data.get("parents", False)
    exists_ok = data.get("exists_ok", False)

    # Validate name
    if err := storage.validate_name(name):
        return JsonResponse({"error": err}, status=400)

    # Build full path for new folder
    new_path = f"{path}/{name}".strip("/") if path else name

    try:
        storage.mkdir(new_path, parents=parents, exists_ok=exists_ok)
    except InvalidPathError as e:
        return JsonResponse({"error": e.message, "path": e.path}, status=400)
    except PathNotFoundError as e:
        return JsonResponse({"error": e.message, "path": e.path}, status=404)
    except PathExistsError as e:
        return JsonResponse({"error": e.message, "path": e.path}, status=400)
    except PermissionDeniedError as e:
        return JsonResponse({"error": e.message, "path": e.path}, status=403)
    except StorageError as e:
        return JsonResponse({"error": e.message, "path": e.path}, status=500)

    return JsonResponse({"success": True, "name": name})


@require_POST
def api_delete(request, volume_name: str):
    """API: Delete files/folders."""
    volume, error = get_volume_and_check_edit(request, volume_name)
    if error:
        return error

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    storage = get_storage(volume)

    items = [storage.normalize_path(item) for item in data.get("items", [])]
    if not items:
        return JsonResponse({"error": "No items specified"}, status=400)
    deleted = []
    errors = []

    for item in items:
        try:
            storage.delete(item)
            deleted.append(item)
        except PathNotFoundError as e:
            errors.append({"item": item, "error": e.message})
        except InvalidPathError as e:
            errors.append({"item": item, "error": e.message})
        except PermissionDeniedError as e:
            errors.append({"item": item, "error": e.message})
        except StorageError as e:
            errors.append({"item": item, "error": e.message})

    return JsonResponse({"deleted": deleted, "errors": errors})


@require_POST
def api_rename(request, volume_name: str):
    """API: Rename a file/folder."""
    volume, error = get_volume_and_check_edit(request, volume_name)
    if error:
        return error

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    storage = get_storage(volume)

    path = storage.normalize_path(data.get("path", ""))
    new_name = data.get("new_name", "")

    if not path:
        return JsonResponse({"error": "Path is required"}, status=400)

    # Validate new name
    if err := storage.validate_name(new_name):
        return JsonResponse({"error": err}, status=400)

    try:
        storage.rename(path, new_name)
    except PathNotFoundError as e:
        return JsonResponse({"error": e.message, "path": e.path}, status=404)
    except PathExistsError as e:
        return JsonResponse({"error": e.message, "path": e.path}, status=400)
    except InvalidPathError as e:
        return JsonResponse({"error": e.message, "path": e.path}, status=400)
    except PermissionDeniedError as e:
        return JsonResponse({"error": e.message, "path": e.path}, status=403)
    except StorageError as e:
        return JsonResponse({"error": e.message, "path": e.path}, status=500)

    return JsonResponse({"success": True, "new_name": new_name})


@require_POST
def api_upload(request, volume_name: str):
    """API: Upload files."""
    volume, error = get_volume_and_check_edit(request, volume_name)
    if error:
        return error

    storage = get_storage(volume)

    path = storage.normalize_path(request.POST.get("path", ""))

    # Check target directory exists
    if path and not storage.is_dir(path):
        return JsonResponse({"error": "Target directory not found"}, status=404)

    # Parse relative paths if provided (for directory uploads)
    relative_paths_json = request.POST.get("relative_paths", "")
    relative_paths = None
    if relative_paths_json:
        try:
            relative_paths = [
                storage.normalize_path(p) for p in json.loads(relative_paths_json)
            ]
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid relative_paths JSON"}, status=400)

    uploaded = []
    errors = []
    files = request.FILES.getlist("files")

    for i, f in enumerate(files):
        # Determine the relative path for this file
        if relative_paths and i < len(relative_paths):
            rel_path = relative_paths[i]
            # Validate each component of the path
            parts = rel_path.split("/")
            for part in parts:
                if err := storage.validate_name(part):
                    errors.append({"file": rel_path, "error": err})
                    break
            else:
                # All parts valid, continue with upload
                pass
            if any(e.get("file") == rel_path for e in errors):
                continue
            display_name = rel_path
        else:
            rel_path = f.name
            display_name = f.name
            # Validate filename
            if err := storage.validate_name(f.name):
                errors.append({"file": f.name, "error": err})
                continue

        # Validate file size
        if f.size > volume.max_file_size:
            errors.append(
                {
                    "file": display_name,
                    "error": f"File size exceeds limit ({volume.max_file_size} bytes)",
                }
            )
            continue

        # Build full destination path
        dest_path = f"{path}/{rel_path}".strip("/") if path else rel_path

        try:
            storage.write_file(dest_path, f.chunks())
            uploaded.append(display_name)
        except PathExistsError as e:
            errors.append({"file": display_name, "error": e.message})
        except InvalidPathError as e:
            errors.append({"file": display_name, "error": e.message})
        except PermissionDeniedError as e:
            errors.append({"file": display_name, "error": e.message})
        except StorageError as e:
            errors.append({"file": display_name, "error": e.message})

    return JsonResponse({"uploaded": uploaded, "errors": errors})


@require_POST
def api_copy(request, volume_name: str):
    """API: Copy files/folders."""
    volume, error = get_volume_and_check_edit(request, volume_name)
    if error:
        return error

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    storage = get_storage(volume)

    items = [storage.normalize_path(item) for item in data.get("items", [])]
    dest_path = storage.normalize_path(data.get("destination", ""))

    if not items:
        return JsonResponse({"error": "No items specified"}, status=400)

    # Check destination is a directory
    if not storage.is_dir(dest_path):
        return JsonResponse({"error": "Destination is not a directory"}, status=400)

    copied = []
    errors = []

    for item in items:
        try:
            storage.copy(item, dest_path)
            copied.append(item)
        except PathNotFoundError as e:
            errors.append({"item": item, "error": e.message})
        except PathExistsError as e:
            errors.append({"item": item, "error": e.message})
        except PermissionDeniedError as e:
            errors.append({"item": item, "error": e.message})
        except StorageError as e:
            errors.append({"item": item, "error": e.message})

    return JsonResponse({"copied": copied, "errors": errors})


@require_POST
def api_move(request, volume_name: str):
    """API: Move files/folders."""
    volume, error = get_volume_and_check_edit(request, volume_name)
    if error:
        return error

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    storage = get_storage(volume)

    items = [storage.normalize_path(item) for item in data.get("items", [])]
    dest_path = storage.normalize_path(data.get("destination", ""))

    if not items:
        return JsonResponse({"error": "No items specified"}, status=400)

    # Check destination is a directory
    if not storage.is_dir(dest_path):
        return JsonResponse({"error": "Destination is not a directory"}, status=400)

    moved = []
    errors = []

    for item in items:
        try:
            storage.move(item, dest_path)
            moved.append(item)
        except PathNotFoundError as e:
            errors.append({"item": item, "error": e.message})
        except PathExistsError as e:
            errors.append({"item": item, "error": e.message})
        except InvalidPathError as e:
            errors.append({"item": item, "error": e.message})
        except PermissionDeniedError as e:
            errors.append({"item": item, "error": e.message})
        except StorageError as e:
            errors.append({"item": item, "error": e.message})

    return JsonResponse({"moved": moved, "errors": errors})
