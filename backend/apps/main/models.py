from django.conf import settings
from django.db import models
from django.db.models import F
from django.urls import reverse
from django.utils.text import slugify


def generate_unique_slug(instance, source, fallback='item', reserved=()):
    """
    Генерирует уникальный slug для instance из строки source.
    При коллизии добавляет суффикс -2, -3 и т.д.
    Если slugify вернул пустую строку (например, для кириллицы),
    используется fallback.
    """
    model = instance.__class__
    max_length = instance._meta.get_field('slug').max_length

    base = slugify(source)[:max_length] or fallback
    slug = base
    counter = 2

    while (
        slug in reserved
        or model._default_manager.filter(slug=slug).exclude(pk=instance.pk).exists()
    ):
        suffix = f'-{counter}'
        slug = base[:max_length - len(suffix)] + suffix
        counter += 1

    return slug


class Category(models.Model):
    """Категория постов блога."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, self.name, fallback='category')
        super().save(*args, **kwargs)


class PostQuerySet(models.QuerySet):
    """QuerySet с цепочечными методами: Post.objects.published().with_related()"""

    def published(self):
        return self.filter(status=Post.Status.PUBLISHED)

    def with_related(self):
        return self.select_related('author', 'category')

    def visible_to(self, user):
        """Опубликованные посты + собственные черновики пользователя."""
        if user and user.is_authenticated:
            return self.filter(
                models.Q(status=Post.Status.PUBLISHED) | models.Q(author=user)
            )
        return self.published()


class Post(models.Model):
    """Пост блога."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'

    # slug'и, совпадающие со служебными URL (см. urls.py)
    RESERVED_SLUGS = ('categories', 'my-posts', 'popular', 'recent')

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    content = models.TextField()
    image = models.ImageField(upload_to='posts/', blank=True, null=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='posts',
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,  # безопаснее начинать с черновика
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    views_count = models.PositiveIntegerField(default=0)

    objects = PostQuerySet.as_manager()

    class Meta:
        db_table = 'posts'
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['category', '-created_at']),
            models.Index(fields=['author', '-created_at']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # slug создаётся один раз и дальше не меняется,
        # чтобы не ломать существующие ссылки
        if not self.slug:
            self.slug = generate_unique_slug(
                self, self.title, fallback='post', reserved=self.RESERVED_SLUGS
            )
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('post-detail', kwargs={'slug': self.slug})

    def increment_views(self):
        """Атомарно увеличивает счётчик просмотров (без гонок)."""
        type(self).objects.filter(pk=self.pk).update(views_count=F('views_count') + 1)
        self.views_count += 1