from django.urls import path

from .views import (
    file_detail_view,
    file_download_view,
    file_public_download_view,
    file_share_detail_view,
    file_shares_view,
    files_presign_view,
    files_view,
    folder_detail_view,
    folder_share_detail_view,
    folder_shares_view,
    folders_view,
    s3_settings_test_view,
    s3_settings_view,
)

urlpatterns = [
    path('folders/', folders_view, name='folders'),
    path('folders/<uuid:folder_pk>/', folder_detail_view, name='folder-detail'),
    path('folders/<uuid:folder_pk>/shares/', folder_shares_view, name='folder-shares'),
    path('folders/<uuid:folder_pk>/shares/<uuid:share_pk>/', folder_share_detail_view, name='folder-share-detail'),
    path('presign/', files_presign_view, name='files-presign'),
    path('settings/s3/', s3_settings_view, name='s3-settings'),
    path('settings/s3/test/', s3_settings_test_view, name='s3-settings-test'),
    path('', files_view, name='files'),
    path('<uuid:file_pk>/', file_detail_view, name='file-detail'),
    path('<uuid:file_pk>/download/', file_download_view, name='file-download'),
    path('<uuid:file_pk>/public/', file_public_download_view, name='file-public-download'),
    path('<uuid:file_pk>/shares/', file_shares_view, name='file-shares'),
    path('<uuid:file_pk>/shares/<uuid:share_pk>/', file_share_detail_view, name='file-share-detail'),
]
