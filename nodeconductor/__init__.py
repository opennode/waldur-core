# The dancing with the function and its deletion is done
# to keep the namespace clean: only __version__ is going to be exposed.


# https://gist.github.com/edufelipe/1027906
def _check_output(*popenargs, **kwargs):
    r"""Run command with arguments and return its output as a byte string.

    Backported from Python 2.7 as it's implemented as pure python on stdlib.

    >>> _check_output(['/usr/bin/python', '--version'])
    Python 2.6.2
    """
    import subprocess  # nosec
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)  # nosec
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        error = subprocess.CalledProcessError(retcode, cmd)
        error.output = output
        raise error
    return output


def _get_version(package_name='nodeconductor'):
    import pkg_resources

    # Based on http://stackoverflow.com/a/17638236/175349
    # and https://github.com/pwaller/__autoversion__/blob/master/__autoversion__.py

    try:
        return pkg_resources.get_distribution(package_name).version
    except pkg_resources.DistributionNotFound:
        import os.path
        import re
        import subprocess  # nosec

        repo_dir = os.path.join(os.path.dirname(__file__), os.path.pardir)

        try:
            with open(os.devnull, 'w') as DEV_NULL:
                description = _check_output(
                    ['git', 'describe', '--tags', '--dirty=.dirty'],
                    cwd=repo_dir, stderr=DEV_NULL
                ).strip()

            v = re.search(r'-[0-9]+-', description)
            if v is not None:
                # Replace -n- with -branchname-n-
                # branch = r"-{0}-\1-".format(cls.get_branch(path))
                description, _ = re.subn('-([0-9]+)-', r'+\1.', description, 1)

            if description[0] == 'v':
                description = description[1:]

            return description
        except (OSError, subprocess.CalledProcessError):
            return 'unknown'


__version__ = _get_version()
