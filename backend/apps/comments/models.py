from django.conf import settings
from django.db import models


class Comment(models.Model):
    """Модель комментария с поддержкой вложенных ответов."""

    post = models.ForeignKey(
        'main.Post',
        on_delete=models.CASCADE,
        related_name='comments',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
    )
    content = models.TextField(max_length=2000)  # ← ограничили длину
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'comments'
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', '-created_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['parent', '-created_at']),
            models.Index(fields=['post', 'is_active', '-created_at']),  # ← полезный индекс
        ]

    def __str__(self):
        return f'Comment by {self.author} on {self.post}'

    @property
    def is_reply(self):
        """Является ли комментарий ответом на другой комментарий."""
        return self.parent_id is not None

    def soft_delete(self):
        """Мягкое удаление комментария."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])