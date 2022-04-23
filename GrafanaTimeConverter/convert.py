from datetime import datetime

def convert(*, time_from: str = None, time_to: str = None, time_now: datetime = None) -> tuple[datetime, datetime]:
    if not time_now:
        time_now = datetime.now()

    return datetime.now(), datetime.now()
    