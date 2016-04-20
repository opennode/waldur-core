import yaml

from django import template

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
        ...:  - [ /usr/local/bin/bootstrap.sh, -a admin -p password ]
        ...: '''
        In [2]: bootstrap_opts(y, 'a')
        Out[2]: 'admin'
    """
    try:
        y = yaml.load(value)
        opts = y['runcmd'][0][1]
        opts = dict(zip(opts.split()[::2], opts.split()[1::2]))
        opts = {k[1:]: v for k, v in opts.items()}
        return opts[key]
    except (ValueError, KeyError, IndexError) as e:
        raise TemplateAppTagError('Cannot extract option "%s" from %s. Error: %s' % (key, value, e))
