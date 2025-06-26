# D:\GrowthFlow\feedback_app\models.py

from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('manager', 'Manager'),
        ('employee', 'Employee'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='employee')
    # Manager field: an employee can have one manager. A manager can have many employees.
    manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL, # If manager is deleted, employee's manager field becomes NULL
        null=True, blank=True,
        related_name='employees', # A manager can access their 'employees'
        limit_choices_to={'role': 'manager'} # Only managers can be selected as managers
    )

    def __str__(self):
        return f"{self.username} ({self.role})"


class Feedback(models.Model):
    # The manager who GAVE the feedback
    manager = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='feedback_given', # Manager can see 'feedback_given' by them
        limit_choices_to={'role': 'manager'}
    )
    # The employee who RECEIVED the feedback
    employee = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='feedback_received', # Employee can see 'feedback_received' by them
        limit_choices_to={'role': 'employee'}
    )
    strengths = models.TextField()
    areas_to_improve = models.TextField()
    sentiment = models.CharField(max_length=50, blank=True, null=True) # Optional field
    is_acknowledged = models.BooleanField(default=False) # Employee acknowledges feedback
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at'] # Order by most recent feedback first

    def __str__(self):
        return f"Feedback from {self.manager.username} to {self.employee.username} on {self.created_at.strftime('%Y-%m-%d')}"

# --- NEW MODEL: Comment on Feedback ---
class Comment(models.Model):
    feedback = models.ForeignKey(
        Feedback,
        on_delete=models.CASCADE,
        related_name='comments' # Feedback can have many comments
    )
    author = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='comments_made' # User can make many comments
    )
    content = models.TextField()
    # Flag for Markdown support (will be true if content is markdown)
    is_markdown = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at'] # Order comments chronologically

    def __str__(self):
        return f"Comment by {self.author.username} on Feedback ID {self.feedback.id}"

# --- NEW MODEL: Feedback Request ---
class FeedbackRequest(models.Model):
    requester = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='feedback_requests_made', # Employee made this request
        limit_choices_to={'role': 'employee'}
    )
    # Manager who will provide feedback (optional, can be null if not assigned)
    target_manager = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='feedback_requests_received', # Manager received this request
        limit_choices_to={'role': 'manager'}
    )
    reason = models.TextField(
        help_text="Why are you requesting feedback? E.g., 'For my Q2 performance review.'"
    )
    is_fulfilled = models.BooleanField(default=False) # True when feedback is given for this request
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Feedback Request from {self.requester.username} to {self.target_manager.username if self.target_manager else 'Unassigned'}"

# --- NEW MODEL: Anonymous Peer Feedback ---
class PeerFeedback(models.Model):
    # The user GIVING the feedback (can be anonymous or not)
    # If is_anonymous is True, the giver's identity is hidden
    giver = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='peer_feedback_given'
    )
    # The user RECEIVING the feedback
    receiver = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='peer_feedback_received',
        limit_choices_to={'role__in': ['employee', 'manager']} # Peers can be employees or managers
    )
    feedback_text = models.TextField()
    is_anonymous = models.BooleanField(default=False) # If true, giver's identity is hidden from receiver
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Peer Feedback"

    def __str__(self):
        giver_display = "Anonymous" if self.is_anonymous else self.giver.username
        return f"Peer Feedback from {giver_display} to {self.receiver.username}"