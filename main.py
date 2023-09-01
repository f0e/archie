from database import database
from downloader import downloader
import parse

if __name__ == "__main__":
    database.connect()

    parse.init()
    parse.parse_accepted_channels()

    downloader.run()

    database.close()
