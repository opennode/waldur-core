default_app_config = 'nodeconductor.cost_tracking.apps.CostTrackingConfig'


class PriceItemTypes(object):
    FLAVOR = 'flavor'
    STORAGE = 'storage'
    LICENSE_APPLICATION = 'license-application'
    LICENSE_OS = 'license-os'
    SUPPORT = 'support'
    NETWORK = 'network'
    USAGE = 'usage'
    USERS = 'users'

    CHOICES = (
        (FLAVOR, 'flavor'),
        (STORAGE, 'storage'),
        (LICENSE_APPLICATION, 'license-application'),
        (LICENSE_OS, 'license-os'),
        (SUPPORT, 'support'),
        (NETWORK, 'network'),
        (USAGE, 'usage'),
        (USERS, 'users'),
    )

    NUMERICS = (STORAGE, USERS)


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

    CATEGORIES = {
        'linux': (CENTOS6, CENTOS7, UBUNTU, RHEL6, RHEL7)
    }


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


class SupportTypes(object):
    BASIC = 'basic'
    PREMIUM = 'premium'

    CHOICES = (
        (BASIC, 'Basic'),
        (PREMIUM, 'Premium'),
    )


class CostConstants(object):
    PriceItem = PriceItemTypes
    Application = ApplicationTypes
    Os = OsTypes
    Support = SupportTypes
