# Keycloak - Конфигурация и пользователи

## Описание

Keycloak используется для аутентификации и авторизации пользователей в системе BionicPro.

## Realm: reports-realm

### Роли

- **users** - базовая роль для обычных пользователей
- **administrators** - роль администратора
- **prosthetic_users** - роль для пользователей с протезами (наследует роль users)
- **customers** - роль для клиентов из LDAP (наследует роль prosthetic_users)
- **employees** - роль для сотрудников из LDAP (наследует роль users)

### Пользователи

#### Обычные пользователи (роль: users)

| Username | Пароль       | Email               | Роль  | UUID                                 |
|----------|--------------|---------------------|-------|--------------------------------------|
| user1    | password123  | user1@example.com   | users | 068e58f3-8df4-4103-a672-d9b94deac511 |
| user2    | password123  | user2@example.com   | users | d0785132-f3b5-4a3c-a462-47e71cfe4236 |

#### Администраторы (роль: administrators)

| Username | Пароль   | Email               | Роль            | UUID                                 |
|----------|----------|---------------------|-----------------|--------------------------------------|
| admin1   | admin123 | admin1@example.com  | administrators  | a49617c1-8ec5-4ee3-b73f-7759c4ddf715 |

#### Пользователи с протезами (роль: prosthetic_users)

| Username     | Пароль         | Email                     | Роль             | UUID                                 |
|--------------|----------------|---------------------------|------------------|--------------------------------------|
| prosthetic1  | prosthetic123  | prosthetic1@example.com   | prosthetic_users | 54885c9b-6eea-48f7-89f9-353ad8273e95 |
| prosthetic2  | prosthetic123  | prosthetic2@example.com   | prosthetic_users | 7f7861be-8810-4c0c-bdd0-893b6a91aec5 |
| prosthetic3  | prosthetic123  | prosthetic3@example.com   | prosthetic_users | ae152063-1320-4115-ab79-604c132f6475 |

**Примечание:** У всех пользователей email подтверждён (emailVerified: true).

### Клиенты

#### reports-frontend
- **Тип:** Public Client
- **Протокол:** OpenID Connect
- **Redirect URIs:** http://localhost:3000/*, http://localhost:5173/*
- **Описание:** Фронтенд-приложение для работы с отчётами

#### reports-api
- **Тип:** Bearer-only Client
- **Протокол:** OpenID Connect
- **Secret:** oNwoLQdvJAvRcL89SydqCWCe5ry1jMgq
- **Описание:** Backend API для генерации отчётов

#### auth-proxy
- **Тип:** Confidential Client
- **Протокол:** OpenID Connect
- **Secret:** auth-proxy-secret-key-12345
- **Redirect URIs:** http://localhost:3000/callback, http://localhost:3000/*
- **Описание:** Прокси-сервер для аутентификации

### Интеграции

#### LDAP (china-ldap)
- **Провайдер:** OpenLDAP
- **Connection URL:** ldap://openldap-china:389
- **Users DN:** dc=china,dc=local
- **Bind DN:** cn=admin,dc=china,dc=local
- **Режим:** READ_ONLY
- **Синхронизация:** Отключена (fullSyncPeriod: -1)

#### OAuth2 (yandex-oauth)
- **Провайдер:** Yandex OAuth
- **Authorization URL:** https://oauth.yandex.ru/authorize
- **Token URL:** https://oauth.yandex.ru/token
- **User Info URL:** https://login.yandex.ru/info?format=json
- **Client ID:** 9b6da4df39184a81bfd49df26bce11b9
- **Scopes:** login:info, login:email

## Доступ к Keycloak Admin Console

- **URL:** http://localhost:8080
- **Admin Username:** admin
- **Admin Password:** admin

## Импорт realm

Realm автоматически импортируется при запуске контейнера из файла `realm-export.json`.

Для ручного импорта:
```bash
docker exec -it keycloak /opt/keycloak/bin/kc.sh import --file /opt/keycloak/data/import/realm-export.json
```

## Экспорт realm

Для экспорта текущей конфигурации realm:
```bash
docker exec -it keycloak /opt/keycloak/bin/kc.sh export --file /tmp/realm-export.json --realm reports-realm
docker cp keycloak:/tmp/realm-export.json ./keycloak/realm-export.json
```
