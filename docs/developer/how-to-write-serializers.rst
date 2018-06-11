How to write serializers
========================

Object identity
---------------

When you're writing serializer, you may want user to reliably specify
particular object in API request and serialize object in API response.
Basically there are three aspects to consider:

1) Consistency. We need to ensure consistent serialization format for API request and response
not only within particular application, but also within whole system across different applications.

2) Stability. We need to reliable identify object using some stable field so that
value of this field would be the same even if all other fields are changed.

3) Universality. There are generic API endpoints which accept objects from different application.

Therefore you may ask what is the best way to reliably and consistently identify object in API.

In terms of frontend rendering, user is usually concerned with object name.
Typically we use name only as filtering parameter because names are not unique.
That's why object identity is implemented via a `UUID <https://en.wikipedia.org/wiki/Universally_unique_identifier>`_.

In order to decouple client and server we're implementing `HATEOAS <https://en.wikipedia.org/wiki/HATEOAS>`_
component of REST API. That's why usually we're using `HyperlinkedRelatedField` serializer, for example:

.. code-block:: python

    project = serializers.HyperlinkedRelatedField(
        queryset=models.Project.objects.all(),
        view_name='project-detail',
        lookup_field='uuid',
        write_only=True)

There are four notes here:

1) We need to specify `lookup_field` explicitly because it's default value is 'pk'.

2) We need to specify `view_name` explicitly in order to avoid clash of models names between different applications.
You need to ensure that it matches view name specified in `urls.py` module.

3) When debug mode is enabled, you may navigate to related objects via hyperlinks using browsable API renderer
and select related object from the list.

4) Serialized hyperlink contains not only UUID, but also application name and model.
It allows to use serialized URL as request parameter for generic API endpoint.
Generic API works with different models from arbitrary applications.
Thus UUID alone is not enough for full unambiguous identification of the object in this case.

Generic serializers
-------------------

Typically serializer allows you to specify object related to one particular database model.
However it is not always the case. For example, issue serializer allows you to specify object
related to any model with quota. In this case you would need to use `GenericRelatedField` serializer.
It is expected that `related_models` parameter provides a list of all valid models.

.. code-block:: python

    class IssueSerializer(JiraPropertySerializer):
        scope = core_serializers.GenericRelatedField(
            source='resource',
            related_models=structure_models.ResourceMixin.get_all_models(),
            required=False
        )

Usually `get_all_models` method is implemented in base class and uses Django application
registry which provides access to all registered models. Consider the following example:

.. code-block:: python

    @classmethod
    @lru_cache(maxsize=1)
    def get_all_models(cls):
        return [model for model in apps.get_models() if issubclass(model, cls)]

In terms of database model reference to the resource is stored as generic foreign key, for example:

.. code-block:: python

    resource_content_type = models.ForeignKey(ContentType, blank=True, null=True, related_name='jira_issues')
    resource_object_id = models.PositiveIntegerField(blank=True, null=True)
    resource = GenericForeignKey('resource_content_type', 'resource_object_id')
