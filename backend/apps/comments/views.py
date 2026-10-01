from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.main.models import Post
from .models import Comment
from .permissions import IsAuthorOrReadOnly
from .serializers import (
    CommentCreateSerializer,
    CommentDetailSerializer,
    CommentSerializer,
    CommentUpdateSerializer,
)


class CommentPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


def get_active_comments_queryset():
    """Базовый queryset активных комментариев с оптимизацией."""
    return (
        Comment.objects
        .filter(is_active=True)
        .select_related('author', 'post', 'parent')
        .annotate(
            active_replies_count=Count(
                'replies',
                filter=Q(replies__is_active=True)
            )
        )
    )


class PostCommentsView(generics.ListCreateAPIView):
    """
    Список комментариев конкретного поста + создание нового комментария.
    URL: /api/v1/posts/<slug>/comments/
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = CommentPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_post(self):
        return get_object_or_404(
            Post.objects.published(),
            slug=self.kwargs['slug']
        )

    def get_queryset(self):
        post = self.get_post()
        # Только корневые комментарии (ответы подгружаются вложенно)
        return (
            get_active_comments_queryset()
            .filter(post=post, parent=None)
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CommentCreateSerializer
        return CommentDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['post'] = self.get_post()          # важно!
        return context

    def perform_create(self, serializer):
        serializer.save()


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Детальный просмотр / редактирование / мягкое удаление комментария.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    lookup_field = 'pk'

    def get_queryset(self):
        return get_active_comments_queryset()

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return CommentUpdateSerializer
        return CommentDetailSerializer

    def perform_destroy(self, instance):
        # Мягкое удаление
        instance.soft_delete()


class MyCommentsView(generics.ListAPIView):
    """Комментарии текущего пользователя"""
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CommentPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['post', 'parent']
    search_fields = ['content']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            get_active_comments_queryset()
            .filter(author=self.request.user)
        )