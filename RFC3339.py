## https://gist.github.com/Hypro999/042582678582315a0a6ffac49d6c5e49
from datetime import datetime, timedelta, timezone
import re
class RFC3339:
    class patterns:
        # date-fullyear   = 4DIGIT
        date_fullyear: str = r"[0-9]{4}"
        
        # date-month      = 2DIGIT  ; 01-12
        date_month: str = r"0[0-9]|1[0-2]"
        
        # date-mday       = 2DIGIT  ; 01-28, 01-29, 01-30, 01-31 (based on month/year)
        date_mday: str = r"0[1-9]|[1-2][0-9]|3[0-1]"
        # To keep these regular expressions simpler and independent of each other, we will not enforce the
        # "based on month/year" part here despite the fact that regular expressions are Turing complete.

        # time-hour       = 2DIGIT  ; 00-23
        time_hour: str = r"[0-1][0-9]|2[0-3]"
        
        # time-minute     = 2DIGIT  ; 00-59
        time_minute: str = r"[0-5][0-9]"
        
        # time-second     = 2DIGIT  ; 00-58, 00-59, 00-60 based on leap second rules
        time_second: str = r"[0-5][0-9]|60"
        
        # time-secfrac    = "." 1*DIGIT
        time_secfrac: str = r"\.[0-9]+"
        
        # time-numoffset  = ("+" / "-") time-hour ":" time-minute
        time_numoffset: str = f"[+-](?P<offset_hour>{time_hour}):(?P<offset_minute>{time_minute})"
        
        # time-numoffset  = ("+" / "-") time-hour ":" time-minute
        time_offset: str = f"[Zz]|({time_numoffset})"

        # partial-time    = time-hour ":" time-minute ":" time-second [time-secfrac]
        partial_time: str = f"(?P<hour>{time_hour}):(?P<minute>{time_minute}):(?P<second>{time_second})(?P<secfrac>{time_secfrac})?"

        # full-date       = date-fullyear "-" date-month "-" date-mday
        full_date: str = f"(?P<year>{date_fullyear})-(?P<month>{date_month})-(?P<day>{date_mday})"

        # full-time       = partial-time time-offset
        # full_time: str = f"(?P<time>{partial_time})(?P<offset>{time_offset})"
        full_time: str = f"(?P<time>{partial_time})(?P<offset>{time_offset})"

        # date-time       = full-date "T" full-time
        date_time: str = f"^(?P<date>{full_date})[Tt]({full_time})$"

    def __init__(self):
        self.pattern = re.compile(self.patterns.date_time)

    def is_valid(self, timestamp: str) -> bool:
        return bool(self.pattern.match(timestamp))

    def extract_datetime(self, timestamp: str) -> datetime:
        match: re.Match = self.pattern.match(timestamp)
        if match == None:
            raise ValueError("Invalid format. The string \"{timestamp}\" Does not follow RFC 3339.")
        
        second = int(match["second"])
        if second == 60:
            # Python's datetime library doesn't support leap seconds so we
            # will handle this by rounding down by one second if needed.
            # https://docs.python.org/3.6/library/datetime.html#available-types
            second = 59
        
        secfrac = match["secfrac"]
        microsecond = 0
        if secfrac:
            microsecond = int(float(match["secfrac"]) * 10**6)
        
        factor = 1
        tz_offset = match["offset"]
        if tz_offset in ["Z", "z"]:
            hours = 0
            minutes = 0
        else:
            if tz_offset.startswith("-"):
                factor = -1
            hours = int(match["offset_hour"])
            minutes = int(match["offset_minute"])
        tz = timezone(factor * timedelta(hours=hours, minutes=minutes))
 
        return datetime(
            year=int(match["year"]),
            month=int(match["month"]),
            day=int(match["day"]),
            hour=int(match["hour"]),
            minute=int(match["minute"]),
            second=second,
            microsecond=microsecond,
            tzinfo=tz,
        )

    def encode_datetime(self, dt: datetime) -> str:
        # ISO 8601 strings are compatible with RFC 3339.
        timestamp = dt.isoformat()
        if timestamp.endswith("+00:00"):
            timestamp = timestamp[:-6] + "Z"
        return timestamp
