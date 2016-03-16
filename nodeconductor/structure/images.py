import os
import tempfile

from django.db import models


def get_upload_path(instance, filename):
    path = '%s/%s' % (instance._meta.model_name, instance.uuid.hex)
    _, ext = os.path.splitext(filename)
    return '%s%s' % (path, ext)


def dummy_image(filetype='gif'):
    """ Generate empty image in temporary file for testing """
    # 1x1px Transparent GIF
    GIF = 'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
    tmp_file = tempfile.NamedTemporaryFile(suffix='.%s' % filetype)
    tmp_file.write(GIF.decode('base64'))
    return open(tmp_file.name)


class ImageModelMixin(models.Model):
    class Meta(object):
        abstract = True

    image = models.ImageField(upload_to=get_upload_path, null=True, blank=True)
