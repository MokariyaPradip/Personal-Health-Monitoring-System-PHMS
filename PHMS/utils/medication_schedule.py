from datetime import time


def _every_minutes(minutes):
    """
    Generate evenly spaced time points throughout a 24-hour period.
    
    Used for high-frequency medication schedules where doses repeat
    at regular intervals throughout the day.
    
    Args:
        minutes (int): Interval in minutes between each time point.
                      E.g., 60 = every 1 hour, 30 = every 30 minutes
    
    Returns:
        list: Array of time objects spaced at the given interval starting from 00:00
    """
    times = []
    for total_minutes in range(0, 24 * 60, minutes):
        hours = total_minutes // 60
        mins = total_minutes % 60
        times.append(time(hours, mins))
    return times

MEDICATION_SCHEDULE = {
    # Daily frequencies with specific times
    1: [time(8, 0)],                                      # once a day - gap: 24h
    2: [time(8, 0), time(20, 0)],                         # twice a day - gap: 12h
    3: [time(8, 0), time(14, 0), time(20, 0)],            # three times - gap: 6h
    4: [time(8, 0), time(12, 0), time(16, 0), time(20, 0)],  # four times - gap: 4h
    6: [time(6, 0), time(10, 0), time(14, 0), time(18, 0), time(22, 0), time(2, 0)],  # six times - gap: 4h
    # Regular interval frequencies
    8: _every_minutes(180),                                # every 3 hours - gap: 180min
    12: _every_minutes(120),                               # every 2 hours - gap: 120min
    24: _every_minutes(60),                                # every 1 hour - gap: 60min
    48: _every_minutes(30),                                # every 30 min - gap: 30min
    72: _every_minutes(20),                                # every 20 min - gap: 20min
    96: _every_minutes(15),                                # every 15 min - gap: 15min
    120: _every_minutes(10),                               # every 10 min - gap: 10min
    240: _every_minutes(6)                                 # every 6 min - gap: 6min
}

def get_scheduled_time_for_frequency(frequency):
    """
    Get scheduled intake times for a given medication frequency.
    
    Args:
        frequency (int): Number of times medication should be taken per day.
                        Valid values: 1, 2, 3, 4, 6, 8, 12, 24, 48, 72, 96, 120, 240
    
    Returns:
        list: Array of time objects representing scheduled doses throughout the day.
              Returns empty list if frequency is not found.
    """
    return MEDICATION_SCHEDULE.get(frequency, [])


def get_minimum_dose_gap_minutes(frequency):
    """
    Calculate the minimum time gap (in minutes) between consecutive doses for a given frequency.
    
    This is used to determine the grace period for medication logging. The grace period is
    set to the maximum of:
    - 30 minutes (minimum grace period)
    - The time gap between consecutive doses
    
    Args:
        frequency (int): Number of times medication should be taken.
    
    Returns:
        int: Minimum gap in minutes between consecutive doses.
             For single doses, returns 1440 (24 hours).
    """
    # Get all scheduled times for this frequency
    times = get_scheduled_time_for_frequency(frequency)
    
    # If only one dose per day, gap is 24 hours (1440 minutes)
    if len(times) <= 1:
        return 1440
    
    # Calculate gaps between consecutive doses
    gaps = []
    for i in range(len(times) - 1):
        current_time_minutes = times[i].hour * 60 + times[i].minute
        next_time_minutes = times[i + 1].hour * 60 + times[i + 1].minute
        gap = next_time_minutes - current_time_minutes
        gaps.append(gap)
    
    # Handle gap from last dose to first dose next day
    last_time_minutes = times[-1].hour * 60 + times[-1].minute
    first_time_minutes = times[0].hour * 60 + times[0].minute
    gap_to_next_day = (24 * 60 - last_time_minutes) + first_time_minutes
    gaps.append(gap_to_next_day)
    
    # Return minimum gap between any two consecutive doses
    return min(gaps) if gaps else 1440
