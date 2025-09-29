from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import SpeechSession

User = get_user_model()


class SpeechSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for SpeechSession model with comprehensive field handling.
    
    This serializer handles both read and write operations for the API,
    including user assignment and validation.
    """
    
    # Read-only fields for additional information
    user_email = serializers.EmailField(source='user.email', read_only=True)
    duration_minutes = serializers.CharField(read_only=True)
    filler_rate = serializers.FloatField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # File field with custom representation
    audio_file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = SpeechSession
        fields = [
            'id',
            'user',
            'user_email',
            'date',
            'duration',
            'duration_minutes',
            'filler_count',
            'filler_rate',
            'pacing_analysis',
            'status',
            'status_display',
            'audio_file',
            'audio_file_url',
            'transcription',
            'confidence_score',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'date', 'created_at', 'updated_at']
        
    def get_audio_file_url(self, obj):
        """Return the full URL for the audio file if it exists."""
        if obj.audio_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.audio_file.url)
            return obj.audio_file.url
        return None
    
    def validate_duration(self, value):
        """Validate that duration is positive."""
        if value <= 0:
            raise serializers.ValidationError("Duration must be greater than 0 seconds.")
        return value
    
    def validate_filler_count(self, value):
        """Validate that filler count is non-negative."""
        if value < 0:
            raise serializers.ValidationError("Filler count cannot be negative.")
        return value
    
    def validate_confidence_score(self, value):
        """Validate that confidence score is between 0 and 1."""
        if value is not None and (value < 0 or value > 1):
            raise serializers.ValidationError("Confidence score must be between 0.0 and 1.0.")
        return value


class SpeechSessionCreateSerializer(serializers.ModelSerializer):
    """
    Specialized serializer for creating speech sessions.
    
    This serializer is optimized for session creation with minimal required fields
    and automatic analysis simulation.
    """
    
    class Meta:
        model = SpeechSession
        fields = [
            'duration',
            'audio_file',
            'transcription',
        ]
    
    def validate_duration(self, value):
        """Validate that duration is positive."""
        if value <= 0:
            raise serializers.ValidationError("Duration must be greater than 0 seconds.")
        return value
    
    def create(self, validated_data):
        """Create a speech session with simulated analysis."""
        # Add user from request context
        request = self.context.get('request')
        if request and request.user:
            validated_data['user'] = request.user
        
        # Create the session
        session = SpeechSession.objects.create(**validated_data)
        
        # Simulate analysis if audio file is provided
        if session.audio_file:
            session.filler_count = 5  # Simulated
            session.pacing_analysis = "Simulated analysis: Good pacing with occasional slow segments. Average speaking rate detected."
            session.confidence_score = 0.85  # Simulated
            session.status = 'analyzed'
            session.save()
        
        return session


class SpeechSessionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing speech sessions.
    
    This serializer includes only essential fields for list views
    to improve performance.
    """
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    duration_minutes = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = SpeechSession
        fields = [
            'id',
            'user_email',
            'date',
            'duration',
            'duration_minutes',
            'filler_count',
            'status',
            'status_display',
            'confidence_score',
        ]


class SpeechSessionAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for speech session analytics data.
    
    This serializer handles aggregated analytics data
    that doesn't correspond to a specific model.
    """
    
    total_sessions = serializers.IntegerField()
    total_duration = serializers.IntegerField()
    average_duration = serializers.FloatField()
    total_filler_words = serializers.IntegerField()
    average_filler_rate = serializers.FloatField()
    sessions_by_status = serializers.DictField()
    recent_sessions_count = serializers.IntegerField()
    improvement_metrics = serializers.DictField(required=False)

