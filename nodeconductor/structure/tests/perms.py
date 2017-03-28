from nodeconductor.structure import perms as structure_perms


PERMISSION_LOGICS = (
    ('structure_tests.TestService', structure_perms.service_permission_logic),
    ('structure_tests.TestServiceProjectLink', structure_perms.service_project_link_permission_logic),
    ('structure_tests.TestNewInstance', structure_perms.resource_permission_logic),
)
