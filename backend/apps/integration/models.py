import uuid
from django.db import models

class HandshakeLog(models.Model):
    """
    Records bidirectional connectivity and handshakes between
    external agent runtimes (e.g., Hermes) and the Django backend.
    """
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_id = models.CharField(max_length=120, default='hermes-agent')
    version = models.CharField(max_length=60, blank=True, default='unknown')
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    server_response = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Handshake Log'
        verbose_name_plural = 'Handshake Logs'

    def __str__(self):
        return f"{self.agent_id} ({self.status}) @ {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"


class AgentTask(models.Model):
    """
    Represents a task dispatched to or executed by an agent.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_name = models.CharField(max_length=120, default='hermes-agent')
    task_name = models.CharField(max_length=200)
    input_payload = models.JSONField(default=dict, blank=True)
    output_result = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Agent Task'
        verbose_name_plural = 'Agent Tasks'

    def __str__(self):
        return f"[{self.status.upper()}] {self.task_name} ({self.agent_name})"
