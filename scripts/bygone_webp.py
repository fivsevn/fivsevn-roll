"""Convert static Bygone uploads without resizing their oriented pixels."""
from io import BytesIO
from pathlib import PurePosixPath
import warnings

from PIL import Image, ImageCms, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener(thumbnails=False)

FORMATS = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP', '.gif': 'GIF',
           '.heic': 'HEIF', '.heif': 'HEIF'}


def convert(data, filename):
    expected = FORMATS.get(PurePosixPath(filename).suffix.lower())
    if expected is None:
        raise ValueError('Bygone supports JPG/JPEG, PNG, WebP, static GIF and HEIC/HEIF uploads')
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(BytesIO(data)) as source:
            if source.format != expected:
                raise ValueError('Bygone filename extension does not match image data')
            source.verify()
        with Image.open(BytesIO(data)) as source:
            if getattr(source, 'is_animated', False):
                raise ValueError('Animated Bygone uploads are not supported; the original stays in the inbox')
            source.load()
            orientation = source.getexif().get(274, 1)
            image = ImageOps.exif_transpose(source)
            alpha = image.mode in {'RGBA', 'LA', 'PA'} or 'transparency' in image.info
            icc = image.info.get('icc_profile', b'')
            exif = image.getexif().tobytes()
            if image.mode in {'P', 'PA'}:
                image = image.convert('RGBA' if alpha else 'RGB')
            if icc and image.mode not in {'RGB', 'RGBA'}:
                opacity = image.convert('RGBA').getchannel('A') if alpha else None
                colors = image.getchannel('L') if image.mode == 'LA' else image
                profile = ImageCms.ImageCmsProfile(BytesIO(icc))
                target = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
                image = ImageCms.profileToProfile(colors, profile, target, outputMode='RGB')
                if opacity is not None:
                    image.putalpha(opacity)
                icc = target.tobytes()
            image = image.convert('RGBA' if alpha else 'RGB')
            # A correctly oriented WebP already satisfies the storage contract.
            if expected == 'WEBP' and orientation == 1:
                return data, image.size
            lossless = expected in {'PNG', 'GIF'} or alpha
            output = BytesIO()
            image.save(output, 'WEBP', quality=95, method=6, lossless=lossless,
                       exact=True, icc_profile=icc, exif=exif)
            encoded = output.getvalue()
            with Image.open(BytesIO(encoded)) as check:
                if check.format != 'WEBP' or check.size != image.size:
                    raise ValueError('Bygone conversion changed image dimensions')
                if lossless and check.convert(image.mode).tobytes() != image.tobytes():
                    raise ValueError('Bygone lossless conversion changed image pixels')
            return encoded, image.size
