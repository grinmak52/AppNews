from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Comment
from apps.main.models import Post

User = get_user_model()


class CommentAuthorSerializer(serializers.ModelSerializer):
    """Краткая информация об авторе комментария"""
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'avatar']


class CommentSerializer(serializers.ModelSerializer):
    """Базовый сериализатор комментария (для списка и вложенных ответов)"""
    author = CommentAuthorSerializer(read_only=True)
    replies_count = serializers.SerializerMethodField()
    is_reply = serializers.BooleanField(read_only=True)

    class Meta:
        model = Comment
        fields = [
            'id',
            'content',
            'author',
            'parent',
            'is_active',
            'replies_count',
            'is_reply',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['author', 'is_active', 'parent']

    def get_replies_count(self, obj):
        # Если во view сделали аннотацию — используем её
        annotated = getattr(obj, 'active_replies_count', None)
        if annotated is not None:
            return annotated
        # Fallback (лучше не допускать до сюда)
        return obj.replies.filter(is_active=True).count()


class CommentCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания комментария"""

    class Meta:
        model = Comment
        fields = ['content', 'parent']   # post будем брать из URL

    def validate_parent(self, value):
        """Проверяем, что родительский комментарий существует и активен"""
        if value is None:
            return value

        if not value.is_active:
            raise serializers.ValidationError('Cannot reply to an inactive comment.')

        # post мы получим из context (из URL)
        post = self.context.get('post')
        if post and value.post_id != post.id:
            raise serializers.ValidationError(
                'Parent comment must belong to the same post.'
            )
        return value

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Comment cannot be empty.')
        return value

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        validated_data['post'] = self.context['post']   # берём из URL
        return super().create(validated_data)


class CommentUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для обновления комментария"""

    class Meta:
        model = Comment
        fields = ['content']

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Comment cannot be empty.')
        return value


class CommentDetailSerializer(CommentSerializer):
    """Детальный сериализатор с вложенными ответами"""
    replies = serializers.SerializerMethodField()

    class Meta(CommentSerializer.Meta):
        fields = CommentSerializer.Meta.fields + ['replies']

    def get_replies(self, obj):
        # Показываем ответы только у корневых комментариев
        if obj.parent_id is not None:
            return []

        replies = (
            obj.replies
            .filter(is_active=True)
            .select_related('author')
            .order_by('created_at')
        )
        return CommentSerializer(replies, many=True, context=self.context).data