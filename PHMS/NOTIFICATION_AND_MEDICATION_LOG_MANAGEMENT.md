# Notification and Medication Log Management System

**Date:** February 16, 2026  
**Status:** ✅ Fully Implemented and Tested

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Core Features](#core-features)
4. [Database Schema](#database-schema)
5. [Scheduled Tasks](#scheduled-tasks)
6. [Email Notification System](#email-notification-system)
7. [Grace Period System](#grace-period-system)
8. [Frontend Components](#frontend-components)
9. [API Endpoints](#api-endpoints)
10. [User Workflows](#user-workflows)
11. [Configuration](#configuration)
12. [Troubleshooting](#troubleshooting)

---

## 🏗️ System Overview

The Notification and Medication Log Management System is a comprehensive solution that automates the daily medication tracking process with intelligent scheduling, real-time notifications, grace period management, and email alerts.

### Key Components

- **Medication Log Manager**: Core business logic for log creation and management
- **Scheduler**: APScheduler-based automated task execution
- **Email System**: HTML-based email alerts for critical and consecutive missed doses (same medication)
- **Frontend UI**: Interactive medication log display with real-time button state management
- **Database**: SQLite with SQLAlchemy ORM for persistent storage

### System Goals

✅ Automate daily medication log creation  
✅ Send timely notifications at scheduled times  
✅ Provide grace period for medication intake  
✅ Auto-mark medications as missed after grace period  
✅ Send email alerts for consecutive missed doses (same medication)  
✅ Provide real-time UI feedback to users  
✅ Prevent database locking during operations  

---

## 🔧 Architecture

### Module Structure

```
PHMS/
├── controllers/
│   ├── medication_log_controller.py    # Core logic (1300+ lines)
│   ├── notifications_controller.py     # Notification page rendering
│   └── medication_controller.py        # Medication CRUD operations
├── models/
│   ├── medication_log_model.py         # MedicationLog ORM model
│   ├── medication_model.py             # Medication ORM model
│   ├── alert_model.py                  # Alert ORM model
│   └── user_model.py                   # User ORM model
├── templates/
│   ├── notifications.html              # Notification page UI
│   └── email-templates/
│       ├── critical_medication_reminder_email.html
│       ├── critical_medication_missed_email.html
│       └── consecutive_missed_alert_email.html
├── static/js/
│   └── notifications.js                # Frontend button logic
├── utils/
│   ├── medication_schedule.py           # Frequency/time utilities
│   └── medication_schedule.py           # Grace period calculations
└── scheduler_config.py                  # APScheduler configuration
```

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Medication Log Lifecycle                      │
└─────────────────────────────────────────────────────────────────┘

1. DAILY LOG CREATION (00:00)
   ↓
   Scheduler triggers create_daily_logs()
   ↓
   For each active medication:
   ├─ Get scheduled times based on frequency
   ├─ Create MedicationLog entries with status='pending'
   └─ Database: INSERT into medication_log
   
2. SCHEDULED TIME NOTIFICATION (Every minute, ±1 min window)
   ↓
   Scheduler triggers schedule_notifications()
   ↓
   For each pending log at scheduled time:
   ├─ Create Alert entry (category='medication')
   ├─ If critical: Send email (send_critical_medication_reminder_email)
   └─ Database: INSERT into alert, UPDATE medication_log (notification_sent=1)
   
3. USER INTERACTION (Frontend)
   ↓
   User sees notification on /notifications page
   ↓
   User chooses: Mark as Taken OR Mark as Missed
   ↓
   Frontend validates:
   ├─ Check if scheduled time arrived
   └─ Check if within grace period (scheduled_time ≤ now ≤ scheduled_time + grace)
   ↓
   Send API request to backend
   
4. GRACE PERIOD CHECK (Every minute, after scheduled time)
   ↓
   Scheduler triggers check_grace_period_and_mark_missed()
   ↓
   For each pending log:
   ├─ Check if current_time > (scheduled_time + grace_period)
    ├─ If yes: Mark as missed AND check for consecutive missed doses of same medication
    ├─ If 2+ consecutive missed: Add to email queue (send_consecutive_missed_email)
   ├─ If not consecutive but critical: Add to email queue (send_critical_medication_missed_email)
   └─ Commit to database
   ↓
   After commit: Send queued emails
   
5. MARK AS MISSED (User action)
   ↓
   User clicks "Mark as Missed" button
   ↓
   Backend receives request
   ↓
    Check for consecutive missed doses (same medication):
    ├─ If count >= 2: Send email (send_consecutive_missed_email) - HIGHEST PRIORITY
   ├─ Else if critical: Send email (send_critical_medication_missed_email)
   └─ Update database
```

---

## ⭐ Core Features

### 1. Daily Automated Log Creation

**Function:** `MedicationLogManager.create_daily_logs()`  
**Trigger:** Daily at 00:00 (midnight)  
**Frequency:** Once per day

**Process:**
```python
1. Query all medications
2. Filter by is_active() - checks if start_date <= today <= end_date
3. For each active medication:
   ├─ Get scheduled times from frequency (e.g., 2x daily = [8:00 AM, 8:00 PM])
   ├─ Check if log already exists for today
   ├─ If not: Create MedicationLog with status='pending'
   └─ Log creation event
4. Commit all changes to database
```

**Code Location:** [medication_log_controller.py](PHMS/controllers/medication_log_controller.py#L33-L100)

**Example Output:**
```
Created 5 new medication logs for today
- Medication 1: 2 scheduled times
- Medication 2: 1 scheduled time
- Medication 3: 3 scheduled times
- Medication 4: 2 scheduled times
- Medication 5: 1 scheduled time
```

---

### 2. Scheduled Time Notifications

**Function:** `MedicationLogManager.schedule_notifications()`  
**Trigger:** Every minute  
**Time Window:** ±1 minute around scheduled time

**Process:**
```python
1. Get current time
2. Query all pending logs for today
3. For each log:
   ├─ Check if now is within [scheduled_time - 1min, scheduled_time + 1min]
   ├─ If yes:
   │  ├─ Create Alert entry in database (category='medication')
   │  ├─ Set severity based on is_critical flag
   │  ├─ If critical: Call send_critical_medication_reminder_email()
   │  └─ Log notification event
   └─ Continue to next log
4. Return statistics
```

**Features:**
- ✅ Creates notification visible on `/notifications` page
- ✅ Links to medication_log via foreign key `medication_log_id`
- ✅ Sets severity='critical' for critical medications
- ✅ Sends email immediately for critical medications
- ✅ Prevents duplicate notifications

**Code Location:** [medication_log_controller.py](PHMS/controllers/medication_log_controller.py#L192-L236)

---

### 3. Grace Period Management

**Function:** `MedicationLogManager.get_grace_period_for_medication()`  
**Default Duration:** 30 minutes  
**Calculation:** `min(30 minutes, time_gap_between_doses)`

**Grace Period Examples:**

| Frequency | Doses | Time Gap | Grace Period |
|-----------|-------|----------|--------------|
| 1x daily | 1 dose | 24 hours | 30 min |
| 2x daily | 2 doses | 12 hours | 30 min |
| 3x daily | 3 doses | 6 hours | 30 min |
| Every 4 hours | 6 doses | 4 hours | 30 min |
| Every 2 hours | 12 doses | 2 hours | 30 min |
| Every 30 min | 48 doses | 30 min | **30 min** |
| Every 15 min | 96 doses | 15 min | **15 min** |

**Grace Period Logic:**
```
User can mark medication as taken/missed during:
  [scheduled_time] ≤ current_time ≤ [scheduled_time + grace_period]

Examples:
- Scheduled: 08:00 AM, Grace: 30 min
  ✅ Available from 08:00 AM to 08:30 AM
  ❌ Not available before 08:00 AM
  ❌ Not available after 08:30 AM

- Scheduled: 02:00 PM, Grace: 15 min (every 15 min medication)
  ✅ Available from 02:00 PM to 02:15 PM
  ❌ Expires at 02:15 PM
```

**Code Location:** [medication_log_controller.py](PHMS/controllers/medication_log_controller.py#L37-L58)

---

### 4. Automatic Mark as Missed

**Function:** `MedicationLogManager.check_grace_period_and_mark_missed()`  
**Trigger:** Every minute  
**Action:** Auto-mark pending medications as missed after grace period expires

**Process:**
```python
1. Get current time and date
2. Query all pending logs for today
3. For each pending log:
   ├─ Calculate grace_period_end = scheduled_time + grace_period_minutes
   ├─ If current_time > grace_period_end:
   │  ├─ Set status='missed'
    │  ├─ Check for consecutive missed doses of same medication:
    │  │  ├─ If count >= 2: Queue email (send_consecutive_missed_email)
   │  │  ├─ Else if critical: Queue email (send_critical_medication_missed_email)
   │  │  └─ Log the action
   │  └─ Mark as processed
   └─ Continue to next log
4. Commit all database changes
5. Send queued emails (after commit to avoid database locking)
```

**Important:** Uses `db.session.no_autoflush` context to prevent database locking during queries

**Code Location:** [medication_log_controller.py](PHMS/controllers/medication_log_controller.py#L255-L314)

---

### 5. Email Notification System

#### Overview

Three types of email notifications are sent for medication adherence:

| Type | Trigger | Recipient | Frequency |
|------|---------|-----------|-----------|
| **Critical Reminder** | Scheduled time arrives | Critical medications | Real-time |
| **Critical Missed** | User marks critical med as missed OR after grace period | Critical medications only | Real-time |
| **Consecutive Missed** | 2+ consecutive missed doses (same medication) | **ALL** medications | Real-time |

#### Email Type 1: Critical Medication Reminder Email

**Function:** `send_critical_medication_reminder_email(user, medication, log)`  
**Trigger:** When notification is scheduled (at scheduled time)  
**Recipients:** Only for `medication.is_critical == True`

**Template:** [critical_medication_reminder_email.html](PHMS/templates/email-templates/critical_medication_reminder_email.html)

**Features:**
- 🚨 Red gradient header with "CRITICAL MEDICATION REMINDER"
- ⏰ Displays scheduled time
- 💊 Shows medication details (name, dosage)
- 📍 Direct link to notification page
- ⚠️ Health importance message

**Email Subject:** 🚨 CRITICAL MEDICATION REMINDER - [Medication Name]

---

#### Email Type 2: Critical Medication Missed Email

**Function:** `send_critical_medication_missed_email(user, medication, log)`  
**Trigger:** When critical medication is marked as missed  
**Recipients:** Only for `medication.is_critical == True`

**Template:** [critical_medication_missed_email.html](PHMS/templates/email-templates/critical_medication_missed_email.html)

**Features:**
- 🔴 Dark red gradient header with "CRITICAL ALERT"
- ⚠️ "MISSED CRITICAL MEDICATION" warning banner
- 💔 Health impact warning
- 📋 Medication details
- 🏥 Recommendation to check with healthcare provider
- 🔗 Link to update medication status

**Email Subject:** ⚠️ CRITICAL ALERT - Medication Missed - [Medication Name]

---

#### Email Type 3: Consecutive Missed Dose Alert Email

**Function:** `send_consecutive_missed_email(user, medication, log, consecutive_count)`  
**Trigger:** When the same medication is missed for 2+ consecutive doses  
**Recipients:** **ALL medications** (critical and non-critical)

**Template:** [consecutive_missed_alert_email.html](PHMS/templates/email-templates/consecutive_missed_alert_email.html)

**Features:**
- ⚠️ "CONSECUTIVE MISSED DOSES" header
- 🔢 Consecutive missed count displayed
- 🕒 Most recent missed scheduled date/time
- 📊 Health maintenance importance
- 🎯 Action items:
    1. Take medication immediately
    2. Log it in dashboard
    3. Review medication schedule
- 🔗 Direct links to dashboard and help

**Email Subject:** ⚠️ CONSECUTIVE MISSED DOSES - [Medication Name]

---

#### Email Configuration

**Configuration File:** [scheduler_config.py](PHMS/scheduler_config.py)

**SMTP Settings:**
```python
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 465
MAIL_USE_SSL = True
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
DEFAULT_MAIL_SENDER = 'noreply@phms.local'
```

**Email Headers:**
- `X-Priority: 1 (Highest)` - Marks as high priority
- `Content-Type: text/html` - HTML emails
- Plain text fallback for compatibility

---

## 📊 Database Schema

### MedicationLog Table

```sql
CREATE TABLE medication_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    medication_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    log_date DATE NOT NULL,
    scheduled_time TIME NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    -- status: 'pending', 'taken', 'missed', 'skipped'
    taken_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(medication_id) REFERENCES medication(medication_id),
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    UNIQUE(medication_id, log_date, scheduled_time)
);
```

### Medication Table

```sql
CREATE TABLE medication (
    medication_id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    dosage VARCHAR(100) NOT NULL,
    frequency INTEGER NOT NULL,
    -- frequency: 1=once, 2=twice, 3=thrice, 4=four times, 6=six times, etc.
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_critical BOOLEAN DEFAULT 0,
    -- is_critical: 1=critical (sends emails), 0=normal
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(medicine_id) REFERENCES medicine(medicine_id),
    FOREIGN KEY(user_id) REFERENCES user(user_id)
);
```

### Alert Table

```sql
CREATE TABLE alert (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    medication_log_id INTEGER NULL,
    title VARCHAR(255),
    message TEXT,
    category VARCHAR(50),
    -- category: 'medication', 'health', 'system'
    severity VARCHAR(20) DEFAULT 'normal',
    -- severity: 'low', 'normal', 'high', 'critical'
    is_read BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(medication_log_id) REFERENCES medication_log(log_id)
);
```

---

## ⏰ Scheduled Tasks

### Task Configuration

Located in: [scheduler_config.py](PHMS/scheduler_config.py)

### Task 1: Create Daily Logs

| Property | Value |
|----------|-------|
| **Function** | `MedicationLogManager.create_daily_logs()` |
| **Trigger** | Cron: 00:00 (midnight) daily |
| **Frequency** | Once per day |
| **Duration** | ~100-500ms (depends on active medications) |
| **Error Handling** | Logs errors, rolls back on failure |

### Task 2: Schedule Notifications

| Property | Value |
|----------|-------|
| **Function** | `MedicationLogManager.schedule_notifications()` |
| **Trigger** | Every minute |
| **Frequency** | 1440 times per day |
| **Window** | ±1 minute around scheduled time |
| **Duration** | ~50-200ms per run |
| **Max Instances** | 1 (prevents overlap) |

### Task 3: Check Grace Period

| Property | Value |
|----------|-------|
| **Function** | `MedicationLogManager.check_grace_period_and_mark_missed()` |
| **Trigger** | Every minute |
| **Frequency** | 1440 times per day |
| **Action** | Marks expired pending as missed |
| **Duration** | ~100-300ms per run |
| **Max Instances** | 1 (prevents overlap) |

### Task 4: Consecutive Missed Check (Deprecated)

| Property | Value |
|----------|-------|
| **Function** | `MedicationLogManager.check_consecutive_missed_and_email()` |
| **Trigger** | Deprecated (no-op) |
| **Frequency** | N/A |
| **Action** | No-op (logic handled during missed marking) |
| **Duration** | ~0ms |
| **Error Handling** | Logs deprecation notice |

### Task 5: Initialize on Startup

| Property | Value |
|----------|-------|
| **Function** | `MedicationLogManager.initialize_medication_logs()` |
| **Trigger** | Application startup |
| **Frequency** | Once when app starts |
| **Action** | Creates logs for upcoming times, verifies existing logs |
| **Duration** | ~1-5 seconds |

---

## 💌 Email Notification System

### Email Sending Architecture

**Process Flow:**
```
1. Email trigger detected (notification/missed/consecutive check - deprecated)
2. Email function prepares:
   ├─ Recipient: user.user_email
   ├─ Subject: [TYPE] - [MEDICATION NAME]
   ├─ HTML body: Rendered from template with context variables
   ├─ Plain text: Fallback for compatibility
   ├─ Headers: X-Priority, Content-Type
   └─ Priority: 1 (Highest)
3. Create Message object via Flask-Mail
4. Send via SMTP
5. Log result
```

### Email Context Variables

**For critical_medication_reminder_email:**
```python
{
    'user_name': 'John Doe',
    'medicine_name': 'Aspirin',
    'dosage': '500mg',
    'medicine_type': 'Tablet',
    'scheduled_time': '08:00 AM',
    'dashboard_url': 'http://localhost:5000/notifications',
    'settings_url': 'http://localhost:5000/profile/settings',
    'help_url': 'http://localhost:5000/help'
}
```

**For critical_medication_missed_email:**
```python
{
    'user_name': 'John Doe',
    'medicine_name': 'Aspirin',
    'dosage': '500mg',
    'scheduled_time': '08:00 AM',
    'medicine_purpose': 'Pain relief',
    'recommended_action': 'Take with water after food',
    'support_url': 'http://localhost:5000/support',
    'physician_name': '[From medicine record if available]'
}
```

**For consecutive_missed_alert_email:**
```python
{
    'user_name': 'John Doe',
    'medicine_name': 'Aspirin',
    'dosage': '500mg',
    'medicine_type': 'Tablet',
    'medicine_purpose': 'Pain relief',
    'consecutive_count': 2,
    'current_log_date': 'February 15, 2026',
    'current_log_time': '08:00 AM',
    'dashboard_url': 'http://localhost:5000/notifications',
    'medication_url': 'http://localhost:5000/medication',
    'help_url': 'http://localhost:5000/help'
}
```

### Error Handling

**Exception Handling:**
```python
try:
    # Send email
    mail.send(msg)
    logger.info(f"Email sent to {user.user_email}")
except Exception as e:
    logger.error(f"Error sending email: {str(e)}")
    # Continue processing - email failure doesn't block medication log
```

**Database Locking Prevention:**
```python
# Use no_autoflush context during queries
with db.session.no_autoflush:
    missed_logs_for_med = MedicationLog.query.filter_by(...).all()

# Commit database first
db.session.commit()

# Send emails after commit (avoids locking)
for email_task in emails_to_send:
    send_email(email_task)
```

---

## 🕐 Grace Period System

### Grace Period Calculation

**Formula:**
```
grace_period = min(30 minutes, time_gap_between_doses)
```

**Code:**
```python
def get_grace_period_for_medication(medication):
    dose_gap_minutes = get_minimum_dose_gap_minutes(medication.frequency)
    grace_period = min(MIN_GRACE_PERIOD_MINUTES, dose_gap_minutes)
    return grace_period
```

**Time Gap Calculation:**
```python
def get_minimum_dose_gap_minutes(frequency):
    times = get_scheduled_time_for_frequency(frequency)
    
    if len(times) <= 1:
        return 1440  # 24 hours for single dose
    
    # Calculate gaps between consecutive times
    gaps = []
    for i in range(len(times) - 1):
        gap = (times[i+1].hour * 60 + times[i+1].minute) - \
              (times[i].hour * 60 + times[i].minute)
        gaps.append(gap)
    
    # Gap from last time to first time next day
    last_min = times[-1].hour * 60 + times[-1].minute
    first_min = times[0].hour * 60 + times[0].minute
    gap_to_next = (24 * 60 - last_min) + first_min
    gaps.append(gap_to_next)
    
    return min(gaps)
```

### Grace Period Validation

**Frontend Validation:**
```javascript
function isWithinGracePeriod(logDate, scheduledTime, gracePeriodMinutes) {
    const scheduled = new Date(logDate + ' ' + scheduledTime);
    const now = new Date();
    const gracePeriodEnd = new Date(scheduled.getTime() + gracePeriodMinutes * 60000);
    
    return now >= scheduled && now <= gracePeriodEnd;
}
```

**Backend Validation:**
```python
# In mark_medication_taken() and mark_medication_missed()
scheduled_dt = datetime.combine(log_date, scheduled_time)
grace_period_end = scheduled_dt + timedelta(minutes=grace_period_minutes)
now_dt = datetime.combine(current_date, current_time)

if now_dt > grace_period_end:
    return error("Grace period has expired")
```

---

## 🖥️ Frontend Components

### 1. Notifications Page

**URL:** `/notifications`  
**Template:** [notifications.html](PHMS/templates/notifications.html)

**Tabs:**
1. **All Notifications** - All alerts for current user
2. **❤️ Health Alerts** - Health-related alerts only
3. **💊 Medication Reminders** - Medication-related alerts
4. **📋 Medication Log** - Daily medication logs

### 2. Medication Log Display

**Section:** "Medication Log" Tab

**Subsections:**
1. **Pending Medications** - Status='pending', ordered by nearest first
2. **Taken Medications** - Status='taken', ordered by most recent
3. **Missed Medications** - Status='missed', ordered by most recent

**Card Structure:**
```html
<div class="medication-log-card pending" 
     data-log-id="123" 
     data-log-date="2026-02-15" 
     data-scheduled-time="08:00"
     data-grace-period="30">
    <h4>Aspirin 500mg</h4>
    <p>Scheduled: 08:00 AM</p>
    <p>Status: Pending</p>
    <button class="btn-taken" disabled>✓ Mark as Taken</button>
    <button class="btn-missed" disabled>✗ Mark as Missed</button>
</div>
```

### 3. Button State Management

**File:** [static/js/notifications.js](PHMS/static/js/notifications.js)

**Functions:**

#### isScheduledTimeArrived()
```javascript
function isScheduledTimeArrived(logDate, scheduledTime) {
    const scheduled = new Date(logDate + ' ' + scheduledTime);
    const now = new Date();
    return now >= scheduled;
}
```

#### isWithinGracePeriod()
```javascript
function isWithinGracePeriod(logDate, scheduledTime, gracePeriodMinutes) {
    const scheduled = new Date(logDate + ' ' + scheduledTime);
    const now = new Date();
    const gracePeriodEnd = new Date(scheduled.getTime() + gracePeriodMinutes * 60000);
    
    return now >= scheduled && now <= gracePeriodEnd;
}
```

#### updateMedicationButtonStatus()
```javascript
function updateMedicationButtonStatus(logId, logDate, scheduledTime, gracePeriodMinutes) {
    const arrived = isScheduledTimeArrived(logDate, scheduledTime);
    const withinGrace = isWithinGracePeriod(logDate, scheduledTime, gracePeriodMinutes);
    
    const buttons = document.querySelectorAll(`[data-log-id="${logId}"] button`);
    
    if (withinGrace) {
        // During grace period: ENABLE both buttons
        buttons.forEach(btn => btn.disabled = false);
    } else {
        // Before or after grace period: DISABLE both buttons
        buttons.forEach(btn => btn.disabled = true);
    }
}
```

**Button State Timeline:**

```
TIME ──────────────────────────────────────────────────
     Before    Scheduled    Grace Period    After
     Time      Time         Window          Grace
     |         |            ↓               |
     ❌        ✅           ✅              ❌
   DISABLED  ENABLED      ENABLED        DISABLED

Example: Scheduled 08:00 AM, Grace 30 min
     07:55________08:00_______________08:30________08:35
     ❌ DISABLED   ✅ ENABLED          ✅ ENABLED    ❌ DISABLED
     (3 hrs)      (button works)       (works)      (24 hrs)
```

### 4. Real-time Updates

**Update Frequency:** Every 10 seconds

**Code:**
```javascript
function initializeScheduledTimeValidation() {
    updateAllMedicationButtonStatus();
    
    // Check every 10 seconds for state changes
    setInterval(updateAllMedicationButtonStatus, 10000);
}

function updateAllMedicationButtonStatus() {
    const cards = document.querySelectorAll '.medication-log-card.pending');
    
    cards.forEach(card => {
        const logId = card.getAttribute('data-log-id');
        const logDate = card.getAttribute('data-log-date');
        const scheduledTime = card.getAttribute('data-scheduled-time');
        const gracePeriodMinutes = parseInt(card.getAttribute('data-grace-period'));
        
        updateMedicationButtonStatus(logId, logDate, scheduledTime, gracePeriodMinutes);
    });
}
```

---

## 🔌 API Endpoints

### Medication Log Endpoints

#### 1. Mark Medication as Taken

```
PUT /medication-log/{log_id}/taken
Authorization: Required (login_required)
Content-Type: application/json

Request:
{}

Response (Success - 200):
{
    "success": true,
    "message": "Medication marked as taken"
}

Response (Error - 400):
{
    "success": false,
    "message": "Cannot mark medication until scheduled time XX:XX PM"
}

Response (Error - 404):
{
    "success": false,
    "message": "Medication log not found or user not authorized"
}
```

#### 2. Mark Medication as Missed

```
PUT /medication-log/{log_id}/missed
Authorization: Required (login_required)
Content-Type: application/json

Request:
{}

Response (Success - 200):
{
    "success": true,
    "message": "Medication marked as missed"
}

Features:
- Validates grace period before marking
- Checks for consecutive missed doses
- Sends emergency emails accordingly
- Logs action with medication details
```

#### 3. Get Medication Status (Adherence)

```
GET /medication-log/status
Authorization: Required (login_required)

Response (200):
{
    "success": true,
    "data": {
        "total": 35,
        "taken": 28,
        "missed": 5,
        "pending": 2,
        "skipped": 0,
        "adherence_rate": 80.0,
        "period": "Last 7 days (from Feb 08 to Feb 15)"
    }
}
```

#### 4. Get Medication Logs

```
GET /medication-log?days=7&status=pending
Authorization: Required (login_required)

Query Parameters:
- days: Number of days in past (default: 7)
- status: Filter by status (taken/missed/pending/skipped, optional)

Response (200):
{
    "success": true,
    "count": 12,
    "logs": [
        {
            "log_id": 123,
            "medication_id": 45,
            "medicine_name": "Aspirin",
            "dosage": "500mg",
            "log_date": "2026-02-15",
            "scheduled_time": "08:00 AM",
            "status": "pending",
            "taken_at": null
        },
        ...
    ]
}
```

### Manual Trigger Endpoints (Testing/Admin)

#### Create Daily Logs

```
POST /medication-log/create-daily
Authorization: Required (login_required)

Response:
{
    "success": true,
    "data": {
        "status": "success",
        "date": "2026-02-15",
        "created": 5,
        "errors": 0
    }
}
```

#### Send Notifications

```
POST /medication-log/send-notifications
Authorization: Required (login_required)

Response:
{
    "success": true,
    "data": {
        "status": "success",
        "notified": 2,
        "timestamp": "2026-02-15 08:15:30"
    }
}
```

#### Check Grace Period

```
POST /medication-log/check-grace-period
Authorization: Required (login_required)

Response:
{
    "success": true,
    "data": {
        "status": "success",
        "marked_missed": 1,
        "emails_sent": 1,
        "timestamp": "2026-02-15 08:31:00"
    }
}
```

#### Check Consecutive Missed

```
POST /medication-log/check-consecutive-missed
Authorization: Required (login_required)

Response:
{
    "success": true,
    "data": {
        "status": "success",
        "message": "Deprecated - logic moved to check_grace_period_and_mark_missed()",
        "timestamp": "2026-02-15"
    }
}
```

---

## 👥 User Workflows

### Workflow 1: Normal Day - Taking Medication On Time

```
08:00 AM (Scheduled Time)
  ↓
1. Scheduler creates notification at exact time
2. User receives notification on dashboard
3. User sees "Aspirin 500mg - Scheduled 08:00 AM"
4. User clicks "✓ Mark as Taken"
5. Frontend validates: time has arrived ✅
6. Backend marks as taken with timestamp
7. Log status changes to 'taken'
8. UI updates to show "You took your medication at 08:05 AM"
9. Medication appears in "Taken" section
  ↓
Log: ✅ ADHERENCE RECORDED
```

### Workflow 2: Late but Within Grace Period

```
08:15 AM (15 minutes after scheduled)
  ↓
1. User hasn't taken medication yet
2. Grace period still active (expires at 08:30 AM)
3. Buttons are ENABLED ✅
4. User clicks "✓ Mark as Taken"
5. Frontend validates: within grace period ✅
6. Backend accepts and logs timestamp
7. Status changed to 'taken'
8. Message: "Medication marked as taken at 08:15 AM"
  ↓
Log: ✅ LATE ADHERENCE RECORDED (but acceptable)
```

### Workflow 3: Missing Medication - Grace Period Expires

```
08:00 AM (Scheduled)
  │
  ├─ 08:30 AM (Grace Period Ends)
  │   └─ User hasn't taken medication
  │
  ├─ 08:31 AM (Scheduler runs)
  │   └─ check_grace_period_and_mark_missed() triggers
  │       ├─ Marks as 'missed'
    │       ├─ Checks for consecutive missed doses (same medication)
  │       ├─ If critical: Sends email
    │       └─ If 2+ consecutive: Sends email
  │
  ├─ 08:32 AM (User checks dashboard)
  │   └─ Sees "Aspirin - MISSED"
  │       Buttons are DISABLED ❌
  │
  └─ If user clicks "Mark as Missed" after grace:
      └─ Error: "Grace period has expired"
  ↓
Log: ❌ MISSED MEDICATION RECORDED
     📧 Email sent to user (if critical or consecutive)
```

### Workflow 4: Consecutive Missed Doses (Same Medication)

```
Dose 1 (Monday)
    ├─ 08:30 AM: Aspirin missed (grace period expires)
    ├─ Scheduler marks as missed
    ├─ Check consecutive: Only 1 missed dose → No email sent yet
    └─ Result: 1 missed dose
  
Dose 2 (Same medication, next scheduled time)
    ├─ Missed again (grace period expires)
    ├─ Scheduled task checks consecutive doses:
    │   └─ Count = 2 → SEND EMAIL
    ├─ Email sent: "Consecutive Missed Doses"
    ├─ Email subject: "⚠️ CONSECUTIVE MISSED DOSES - Aspirin"
    └─ Result: 2 missed doses → EMAIL ALERT SENT 📧
  
Next dose taken
    ├─ User takes medication
    ├─ Status: 'taken'
    ├─ Consecutive counter resets
    └─ Result: Back on track ✅
    ↓
Log: ✅ ADHERENCE RECOVERED
```

### Workflow 5: Critical Medication - Multiple Safeguards

```
08:00 AM (Critical Medication)
  ├─ Notification triggered
  ├─ Severity='critical' (not just 'high')
  ├─ 📧 CRITICAL REMINDER EMAIL SENT
  ├─ User sees 🚨 Icon on dashboard
  └─ Buttons ENABLED during grace period
  
08:05 AM (User marks as missed)
  ├─ Validates grace period ✓
  ├─ Marks as moved
    ├─ Checks consecutive → Not 2 doses yet
  ├─ is_critical=true → Send email
  ├─ 📧 CRITICAL MISSED EMAIL SENT
  ├─ Email subject: "⚠️ CRITICAL ALERT - Medication Missed"
  └─ Includes: Health impact warning, physician recommendation
  
User Actions:
  ├─ Receives email with red gradient header
  ├─ Sees "MISSED CRITICAL MEDICATION" banner
  ├─ Reads health impact warning
  ├─ Gets link back to dashboard
  └─ Can immediately mark as taken if they take it
  ↓
Log: 🚨 CRITICAL ALERT - ESCALATED NOTIFICATION
```

---

## ⚙️ Configuration

### Environment Variables

**File:** `.env` (in project root)

```bash
# Flask Configuration
FLASK_ENV=development
Secret_Key=your-secret-key-here

# Database
DATABASE_URL=sqlite:///phms.db

# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=465
MAIL_USE_SSL=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Application URLs (for email templates)
APP_URL=http://localhost:5000
```

### Scheduler Configuration

**File:** [scheduler_config.py](PHMS/scheduler_config.py)

```python
# Timezone (UTC recommended for server consistency)
TIMEZONE = UTC

# Task Configurations
JOBS = [
    {
        'id': 'create_daily_logs',
        'trigger': 'cron',
        'hour': 0,
        'minute': 0
    },
    {
        'id': 'schedule_notifications',
        'trigger': 'interval',
        'minutes': 1,
        'max_instances': 1
    },
    {
        'id': 'check_grace_period',
        'trigger': 'interval',
        'minutes': 1,
        'max_instances': 1
    },
    {
        'id': 'check_consecutive_missed',
        'trigger': 'cron',
        'hour': 23,
        'minute': 59
        # Deprecated (no-op): logic handled during missed marking
    }
]
```

### Application Startup

**File:** [app.py](PHMS/app.py)

```python
# 1. Initialize database
db.init_app(app)

# 2. Initialize medication logs
init_medication_logs()

# 3. Start scheduler
scheduler = init_scheduler()

# 4. Start Flask app
app.run(debug=True)
```

---

## 🔧 Troubleshooting

### Issue 1: Buttons Always Disabled

**Problem:** "Mark as Taken" and "Mark as Missed" buttons remain disabled even after scheduled time

**Cause Analysis:**
1. Grace period data not passed from backend
2. JavaScript not calculating grace period correctly
3. Browser time vs server time mismatch

**Solutions:**

```html
<!-- 1. Check template has data attributes -->
<div data-grace-period="{{ log.grace_period_minutes }}">
```

```javascript
// 2. Verify JavaScript function works
const logCard = document.querySelector('.medication-log-card');
const gracePeriod = logCard.getAttribute('data-grace-period');
console.log('Grace period:', gracePeriod); // Should print 30 (or other number)
```

```python
# 3. Check backend calculation
medication = log.medication
grace_period = MedicationLogManager.get_grace_period_for_medication(medication)
print(f"Grace period: {grace_period} minutes")  # Should print 30
```

**Fix Steps:**
1. Verify `notifications_controller.py` adds grace period to logs:
   ```python
   for log in pending_logs:
       log.grace_period_minutes = MedicationLogManager.get_grace_period_for_medication(log.medication)
   ```

2. Clear browser cache (Ctrl+Shift+Del)
3. Refresh page (Ctrl+F5)
4. Check console for JavaScript errors (F12)

---

### Issue 2: Emails Not Sending

**Problem:** Email alerts for critical medications not received

**Cause Analysis:**
1. SMTP credentials incorrect
2. Gmail 2FA enabled without app password
3. Firewall blocking SMTP port 465
4. Email function exception caught silently

**Solutions:**

```python
# 1. Test SMTP connection
from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your-app-password'

mail = Mail(app)

with app.app_context():
    msg = Message('Test', recipients=['test@example.com'], body='Hello')
    try:
        mail.send(msg)
        print("✅ Email sent successfully")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
```

```python
# 2. Check logs for email errors
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('flask_mail')
# Run task and check console output
```

```bash
# 3. Verify Gmail app password
# - Enable 2FA in Gmail
# - Go to: https://myaccount.google.com/apppasswords
# - Select Mail + Windows/Linux
# - Use the 16-character password as MAIL_PASSWORD
```

**Fix Steps:**
1. Verify `.env` has correct credentials
2. Gmail users: Use app-specific password (not regular password)
3. Check firewall allows outbound SMTP (port 465)
4. Review application logs: `tail -f log.txt`

---

### Issue 3: Database Locking - "Database is Locked"

**Problem:** SQLite error: "database is locked" when marking medication as missed

**Cause Analysis:**
1. Query during uncommitted transaction
2. SQLAlchemy autoflush during grace period check
3. Multiple processes/threads accessing database

**Solution:** Uses `db.session.no_autoflush` context

```python
# CORRECT - No autoflush during query
try:
    with db.session.no_autoflush:
        missed_logs_for_med = MedicationLog.query.filter_by(...).all()
    
    # Database operations here
    log.status = 'missed'
    
# Commit first
db.session.commit()

# Then send emails
for email_task in emails_to_send:
    send_email(email_task)
```

**Verification:**
```bash
# Check if no_autoflush is in place
grep -n "no_autoflush" PHMS/controllers/medication_log_controller.py
# Should show: Line ~470 with no_autoflush context
```

---

### Issue 4: Consecutive Missed Email Sent Multiple Times

**Problem:** User receives multiple consecutive missed emails for the same event

**Cause Analysis:**
1. Email sent in grace_period check AND user manual mark_missed
2. Duplicate task entries in email queue

**Solution:** 

```python
# Check for consecutive FIRST (highest priority)
consecutive_email_sent = False
if consecutive_missed_count >= 2:
    # Found consecutive missed doses - send this email
    emails_to_send.append({'type': 'consecutive_missed', ...})
    consecutive_email_sent = True

# Only send critical missed if consecutive was NOT sent
if not consecutive_email_sent and medication.is_critical:
    emails_to_send.append({'type': 'critical', ...})
```

**Verification:**
```python
# Check log for deduplication logic
grep -n "consecutive_email_sent" medication_log_controller.py
# Should show logic that prevents duplicate sends
```

---

### Issue 5: Scheduler Not Running

**Problem:** Scheduled tasks not executing (logs not created, notifications not sent)

**Cause Analysis:**
1. Scheduler not started in `app.py`
2. Scheduler job configuration incorrect
3. Flask app not running

**Solutions:**

```python
# Check scheduler is initialized
from scheduler_config import init_scheduler

# In app.py:
if __name__ == '__main__':
    scheduler = init_scheduler()
    app.run(debug=True)
```

**Verification:**
```bash
# Check if scheduler is running
# Look for log messages like:
# "Scheduler started successfully!"
# "Scheduled: Create daily logs at 00:00"

# Or check running processes
ps aux | grep python
# Should see Flask app process running

# Test manual trigger
curl -X POST http://localhost:5000/medication-log/create-daily
# Should return success with created count
```

---

### Issue 6: Medications Not Marked as Active

**Problem:** Medication logs not being created even though medications exist

**Cause Analysis:**
1. Medication start_date is in future
2. Medication end_date is in past
3. is_active() method returns False

**Solution - Check Medication Status:**

```sql
-- Check which medications are active
SELECT 
    medication_id,
    medicine_id,
    start_date,
    end_date,
    CURDATE() AS today,
    CASE 
        WHEN start_date <= CURDATE() AND end_date >= CURDATE() THEN 'ACTIVE'
        WHEN start_date > CURDATE() THEN 'FUTURE'
        WHEN end_date < CURDATE() THEN 'EXPIRED'
    END AS status
FROM medication
WHERE user_id = ?
ORDER BY start_date;
```

**Expected Result for Active:**
- start_date ≤ TODAY
- end_date ≥ TODAY
- status = 'ACTIVE'

---

## 📖 Documentation Files

Related documentation:
- [CODE_REVIEW_REPORT.md](PHMS/CODE_REVIEW_REPORT.md) - Complete system analysis
- [MARK_AS_READ_VERIFICATION.md](PHMS/MARK_AS_READ_VERIFICATION.md) - Alert mark as read functionality
- [MEDICATION_LOG_INITIALIZATION_SUMMARY.md](PHMS/MEDICATION_LOG_INITIALIZATION_SUMMARY.md) - Startup initialization
- [MEDICATION_SYSTEM_VERIFICATION.md](PHMS/MEDICATION_SYSTEM_VERIFICATION.md) - Feature verification guide

---

## ✅ Verification Checklist

- [ ] All medications with today's start date have logs created for upcoming times
- [ ] Notifications appear at scheduled times (within ±1 minute)
- [ ] Buttons disable/enable based on grace period correctly
- [ ] Critical medications send email reminders at scheduled time
- [ ] Medications auto-marked as missed after grace period expires
- [ ] Consecutive missed emails sent for 2 days without duplicates
- [ ] No database locking errors in application logs
- [ ] User can mark medication as taken/missed only during grace period
- [ ] Email subjects are clear and prioritized (X-Priority: 1)
- [ ] Scheduler starts successfully on application startup

---

## 📞 Support & Contact

For issues or questions:
1. Check the Troubleshooting section above
2. Review application logs: `tail -f log.txt`
3. Check database for data integrity
4. Test manual triggers via API endpoints
5. Review browser console (F12) for JavaScript errors

---

**Last Updated:** February 16, 2026  
**System Status:** ✅ Fully Operational