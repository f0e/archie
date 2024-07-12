from redis import Redis

# helper fns for redis dbs


def get_undownloaded_id(r: Redis, service_key: str, content_type_str: str, skip_ids: list[str]):
    all_keys = r.keys(f"{service_key}:{content_type_str}:*")

    # get ids to search
    search_ids = []
    for key in all_keys:
        id = key.split(":")[-1]

        if id in skip_ids:
            continue

        search_ids.append(id)

    # TODO: watch execution time when there's a lot of stuff, may need to batch here

    # batch check if ids are downloaded (exist as download key)
    pipe = r.pipeline()

    for id in search_ids:
        if id in skip_ids:
            continue

        pipe.exists(f"{service_key}:download:{id}")

    results = pipe.execute()

    # get first non-existing download
    for id, exists in zip(search_ids, results):
        if not exists:
            return id
