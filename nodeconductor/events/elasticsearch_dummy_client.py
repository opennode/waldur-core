from operator import itemgetter

from nodeconductor.events import elasticsearch_client


class ElasticsearchDummyClient(elasticsearch_client.ElasticsearchClient):

    # We do not need connection with real elasticsearch
    def __init__(self):
        pass

    def _get_dummy_events(self, user=None):
        if user:
            user_data = {
                'user_username': user.username,
                'user_uuid': user.uuid.hex,
                'user_native_name': user.native_name,
                'user_full_name': user.full_name,
            }
            for data in DUMMY_EVENTS:
                data.update(user_data)

        return DUMMY_EVENTS

    def get_user_events(
            self, user, event_types=None, search_text=None, sort='-@timestamp', index='_all', from_=0, size=10):
        filtered_events = []
        for event in self._get_dummy_events(user):
            # define event type filter condition
            if event_types:
                event_type_condition = event['event_type'] in event_types
            else:
                event_type_condition = True
            # define search text filter condition
            if search_text:
                search_text_condition = any([search_text in event[field] for field in self.FTS_FIELDS])
            else:
                search_text_condition = True
            # define permitted objects filter condition
            permitted_objects_condition = any(
                [event[key] in uuids for key, uuids
                    in self._get_permitted_objects_uuids(user).items() if key in event])
            # filter out needed events
            if event_type_condition and search_text_condition and permitted_objects_condition:
                filtered_events.append(event)

        reverse = sort.startswith('-')
        sort = sort[1:] if reverse else sort
        return {
            'events': sorted(filtered_events, key=itemgetter(sort), reverse=reverse),
            'total': len(filtered_events),
        }


DUMMY_EVENTS = [
    {
        "@timestamp": "2015-05-08T07:03:22.867-04:00",
        "event_type": "auth_logged_in_with_username",
        "user_uuid": "bfc02b7c9f304bfe8a26eb50f7399dbf",
        "user_username": "Alice",
        "user_full_name": "Alice Lebowski",
        "user_native_name": "Alice Lebowski",
        "message": "User Alice with full name Alice Lebowski authenticated successfully with username and password",
        "importance": "normal",
        "importance_code": 20,
        "@version": 1,
        "levelname": "INFO",
        "logger": "nodeconductor.core.views",
        "host": "127.0.0.1",
        "type": "gcloud-event",
    },
    {
        "@timestamp": "2015-05-08T02:38:09.838-04:00",
        "event_type": "project_creation_succeeded",
        "user_uuid": "7033e7af99c949698d30bea71602b42c",
        "user_username": "Walter",
        "user_full_name": "Walter Lebowski",
        "user_native_name": "Walter Lebowski",
        "project_uuid": "2ee0e7995ad545f09b42dbc17970ab60",
        "project_name": "5fd8b4a4-a03f-4266-983a-6e15ade3a99f",
        "customer_uuid": "dc95803f1d8a4234b437cd381b12177a",
        "customer_name": "Alice",
        "customer_abbreviation": "Alice",
        "customer_contact_details": "",
        "message": "Project 5fd8b4a4-a03f-4266-983a-6e15ade3a99f has been created.",
        "importance": "normal",
        "importance_code": 20,
        "@version": 1,
        "levelname": "INFO",
        "logger": "nodeconductor.structure.handlers",
        "host": "127.0.0.1",
        "type": "gcloud-event",
    },
    {
        "@timestamp": "2015-05-08T02:56:57.378-04:00",
        "event_type": "iaas_instance_creation_scheduled",
        "user_uuid": "ef2df123a73947e6a3f5512b940ba0fa",
        "user_username": "Dave",
        "user_full_name": "Dave Lebowski",
        "user_native_name": "Dave Lebowski",
        "project_name": "whistles.org",
        "project_uuid": "f6d4b5e3132847ae9be27e214655777c",
        "project_group_uuid": "c472b4a3afd24fbf819c08a23476c2ad",
        "project_group_name": "Whistles Portal",
        "cloud_account_uuid": "5630932f2f854ed786cef73ea377f71a",
        "cloud_account_name": "Cumulus",
        "customer_uuid": "75bcbff5db784307a4f556b4a8912f09",
        "customer_name": "Ministry of Whistles",
        "customer_abbreviation": "MoW",
        "customer_contact_details": "",
        "iaas_instance_uuid": "5228510979d444e6859861ecbea9ddec",
        "iaas_instance_name": "e97ceabc-5776-41ec-bd78-d15c5b4264b2",
        "iaas_instance_flavor_uuid": "375c7c257e3840da9242df472e188398",
        "iaas_instance_flavor_name": "m1.medium",
        "iaas_instance_flavor_ram": 4096,
        "iaas_instance_flavor_disk": 10240,
        "iaas_instance_flavor_cores": 2,
        "message": "Virtual machine e97ceabc-5776-41ec-bd78-d15c5b4264b2 creation has been scheduled.",
        "importance": "normal",
        "importance_code": 20,
        "@version": 1,
        "levelname": "INFO",
        "logger": "nodeconductor.iaas.views",
        "host": "127.0.0.1",
        "type": "gcloud-event",
    },
    {
        "@timestamp": "2015-05-07T19:30:21.065-04:00",
        "event_type": "role_granted",
        "role_name": "administrator",
        "structure_type": "project",
        "affected_user_uuid": "5f60426dfc7b42ada0150599f0615829",
        "affected_user_username": "Charlie",
        "affected_user_full_name": "Charlie Lebowski",
        "affected_user_native_name": "Charlie Lebowski",
        "customer_uuid": "44a505a4950a4cf38cc967890271c63d",
        "customer_name": "Ministry of Bells",
        "customer_abbreviation": "MoB",
        "customer_contact_details": "",
        "project_uuid": "b5e620748460434a8bea3068c65e1820",
        "project_name": "bells.org",
        "project_group_uuid": "c6288955b7004e4e9dd0dbf65b3e249e",
        "project_group_name": "Bells Portal",
        "message": "User Charlie has gained role of administrator in project bells.org.",
        "importance": "normal",
        "importance_code": 20,
        "@version": 1,
        "levelname": "INFO",
        "logger": "nodeconductor.structure.models",
        "host": "127.0.0.1",
        "type": "gcloud-event",
    },
]
