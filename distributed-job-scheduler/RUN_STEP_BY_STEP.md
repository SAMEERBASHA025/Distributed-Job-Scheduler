# Run Step By Step

Follow these steps exactly from the beginning.

## 1. Open PowerShell

Open Windows PowerShell.

## 2. Go To Project Folder

```powershell
cd C:\Users\ASUA\Documents\Codex\2026-07-04\intern-assignment-distributed-job-scheduler-objective\outputs\distributed-job-scheduler
```

## 3. Initialize Database

```powershell
python -m app.main --init-db --seed
```

This creates `scheduler.db` and demo data.

## 4. Start Server

```powershell
python -m app.main --serve
```

Keep this terminal open.

Open the browser:

```text
http://127.0.0.1:8000
```

If the page was already open, press:

```text
Ctrl + F5
```

## 5. Sign In With Demo Account

Choose:

```text
Sign in
```

Use:

```text
Email: demo@example.com
Password: demo-password
```

Click `Sign in`.

## 6. Sign Up New Account

Choose:

```text
Sign up
```

Use a fresh email every time, for example:

```text
Email: student2@example.com
Password: student123
Display name: Sameer Basha
Organization name: Student Org
```

Click `Sign up`.

If you see:

```text
email already registered
```

then either choose `Sign in` or use another new email like `student3@example.com`.

## 7. Start Worker

Open a second PowerShell window.

```powershell
cd C:\Users\ASUA\Documents\Codex\2026-07-04\intern-assignment-distributed-job-scheduler-objective\outputs\distributed-job-scheduler
python -m app.worker --worker-name worker-a
```

Keep this worker terminal open.

## 8. Create Immediate Job

In the dashboard:

```text
Queue: emails
Type: send_email
Priority: 100
Schedule At: leave empty
```

Payload JSON:

```json
{"to":"customer@example.com","duration_seconds":0.5}
```

Click:

```text
Create Job
```

You should see:

```text
Job created successfully
```

If worker is running, the job may quickly move to `Completed`.

## 9. Create Scheduled Job

Use a full date-time in `Schedule At`.

Example:

```text
2026-07-04T12:30:00+05:30
```

Do not type only `12`.

## 10. See Jobs

In the `Jobs` dropdown choose:

```text
All
```

or:

```text
Completed
```

Click `Logs` beside a job to see lifecycle logs.

## 11. Run Tests

Open another PowerShell window.

```powershell
cd C:\Users\ASUA\Documents\Codex\2026-07-04\intern-assignment-distributed-job-scheduler-objective\outputs\distributed-job-scheduler
python -m unittest discover -s tests
```

Expected result:

```text
Ran 6 tests
OK
```

## 12. Stop Application

In server terminal:

```text
Ctrl + C
```

In worker terminal:

```text
Ctrl + C
```
