from django.urls import path

from .views import (
    change_password_view,
    forgot_password_view,
    login_view,
    logout_view,
    me_view,
    resend_signup_otp_view,
    reset_password_view,
    signup_company_view,
    signup_individual_view,
    verify_otp_view,
    verify_signup_otp_view,
)

urlpatterns = [
    path('signup/company/', signup_company_view, name='signup-company'),
    path('signup/individual/', signup_individual_view, name='signup-individual'),
    path('verify-signup-otp/', verify_signup_otp_view, name='verify-signup-otp'),
    path('resend-signup-otp/', resend_signup_otp_view, name='resend-signup-otp'),
    path('login/', login_view, name='login'),
    path('change-password/', change_password_view, name='change-password'),
    path('forgot-password/', forgot_password_view, name='forgot-password'),
    path('verify-otp/', verify_otp_view, name='verify-otp'),
    path('reset-password/', reset_password_view, name='reset-password'),
    path('me/', me_view, name='me'),
    path('logout/', logout_view, name='logout'),
]
