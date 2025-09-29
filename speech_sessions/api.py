from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Avg, Sum, Count
from django.utils import timezone
from datetime import timedelta

from .models import SpeechSession
from .serializers import (
    SpeechSessionSerializer,
    SpeechSessionCreateSerializer,
    SpeechSessionListSerializer,
    SpeechSessionAnalyticsSerializer
)


class IsOwnerPermission(permissions.BasePermission):
    """
    Custom permission to ensure users can only access their own speech sessions.
    
    This permission class integrates with the 2FA system by checking if the user
    is properly authenticated and verified.
    """
    
    def has_permission(self, request, view):
        """Check if user has permission to access the view."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check 2FA requirements if enabled
        if hasattr(request.user, 'is_2fa_enabled') and request.user.is_2fa_enabled:
            # If 2FA is enabled, user must be verified
            return request.user.is_verified()
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission to access the specific object."""
        return obj.user == request.user


class SpeechSessionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing speech sessions via REST API.
    
    This ViewSet provides full CRUD operations for speech sessions with:
    - Token-based authentication
    - User-specific filtering (users can only see their own sessions)
    - 2FA integration
    - Filtering and search capabilities
    - Custom analytics endpoint
    
    Endpoints:
    - GET /api/sessions/ - List user's sessions
    - POST /api/sessions/ - Create new session
    - GET /api/sessions/{id}/ - Retrieve specific session
    - PUT/PATCH /api/sessions/{id}/ - Update session
    - DELETE /api/sessions/{id}/ - Delete session
    - GET /api/sessions/analytics/ - Get analytics data
    """
    
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, IsOwnerPermission]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    
    # Filtering options
    filterset_fields = ['status', 'date']
    search_fields = ['transcription', 'pacing_analysis']
    ordering_fields = ['date', 'duration', 'filler_count', 'confidence_score']
    ordering = ['-date']  # Default ordering by most recent first
    
    def get_queryset(self):
        """Return sessions for the authenticated user only."""
        return SpeechSession.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on the action."""
        if self.action == 'create':
            return SpeechSessionCreateSerializer
        elif self.action == 'list':
            return SpeechSessionListSerializer
        elif self.action == 'analytics':
            return SpeechSessionAnalyticsSerializer
        return SpeechSessionSerializer
    
    def perform_create(self, serializer):
        """Save the session with the current user."""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """
        Get analytics data for the user's speech sessions.
        
        Returns aggregated data including:
        - Total sessions count
        - Total and average duration
        - Filler word statistics
        - Sessions by status
        - Recent activity metrics
        """
        sessions = self.get_queryset()
        
        # Basic counts
        total_sessions = sessions.count()
        if total_sessions == 0:
            return Response({
                'total_sessions': 0,
                'total_duration': 0,
                'average_duration': 0,
                'total_filler_words': 0,
                'average_filler_rate': 0,
                'sessions_by_status': {},
                'recent_sessions_count': 0,
            })
        
        # Duration analytics
        duration_stats = sessions.aggregate(
            total_duration=Sum('duration'),
            avg_duration=Avg('duration')
        )
        
        # Filler word analytics (only for analyzed sessions)
        analyzed_sessions = sessions.filter(status='analyzed')
        filler_stats = analyzed_sessions.aggregate(
            total_fillers=Sum('filler_count'),
            avg_fillers=Avg('filler_count')
        )
        
        # Calculate average filler rate
        avg_filler_rate = 0
        if analyzed_sessions.exists():
            total_analyzed_duration = analyzed_sessions.aggregate(
                total=Sum('duration')
            )['total']
            if total_analyzed_duration and total_analyzed_duration > 0:
                avg_filler_rate = (filler_stats['total_fillers'] or 0) / total_analyzed_duration * 60
        
        # Sessions by status
        status_counts = sessions.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        sessions_by_status = {item['status']: item['count'] for item in status_counts}
        
        # Recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_sessions_count = sessions.filter(date__gte=thirty_days_ago).count()
        
        # Improvement metrics (compare last 30 days vs previous 30 days)
        improvement_metrics = {}
        if total_sessions > 1:
            sixty_days_ago = timezone.now() - timedelta(days=60)
            
            recent_sessions = sessions.filter(date__gte=thirty_days_ago)
            previous_sessions = sessions.filter(
                date__gte=sixty_days_ago,
                date__lt=thirty_days_ago
            )
            
            if recent_sessions.exists() and previous_sessions.exists():
                recent_avg_fillers = recent_sessions.aggregate(
                    avg=Avg('filler_count')
                )['avg'] or 0
                
                previous_avg_fillers = previous_sessions.aggregate(
                    avg=Avg('filler_count')
                )['avg'] or 0
                
                if previous_avg_fillers > 0:
                    filler_improvement = (
                        (previous_avg_fillers - recent_avg_fillers) / previous_avg_fillers
                    ) * 100
                    improvement_metrics['filler_improvement_percent'] = round(filler_improvement, 2)
        
        analytics_data = {
            'total_sessions': total_sessions,
            'total_duration': duration_stats['total_duration'] or 0,
            'average_duration': round(duration_stats['avg_duration'] or 0, 2),
            'total_filler_words': filler_stats['total_fillers'] or 0,
            'average_filler_rate': round(avg_filler_rate, 2),
            'sessions_by_status': sessions_by_status,
            'recent_sessions_count': recent_sessions_count,
            'improvement_metrics': improvement_metrics,
        }
        
        return Response(analytics_data)
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        Bulk update multiple sessions.
        
        Expected payload:
        {
            "session_ids": [1, 2, 3],
            "updates": {
                "status": "archived"
            }
        }
        """
        session_ids = request.data.get('session_ids', [])
        updates = request.data.get('updates', {})
        
        if not session_ids or not updates:
            return Response(
                {'error': 'Both session_ids and updates are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Filter to user's sessions only
        sessions = self.get_queryset().filter(id__in=session_ids)
        
        if not sessions.exists():
            return Response(
                {'error': 'No valid sessions found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate updates
        allowed_fields = ['status', 'pacing_analysis', 'filler_count', 'confidence_score']
        invalid_fields = set(updates.keys()) - set(allowed_fields)
        
        if invalid_fields:
            return Response(
                {'error': f'Invalid fields for bulk update: {list(invalid_fields)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Perform bulk update
        updated_count = sessions.update(**updates)
        
        return Response({
            'success': True,
            'updated_count': updated_count,
            'message': f'{updated_count} session(s) updated successfully'
        })
    
    @action(detail=True, methods=['post'])
    def reanalyze(self, request, pk=None):
        """
        Trigger re-analysis of a speech session.
        
        This is a placeholder endpoint that simulates re-running
        the speech analysis on a session.
        """
        session = self.get_object()
        
        if not session.audio_file:
            return Response(
                {'error': 'No audio file available for analysis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Simulate re-analysis (placeholder)
        session.filler_count = max(0, session.filler_count + (-2, -1, 0, 1, 2)[hash(str(session.id)) % 5])
        session.pacing_analysis = f"Re-analyzed on {timezone.now().strftime('%Y-%m-%d %H:%M')}: " + session.pacing_analysis
        session.confidence_score = min(1.0, max(0.0, (session.confidence_score or 0.8) + 0.05))
        session.status = 'analyzed'
        session.save()
        
        serializer = self.get_serializer(session)
        return Response({
            'success': True,
            'message': 'Session re-analyzed successfully',
            'session': serializer.data
        })

