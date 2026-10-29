from django.contrib import admin

from .models import Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'owner', 'analysis_status', 'file_size', 'created_at')
    list_filter = ('analysis_status',)
    search_fields = ('title',)
    # Written by the analysis, not by hand.
    readonly_fields = ('json_analysis',)
