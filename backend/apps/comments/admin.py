from django.contrib import admin
from django.db.models import Count, Q

from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        'short_content',
        'author',
        'post',
        'parent',
        'is_active',
        'replies_count',
        'created_at',
    )
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = (
        'content',
        'author__username',
        'author__email',
        'post__title',
    )
    raw_id_fields = ('author', 'post', 'parent')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_select_related = ('author', 'post', 'parent')
    actions = ('make_active', 'make_inactive')

    fieldsets = (
        (None, {
            'fields': ('post', 'author', 'parent', 'content'),
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('author', 'post', 'parent')
            .annotate(
                _replies_count=Count(
                    'replies',
                    filter=Q(replies__is_active=True),
                )
            )
        )

    @admin.display(description='Content')
    def short_content(self, obj):
        return obj.content[:60] + '...' if len(obj.content) > 60 else obj.content

    @admin.display(description='Replies', ordering='_replies_count')
    def replies_count(self, obj):
        return obj._replies_count

    @admin.action(description='Активировать выбранные комментарии')
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Активировано комментариев: {updated}')

    @admin.action(description='Деактивировать выбранные комментарии')
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Деактивировано комментариев: {updated}')