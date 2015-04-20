from nodeconductor.events import elasticsearch_dummy_client


class EventFactory(object):

    def __init__(self, **kwargs):
        self.create(**kwargs)
        self.save()

    def create(self, **kwargs):
        self.fields = {
            u'@timestamp': u'2015-04-19T16:25:45.376+04:00',
            u'@version': 1,
            u'cloud_account_name': u'test_cloud_account_name',
            u'cloud_account_uuid': u'test_cloud_account_uuid',
            u'customer_abbreviation': u'TCAN',
            u'customer_contact_details': u'test details',
            u'customer_name': u'Test cusomter',
            u'customer_uuid': u'test_customer_uuid',
            u'event_type': u'test_event_type',
            u'host': u'example.com',
            u'importance': u'high',
            u'importance_code': 30,
            u'levelname': u'WARNING',
            u'logger': u'nodeconductor.test',
            u'message': u'Test message',
            u'project_group_name': u'test_group_name',
            u'project_group_uuid': u'test_group_uuid',
            u'project_name': u'test_project',
            u'project_uuid': u'test_project_uuid',
            u'tags': [u'_jsonparsefailure'],
            u'type': u'gcloud-event',
        }
        for key, value in self.fields.items():
            if key in kwargs:
                self.fields[key] = kwargs[key]

    def save(self):
        elasticsearch_dummy_client.ElasticsearchDummyClient.DUMMY_EVENTS.append(self.fields)
