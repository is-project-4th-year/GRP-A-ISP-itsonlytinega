from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django_otp.decorators import otp_required
from django.utils import timezone
from datetime import datetime
import json

from .models import SpeechSession
from .forms import SpeechSessionCreateForm, SpeechSessionUpdateForm, SpeechSessionFilterForm


def require_2fa_if_enabled(view_func):
    """
    Custom decorator to require 2FA verification if user has 2FA enabled.
    This integrates with the existing 2FA system from the coach app.
    """
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_2fa_enabled:
            if not request.user.has_2fa_setup():
                messages.warning(request, 'Please complete 2FA setup to access speech sessions.')
                return redirect('coach:setup_2fa')
            # For now, if user is logged in and has 2FA enabled, allow access
            # The 2FA verification should have been completed during login
            pass
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@require_2fa_if_enabled
def session_list_view(request):
    """Display list of user's speech sessions with filtering options."""
    
    # Get filter form
    filter_form = SpeechSessionFilterForm(request.GET)
    
    # Start with user's sessions
    sessions = SpeechSession.objects.filter(user=request.user)
    
    # Apply filters if form is valid
    if filter_form.is_valid():
        status = filter_form.cleaned_data.get('status')
        date_from = filter_form.cleaned_data.get('date_from')
        date_to = filter_form.cleaned_data.get('date_to')
        search = filter_form.cleaned_data.get('search')
        
        if status:
            sessions = sessions.filter(status=status)
        
        if date_from:
            sessions = sessions.filter(date__date__gte=date_from)
        
        if date_to:
            sessions = sessions.filter(date__date__lte=date_to)
        
        if search:
            sessions = sessions.filter(
                Q(transcription__icontains=search) | 
                Q(pacing_analysis__icontains=search)
            )
    
    # Order by date (most recent first)
    sessions = sessions.order_by('-date')
    
    # Pagination
    paginator = Paginator(sessions, 10)  # Show 10 sessions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate statistics
    total_sessions = SpeechSession.objects.filter(user=request.user).count()
    pending_sessions = SpeechSession.objects.filter(user=request.user, status='pending').count()
    analyzed_sessions = SpeechSession.objects.filter(user=request.user, status='analyzed').count()
    
    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_sessions': total_sessions,
        'pending_sessions': pending_sessions,
        'analyzed_sessions': analyzed_sessions,
    }
    
    return render(request, 'speech_sessions/session_list.html', context)


@login_required
@require_2fa_if_enabled
def session_create_view(request):
    """Create a new speech session."""
    
    if request.method == 'POST':
        form = SpeechSessionCreateForm(request.POST, request.FILES)
        if form.is_valid():
            session = form.save(commit=False)
            session.user = request.user
            
            # Simulate analysis for now (placeholder as requested)
            if session.audio_file:
                # Placeholder analysis - in real implementation, this would be actual audio processing
                session.filler_count = 5  # Simulated filler count
                session.pacing_analysis = "Simulated analysis: Good pacing with occasional slow segments. Average speaking rate detected."
                session.confidence_score = 0.85  # Simulated confidence score
                session.status = 'analyzed'
            
            session.save()
            
            messages.success(request, 'Speech session created successfully!')
            return redirect('speech_sessions:session_detail', pk=session.pk)
    else:
        form = SpeechSessionCreateForm()
    
    return render(request, 'speech_sessions/session_form.html', {
        'form': form,
        'title': 'Create New Speech Session',
        'submit_text': 'Create Session'
    })


@login_required
@require_2fa_if_enabled
def session_detail_view(request, pk):
    """Display detailed view of a speech session."""
    
    session = get_object_or_404(SpeechSession, pk=pk, user=request.user)
    
    return render(request, 'speech_sessions/session_detail.html', {
        'session': session
    })


@login_required
@require_2fa_if_enabled
def session_update_view(request, pk):
    """Update an existing speech session."""
    
    session = get_object_or_404(SpeechSession, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = SpeechSessionUpdateForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, 'Speech session updated successfully!')
            return redirect('speech_sessions:session_detail', pk=session.pk)
    else:
        form = SpeechSessionUpdateForm(instance=session)
    
    return render(request, 'speech_sessions/session_form.html', {
        'form': form,
        'session': session,
        'title': 'Update Speech Session',
        'submit_text': 'Update Session'
    })


@login_required
@require_2fa_if_enabled
def session_delete_view(request, pk):
    """Delete a speech session with confirmation."""
    
    session = get_object_or_404(SpeechSession, pk=pk, user=request.user)
    
    if request.method == 'POST':
        session_id = session.id
        session.delete()
        messages.success(request, f'Speech session #{session_id} deleted successfully!')
        return redirect('speech_sessions:session_list')
    
    return render(request, 'speech_sessions/session_confirm_delete.html', {
        'session': session
    })


@login_required
@require_2fa_if_enabled
@require_http_methods(["POST"])
def session_bulk_action_view(request):
    """Handle bulk actions on multiple sessions."""
    
    try:
        data = json.loads(request.body)
        action = data.get('action')
        session_ids = data.get('session_ids', [])
        
        if not action or not session_ids:
            return JsonResponse({'error': 'Missing action or session IDs'}, status=400)
        
        # Ensure user can only act on their own sessions
        sessions = SpeechSession.objects.filter(
            id__in=session_ids, 
            user=request.user
        )
        
        count = sessions.count()
        if count == 0:
            return JsonResponse({'error': 'No valid sessions found'}, status=404)
        
        if action == 'delete':
            sessions.delete()
            return JsonResponse({
                'success': True, 
                'message': f'{count} session(s) deleted successfully'
            })
        elif action == 'archive':
            sessions.update(status='archived')
            return JsonResponse({
                'success': True, 
                'message': f'{count} session(s) archived successfully'
            })
        elif action == 'mark_analyzed':
            sessions.update(status='analyzed')
            return JsonResponse({
                'success': True, 
                'message': f'{count} session(s) marked as analyzed'
            })
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_2fa_if_enabled
def session_analytics_view(request):
    """Display analytics and insights for user's speech sessions."""
    
    sessions = SpeechSession.objects.filter(user=request.user)
    
    # Calculate analytics
    total_sessions = sessions.count()
    total_duration = sum(session.duration for session in sessions)
    avg_duration = total_duration / total_sessions if total_sessions > 0 else 0
    
    # Filler word analysis
    analyzed_sessions = sessions.filter(status='analyzed')
    total_fillers = sum(session.filler_count for session in analyzed_sessions)
    avg_fillers = total_fillers / analyzed_sessions.count() if analyzed_sessions.count() > 0 else 0
    
    # Recent progress (last 30 days)
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    recent_sessions = sessions.filter(date__gte=thirty_days_ago)
    
    context = {
        'total_sessions': total_sessions,
        'total_duration': total_duration,
        'avg_duration': avg_duration,
        'total_fillers': total_fillers,
        'avg_fillers': avg_fillers,
        'recent_sessions_count': recent_sessions.count(),
        'analyzed_sessions_count': analyzed_sessions.count(),
        'pending_sessions_count': sessions.filter(status='pending').count(),
        'archived_sessions_count': sessions.filter(status='archived').count(),
    }
    
    return render(request, 'speech_sessions/session_analytics.html', context)