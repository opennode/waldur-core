import yaml

from django import template

from nodeconductor.core.utils import pwgen

register = template.Library()


class TemplateAppTagError(Exception):
    pass


@register.filter
def bootstrap_opts(value, key):
    """ Extract bootstrap provision options.

    Inputted value should be YAML in format:
    '''
    runcmd:
     - [ /usr/local/bin/bootstrap.sh, <options>]
    '''

    Example:
        In [1]: y = '''
        ...: #cloud-config
        ...: runcmd:
        ...:  - [ /usr/local/bin/bootstrap, -a, admin, -p, password ]
        ...: '''
        In [2]: bootstrap_opts(y, 'a')
        Out[2]: 'admin'
    """
    try:
        y = yaml.load(value)
        opts = y['runcmd'][0][1:]
        opts = dict(zip(opts[::2], opts[1::2]))
        opts = {k[1:]: v for k, v in opts.items()}
        return opts[key]
    except (ValueError, KeyError, IndexError) as e:
        raise TemplateAppTagError('Cannot extract option "%s" from %s. Error: %s' % (key, value, e))


@register.filter
def random_password(length):
    try:
        return pwgen(int(length))
    except ValueError:
        raise template.TemplateSyntaxError("random_password filter argument should be integer")
