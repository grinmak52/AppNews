from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Редактировать объект может только его автор, читать — все"""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author_id == request.user.id


class IsAdminOrReadOnly(permissions.BasePermission):
    """Читать могут все, изменять — только администраторы (is_staff)"""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)