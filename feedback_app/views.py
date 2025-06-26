

from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Case, When, BooleanField, IntegerField
from django.db.models.functions import TruncMonth # For monthly trends
from django.http import HttpResponse # For PDF export

import datetime
from django.utils import timezone


from .models import CustomUser, Feedback, Comment, FeedbackRequest, PeerFeedback
from .serializers import (
    UserSerializer, FeedbackSerializer, MyTokenObtainPairSerializer, # Make sure MyTokenObtainPairSerializer is here
    CommentSerializer, FeedbackRequestSerializer, PeerFeedbackSerializer
)

from rest_framework_simplejwt.views import TokenObtainPairView


try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
except ImportError:
    canvas = None
    print("ReportLab not installed. PDF export will not function.")


class MyTokenObtainPairView(TokenObtainPairView):
  
    serializer_class = MyTokenObtainPairSerializer



class IsOwnerOfObject(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit/delete it.
    Assumes the object has an 'owner' or 'user' field related to CustomUser.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user

class IsFeedbackManagerOrTargetEmployee(permissions.BasePermission):
    """
    Custom permission for Feedback objects:
    - Manager who gave feedback can Read, Update, Delete.
    - Employee who received feedback can Read and Acknowledge (PATCH for is_acknowledged).
    - Manager of the employee can Read.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user

        if request.method in permissions.SAFE_METHODS:
            if obj.manager == user:
                return True
            if obj.employee == user:
                return True
            if user.role == 'manager' and obj.employee.manager == user:
                return True
            return False

        if request.method in ['PUT', 'DELETE']:
            return user.role == 'manager' and obj.manager == user
        
        if request.method == 'PATCH':
            if user.role == 'manager' and obj.manager == user:
                return True
            if user.role == 'employee' and obj.employee == user:
                if len(request.data) == 1 and 'is_acknowledged' in request.data:
                    return True
                return False
            return False

        return False


class IsRequesterOrTargetManager(permissions.BasePermission):
    """
    Custom permission for FeedbackRequest objects:
    - Requester (employee) can Read, Update, Delete their own request.
    - Target Manager can Read, Update (e.g., mark fulfilled) the request.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        if request.method in permissions.SAFE_METHODS:
            return obj.requester == user or (user.role == 'manager' and obj.target_manager == user)
        return obj.requester == user or (user.role == 'manager' and obj.target_manager == user and request.method in ['PUT', 'PATCH'])

class IsCommentAuthor(permissions.BasePermission):
    """
    Custom permission for Comment objects:
    - Author can Read, Update, Delete their own comment.
    - Others can Read.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user

class IsPeerFeedbackGiverOrReceiver(permissions.BasePermission):
    """
    Custom permission for PeerFeedback objects:
    - Giver can Read, Update, Delete their own feedback.
    - Receiver can Read feedback given to them (regardless of anonymity).
    - Managers (or admins) can Read all.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        if request.method in permissions.SAFE_METHODS:
            return obj.giver == user or obj.receiver == user or user.is_superuser or user.role == 'manager'
        return obj.giver == user


# --- User ViewSet ---
class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return CustomUser.objects.all().order_by('username')
        elif user.role == 'manager':
            return CustomUser.objects.filter(Q(id=user.id) | Q(manager=user)).order_by('username')
        elif user.role == 'employee':
            return CustomUser.objects.filter(id=user.id).order_by('username')
        return CustomUser.objects.none()

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='employees', permission_classes=[permissions.IsAuthenticated])
    def list_employees(self, request):
        if request.user.is_superuser:
            employees = CustomUser.objects.filter(role='employee').order_by('username')
        elif request.user.role == 'manager':
            employees = CustomUser.objects.filter(manager=request.user, role='employee').order_by('username')
        else:
            return Response({"detail": "You do not have permission to view this."}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(employees, many=True)
        return Response(serializer.data)


# --- Feedback ViewSet ---
class FeedbackViewSet(viewsets.ModelViewSet):
    queryset = Feedback.objects.all().order_by('-created_at')
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsFeedbackManagerOrTargetEmployee]

    def perform_create(self, serializer):
        if self.request.user.role != 'manager':
            return Response({"detail": "Only managers can create feedback."}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(manager=self.request.user)

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Feedback.objects.all().order_by('-created_at')
        elif user.role == 'manager':
            return Feedback.objects.filter(
                Q(manager=user) | Q(employee__manager=user)
            ).distinct().order_by('-created_at')
        elif user.role == 'employee':
            return Feedback.objects.filter(employee=user).order_by('-created_at')
        return Feedback.objects.none()

    @action(detail=True, methods=['patch'])
    def acknowledge(self, request, pk=None):
        feedback = self.get_object()
        if feedback.is_acknowledged:
            return Response({"detail": "Feedback already acknowledged."}, status=status.HTTP_400_BAD_REQUEST)
        
        feedback.is_acknowledged = True
        feedback.save()
        serializer = self.get_serializer(feedback)
        return Response(serializer.data)

    # --- Manager Dashboard Summary ---
    @action(detail=False, methods=['get'], url_path='manager-summary',
            permission_classes=[permissions.IsAuthenticated])
    def manager_summary(self, request):
        user = request.user
        if user.role != 'manager' and not user.is_superuser:
            return Response({"detail": "Access denied. Only managers can view feedback summaries."}, status=status.HTTP_403_FORBIDDEN)

        manager_relevant_feedback = self.get_queryset()

        total_feedback_given_by_me = Feedback.objects.filter(manager=user).count()
        total_feedback_for_my_reports = Feedback.objects.filter(employee__manager=user).count()

        sentiment_counts_given_by_me = Feedback.objects.filter(manager=user) \
                                                    .values('sentiment') \
                                                    .annotate(count=Count('sentiment')) \
                                                    .order_by('sentiment')
        sentiment_data_given_by_me = {item['sentiment']: item['count'] for item in sentiment_counts_given_by_me}
        for s in ['Positive', 'Neutral', 'Needs Improvement']:
            sentiment_data_given_by_me.setdefault(s, 0)

        reports_feedback_status = Feedback.objects.filter(employee__manager=user).aggregate(
            total=Count('id'),
            acknowledged=Count(Case(When(is_acknowledged=True, then=1), output_field=IntegerField())),
            pending=Count(Case(When(is_acknowledged=False, then=1), output_field=IntegerField()))
        )

        today = timezone.now()
        six_months_ago = today - datetime.timedelta(days=180)

        monthly_trends_given_by_me = Feedback.objects.filter(manager=user, created_at__gte=six_months_ago) \
                                                    .annotate(month=TruncMonth('created_at')) \
                                                    .values('month') \
                                                    .annotate(
                                                        total=Count('id'),
                                                        positive=Count(Case(When(sentiment='Positive', then=1), output_field=IntegerField())),
                                                        neutral=Count(Case(When(sentiment='Neutral', then=1), output_field=IntegerField())),
                                                        needs_improvement=Count(Case(When(sentiment='Needs Improvement', then=1), output_field=IntegerField()))
                                                    ) \
                                                    .order_by('month')

        formatted_monthly_trends = [
            {
                'month': item['month'].strftime('%Y-%m'),
                'total': item['total'],
                'positive': item['positive'],
                'neutral': item['neutral'],
                'needs_improvement': item['needs_improvement']
            }
            for item in monthly_trends_given_by_me
        ]

        response_data = {
            "total_feedback_given_by_me": total_feedback_given_by_me,
            "total_feedback_for_my_reports": reports_feedback_status.get('total', 0),
            "sentiment_trends_given_by_me": sentiment_data_given_by_me,
            "reports_feedback_acknowledgment_status": {
                "acknowledged": reports_feedback_status.get('acknowledged', 0),
                "pending": reports_feedback_status.get('pending', 0),
            },
            "monthly_trends_given_by_me": formatted_monthly_trends,
        }
        return Response(response_data, status=status.HTTP_200_OK)

    # --- NEW ACTION: Export Feedback as PDF ---
    @action(detail=True, methods=['get'], url_path='export-pdf',
            permission_classes=[permissions.IsAuthenticated, IsFeedbackManagerOrTargetEmployee])
    def export_pdf(self, request, pk=None):
        feedback = self.get_object()

        if not canvas:
            return Response({"detail": "PDF generation library (ReportLab) not installed on server."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="feedback_{feedback.id}.pdf"'

        p = canvas.Canvas(response, pagesize=letter)
        width, height = letter

        p.drawString(1 * inch, height - 1 * inch, f"Performance Feedback ID: {feedback.id}")
        p.drawString(1 * inch, height - 1.3 * inch, f"From: {feedback.manager.username}")
        p.drawString(1 * inch, height - 1.6 * inch, f"To: {feedback.employee.username}")
        p.drawString(1 * inch, height - 1.9 * inch, f"Date: {feedback.created_at.strftime('%Y-%m-%d %H:%M')}")
        p.drawString(1 * inch, height - 2.2 * inch, f"Sentiment: {feedback.sentiment}")
        p.drawString(1 * inch, height - 2.5 * inch, f"Acknowledged: {'Yes' if feedback.is_acknowledged else 'No'}")

        # Strengths
        p.drawString(1 * inch, height - 3 * inch, "Strengths:")
        textobject = p.beginText()
        textobject.setTextOrigin(1 * inch, height - 3.2 * inch)
        textobject.setFont("Helvetica", 10)
        for line in feedback.strengths.split('\n'):
            textobject.textLine(line)
        p.drawText(textobject)

        # Areas to Improve
        p.drawString(1 * inch, height - 4.5 * inch, "Areas to Improve:")
        textobject = p.beginText()
        textobject.setTextOrigin(1 * inch, height - 4.7 * inch)
        textobject.setFont("Helvetica", 10)
        for line in feedback.areas_to_improve.split('\n'):
            textobject.textLine(line)
        p.drawText(textobject)

        # Comments (Basic implementation)
        p.drawString(1 * inch, height - 6 * inch, "Comments:")
        y_pos = height - 6.2 * inch
        for comment in feedback.comments.all():
            p.drawString(1 * inch, y_pos, f"   - {comment.author.username} ({comment.created_at.strftime('%Y-%m-%d')}): {comment.content}")
            y_pos -= 0.2 * inch
            if y_pos < 1 * inch:
                p.showPage()
                y_pos = height - 1 * inch

        p.showPage()
        p.save()
        return response


# --- NEW ViewSet: CommentViewSet ---
class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all().order_by('created_at')
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsCommentAuthor]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        feedback_id = self.request.query_params.get('feedback', None)
        if feedback_id:
            return Comment.objects.filter(feedback_id=feedback_id).order_by('created_at')
        user = self.request.user
        if user.is_superuser:
            return Comment.objects.all().order_by('created_at')
        return Comment.objects.filter(author=user).order_by('created_at')


# --- NEW ViewSet: FeedbackRequestViewSet ---
class FeedbackRequestViewSet(viewsets.ModelViewSet):
    queryset = FeedbackRequest.objects.all().order_by('-created_at')
    serializer_class = FeedbackRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsRequesterOrTargetManager]

    def perform_create(self, serializer):
        if self.request.user.role != 'employee':
            return Response({"detail": "Only employees can request feedback."}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(requester=self.request.user)

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return FeedbackRequest.objects.all().order_by('-created_at')
        elif user.role == 'manager':
            return FeedbackRequest.objects.filter(
                Q(target_manager=user) | Q(requester__manager=user)
            ).distinct().order_by('-created_at')
        elif user.role == 'employee':
            return FeedbackRequest.objects.filter(requester=user).order_by('-created_at')
        return FeedbackRequest.objects.none()

    @action(detail=True, methods=['patch'], url_path='mark-fulfilled',
            permission_classes=[permissions.IsAuthenticated])
    def mark_fulfilled(self, request, pk=None):
        req_instance = self.get_object()
        user = request.user

        if not (user.is_superuser or (user.role == 'manager' and req_instance.target_manager == user)):
            return Response({"detail": "You do not have permission to mark this request as fulfilled."},
                            status=status.HTTP_403_FORBIDDEN)

        if req_instance.is_fulfilled:
            return Response({"detail": "Feedback request is already marked as fulfilled."}, status=status.HTTP_400_BAD_REQUEST)

        req_instance.is_fulfilled = True
        req_instance.save()
        serializer = self.get_serializer(req_instance)
        return Response(serializer.data)


# --- NEW ViewSet: PeerFeedbackViewSet ---
class PeerFeedbackViewSet(viewsets.ModelViewSet):
    queryset = PeerFeedback.objects.all().order_by('-created_at')
    serializer_class = PeerFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsPeerFeedbackGiverOrReceiver]

    def perform_create(self, serializer):
        serializer.save(giver=self.request.user)

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return PeerFeedback.objects.all().order_by('-created_at')
        elif user.role == 'manager':
            return PeerFeedback.objects.filter(
                Q(giver=user) | Q(receiver=user) | Q(receiver__manager=user) | Q(giver__manager=user)
            ).distinct().order_by('-created_at')
        else: # Employee role
            return PeerFeedback.objects.filter(Q(giver=user) | Q(receiver=user)).order_by('-created_at')