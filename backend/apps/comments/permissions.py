from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Читать могут все.
    Редактировать / удалять — только автор комментария.
    """

    def has_object_permission(self, request, view, obj):
        # GET, HEAD, OPTIONS — разрешаем всем
        if request.method in permissions.SAFE_METHODS:
            return True

        # Для изменения нужен аутентифицированный автор
        return (
            request.user
            and request.user.is_authenticated
            and obj.author_id == request.user.id
        )