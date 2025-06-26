# D:\GrowthFlow\feedback_app\admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Feedback # Make sure Feedback is also imported

# Custom Admin for CustomUser to display the role and manager fields
class CustomUserAdmin(UserAdmin):
    # Add 'role' and 'manager' to the fields displayed in the user list in admin
    list_display = UserAdmin.list_display + ('role', 'manager',)
    # Add 'role' and 'manager' to the fields that can be filtered by in admin
    list_filter = UserAdmin.list_filter + ('role',)
    # Add 'role' and 'manager' to the fields that can be searched
    search_fields = UserAdmin.search_fields + ('role',)

    # Customize fieldsets to include 'role' and 'manager' in the user edit form
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'manager',)}),
    )

# Register your CustomUser model with the custom admin class
admin.site.register(CustomUser, CustomUserAdmin)

# Also register your Feedback model so you can view/manage feedback in the admin
# (Optional, but highly recommended for debugging/management)
admin.site.register(Feedback)