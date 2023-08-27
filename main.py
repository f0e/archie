from database import database
from sources import youtube

if __name__ == "__main__":
    database.connect()

    if not youtube.add_channel('@MrBeast'):
        print("filtered")

    database.close()
