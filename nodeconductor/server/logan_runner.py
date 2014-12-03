from logan.runner import run_app

def generate_settings():
    """
    This command is run when ``default_path`` doesn't exist, or ``init`` is
    run and returns a string representing the default data to put into their
    settings file.
    """
    import os
    import base64

    from ConfigParser import RawConfigParser

    config_dir = os.path.join(os.path.expanduser('~'), '.nodeconductor')
    os.path.isdir(config_dir) or os.makedirs(config_dir)

    config = RawConfigParser()
    config.add_section('global')
    config.set('global', 'debug', 'true')
    config.set('global', 'secret_key', base64.b64encode(os.urandom(32)))
    config.set('global', 'static_root', os.path.join(os.getcwd(), 'static_files'))
    config.set('global', 'template_debug', 'true')

    config.add_section('logging')
    config.set('logging', 'log_file', os.path.join(config_dir, 'nodeconductor.log'))

    config.add_section('openstack')
    config.set('openstack', 'auth_url', 'http://keystone.example.com:5000/v2')
    config.set('openstack', 'username', 'nodeconductor')
    config.set('openstack', 'password', 'nodeconductor')
    config.set('openstack', 'tenant_name', 'admin')

    config.add_section('zabbix')
    config.set('zabbix', 'server_url', 'http://zabbix.example.com/zabbix')
    config.set('zabbix', 'username', 'nodeconductor')
    config.set('zabbix', 'password', 'nodeconductor')
    config.set('zabbix', 'host_template_id', '10106')
    config.set('zabbix', 'db_host', '')

    with open(os.path.join(config_dir, 'settings.ini'), 'w+') as f:
        config.write(f)

    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'settings_ini.py')) as f:
        config_template = f.read()

    return config_template


def main():
    run_app(
        project='nodeconductor',
        default_config_path='~/.nodeconductor/settings.py',
        default_settings='nodeconductor.server.base_settings',
        settings_initializer=generate_settings,
        settings_envvar='NODECONDUCTOR_CONF',
    )

if __name__ == '__main__':
    main()
