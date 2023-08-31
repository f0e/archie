from database import database
import parse

if __name__ == "__main__":
    database.connect()

    parse.init()
    parse.parse_accepted_channels()

    database.close()
