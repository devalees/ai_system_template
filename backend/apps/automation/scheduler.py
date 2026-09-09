"""
Celery Beat Scheduling Synchronization for Automation Engine.

Bridges AutomationTrigger time-based triggers with django-celery-beat
PeriodicTask, IntervalSchedule, CrontabSchedule, and ClockedSchedule.
"""

import json
from typing import Optional
from django_celery_beat.models import (
    PeriodicTask,
    IntervalSchedule,
    CrontabSchedule,
    ClockedSchedule,
)


def sync_trigger_to_celery_beat(trigger) -> Optional[PeriodicTask]:
    """
    Synchronizes an AutomationTrigger's time-based scheduling into Celery Beat.
    """
    if trigger.trigger_type != 'time_based':
        if trigger.periodic_task:
            task = trigger.periodic_task
            trigger.periodic_task = None
            trigger.__class__.objects.filter(id=trigger.id).update(periodic_task=None)
            try:
                task.delete()
            except Exception:
                pass
        return None

    task_name = f"automation_trigger_{trigger.id}_{trigger.name[:50]}"
    task_args = json.dumps([trigger.id])
    task_path = "apps.automation.tasks.scheduled_run"

    # 1. One-Shot Scheduled Time
    if trigger.execution_mode == 'once' and trigger.scheduled_time:
        clocked, _ = ClockedSchedule.objects.get_or_create(clocked_time=trigger.scheduled_time)
        periodic_task, _ = PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                'task': task_path,
                'args': task_args,
                'clocked': clocked,
                'one_off': True,
                'enabled': trigger.is_active,
                'description': f"One-shot schedule for AutomationTrigger #{trigger.id}: {trigger.name}",
            }
        )
    # 2. Monthly Crontab Schedule
    elif trigger.schedule_unit == 'months':
        interval_val = trigger.schedule_value or 1
        month_expr = f"*/{interval_val}" if interval_val > 1 else "*"
        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='0',
            day_of_month='1',
            month_of_year=month_expr,
            day_of_week='*'
        )
        periodic_task, _ = PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                'task': task_path,
                'args': task_args,
                'crontab': crontab,
                'enabled': trigger.is_active,
                'description': f"Monthly schedule for AutomationTrigger #{trigger.id}: {trigger.name}",
            }
        )
    # 3. Interval Schedule (seconds, minutes, hours, days, weeks)
    else:
        unit = trigger.schedule_unit or 'minutes'
        val = trigger.schedule_value or 5

        if unit == 'seconds':
            period = IntervalSchedule.SECONDS
        elif unit == 'minutes':
            period = IntervalSchedule.MINUTES
        elif unit == 'hours':
            period = IntervalSchedule.HOURS
        elif unit == 'days':
            period = IntervalSchedule.DAYS
        elif unit == 'weeks':
            period = IntervalSchedule.DAYS
            val = val * 7
        else:
            period = IntervalSchedule.MINUTES

        interval, _ = IntervalSchedule.objects.get_or_create(every=val, period=period)
        periodic_task, _ = PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                'task': task_path,
                'args': task_args,
                'interval': interval,
                'enabled': trigger.is_active,
                'description': f"Periodic schedule for AutomationTrigger #{trigger.id}: {trigger.name}",
            }
        )

    if trigger.periodic_task_id != periodic_task.id:
        trigger.__class__.objects.filter(id=trigger.id).update(periodic_task=periodic_task)
        trigger.periodic_task = periodic_task

    return periodic_task


def delete_trigger_periodic_task(trigger):
    """Cleans up Celery Beat periodic task when trigger is deleted."""
    if trigger.periodic_task:
        try:
            trigger.periodic_task.delete()
        except Exception:
            pass


# Backward-compatibility aliases
sync_rule_to_celery_beat = sync_trigger_to_celery_beat
delete_rule_periodic_task = delete_trigger_periodic_task
