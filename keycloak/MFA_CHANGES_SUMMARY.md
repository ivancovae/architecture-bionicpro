# Сводка изменений для включения MFA

## Изменённые файлы

### 1. `keycloak/realm-export.json`

#### Добавлено в начало realm (после `"enabled": true`):
```json
"otpPolicyType": "totp",
"otpPolicyAlgorithm": "HmacSHA1",
"otpPolicyInitialCounter": 0,
"otpPolicyDigits": 6,
"otpPolicyLookAheadWindow": 1,
"otpPolicyPeriod": 30,
"otpPolicyCodeReusable": false,
"otpSupportedApplications": ["totpAppGoogleName", "totpAppFreeOTPName", "totpAppMicrosoftAuthenticatorName"]
```

#### Добавлено для каждого пользователя:
```json
"requiredActions": [
  "CONFIGURE_TOTP"
]
```

Затронутые пользователи:
- user1
- user2
- admin1
- prosthetic1
- prosthetic2
- prosthetic3

#### Добавлено в конец realm:
```json
"authenticationFlows": [
  {
    "alias": "browser",
    "description": "Browser based authentication with required OTP",
    "providerId": "basic-flow",
    "topLevel": true,
    "builtIn": false,
    "authenticationExecutions": [
      {
        "authenticator": "auth-cookie",
        "requirement": "ALTERNATIVE",
        "priority": 10,
        "userSetupAllowed": false,
        "autheticatorFlow": false
      },
      {
        "authenticator": "identity-provider-redirector",
        "requirement": "ALTERNATIVE",
        "priority": 25,
        "userSetupAllowed": false,
        "autheticatorFlow": false
      },
      {
        "flowAlias": "browser-forms",
        "requirement": "ALTERNATIVE",
        "priority": 30,
        "userSetupAllowed": false,
        "autheticatorFlow": true
      }
    ]
  },
  {
    "alias": "browser-forms",
    "description": "Username, password, OTP form",
    "providerId": "basic-flow",
    "topLevel": false,
    "builtIn": false,
    "authenticationExecutions": [
      {
        "authenticator": "auth-username-password-form",
        "requirement": "REQUIRED",
        "priority": 10,
        "userSetupAllowed": false,
        "autheticatorFlow": false
      },
      {
        "authenticator": "auth-otp-form",
        "requirement": "REQUIRED",
        "priority": 20,
        "userSetupAllowed": false,
        "autheticatorFlow": false
      }
    ]
  }
],
"browserFlow": "browser",
"requiredActions": [
  {
    "alias": "CONFIGURE_TOTP",
    "name": "Configure OTP",
    "providerId": "CONFIGURE_TOTP",
    "enabled": true,
    "defaultAction": true,
    "priority": 10,
    "config": {}
  },
  {
    "alias": "UPDATE_PASSWORD",
    "name": "Update Password",
    "providerId": "UPDATE_PASSWORD",
    "enabled": true,
    "defaultAction": false,
    "priority": 30,
    "config": {}
  },
  {
    "alias": "UPDATE_PROFILE",
    "name": "Update Profile",
    "providerId": "UPDATE_PROFILE",
    "enabled": true,
    "defaultAction": false,
    "priority": 40,
    "config": {}
  },
  {
    "alias": "VERIFY_EMAIL",
    "name": "Verify Email",
    "providerId": "VERIFY_EMAIL",
    "enabled": true,
    "defaultAction": false,
    "priority": 50,
    "config": {}
  }
]
```

## Созданные файлы

### 1. `keycloak/MFA_SETUP.md`
Полная документация по настройке и использованию MFA:
- Инструкции для пользователей
- Инструкции для администраторов
- Troubleshooting
- Рекомендации по безопасности

### 2. `keycloak/APPLY_MFA.sh`
Скрипт для применения настроек MFA:
```bash
bash keycloak/APPLY_MFA.sh
```

## Как применить изменения

### Вариант 1: Полный перезапуск (рекомендуется)
```bash
# Остановить и удалить Keycloak
docker compose stop keycloak
docker compose rm -f keycloak

# Удалить данные Keycloak (опционально, для чистого импорта)
docker volume rm architecture-bionicpro_keycloak_data

# Запустить Keycloak заново
docker compose up -d keycloak

# Дождаться запуска
docker logs -f keycloak
```

### Вариант 2: Использовать скрипт
```bash
bash keycloak/APPLY_MFA.sh
```

### Вариант 3: Простой перезапуск (если realm уже импортирован)
```bash
docker compose restart keycloak
```

## Проверка

### 1. Проверка через Admin Console
```bash
# Открыть Admin Console
open http://localhost:8080/admin

# Войти как admin
# Выбрать realm: reports-realm
# Перейти в Authentication → Flows
# Проверить flow "browser" - должен содержать обязательный OTP
```

### 2. Проверка через фронтенд
```bash
# Открыть фронтенд
open http://localhost:3000

# Войти как prosthetic1:prosthetic123
# Должен появиться экран настройки OTP с QR-кодом
```

## Откат изменений

Если нужно откатить MFA:

### 1. Восстановить старый realm-export.json
```bash
git checkout HEAD~1 keycloak/realm-export.json
```

### 2. Перезапустить Keycloak
```bash
docker compose stop keycloak
docker compose rm -f keycloak
docker volume rm architecture-bionicpro_keycloak_data
docker compose up -d keycloak
```

## Дополнительная информация

- **Документация**: `keycloak/MFA_SETUP.md`
- **Скрипт применения**: `keycloak/APPLY_MFA.sh`
- **Keycloak Docs**: https://www.keycloak.org/docs/latest/server_admin/#otp-policies
