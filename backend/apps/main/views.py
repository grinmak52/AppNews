from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Category, Post
from .permissions import IsAdminOrReadOnly, IsAuthorOrReadOnly
from .serializers import (
    CategorySerializer,
    PostCreateUpdateSerializer,
    PostDetailSerializer,
    PostListSerializer,
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 50


def categories_queryset():
    """Категории со счётчиком опубликованных постов (один запрос на весь список)."""
    return Category.objects.annotate(
        published_posts_count=Count(
            'posts',
            filter=Q(posts__status=Post.Status.PUBLISHED),
        )
    )


class CategoryListCreateView(generics.ListCreateAPIView):
    """Список категорий; создавать могут только администраторы"""
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return categories_queryset()


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Конкретная категория; изменять и удалять могут только администраторы"""
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'slug'

    def get_queryset(self):
        return categories_queryset()


class CategoryPostsView(generics.ListAPIView):
    """Опубликованные посты определённой категории"""
    serializer_class = PostListSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'views_count', 'title']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        category = get_object_or_404(Category, slug=self.kwargs['category_slug'])
        return (
            Post.objects
            .with_related()
            .published()
            .filter(category=category)
            .annotate(
                active_comments_count=Count(
                    'comments',
                    filter=Q(comments__is_active=True)
                )
            )
        )


class PostListCreateView(generics.ListCreateAPIView):
    """
    Список постов: опубликованные + собственные черновики
    авторизованного пользователя.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'author', 'status']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'updated_at', 'views_count', 'title']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return (
            Post.objects
            .with_related()
            .visible_to(self.request.user)
            .annotate(
                active_comments_count=Count(
                    'comments',
                    filter=Q(comments__is_active=True)
                )
            )
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PostCreateUpdateSerializer
        return PostListSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class PostDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Конкретный пост. Чужие черновики недоступны (404),
    редактировать и удалять может только автор.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    lookup_field = 'slug'

    def get_queryset(self):
        return (
            Post.objects
            .with_related()
            .visible_to(self.request.user)
            .annotate(
                active_comments_count=Count(
                    'comments',
                    filter=Q(comments__is_active=True)
                )
            )
        )

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return PostCreateUpdateSerializer
        return PostDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        """Увеличивает счётчик просмотров (кроме просмотров самого автора)"""
        instance = self.get_object()

        if instance.author_id != request.user.id:
            instance.increment_views()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class MyPostsView(generics.ListAPIView):
    """Посты текущего пользователя (включая черновики)"""
    serializer_class = PostListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'status']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'updated_at', 'views_count', 'title']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Post.objects.with_related().filter(author=self.request.user)


def _top_published_posts(request, ordering):
    """Вспомогательная функция для popular / recent с поддержкой ?limit="""
    try:
        limit = int(request.query_params.get('limit', 10))
    except (TypeError, ValueError):
        limit = 10

    # Ограничиваем разумными пределами
    limit = max(1, min(limit, 50))

    posts = (
        Post.objects
        .with_related()
        .published()
        .order_by(ordering)[:limit]
    )
    serializer = PostListSerializer(posts, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def popular_posts(request):
    """Самые популярные посты (по умолчанию 10, можно ?limit=)"""
    return _top_published_posts(request, '-views_count')


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def recent_posts(request):
    """Последние опубликованные посты (по умолчанию 10, можно ?limit=)"""
    return _top_published_posts(request, '-created_at')