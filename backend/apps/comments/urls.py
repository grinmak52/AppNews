from django.urls import path
from . import views

urlpatterns = [
    path('<int:pk>/', views.CommentDetailView.as_view(), name='comment-detail'),
    path('my/', views.MyCommentsView.as_view(), name='my-comments'),
]