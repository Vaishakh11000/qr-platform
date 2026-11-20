import hashlib
import os
import re
import tempfile

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import settings


DEFAULT_STORAGE_ROOT = settings.media_storage_root

CHUNK_SIZE = 1024 * 1024

MAX_FILE_SIZES = {
    "IMAGE": 10 * 1024 * 1024,
    "VIDEO": 100 * 1024 * 1024,
    "DOCUMENT": 25 * 1024 * 1024,
}


class UnsupportedMediaType(Exception):
    pass


class InvalidMediaFile(Exception):
    pass


class UploadTooLarge(Exception):
    pass


@dataclass(frozen=True)
class StoredMedia:
    storage_key: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    checksum_sha256: str


def sanitize_filename(filename: str | None) -> str:
    if not filename:
        return "upload"

    filename = filename.replace("\\", "/").split("/")[-1]
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)
    filename = filename.strip()

    if not filename:
        return "upload"

    return filename[:255]


def detect_media(
    file_path: Path,
    media_type: str,
) -> tuple[str, str]:

    with file_path.open("rb") as file:
        header = file.read(32)

    if not header:
        raise InvalidMediaFile("The uploaded file is empty.")

    if media_type == "IMAGE":
        try:
            with Image.open(file_path) as image:
                image_format = image.format
                image.verify()

        except (
            UnidentifiedImageError,
            OSError,
            Image.DecompressionBombError,
        ) as exc:
            raise InvalidMediaFile(
                "The uploaded image is invalid or unsupported."
            ) from exc

        image_types = {
            "JPEG": ("image/jpeg", ".jpg"),
            "PNG": ("image/png", ".png"),
            "WEBP": ("image/webp", ".webp"),
        }

        if image_format not in image_types:
            raise UnsupportedMediaType(
                "Only JPEG, PNG and WebP images are allowed."
            )

        return image_types[image_format]

    if media_type == "VIDEO":
        if len(header) >= 12 and header[4:8] == b"ftyp":
            return "video/mp4", ".mp4"

        if header.startswith(b"\x1a\x45\xdf\xa3"):
            return "video/webm", ".webm"

        raise UnsupportedMediaType(
            "Only MP4 and WebM videos are allowed."
        )

    if media_type == "DOCUMENT":
        if header.startswith(b"%PDF-"):
            return "application/pdf", ".pdf"

        raise UnsupportedMediaType(
            "Only PDF documents are allowed."
        )

    raise UnsupportedMediaType(
        "Media type must be IMAGE, VIDEO or DOCUMENT."
    )


async def store_upload(
    upload: UploadFile,
    media_type: str,
    storage_root: Path | None = None,
) -> StoredMedia:

    media_type = media_type.upper()

    if media_type not in MAX_FILE_SIZES:
        raise UnsupportedMediaType(
            "Media type must be IMAGE, VIDEO or DOCUMENT."
        )

    root = Path(storage_root or DEFAULT_STORAGE_ROOT)

    temporary_dir = root / "temporary"

    target_dir = (
        root / "documents"
        if media_type == "DOCUMENT"
        else root / "products"
    )

    temporary_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    original_filename = sanitize_filename(upload.filename)

    temporary_path = None
    final_path = None
    completed = False

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix="upload_",
            suffix=".part",
            dir=temporary_dir,
            delete=False,
        ) as temporary_file:

            temporary_path = Path(temporary_file.name)

            checksum = hashlib.sha256()
            file_size = 0

            while True:
                chunk = await upload.read(CHUNK_SIZE)

                if not chunk:
                    break

                file_size += len(chunk)

                if file_size > MAX_FILE_SIZES[media_type]:
                    raise UploadTooLarge(
                        f"{media_type} upload exceeds the maximum "
                        f"size of {MAX_FILE_SIZES[media_type]} bytes."
                    )

                temporary_file.write(chunk)
                checksum.update(chunk)

        if file_size == 0:
            raise InvalidMediaFile("The uploaded file is empty.")

        mime_type, extension = detect_media(
            temporary_path,
            media_type,
        )

        storage_filename = f"{uuid4().hex}{extension}"
        final_path = target_dir / storage_filename

        os.replace(temporary_path, final_path)
        temporary_path = None

        storage_key = (
            f"documents/{storage_filename}"
            if media_type == "DOCUMENT"
            else f"products/{storage_filename}"
        )

        result = StoredMedia(
            storage_key=storage_key,
            original_filename=original_filename,
            mime_type=mime_type,
            file_size_bytes=file_size,
            checksum_sha256=checksum.hexdigest(),
        )

        completed = True
        return result

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

        if final_path is not None and not completed:
            final_path.unlink(missing_ok=True)

