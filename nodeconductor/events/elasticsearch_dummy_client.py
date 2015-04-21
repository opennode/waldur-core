from operator import itemgetter

from nodeconductor.events import elasticsearch_client


class ElasticsearchDummyClient(elasticsearch_client.ElasticsearchClient):

    DUMMY_EVENTS = []

    # We do not need connection with real elasticsearch
    def __init__(self):
        pass

    def _get_dummy_events(self):
        return self.__class__.DUMMY_EVENTS

    def clear_dummy_events(self):
        self.__class__.DUMMY_EVENTS = []

    def get_user_events(
            self, user, event_types=None, search_text=None, sort='-@timestamp', index='_all', from_=0, size=10):
        filtered_events = []
        for event in self._get_dummy_events():
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
                [event[key] in uuids for key, uuids in self._get_permitted_objects_uuids(user).items()])
            # filter out needed events
            if event_type_condition and search_text_condition and permitted_objects_condition:
                filtered_events.append(event)

        reverse = sort.startswith('-')
        sort = sort[1:] if reverse else sort
        return {
            'events': sorted(filtered_events, key=itemgetter(sort), reverse=reverse),
            'total': len(filtered_events),
        }
