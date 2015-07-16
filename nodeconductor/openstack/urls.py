from nodeconductor.openstack import views


def register_in(router):
    router.register(r'openstack', views.OpenStackServiceViewSet, base_name='openstack')
    router.register(r'openstack-images', views.ImageViewSet, base_name='openstack-image')
    router.register(r'openstack-flavors', views.FlavorViewSet, base_name='openstack-flavor')
    router.register(r'openstack-instances', views.InstanceViewSet, base_name='openstack-instance')
    router.register(r'openstack-service-project-link', views.OpenStackServiceProjectLinkViewSet, base_name='openstack-spl')
