from datetime import datetime, timedelta, timezone


BEIJING_TZ = timezone(timedelta(hours=8))


def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def beijing_timestamp() -> str:
    return beijing_now().strftime("%Y%m%d%H%M%S")


def beijing_isoformat() -> str:
    return beijing_now().isoformat()
