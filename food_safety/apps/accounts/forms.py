from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from apps.accounts.models import Role, User


class RegisterForm(UserCreationForm):
    """التسجيل الذاتي ينشئ حساب زائر فقط — باقي الأدوار عبر مدير النظام."""

    full_name = forms.CharField(label="الاسم الكامل", max_length=150)
    email = forms.EmailField(label="البريد الإلكتروني", required=True)
    phone = forms.CharField(label="الهاتف", max_length=20, required=False)

    class Meta:
        model = User
        fields = ("username", "full_name", "email", "phone", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.full_name = self.cleaned_data["full_name"]
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone") or None
        user.role = Role.USER  # زائر فقط — لا يمكن اختيار دور رقابي من هنا
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="اسم المستخدم")
    password = forms.CharField(label="كلمة المرور", widget=forms.PasswordInput)
