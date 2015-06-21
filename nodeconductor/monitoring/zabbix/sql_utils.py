from django.conf import settings
from django.db import NotSupportedError


def make_union(queries):
    """
    >>> make_union(["SELECT * from A", "SELECT * from B"])
    "(SELECT * from A) UNION (SELECT * from B)"
    """
    return " UNION ".join("({})".format(query) for query in queries)


def make_list_placeholder(count):
    return ", ".join(r'%s' for _ in range(count))


def make_date_span(engine, interval, field):
    """
    Returns start and end of timeframe for given duration:
    1) Format 2015-06-09 to 1433808000
    2) Format (2015-06-09 + 1 day) to 1433894400
    """
    FUNCTIONS_FOR_ENGINES = {
        "mysql": "UNIX_TIMESTAMP(`{field}`), UNIX_TIMESTAMP(DATE_ADD(`{field}`, INTERVAL 1 {interval}))",
        "postgresql": "EXTRACT(EPOCH FROM ({field}::date)), EXTRACT(EPOCH FROM ({field}::date + INTERVAL '1 {interval}'))"
    }

    if engine not in FUNCTIONS_FOR_ENGINES:
        raise NotSupportedError('Database engine %s is not supported' % engine)

    template = FUNCTIONS_FOR_ENGINES[engine]
    return template.format(field=field, interval=interval)


def truncate_date(engine, interval, field):
    """
    Returns function which truncates UNIX timestamp to interval
    >>> truncate_date('mysql', 'minute', 'clock')
    "DATE_FORMAT(`clock`, '%%Y-%%m-%%d %%H:%%i')"
    """
    FUNCTIONS_FOR_ENGINES = {
        "mysql": {
            "minute": "FROM_UNIXTIME(`{}`, '%%Y-%%m-%%d %%H:%%i')",
            "hour": "FROM_UNIXTIME(`{}`, '%%Y-%%m-%%d %%H:00')",
            "day": "FROM_UNIXTIME(`{}`, '%%Y-%%m-%%d')",
            "week": "DATE_FORMAT(DATE_SUB(FROM_UNIXTIME(`{}`), INTERVAL(WEEKDAY(FROM_UNIXTIME(`{}`))) DAY), '%%Y-%%m-%%d')",
            "month": "FROM_UNIXTIME(`{}`, '%%Y-%%m-01')",
            "year": "FROM_UNIXTIME(`{}`, '%%Y-01-01')",
        },
        "postgresql": {
            "minute": "DATE_TRUNC('minute', TO_TIMESTAMP({}))",
            "hour": "DATE_TRUNC('hour', TO_TIMESTAMP({}))",
            "day": "DATE_TRUNC('day', TO_TIMESTAMP({}))",
            "week": "DATE_TRUNC('week', TO_TIMESTAMP({}))",
            "month": "DATE_TRUNC('month', TO_TIMESTAMP({}))",
            "year": "DATE_TRUNC('year', TO_TIMESTAMP({}))",
        }
    }

    if engine not in FUNCTIONS_FOR_ENGINES:
        raise NotSupportedError('Database engine %s is not supported' % engine)

    if interval not in FUNCTIONS_FOR_ENGINES[engine]:
        raise NotSupportedError('Interval %s is not supported by database' % interval)

    template = FUNCTIONS_FOR_ENGINES[engine][interval]
    return template.replace('{}', field)


def get_zabbix_engine():
    cls_name = settings.DATABASES['zabbix']['ENGINE']

    for engine in ('mysql', 'postgresql'):
        if engine in cls_name:
            return engine
    raise NotSupportedError("Database engine %s is not supported" % engine)
