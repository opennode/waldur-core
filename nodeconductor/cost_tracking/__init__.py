default_app_config = 'nodeconductor.cost_tracking.apps.CostTrackingConfig'


class PriceItemTypes(object):
    FLAVOR = 'flavor'
    STORAGE = 'storage'
    LICENSE_APPLICATION = 'license-application'
    LICENSE_OS = 'license-os'
    SUPPORT = 'support'
    NETWORK = 'network'

    CHOICES = (
        (FLAVOR, 'flavor'),
        (STORAGE, 'storage'),
        (LICENSE_APPLICATION, 'license-application'),
        (LICENSE_OS, 'license-os'),
        (SUPPORT, 'support'),
        (NETWORK, 'network'),
    )


class OsTypes(object):
    CENTOS6 = 'centos6'
    CENTOS7 = 'centos7'
    UBUNTU = 'ubuntu'
    RHEL6 = 'rhel6'
    RHEL7 = 'rhel7'
    FREEBSD = 'freebsd'
    WINDOWS = 'windows'
    OTHER = 'other'

    CHOICES = (
        (CENTOS6, 'Centos 6'),
        (CENTOS7, 'Centos 7'),
        (UBUNTU, 'Ubuntu'),
        (RHEL6, 'RedHat 6'),
        (RHEL7, 'RedHat 7'),
        (FREEBSD, 'FreeBSD'),
        (WINDOWS, 'Windows'),
        (OTHER, 'Other'),
    )


class ApplicationTypes(object):
    WORDPRESS = 'wordpress'
    POSTGRESQL = 'postgresql'
    ZIMBRA = 'zimbra'
    NONE = 'none'

    CHOICES = (
        (WORDPRESS, 'WordPress'),
        (POSTGRESQL, 'PostgreSQL'),
        (ZIMBRA, 'Zimbra'),
        (NONE, 'None'),
    )
