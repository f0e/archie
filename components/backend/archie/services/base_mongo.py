from pymongo import MongoClient

# TODO: store in config(?)
client: MongoClient = MongoClient("localhost", 27017, tz_aware=True)
db = client.get_database("archie")
