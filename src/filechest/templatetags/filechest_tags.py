from datetime import datetime

from django import template

register = template.Library()


FILE_ICONS = {
    "pdf": "📄",
    "doc": "📝",
    "docx": "📝",
    "xls": "📊",
    "xlsx": "📊",
    "png": "🖼️",
    "jpg": "🖼️",
    "jpeg": "🖼️",
    "gif": "🖼️",
    "webp": "🖼️",
    "svg": "🖼️",
    "mp3": "🎵",
    "wav": "🎵",
    "flac": "🎵",
    "ogg": "🎵",
    "mp4": "🎬",
    "mkv": "🎬",
    "avi": "🎬",
    "mov": "🎬",
    "webm": "🎬",
    "zip": "📦",
    "tar": "📦",
    "gz": "📦",
    "rar": "📦",
    "7z": "📦",
    "py": "🐍",
    "js": "📜",
    "ts": "📜",
    "html": "🌐",
    "css": "🎨",
    "json": "📋",
    "xml": "📋",
    "yaml": "📋",
    "yml": "📋",
    "md": "📝",
    "txt": "📝",
    "rst": "📝",
}


@register.filter
def file_icon(filename: str, is_dir: bool) -> str:
    """Return an emoji icon based on file type."""
    if is_dir:
        return "📁"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return FILE_ICONS.get(ext, "📄")


@register.filter
def timestamp_to_date(timestamp: float) -> str:
    """Convert Unix timestamp to formatted date string."""
    if not timestamp:
        return ""
    dt = datetime.fromtimestamp(timestamp).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@register.filter
def add_path(base: str, name: str) -> str:
    """Join path components."""
    if base:
        return f"{base}/{name}"
    return name


IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico"}


@register.filter
def is_image_file(filename: str) -> bool:
    """Check if file is an image based on extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in IMAGE_EXTENSIONS
