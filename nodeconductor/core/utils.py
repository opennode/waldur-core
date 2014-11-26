from operator import itemgetter

from django.utils.datastructures import SortedDict


def sort_dict(unsorted_dict):
    """
    Return a SortedDict ordered by key names from the :unsorted_dict:
    """
    sorted_dict = SortedDict()
    # sort items before inserting them into a dict
    for key, value in sorted(unsorted_dict.items(), key=itemgetter(0)):
        sorted_dict[key] = value
    return sorted_dict