import os
import tempfile

from django.db import models
from django.utils.image import Image

def get_upload_path(instance, filename):
    path = 'upload/%s/%s' % (instance._meta.model_name, instance.uuid.hex)
    _, ext = os.path.splitext(filename)
    return '%s%s' % (path, ext)

def dummy_image(filetype='gif'):
    """
    Generate empty image in temporary file for testing
    """
    tmp_file = tempfile.NamedTemporaryFile(suffix='.%s' % filetype)
    image = Image.new('RGB', (100, 100))
    image.save(tmp_file)
    return open(tmp_file.name)


class ImageModelMixin(models.Model):
    class Meta(object):
        abstract = True

    image = models.ImageField(upload_to=get_upload_path, null=True, blank=True)
