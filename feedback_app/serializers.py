

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import CustomUser, Feedback, Comment, FeedbackRequest, PeerFeedback



class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        token['role'] = user.role       
        token['is_superuser'] = user.is_superuser 
        token['user_id'] = user.id 

        return token



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        # Include all fields relevant for displaying user info and for managers to pick employees
        fields = ['id', 'username', 'email', 'role', 'manager', 'is_superuser']
        read_only_fields = ['is_superuser'] # is_superuser should not be changeable via this serializer



class CommentSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')

    class Meta:
        model = Comment
        fields = ['id', 'feedback', 'author', 'author_username', 'content', 'is_markdown', 'created_at', 'updated_at']
        read_only_fields = ['author', 'created_at', 'updated_at'] # Author set by view



class FeedbackSerializer(serializers.ModelSerializer):
    manager_username = serializers.ReadOnlyField(source='manager.username')
    employee_username = serializers.ReadOnlyField(source='employee.username')
    # Nested serializer for comments
    comments = CommentSerializer(many=True, read_only=True) # Feedback can have multiple comments

    employee = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role='employee')
    )

    class Meta:
        model = Feedback
        fields = [
            'id', 'manager', 'manager_username', 'employee', 'employee_username',
            'strengths', 'areas_to_improve', 'sentiment', 'is_acknowledged',
            'created_at', 'updated_at', 'comments' # Include comments field
        ]
        read_only_fields = ['manager', 'is_acknowledged', 'created_at', 'updated_at']


# --- NEW SERIALIZER: FeedbackRequestSerializer ---
class FeedbackRequestSerializer(serializers.ModelSerializer):
    requester_username = serializers.ReadOnlyField(source='requester.username')
    target_manager_username = serializers.ReadOnlyField(source='target_manager.username')

    class Meta:
        model = FeedbackRequest
        fields = ['id', 'requester', 'requester_username', 'target_manager',
                  'target_manager_username', 'reason', 'is_fulfilled', 'created_at', 'updated_at']
        read_only_fields = ['requester', 'is_fulfilled', 'created_at', 'updated_at'] # Requester set by view



class PeerFeedbackSerializer(serializers.ModelSerializer):
    # Only display giver username if not anonymous
    giver_username = serializers.SerializerMethodField()
    receiver_username = serializers.ReadOnlyField(source='receiver.username')

    class Meta:
        model = PeerFeedback
        fields = ['id', 'giver', 'giver_username', 'receiver', 'receiver_username',
                  'feedback_text', 'is_anonymous', 'created_at', 'updated_at']
        read_only_fields = ['giver', 'created_at', 'updated_at'] # Giver set by view

    def get_giver_username(self, obj):
        if obj.is_anonymous:
            return "Anonymous"
        return obj.giver.username

    def validate(self, data):
        # Prevent self-feedback for peer feedback
        request = self.context.get('request')
        if request and request.user == data['receiver']:
            raise serializers.ValidationError("You cannot give peer feedback to yourself.")
        return data