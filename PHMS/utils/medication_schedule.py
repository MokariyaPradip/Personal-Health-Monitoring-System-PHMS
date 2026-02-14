from datetime import time

MEDICATION_SCHEDULE = {
    1: [time(8, 0)],                                      # once a day (morning)
    2: [time(8, 0), time(20, 0)],                         # twice a day (morning + night)
    3: [time(8, 0), time(14, 0), time(20, 0)],            # three times a day (morning + afternoon + night)
    4: [time(8, 0), time(12, 0), time(16, 0), time(20, 0)],  # four times a day (every 4 hours)
    6: [time(6, 0), time(10, 0), time(14, 0), time(18, 0), time(22, 0), time(2, 0)]  # six times a day (every 4 hours)
}

def get_intake_times(frequency):
    """Get scheduled intake times for a given medication frequency"""
    return MEDICATION_SCHEDULE.get(frequency, [])
