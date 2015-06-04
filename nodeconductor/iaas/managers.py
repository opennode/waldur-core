from django.db import models

class InstanceManager(models.Manager):

    def for_aggregates(self, model_name, aggregates):
        if model_name == 'project':
            return self.for_projects(aggregates)
        elif model_name == 'project_group':
            return self.for_project_groups(aggregates)
        elif model_name == 'customer':
            return self.for_customers(aggregates)

    def for_projects(self, qs):
        """
        Filters instances by projects
        """
        return self.get_queryset().filter(cloud_project_membership__project__in=qs)

    def for_project_groups(self, qs):
        """
        Filters instances by project groups
        """
        return self.get_queryset().filter(cloud_project_membership__project__project_groups__in=qs)

    def for_customers(self, qs):
        """
        Filters instances by customers
        """
        return self.get_queryset().filter(cloud_project_membership__project__customer__in=qs)
