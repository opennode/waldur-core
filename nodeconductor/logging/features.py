# Group event and alerts by features in order to prevent large HTTP GET request
# TODO: Refactor

EVENT_FEATURES = {
    'users': [
        'auth_logged_in_with_username',
        'user_activated',
        'user_deactivated',
        'user_creation_succeeded',
        'user_deletion_succeeded',
        'user_update_succeeded',
        'role_granted',
        'role_revoked',
    ],
    'password': [
        'user_password_updated',
    ],
    'ssh': [
        'ssh_key_creation_succeeded',
        'ssh_key_deletion_succeeded',
    ],
    'projects': [
        'project_creation_succeeded',
        'project_deletion_succeeded',
        'project_name_update_succeeded',
        'project_update_succeeded',
        'quota_threshold_reached'
    ],
    'project_groups': [
        'project_added_to_project_group',
        'project_group_creation_succeeded',
        'project_group_deletion_succeeded',
        'project_group_update_succeeded',
        'project_removed_from_project_group',
    ],
    'customers': [
        'customer_creation_succeeded',
        'customer_deletion_succeeded',
        'customer_update_succeeded',
        'customer_account_credited',
        'customer_account_debited',
        'user_organization_approved',
        'user_organization_claimed',
        'user_organization_rejected',
        'user_organization_removed',
    ],
    'payments': [
        'payment_approval_succeeded',
        'payment_cancel_succeeded',
        'payment_creation_succeeded',
    ],
    'invoices': [
        'invoice_creation_succeeded',
        'invoice_deletion_succeeded',
        'invoice_update_succeeded',
    ],
    'vms': [
        'resource_start_scheduled',
        'resource_start_succeeded',
        'resource_start_failed',
        'resource_stop_scheduled',
        'resource_stop_succeeded',
        'resource_stop_failed',
        'resource_restart_scheduled',
        'resource_restart_succeeded',
        'resource_restart_failed',
        'resource_creation_scheduled',
        'resource_creation_succeeded',
        'resource_creation_failed',
        'resource_import_succeeded',
        'resource_deletion_scheduled',
        'resource_deletion_succeeded',
        'resource_deletion_failed',
    ],
    'templates': [
        'template_creation_succeeded',
        'template_deletion_succeeded',
        'template_service_creation_succeeded',
        'template_service_deletion_succeeded',
        'template_service_update_succeeded',
        'template_update_succeeded',
    ],
    'monitoring': [
        'zabbix_host_creation_failed',
        'zabbix_host_creation_succeeded',
        'zabbix_host_deletion_failed',
        'zabbix_host_deletion_succeeded',
    ],
}

UPDATE_EVENTS = [
    'customer_update_succeeded',
    'project_group_update_succeeded',
    'project_name_update_succeeded',
    'project_update_succeeded',
    'resource_update_succeeded',
    'template_service_update_succeeded',
    'template_update_succeeded',
    'user_update_succeeded'
]

ALERT_FEATURES = {
    'services': [
        'customer_has_zero_services',
        'service_unavailable',
        'customer_service_count_exceeded',
        'service_has_unmanaged_resources'
    ],
    'resources': [
        'customer_has_zero_resources',
        'service_has_unmanaged_resources',
        'resource_disappeared_from_backend',
        'customer_resource_count_exceeded'
    ],
    'projects': [
        'customer_has_zero_projects',
        'customer_project_count_exceeded'
    ],
    'quota': [
        'customer_projected_costs_exceeded',
    ]
}


def features_to_types(mapping, features):
    event_types = set()
    for feature in features:
        event_types.update(mapping.get(feature, []))
    return list(event_types)


def features_to_events(features):
    return features_to_types(EVENT_FEATURES, features)


def features_to_alerts(features):
    return features_to_types(ALERT_FEATURES, features)
