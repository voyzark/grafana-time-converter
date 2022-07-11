import re
from datetime import datetime, timedelta
import calendar

datemath_pattern = re.compile(r'^(([+-]\d{0,10}[yMwdhmsQ])|(\/1*f*[yMwdhmsQ]))+$')
expression_pattern = re.compile(r'([+-/])(\d{0,10})(f*)([yMwdhmsQ])')


def round_date_unit(start_date: datetime, unit: str, round_up: bool, **_):
    if unit == 'y':
        year = start_date.year + 1 if round_up else start_date.year
        return start_date.replace(year=year, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    elif unit == 'M':
        month_end = calendar.monthrange(start_date.year, start_date.month)[1]
        rounded_date = start_date.replace(day=month_end) + timedelta(days=1) if round_up else start_date
        return rounded_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
    elif unit == 'w':
        current_weekday = calendar.weekday(start_date.year, start_date.month, start_date.day)
        week_start = start_date - timedelta(days=current_weekday)
        week_end = start_date + timedelta(days=7-current_weekday)
        rounded_date = week_end if round_up else week_start
        return rounded_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    elif unit == 'd':
        rounded_date = start_date + timedelta(day=1) if round_up else start_date
        return rounded_date.replace(hour=0, minute=0, second=0, microsecond=0)

    elif unit == 'h':
        rounded_date = start_date + timedelta(hours=1) if round_up else start_date
        return rounded_date.replace(minute=0, second=0, microsecond=0)
    
    elif unit == 'm':
        rounded_date = start_date + timedelta(minutes=1) if round_up else start_date
        return rounded_date.replace(second=0, microsecond=0)

    elif unit == 's':
        rounded_date = start_date + timedelta(seconds=1) if round_up else start_date
        return rounded_date.replace(microsecond=0)
    
    elif unit == 'Q':
        quarter_start_month = (start_date.month-1) // 3 * 3 + 1
        quarter_start_date = start_date.replace(month=quarter_start_month, day=1)
        next_quarter_start_date = round_date_unit(quarter_start_date.replace(month=quarter_start_month+2), 'M', True)
        rounded_date = next_quarter_start_date if round_up else quarter_start_date
        return rounded_date.replace(hour=0, minute=0, second=0, microsecond=0)

    else:
        raise ValueError(f'Unknown unit "{unit}"')


def add_date(start_date: datetime, amount: int, unit: str, **_) -> datetime:
    if unit == 'y':
        end_year = start_date.year + amount
        
        # in this special case we want to land on the 28th of february (because thats how Moments behave in grafana)
        if start_date.month == 2 and start_date.day == 29 and not calendar.isleap(end_year):
            return start_date.replace(year=end_year, day=28)
        
        return start_date.replace(year=end_year)

    # adding months behaves like this in grafana's Moments:
    # the day of the month will always stay the same. if the month we land on doesn't have as many days, 
    # we'll round down to the maximum day of that month.
    # e.g. Jan. 31 + 1M => Feb. 28 (or Feb. 29 during a leap year)
    elif unit == 'M':
        if amount >= 0:
            end_year = start_date.year + ((start_date.month + amount) // 12)        
            end_month = (start_date.month + amount - 1) % 12 + 1
        elif amount < 0:
            end_year = start_date.year - ((12 - start_date.month - amount) // 12)
            end_month = 12 - ((-amount - start_date.month) % 12)

        month_end = calendar.monthrange(end_year, end_month)[1]
        end_day = start_date.day if month_end > start_date.day else month_end
        return start_date.replace(year=end_year, month=end_month, day=end_day)

    elif unit == 'w':
        return add_date(start_date, amount * 7, 'd')

    elif unit == 'd':
        return start_date + timedelta(days=amount)

    elif unit == 'h':
        return start_date + timedelta(hours=amount)

    elif unit == 'm':
        return start_date + timedelta(minutes=amount)

    elif unit == 's':
        return start_date + timedelta(seconds=amount)

    elif unit == 'Q':
        return add_date(start_date, amount*3, 'M')

    else:
        raise ValueError(f'Unknown unit "{unit}"')


def subtract_date(start_date: datetime, amount: int, unit: str, **_) -> datetime:
    return add_date(start_date, -amount, unit)


def round_to_fiscal(start_date: datetime, fiscal_year_start_month: datetime, unit: str, round_up: bool, **_):
    if unit == 'y':
        if round_up:
            fiscal_start = round_to_fiscal(start_date, fiscal_year_start_month, unit, False)
            fiscal_end_month = add_date(fiscal_start, 11, 'M')
            return round_date_unit(fiscal_end_month, 'M', True)
        else:
            diff_to_fiscal_start = (start_date.month - fiscal_year_start_month + 12) % 12
            start_date_month = subtract_date(start_date=start_date, amount=diff_to_fiscal_start, unit='M')
            return round_date_unit(start_date_month, 'M', False)

    elif unit == 'Q':
        if round_up:
            fiscal_start = round_to_fiscal(start_date, fiscal_year_start_month, unit, False)
            fiscal_end_month = add_date(fiscal_start, 2, 'M')
            return round_date_unit(fiscal_end_month, 'M', True)
        else:
            diff_to_fiscal_start = (start_date.month - fiscal_year_start_month + 3) % 3
            start_date_month = subtract_date(start_date=start_date, amount=diff_to_fiscal_start, unit='M')
            return round_date_unit(start_date_month, 'M', False)
    
    else:
        raise ValueError(f'Unknown unit "{unit}"')


# a pythonic implementation of the parseDateMath function of @grafana/data datemath.ts using regexp instead of iterating over single chars
def parse_date_math(math_string: str, time: datetime, round_up: bool, fiscal_year_start_month: int = 1) -> datetime:
    stripped_math_string = re.sub(r'\s', '', math_string)    
   
    # Check if the whole string is valid
    if not re.match(datemath_pattern, stripped_math_string):
        return None
        
    math_funcs = {
        '-': subtract_date,
        '+': add_date,
        '/': round_date_unit,
        'f': round_to_fiscal,
    }

    dt: datetime = time    
    for match in re.finditer(expression_pattern, stripped_math_string):
        is_fiscal = match.group(3) != ''        
        operator = 'f' if is_fiscal else match.group(1)
        num = match.group(2) or 1
        unit = match.group(4)

        math_func = math_funcs[operator]
        
        dt = math_func(start_date=dt, 
                       amount=int(num), 
                       unit=unit, 
                       fiscal_year_start_month=fiscal_year_start_month, 
                       round_up=round_up)
    
    return dt
