from nodeconductor.core.utils import sort_dict

def format_timeline(rows):
    """
    >>> format_timeline([
      (start, end, key1, val1),
      (start, end, key2, val2)
    ])
    {
      from: start,
      to: end,
      key1: val1
      key2: val2
    }
    """
    # Collect key value pairs to the same date bucket
    frames = {}
    for row in rows:
        start, end, item, value = row
        key = (start, end)
        if key not in frames:
            frames[key] = {}
        frames[key][item] = value

    # Format flat dictionary
    results = []
    for key, items in frames.items():
        start, end = key
        row = {
            'from': start,
            'to': end
        }
        row.update(items)
        results.append(sort_dict(row))
    return results
