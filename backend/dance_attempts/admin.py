from django.contrib import admin
from .models import DanceAttempt

@admin.register(DanceAttempt)
class DanceAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'reference_title', 'score', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('reference_title', 'user__username')
    
    readonly_fields = ('score', 'status', 'json_analysis', 'score_details')