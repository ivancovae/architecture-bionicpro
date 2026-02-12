# Настройка Multi-Factor Authentication (MFA) в Keycloak

## Обзор

В realm `reports-realm` включена обязательная двухфакторная аутентификация (MFA) с использованием TOTP (Time-based One-Time Password) для всех пользователей.

## Что изменилось

### 1. OTP-политика realm
- **Тип**: TOTP (Time-based One-Time Password)
- **Алгоритм**: HmacSHA1
- **Количество цифр**: 6
- **Период**: 30 секунд
- **Поддерживаемые приложения**: 
  - Google Authenticator
  - FreeOTP
  - Microsoft Authenticator

### 2. Обязательная настройка для всех пользователей
Все существующие пользователи (user1, user2, admin1, prosthetic1, prosthetic2, prosthetic3) имеют `requiredActions: ["CONFIGURE_TOTP"]`, что означает:
- При следующем входе пользователь **обязан** настроить OTP
- Без настройки OTP доступ к системе будет невозможен

### 3. Authentication Flow
Настроен кастомный browser flow с обязательными шагами:
1. **Cookie authentication** (альтернативный) - для уже авторизованных пользователей
2. **Identity Provider Redirector** (альтернативный) - для OAuth провайдеров
3. **Browser Forms** (альтернативный):
   - **Username/Password** (обязательный)
   - **OTP Code** (обязательный)

## Инструкция для пользователей

### Первый вход после включения MFA

1. **Введите логин и пароль** как обычно
2. **Вы увидите экран настройки OTP** с QR-кодом
3. **Установите приложение-аутентификатор** на телефон:
   - Google Authenticator (Android/iOS)
   - Microsoft Authenticator (Android/iOS)
   - FreeOTP (Android/iOS)
   - Authy (Android/iOS)
4. **Отсканируйте QR-код** в приложении
5. **Введите 6-значный код** из приложения для подтверждения
6. **Сохраните резервные коды** (если предлагается)

### Последующие входы

1. Введите логин и пароль
2. Введите 6-значный код из приложения-аутентификатора
3. Код обновляется каждые 30 секунд

## Для администраторов

### Проверка настроек MFA

После перезапуска Keycloak с новым realm-export.json:

```bash
# Перезапустить Keycloak
docker compose restart keycloak

# Проверить логи
docker logs keycloak | grep -i "totp\|mfa\|otp"
```

### Проверка через Keycloak Admin Console

1. Откройте http://localhost:8080/admin
2. Войдите как admin
3. Выберите realm `reports-realm`
4. Перейдите в **Authentication** → **Flows**
5. Проверьте flow `browser` - должен содержать обязательный OTP
6. Перейдите в **Authentication** → **Required Actions**
7. Проверьте, что `Configure OTP` включен и установлен как `Default Action`

### Сброс MFA для пользователя

Если пользователь потерял доступ к приложению-аутентификатору:

1. Откройте Keycloak Admin Console
2. Перейдите в **Users** → выберите пользователя
3. Вкладка **Credentials**
4. Найдите секцию **OTP** и нажмите **Delete**
5. Вкладка **Required Actions**
6. Добавьте `Configure OTP`
7. При следующем входе пользователь настроит OTP заново

### Отключение MFA для конкретного пользователя

**Не рекомендуется**, но возможно:

1. Откройте Keycloak Admin Console
2. Перейдите в **Users** → выберите пользователя
3. Вкладка **Required Actions**
4. Снимите галочку с `Configure OTP`
5. Вкладка **Credentials**
6. Удалите OTP credential

## Для новых пользователей

Новые пользователи, создаваемые через:
- Keycloak Admin Console
- LDAP синхронизацию
- Self-registration (если включено)

Автоматически получат `requiredAction: CONFIGURE_TOTP` благодаря настройке `defaultAction: true` в realm.

## Совместимость с LDAP

MFA работает для всех типов пользователей:
- **Локальные пользователи** (user1, user2, admin1, prosthetic1-3)
- **LDAP-пользователи** (customer1, customer2, employee1)
- **OAuth-пользователи** (через Yandex OAuth)

OTP credentials хранятся в Keycloak, независимо от источника пользователя.

## Безопасность

### Рекомендации:
1. **Резервные коды**: Убедитесь, что пользователи сохранили резервные коды
2. **Несколько устройств**: Рекомендуйте настроить OTP на нескольких устройствах
3. **Backup**: Регулярно делайте backup realm-export.json
4. **Мониторинг**: Отслеживайте неудачные попытки входа

### Что защищает MFA:
- ✅ Защита от украденных паролей
- ✅ Защита от фишинга (частично)
- ✅ Защита от brute-force атак
- ✅ Соответствие требованиям безопасности

### Что НЕ защищает MFA:
- ❌ Не защищает от malware на устройстве пользователя
- ❌ Не защищает от social engineering
- ❌ Не защищает от компрометации самого приложения-аутентификатора

## Troubleshooting

### Проблема: "Invalid authenticator code"
**Решение**: 
- Проверьте время на телефоне и сервере (должны быть синхронизированы)
- Убедитесь, что вводите актуальный код (обновляется каждые 30 сек)

### Проблема: QR-код не отображается
**Решение**:
- Проверьте логи Keycloak: `docker logs keycloak`
- Убедитесь, что realm импортирован корректно
- Проверьте, что `CONFIGURE_TOTP` включен в Required Actions

### Проблема: Пользователь не может войти после настройки OTP
**Решение**:
- Проверьте Authentication Flow в Admin Console
- Убедитесь, что `auth-otp-form` имеет `REQUIRED` requirement
- Проверьте логи на наличие ошибок

## Дополнительные ресурсы

- [Keycloak OTP Documentation](https://www.keycloak.org/docs/latest/server_admin/#otp-policies)
- [TOTP RFC 6238](https://tools.ietf.org/html/rfc6238)
- [Google Authenticator](https://support.google.com/accounts/answer/1066447)
