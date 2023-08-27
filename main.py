from database import database
from sources import youtube

if __name__ == "__main__":
    database.connect()

    youtube.get_channel('@MrBeast')

    database.close()
