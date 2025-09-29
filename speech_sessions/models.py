from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

User = get_user_model()


class SpeechSession(models.Model):
    """
    Model to store speech session records with analysis data.
    
    This model tracks user speech sessions including duration, filler count,
    pacing analysis, and processing status for the verbal coaching system.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('analyzed', 'Analyzed'),
        ('archived', 'Archived'),
    ]
    
    # Core fields
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='speech_sessions',
        help_text="User who owns this speech session"
    )
    date = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when the session was created"
    )
    duration = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Duration of the speech session in seconds"
    )
    filler_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of filler words detected (e.g., 'um', 'uh', 'like')"
    )
    pacing_analysis = models.TextField(
        blank=True,
        help_text="Analysis of speaking pace and rhythm patterns"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Processing status of the speech session"
    )
    
    # Additional metadata
    audio_file = models.FileField(
        upload_to='speech_sessions/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text="Original audio file for the speech session"
    )
    transcription = models.TextField(
        blank=True,
        help_text="Transcribed text from the speech session"
    )
    confidence_score = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0.0)],
        help_text="Overall confidence score for the analysis (0.0-1.0)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Speech Session'
        verbose_name_plural = 'Speech Sessions'
        indexes = [
            models.Index(fields=['user', '-date']),
            models.Index(fields=['status']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"Session {self.id} - {self.user.email} ({self.date.strftime('%Y-%m-%d %H:%M')})"
    
    @property
    def duration_minutes(self):
        """Return duration in minutes as a formatted string."""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"
    
    @property
    def filler_rate(self):
        """Calculate filler words per minute."""
        if self.duration == 0:
            return 0
        return (self.filler_count / self.duration) * 60
    
    def get_status_display_class(self):
        """Return CSS class for status display."""
        status_classes = {
            'pending': 'bg-yellow-100 text-yellow-800',
            'analyzed': 'bg-green-100 text-green-800',
            'archived': 'bg-gray-100 text-gray-800',
        }
        return status_classes.get(self.status, 'bg-gray-100 text-gray-800')