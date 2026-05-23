from redis import Redis
from rq import Worker

from app.config import get_settings


def main() -> None:
    connection = Redis.from_url(get_settings().redis_url)
    Worker(["image-generation"], connection=connection).work()


if __name__ == "__main__":
    main()
