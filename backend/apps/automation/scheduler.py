"""
Celery Beat Scheduling Synchronization for Automation Engine.

Bridges AutomationRule time-based triggers with django-celery-beat
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


def sync_rule_to_celery_beat(rule) -> Optional[PeriodicTask]:
    """
    Synchronizes an AutomationRule's time-based scheduling into Celery Beat.
    """
    if rule.trigger_type != 'time_based':
        if rule.periodic_task:
            task = rule.periodic_task
            rule.periodic_task = None
            rule.__class__.objects.filter(id=rule.id).update(periodic_task=None)
            try:
                task.delete()
            except Exception:
                pass
        return None

    task_name = f"automation_rule_{rule.id}_{rule.name[:50]}"
    task_args = json.dumps([rule.id])
    task_path = "apps.automation.tasks.scheduled_run"

    # 1. One-Shot Scheduled Time
    if rule.execution_mode == 'once' and rule.scheduled_time:
        clocked, _ = ClockedSchedule.objects.get_or_create(clocked_time=rule.scheduled_time)
        periodic_task, _ = PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                'task': task_path,
                'args': task_args,
                'clocked': clocked,
                'one_off': True,
                'enabled': rule.is_active,
                'description': f"One-shot schedule for AutomationRule #{rule.id}: {rule.name}",
            }
        )
    # 2. Monthly Crontab Schedule
    elif rule.schedule_unit == 'months':
        interval_val = rule.schedule_value or 1
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
                'enabled': rule.is_active,
                'description': f"Monthly schedule for AutomationRule #{rule.id}: {rule.name}",
            }
        )
    # 3. Interval Schedule (seconds, minutes, hours, days, weeks)
    else:
        unit = rule.schedule_unit or 'minutes'
        val = rule.schedule_value or 5

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
                'enabled': rule.is_active,
                'description': f"Periodic schedule for AutomationRule #{rule.id}: {rule.name}",
            }
        )

    if rule.periodic_task_id != periodic_task.id:
        rule.__class__.objects.filter(id=rule.id).update(periodic_task=periodic_task)
        rule.periodic_task = periodic_task

    return periodic_task


def delete_rule_periodic_task(rule):
    """Cleans up Celery Beat periodic task when rule is deleted."""
    if rule.periodic_task:
        try:
            rule.periodic_task.delete()
        except Exception:
            pass
