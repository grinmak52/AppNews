from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.utils.text import Truncator
from rest_framework import serializers

from .models import Category, Post

User = get_user_model()

# Максимальный размер изображения (5 МБ)
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif']


def validate_image(image):
    """Проверка размера и расширения изображения."""
    if image is None:
        return

    if image.size > MAX_IMAGE_SIZE:
        raise serializers.ValidationError(
            f'Image size must not exceed {MAX_IMAGE_SIZE // (1024 * 1024)} MB.'
        )

    ext = image.name.rsplit('.', 1)[-1].lower() if '.' in image.name else ''
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise serializers.ValidationError(
            f'Allowed image formats: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}.'
        )


class CategorySerializer(serializers.ModelSerializer):
    """Сериализатор для категорий"""
    posts_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'posts_count', 'created_at']
        read_only_fields = ['slug', 'created_at']

    def get_posts_count(self, obj):
        # Предпочитаем аннотацию из view (избегаем N+1)
        annotated = getattr(obj, 'published_posts_count', None)
        if annotated is not None:
            return annotated
        return obj.posts.published().count()


class CategoryShortSerializer(serializers.ModelSerializer):
    """Краткая информация о категории (для вложения в пост)"""

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class AuthorSerializer(serializers.ModelSerializer):
    """Краткая информация об авторе (для вложения в пост)"""
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'avatar']


class PostListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка постов"""
    author = AuthorSerializer(read_only=True)
    category = CategoryShortSerializer(read_only=True)
    excerpt = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'excerpt', 'image', 'category',
            'author', 'status', 'created_at', 'updated_at', 'views_count',
        ]
        read_only_fields = fields

    def get_excerpt(self, obj):
        return Truncator(obj.content).chars(200)


class PostDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для детального просмотра поста"""
    author = AuthorSerializer(read_only=True)
    category = CategoryShortSerializer(read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'content', 'image', 'category',
            'author', 'status', 'created_at', 'updated_at', 'views_count',
        ]
        read_only_fields = fields


class PostCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания и обновления постов.
    Автор подставляется во view (perform_create), slug — в модели.
    """
    image = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)],
    )

    class Meta:
        model = Post
        fields = ['title', 'content', 'image', 'category', 'status']

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Title cannot be blank.')
        return value

    def validate_image(self, value):
        validate_image(value)
        return value

    def to_representation(self, instance):
        # В ответе на POST/PUT/PATCH отдаём полный пост (с id и slug)
        return PostDetailSerializer(instance, context=self.context).data