

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView # Keep this one


from feedback_app.views import MyTokenObtainPairView # <--- Correct import

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('feedback_app.urls')),
   
    path('api/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'), # <--- Use the custom view here
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]