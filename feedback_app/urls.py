
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, FeedbackViewSet, CommentViewSet, FeedbackRequestViewSet, PeerFeedbackViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'feedback', FeedbackViewSet, basename='feedback')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'feedback-requests', FeedbackRequestViewSet, basename='feedbackrequest')
router.register(r'peer-feedback', PeerFeedbackViewSet, basename='peerfeedback')

urlpatterns = [
    path('', include(router.urls)),
]