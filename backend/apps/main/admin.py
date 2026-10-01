from django.contrib import admin
from django.db.models import Count

from .models import Category, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'posts_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        # Один запрос на весь список вместо запроса на каждую категорию
        return super().get_queryset(request).annotate(_posts_count=Count('posts'))

    @admin.display(description='Posts', ordering='_posts_count')
    def posts_count(self, obj):
        return obj._posts_count


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'author', 'category', 'status', 'views_count', 'created_at',
    )
    list_filter = ('status', 'category', 'created_at', 'updated_at')
    search_fields = ('title', 'content', 'author__username', 'author__email')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at', 'views_count')
    raw_id_fields = ('author',)
    date_hierarchy = 'created_at'
    actions = ('make_published', 'make_draft')

    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'content', 'image'),
        }),
        ('Meta', {
            'fields': ('category', 'author', 'status'),
        }),
        ('Statistics', {
            'fields': ('views_count', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author', 'category')

    @admin.action(description='Опубликовать выбранные посты')
    def make_published(self, request, queryset):
        updated = queryset.update(status=Post.Status.PUBLISHED)
        self.message_user(request, f'Опубликовано постов: {updated}')

    @admin.action(description='Перевести выбранные посты в черновики')
    def make_draft(self, request, queryset):
        updated = queryset.update(status=Post.Status.DRAFT)
        self.message_user(request, f'Переведено в черновики: {updated}')