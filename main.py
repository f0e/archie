from database import database
from sources import youtube

if __name__ == "__main__":
    database.connect()

    if not youtube.parse_channel('@em-pq6uv'):
        print("filtered")

    database.close()
